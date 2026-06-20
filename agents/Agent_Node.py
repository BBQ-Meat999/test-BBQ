"""
Base AgentNode class.

全エージェントノードの基底クラス。
  - 報奨金に応じて選択された Claude モデルを動的に切り替える
  - コンテキストを圧縮したメッセージ列を組み立てる (コード成果物は messages に載せない)
  - `with_structured_output` による型付き生成のヘルパーを提供する

旧実装では @tool デコレータ付きメソッドを LLM にバインドしようとしていたが、
LangChain の @tool はインスタンスメソッド (self 付き) を扱えず、本体も空だったため
実際には機能していなかった。本システムのノードはコードを「生成」するのが仕事であり、
正しいプリミティブは構造化出力 (with_structured_output) であるため、そちらへ統一した。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.utils.context_manager import ContextManager
from config.settings import settings
from config.systemMessage import SystemMessage as AgentSystemMessage

TModel = TypeVar("TModel", bound=BaseModel)

# 1 ファイルあたりにレビュー/納品ノードへ渡す最大文字数 (コンテキスト保護)
_MAX_FILE_CHARS_FOR_REVIEW = 6_000


class AgentNode(ABC):
    """
    マルチエージェントグラフの全ノードの基底クラス。

    責務:
      - state["model_assignments"] に基づき Claude モデルを動的に選択する
      - コンテキストを圧縮したメッセージ列を組み立てる
      - 構造化出力 (Pydantic スキーマ) で型付きの結果を取得する
    """

    node_name: str = "base_agent"

    def __init__(
        self,
        llm: BaseChatModel,
        llm_factory: Callable[[str], BaseChatModel] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        llm         : デフォルト LLM (model_assignments がないときのフォールバック)
        llm_factory : model_id を受け取り新しい LLM を返すファクトリ。
                      ProjectManager が割り当てたモデルを各ノードが動的に使うために必要。
        """
        self.llm           = llm
        self._llm_factory  = llm_factory
        self.system_prompt = AgentSystemMessage.get(self.node_name)
        self._ctx          = ContextManager(
            max_messages=settings.workflow.max_context_messages
        )
        # cache: model_id (None = default) → base LLM
        self._llm_cache: dict[str | None, BaseChatModel] = {None: llm}

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        現在のグラフステートを処理して更新後のステートを返す。

        ルール:
          - コード/成果物は専用フィールド (*_files, *_results) に書き込む
          - state["messages"] にフルコードを追加しない (短い要約のみ)
          - 生成は _generate() / _generate_text() を使う
        """
        ...

    # ------------------------------------------------------------------
    # Dynamic model selection
    # ------------------------------------------------------------------

    def _get_llm(self, model_id: str | None) -> BaseChatModel:
        """
        model_id に対応する LLM をキャッシュから返す。
        未キャッシュなら llm_factory で生成する。factory 未設定ならデフォルトを返す。
        """
        if model_id is None:
            return self._llm_cache[None]
        if model_id not in self._llm_cache:
            if self._llm_factory is None:
                return self._llm_cache[None]
            self._llm_cache[model_id] = self._llm_factory(model_id)
        return self._llm_cache[model_id]

    def _model_for(self, state: dict[str, Any]) -> str | None:
        """このノードに割り当てられた model_id を state から取得する。"""
        return state.get("model_assignments", {}).get(self.node_name)

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        state: dict[str, Any],
        extra: Sequence[BaseMessage] | None = None,
    ) -> list[BaseMessage]:
        """
        system + (トリム済み履歴) + コンテキスト要約 のメッセージ列を組み立てる。
        extra に追加メッセージ (full code やフィードバック) を渡せる。
        """
        enriched = {
            **state,
            "_current_node":     self.node_name,
            "_max_review_loops": settings.workflow.max_review_loops,
        }
        system_msg  = SystemMessage(content=self.system_prompt)
        context_msg = self._ctx.build_context_message(enriched)
        trimmed     = self._ctx.trim(state.get("messages", []))
        return [system_msg, *trimmed, context_msg, *(extra or [])]

    def _full_artifacts_message(self, state: dict[str, Any]) -> HumanMessage:
        """
        レビュー/納品ノード向けに、成果物のフルコードを含むメッセージを作る。
        通常ノードは要約のみだが、CodeReview と Writer は実コードを見る必要がある。
        """
        parts: list[str] = ["【全成果物 (フルコード)】"]
        labels = {
            "tool_spec_files": "ToolSpecialist",
            "backend_files":   "Backend",
            "frontend_files":  "Frontend",
            "database_files":  "Database",
        }
        for key, label in labels.items():
            files: dict[str, str] = state.get(key) or {}
            for path, code in files.items():
                body = code[:_MAX_FILE_CHARS_FOR_REVIEW]
                if len(code) > _MAX_FILE_CHARS_FOR_REVIEW:
                    body += "\n... (truncated)"
                parts.append(f"\n### [{label}] {path}\n```\n{body}\n```")
        if len(parts) == 1:
            parts.append("(成果物なし)")
        return HumanMessage(content="\n".join(parts))

    # ------------------------------------------------------------------
    # LLM invocation
    # ------------------------------------------------------------------

    def _generate(
        self,
        state: dict[str, Any],
        schema: type[TModel],
        extra: Sequence[BaseMessage] | None = None,
    ) -> TModel:
        """
        割り当てモデルで構造化出力を生成し、Pydantic オブジェクトを返す。
        """
        llm = self._get_llm(self._model_for(state))
        structured = llm.with_structured_output(schema)
        messages = self._build_messages(state, extra=extra)
        result = structured.invoke(messages)
        return result  # type: ignore[return-value]

    def _generate_text(
        self,
        state: dict[str, Any],
        extra: Sequence[BaseMessage] | None = None,
    ) -> str:
        """割り当てモデルで自由形式テキストを生成する。"""
        llm = self._get_llm(self._model_for(state))
        messages = self._build_messages(state, extra=extra)
        response = llm.invoke(messages)
        return response.content if isinstance(response.content, str) else str(response.content)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} node_name={self.node_name!r}>"
