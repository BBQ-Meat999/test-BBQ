"""
Global configuration for the multi-agent RAG system.

Non-sensitive values  → environment variables (see .env.example)
Sensitive credentials → AWS Secrets Manager via secrets.SecretsManager
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property


@dataclass(frozen=True)
class LLMConfig:
    model: str       = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-sonnet-4-6"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int  = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))


@dataclass(frozen=True)
class RAGConfig:
    embedding_model: str  = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    vector_store_path: str = field(default_factory=lambda: os.getenv("VECTOR_STORE_PATH", "./data/vector_store"))
    top_k: int        = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "5")))
    chunk_size: int   = field(default_factory=lambda: int(os.getenv("RAG_CHUNK_SIZE", "512")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("RAG_CHUNK_OVERLAP", "64")))


@dataclass(frozen=True)
class AWSConfig:
    region: str          = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-northeast-1"))
    profile: str | None  = field(default_factory=lambda: os.getenv("AWS_PROFILE"))
    secret_cache_ttl: int = field(default_factory=lambda: int(os.getenv("SECRET_CACHE_TTL", "300")))


class Settings:
    """
    Application-wide settings.

    Secrets (api_key etc.) are fetched lazily from AWS Secrets Manager
    on first access and cached for `aws.secret_cache_ttl` seconds.
    """

    def __init__(self) -> None:
        self.llm = LLMConfig()
        self.rag = RAGConfig()
        self.aws = AWSConfig()
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @cached_property
    def anthropic_api_key(self) -> str:
        """
        Retrieve the Anthropic API key from AWS Secrets Manager.
        Raises SecretsManagerError if unavailable.
        """
        from secrets.secrets_manager import SecretsManager
        return SecretsManager.get_instance().get_anthropic_api_key()


# Singleton used across the application
settings = Settings()
