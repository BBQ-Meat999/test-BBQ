"""
Retriever — orchestrates document retrieval from the VectorStore.
Supports semantic search, keyword search, and hybrid strategies.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from rag.vector_store import VectorStore


class RetrievalStrategy(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class Retriever:
    """
    High-level retriever used by SearchNode.
    Strategy can be switched per-call without rebuilding the object.
    """

    def __init__(self, vector_store: VectorStore, default_top_k: int = 5) -> None:
        self.vector_store = vector_store
        self.default_top_k = default_top_k

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC,
    ) -> list[dict[str, Any]]:
        ...

    def _semantic_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        ...

    def _keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        ...

    def _hybrid_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        ...
