"""
MultiAgentWorkflow — builds and compiles the LangGraph StateGraph.

Graph topology
--------------
                ┌──────────┐
  START ───────►│Supervisor│
                └────┬─────┘
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       ┌──────┐ ┌────────┐ ┌────────┐
       │Search│ │Analysis│ │ Writer │
       └──┬───┘ └───┬────┘ └───┬────┘
          └─────────┴──────────┘
                    │
                    ▼
                   END
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    messages: list[BaseMessage]
    next: str
    retrieved_docs: list[dict[str, Any]]
    analysis_result: str
    final_answer: str


class MultiAgentWorkflow:
    """
    Assembles the LangGraph StateGraph from injected agent nodes.
    Call `.compile()` to obtain a runnable graph.
    """

    def __init__(
        self,
        supervisor_node,
        search_node,
        analysis_node,
        writer_node,
    ) -> None:
        self.supervisor = supervisor_node
        self.search = search_node
        self.analysis = analysis_node
        self.writer = writer_node

    def _route(self, state: AgentState) -> str:
        """Conditional edge: read `state['next']` set by SupervisorNode."""
        return state.get("next", END)

    def compile(self):
        """Build and compile the StateGraph. Returns a LangGraph Runnable."""
        graph = StateGraph(AgentState)

        # Register nodes
        graph.add_node("supervisor", self.supervisor.run)
        graph.add_node("search",     self.search.run)
        graph.add_node("analysis",   self.analysis.run)
        graph.add_node("writer",     self.writer.run)

        # Entry edge
        graph.add_edge(START, "supervisor")

        # Supervisor routes dynamically
        graph.add_conditional_edges(
            "supervisor",
            self._route,
            {
                "search":   "search",
                "analysis": "analysis",
                "writer":   "writer",
                END:        END,
            },
        )

        # Specialist nodes always return to supervisor
        for node in ("search", "analysis", "writer"):
            graph.add_edge(node, "supervisor")

        return graph.compile()
