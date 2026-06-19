"""
ToolRegistry — central catalogue of all @tool decorated callables.

Usage
-----
Register a tool manually:
    registry = ToolRegistry()
    registry.register(my_tool_fn)

Or use the module-level helper as a decorator:
    @register_tool
    @tool
    def my_tool(x: str) -> str: ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from langchain_core.tools import BaseTool


class ToolRegistry:
    """Holds a named mapping of LangChain BaseTool instances."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={self.names()!r}>"


# Module-level singleton
_registry = ToolRegistry()


def register_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that registers a @tool-decorated function into the global registry."""
    if isinstance(fn, BaseTool):
        _registry.register(fn)
    return fn


def get_registry() -> ToolRegistry:
    return _registry
