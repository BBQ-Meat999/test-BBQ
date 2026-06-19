"""
Base AgentNode class.
All agent nodes inherit from this. @tool registration, LLM binding,
and context-aware message building happen here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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
    """

    node_name: str = "base_agent"

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm            = llm
        self.system_prompt  = AgentSystemMessage.get(self.node_name)
        self.tools: list[BaseTool] = self._collect_tools()
        self._bound_llm     = self.llm.bind_tools(self.tools) if self.tools else self.llm
        self._ctx           = ContextManager(
            max_messages=settings.workflow.max_context_messages
        )

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
        Must be implemented by each concrete node.

        Rules:
          - Write code/artifacts to dedicated state fields (*_files, *_result)
          - Do NOT append full code to state["messages"]
          - Use _invoke() to call the LLM with trimmed context
        """
        ...

    # ------------------------------------------------------------------
    # LLM invocation helpers
    # ------------------------------------------------------------------

    def _invoke(self, state: dict[str, Any]) -> Any:
        """
        Build a trimmed, context-aware message list and invoke the LLM.
        - Prepends system prompt
        - Adds a concise context message (summaries only, no full code)
        - Trims message history to prevent context explosion
        """
        # Annotate state with current node name for instruction lookup
        enriched = {**state, "_current_node": self.node_name,
                    "_max_review_loops": settings.workflow.max_review_loops}

        system_msg  = SystemMessage(content=self.system_prompt)
        context_msg = self._ctx.build_context_message(enriched)

        # Trim existing conversation history
        history: list[BaseMessage] = state.get("messages", [])
        trimmed = self._ctx.trim(history)

        messages = [system_msg] + trimmed + [context_msg]
        return self._bound_llm.invoke(messages)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_messages(self, state: dict[str, Any]) -> list[BaseMessage]:
        """
        Legacy helper kept for backward compatibility.
        Prefer _invoke() for new node implementations.
        """
        system_msg  = SystemMessage(content=self.system_prompt)
        context_msg = self._ctx.build_context_message(
            {**state, "_current_node": self.node_name}
        )
        history  = self._ctx.trim(state.get("messages", []))
        return [system_msg] + history + [context_msg]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} node_name={self.node_name!r} tools={len(self.tools)}>"
