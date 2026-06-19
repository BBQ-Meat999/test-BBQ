"""
SupervisorNode — orchestrates routing between specialist agents.
Decides which node should act next based on the current state.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


NEXT_NODES = Literal["search", "analysis", "writer", "END"]


class SupervisorNode(AgentNode):
    """
    Supervisor / orchestrator.
    Reads the conversation state and emits a `next` field that drives
    the conditional edges in the LangGraph workflow.
    """

    node_name = "supervisor"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def route(self, destination: NEXT_NODES) -> str:
        """Instruct the graph to route to the specified next agent node."""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Call the LLM with routing tools and surface the chosen next node
        back into the graph state.
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: parse tool_calls from response to extract `next`
        return {**state, "messages": state["messages"] + [response], "next": "END"}
