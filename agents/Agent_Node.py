"""
Base AgentNode class.
All agent nodes inherit from this. @tool registration and LLM binding happen here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from config.systemMessage import SystemMessage


class AgentNode(ABC):
    """
    Base class for all agent nodes in the multi-agent graph.

    Each concrete node:
      - registers its tools via @tool decorated methods
      - holds a reference to its system prompt from SystemMessage
      - exposes a `run(state)` method invoked by the LangGraph node
    """

    node_name: str = "base_agent"

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm
        self.system_prompt: str = SystemMessage.get(self.node_name)
        self.tools: list[BaseTool] = self._collect_tools()
        self._bound_llm = self.llm.bind_tools(self.tools) if self.tools else self.llm

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
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_messages(self, state: dict[str, Any]) -> list[BaseMessage]:
        """Prepend the system prompt to the current message history."""
        from langchain_core.messages import HumanMessage, SystemMessage as LCSystemMessage

        history: list[BaseMessage] = state.get("messages", [])
        return [LCSystemMessage(content=self.system_prompt)] + list(history)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} node_name={self.node_name!r}>"
