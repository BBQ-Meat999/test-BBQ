"""
VectorStore — interface to the underlying vector database.
Concrete implementations (FAISS, Chroma, Pinecone, …) plug in via dependency injection.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStoreBackend(Protocol):
    def add_documents(self, documents: list[dict[str, Any]]) -> None: ...
    def similarity_search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]: ...
    def delete(self, doc_ids: list[str]) -> None: ...
    def persist(self) -> None: ...


class VectorStore:
    """
    Wraps a VectorStoreBackend and couples it to the EmbeddingModel
    so callers deal only with raw text queries.
    """

    def __init__(self, backend: VectorStoreBackend) -> None:
        self._backend = backend

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        ...

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        ...

    def delete(self, doc_ids: list[str]) -> None:
        ...

    def persist(self) -> None:
        ...
