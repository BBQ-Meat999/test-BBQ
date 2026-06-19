"""
SearchNode — retrieves relevant documents via the RAG pipeline.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode
from rag.retriever import Retriever


class SearchNode(AgentNode):
    """
    Performs semantic search against the vector store and injects
    retrieved chunks into the graph state as `retrieved_docs`.
    """

    node_name = "search"

    def __init__(self, llm, retriever: Retriever) -> None:
        super().__init__(llm)
        self.retriever = retriever

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the vector store for documents relevant to *query*."""
        ...

    @tool
    def keyword_search(self, keywords: list[str]) -> list[dict]:
        """Perform keyword-based search as a fallback retrieval strategy."""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: execute tool_calls, collect retrieved_docs
        retrieved_docs: list[dict] = []
        return {**state, "messages": state["messages"] + [response], "retrieved_docs": retrieved_docs}
