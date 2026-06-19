"""
WriterNode — generates the final user-facing response using analysis results.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class WriterNode(AgentNode):
    """
    Synthesizes analysis_result and retrieved_docs into a polished final answer
    stored in `final_answer`.
    """

    node_name = "writer"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def draft_answer(self, context: str, user_query: str, style: str = "default") -> str:
        """Draft a complete answer for the user given context and their original query."""
        ...

    @tool
    def format_citations(self, answer: str, sources: list[dict]) -> str:
        """Append source citations to the drafted answer."""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: execute tool_calls, build final_answer
        final_answer: str = ""
        return {**state, "messages": state["messages"] + [response], "final_answer": final_answer}
