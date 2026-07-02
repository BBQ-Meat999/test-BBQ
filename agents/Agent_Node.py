"""
Base AgentNode class.

全エージェントノードの基底クラス。
  - 報奨金に応じて選択された Claude モデルを動的に切り替える
  - コンテキストを圧縮したメッセージ列を組み立てる (コード成果物は messages に載せない)
  - Anthropic function calling (tool use) による生成ヘルパーを提供する

【生成方式 — function calling へ全面移行】
  以前は `llm.with_structured_output(Schema)` で構造化出力を得ていたが、
  本システムは LangChain の `bind_tools` による明示的なファンクションコーリングへ統一した。
    - 各ノードは自分の結果スキーマ (WorkPlan / ReviewResult 等) を「submit 関数」として
      バインドし、LLM がそれを呼び出すことで型付き結果を受け取る。
    - ワーカー・Writer・CodeReview はさらに write_file / read_file / list_files などの
      実行可能ツールを持ち、LLM が能動的にツールを呼んで成果物を組み立てる
      (AgentExecutor 型の tool-use ループ)。
  ループの実体は `_run_agent()` に集約されている。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from agents.utils.context_manager import ContextManager
from config.settings import settings
from config.systemMessage import SystemMessage as AgentSystemMessage

TModel = TypeVar("TModel", bound=BaseModel)

# 1 ファイルあたりにレビュー/納品ノードへ渡す最大文字数 (コンテキスト保護)
_MAX_FILE_CHARS_FOR_REVIEW = 6_000

# tool-use ループの既定の最大反復回数 (無限ループ防止)
_DEFAULT_MAX_ITERATIONS = 12


class AgentNode(ABC):
    """
    マルチエージェントグラフの全ノードの基底クラス。

    責務:
      - state["model_assignments"] に基づき Claude モデルを動的に選択する
      - コンテキストを圧縮したメッセージ列を組み立てる
      - function calling (tool use) で型付きの結果・成果物を取得する
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
          - 生成は _run_agent() を使う (function calling)
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
    # Function-calling agent loop
    # ------------------------------------------------------------------

    def _run_agent(
        self,
        state: dict[str, Any],
        result_schema: type[TModel],
        *,
        extra: Sequence[BaseMessage] | None = None,
        tools: Sequence[BaseTool] | None = None,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> TModel:
        """
        function calling による tool-use ループを実行し、型付き結果を返す。

        動作:
          - result_schema を「submit 関数」としてバインドする (名前 = クラス名)。
          - tools (write_file 等の実行可能ツール) があれば併せてバインドし、
            tool_choice="any" で毎ターン必ずいずれかのツールを呼ばせる。
          - LLM が submit 関数を呼んだら、その引数を result_schema へ検証して返す。
          - tools が無い決定系ノード (PM/ReviewManager/Writer) は submit を強制し
            実質 1 回のファンクションコールで結果を得る。

        Parameters
        ----------
        result_schema : LLM に呼ばせる結果スキーマ (Pydantic)。返り値の型。
        tools         : 追加の実行可能ツール (省略時は submit のみ)。
        max_iterations: tool-use ループの最大反復回数。
        """
        llm = self._get_llm(self._model_for(state))
        exec_tools: list[BaseTool] = list(tools or [])
        submit_name = result_schema.__name__

        all_tools: list[Any] = [*exec_tools, result_schema]
        if exec_tools:
            # 実行可能ツールがある: 毎ターンいずれかのツールを必ず呼ばせる
            bound = llm.bind_tools(all_tools, tool_choice="any")
        else:
            # 決定系ノード: submit 関数を直接強制する (1 コールで完了)
            bound = llm.bind_tools(all_tools, tool_choice=submit_name)

        messages: list[BaseMessage] = list(self._build_messages(state, extra=extra))
        tool_map = {t.name: t for t in exec_tools}

        for _ in range(max_iterations):
            ai = bound.invoke(messages)
            messages.append(ai)
            tool_calls = getattr(ai, "tool_calls", None) or []

            if not tool_calls:
                # ツールを呼ばなかった: 明示的に促してリトライ
                messages.append(HumanMessage(content=(
                    f"必ずツールを呼び出してください。完了時は `{submit_name}` を呼びます。"
                )))
                continue

            finished_value: TModel | None = None
            for call in tool_calls:
                name = call.get("name", "")
                args = call.get("args", {}) or {}
                call_id = call.get("id", "") or name

                if name == submit_name:
                    try:
                        finished_value = result_schema.model_validate(args)
                        messages.append(ToolMessage(
                            content="OK: 受理しました。",
                            tool_call_id=call_id,
                        ))
                    except ValidationError as exc:
                        # 引数が不正: エラーを返して再生成させる
                        messages.append(ToolMessage(
                            content=f"ERROR: 引数が不正です。修正して再度 {submit_name} を呼んでください。\n{exc}",
                            tool_call_id=call_id,
                        ))
                    continue

                tool = tool_map.get(name)
                if tool is None:
                    messages.append(ToolMessage(
                        content=f"ERROR: 未知のツール '{name}'。",
                        tool_call_id=call_id,
                    ))
                    continue
                try:
                    output = tool.invoke(args)
                except Exception as exc:  # noqa: BLE001 — ツール実行失敗も LLM に返して継続
                    output = f"ERROR: ツール実行失敗: {exc}"
                messages.append(ToolMessage(content=str(output), tool_call_id=call_id))

            if finished_value is not None:
                return finished_value

        raise RuntimeError(
            f"{self.node_name}: {max_iterations} 反復以内に `{submit_name}` が"
            "呼ばれませんでした (function calling ループ上限到達)。"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} node_name={self.node_name!r}>"
