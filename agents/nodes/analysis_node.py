"""
AnalysisNode — reasons over retrieved documents and produces structured insights.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class AnalysisNode(AgentNode):
    """
    Analyses retrieved_docs from the graph state and populates `analysis_result`.
    """

    node_name = "analysis"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def summarize(self, documents: list[dict], max_tokens: int = 512) -> str:
        """Summarize the provided documents into a concise paragraph."""
        ...

    @tool
    def extract_facts(self, documents: list[dict]) -> list[str]:
        """Extract key factual claims from the provided documents."""
        ...

    @tool
    def compare(self, doc_a: dict, doc_b: dict) -> str:
        """Compare two documents and highlight similarities and differences."""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: execute tool_calls, collect analysis_result
        analysis_result: str = ""
        return {**state, "messages": state["messages"] + [response], "analysis_result": analysis_result}
