"""
Base AgentNode class.
All agent nodes inherit from this. @tool registration, LLM binding,
and context-aware message building happen here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool

from agents.utils.context_manager import ContextManager
from config.settings import settings
from config.systemMessage import SystemMessage as AgentSystemMessage


class AgentNode(ABC):
    """
    Base class for all agent nodes in the multi-agent graph.

    Responsibilities:
      - Auto-collect @tool decorated methods and bind them to the LLM
      - Build context-aware message lists (no code artifacts in messages)
      - Trim message history to prevent context explosion
      - Dynamically switch Claude models based on state["model_assignments"]
        to maximize profit given the UpWork reward amount
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
        llm         : デフォルト LLM (model_assignments がないときに使用)
        llm_factory : model_id を受け取り新しい LLM を返すファクトリ関数。
                      ProjectManager が select_models で割り当てたモデルを
                      各ノードが動的に使うために必要。
        """
        self.llm            = llm
        self._llm_factory   = llm_factory
        self.system_prompt  = AgentSystemMessage.get(self.node_name)
        self.tools: list[BaseTool] = self._collect_tools()
        self._ctx           = ContextManager(
            max_messages=settings.workflow.max_context_messages
        )
        # cache: model_id (None = default) → bound LLM
        self._bound_llm_cache: dict[str | None, BaseChatModel] = {
            None: llm.bind_tools(self.tools) if self.tools else llm
        }

    # ------------------------------------------------------------------
    # Tool collection
    # ------------------------------------------------------------------

    def _collect_tools(self) -> list[BaseTool]:
        """Gather every method decorated with @tool on this instance."""
        tools: list[BaseTool] = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name, None)
            if callable(attr) and hasattr(attr, "is_tool"):
                tools.append(attr)
        return tools

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Process the current graph state and return updated state.

        Rules:
          - Write code/artifacts to dedicated state fields (*_files, *_result)
          - Do NOT append full code to state["messages"]
          - Use _invoke() to call the LLM with trimmed context
        """
        ...

    # ------------------------------------------------------------------
    # Dynamic model selection
    # ------------------------------------------------------------------

    def _get_bound_llm(self, model_id: str | None) -> BaseChatModel:
        """
        model_id に対応する (tool-bound) LLM をキャッシュから返す。
        未キャッシュの場合は llm_factory で生成してキャッシュする。
        llm_factory が未設定の場合はデフォルト LLM を返す。
        """
        if model_id not in self._bound_llm_cache:
            if self._llm_factory is None:
                return self._bound_llm_cache[None]
            base_llm = self._llm_factory(model_id)
            self._bound_llm_cache[model_id] = (
                base_llm.bind_tools(self.tools) if self.tools else base_llm
            )
        return self._bound_llm_cache[model_id]

    # ------------------------------------------------------------------
    # LLM invocation helpers
    # ------------------------------------------------------------------

    def _invoke(self, state: dict[str, Any]) -> Any:
        """
        Build a trimmed, context-aware message list and invoke the LLM.

        モデル選択:
          state["model_assignments"][self.node_name] があればそのモデルを使用。
          なければデフォルト LLM を使用。
        """
        # 割り当てモデルの取得 (ProjectManager が select_models で設定)
        model_id = state.get("model_assignments", {}).get(self.node_name)

        enriched = {
            **state,
            "_current_node":     self.node_name,
            "_max_review_loops": settings.workflow.max_review_loops,
        }

        system_msg  = SystemMessage(content=self.system_prompt)
        context_msg = self._ctx.build_context_message(enriched)

        history: list[BaseMessage] = state.get("messages", [])
        trimmed = self._ctx.trim(history)

        messages = [system_msg] + trimmed + [context_msg]
        return self._get_bound_llm(model_id).invoke(messages)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_messages(self, state: dict[str, Any]) -> list[BaseMessage]:
        """Legacy helper kept for backward compatibility. Prefer _invoke()."""
        system_msg  = SystemMessage(content=self.system_prompt)
        context_msg = self._ctx.build_context_message(
            {**state, "_current_node": self.node_name}
        )
        history = self._ctx.trim(state.get("messages", []))
        return [system_msg] + history + [context_msg]

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"node_name={self.node_name!r} tools={len(self.tools)}>"
        )
