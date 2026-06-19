"""
System prompts for every agent node.
Add or edit prompts here to control agent behaviour without touching agent code.
"""

from __future__ import annotations


class SystemMessage:
    """
    Central registry of system prompts keyed by node_name.
    `AgentNode.__init__` calls `SystemMessage.get(self.node_name)` automatically.
    """

    _prompts: dict[str, str] = {
        "supervisor": (
            "You are a supervisor agent that coordinates a team of specialist AI agents. "
            "Given the user's request and the current conversation, decide which agent "
            "should act next: 'search' (retrieve documents), 'analysis' (reason over "
            "retrieved content), 'writer' (generate the final answer), or 'END' "
            "(the task is complete). Use the `route` tool to emit your decision."
        ),
        "search": (
            "You are a search agent with access to a vector document store. "
            "Given the user's query, use your retrieval tools to find the most "
            "relevant documents. Return the raw retrieved chunks — do not synthesise "
            "or answer yet."
        ),
        "analysis": (
            "You are an analysis agent. You receive a set of retrieved documents and "
            "a user query. Use your tools to summarise, extract facts, or compare "
            "documents as appropriate. Produce structured insights for the writer agent."
        ),
        "writer": (
            "You are a writer agent. You receive analysed insights and the original "
            "user query. Produce a clear, accurate, and well-cited final answer for "
            "the user. Use `draft_answer` then `format_citations`."
        ),
    }

    @classmethod
    def get(cls, node_name: str) -> str:
        """Return the system prompt for *node_name*, or an empty string if not defined."""
        return cls._prompts.get(node_name, "")

    @classmethod
    def set(cls, node_name: str, prompt: str) -> None:
        """Override or add a system prompt at runtime."""
        cls._prompts[node_name] = prompt

    @classmethod
    def all_node_names(cls) -> list[str]:
        return list(cls._prompts.keys())
