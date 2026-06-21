"""
Global configuration for the UpWork multi-agent system.

Non-sensitive values  → environment variables (see .env.example)
Sensitive credentials → AWS Secrets Manager via app_secrets.SecretsManager
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property


@dataclass(frozen=True)
class LLMConfig:
    model: str        = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-sonnet-4-6"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int   = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))


@dataclass(frozen=True)
class AWSConfig:
    region: str           = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-northeast-1"))
    profile: str | None   = field(default_factory=lambda: os.getenv("AWS_PROFILE"))
    secret_cache_ttl: int = field(default_factory=lambda: int(os.getenv("SECRET_CACHE_TTL", "300")))


@dataclass(frozen=True)
class WorkflowConfig:
    """
    ワークフロー制御パラメータ。
    review_manager_node.py などエージェント側はここからインポートすること。
    (循環インポートを防ぐため config 層のみに定義)
    """
    # レビューループ上限 (実装 ↔ レビュー の最大往復回数)
    max_review_loops: int = field(
        default_factory=lambda: int(os.getenv("MAX_REVIEW_LOOPS", "2"))
    )
    # コンテキスト圧縮: messages の保持上限数
    max_context_messages: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))
    )
    # Human-in-the-loop: 作業計画の承認を求めるか
    require_plan_approval: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_PLAN_APPROVAL", "true").lower() == "true"
    )


class Settings:
    """
    Application-wide settings.

    Secrets (api_key 等) は初回アクセス時に AWS Secrets Manager から遅延取得。
    """

    def __init__(self) -> None:
        self.llm      = LLMConfig()
        self.aws      = AWSConfig()
        self.workflow = WorkflowConfig()
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")


    @cached_property
    def anthropic_api_key(self) -> str:
        """Retrieve the Anthropic API key from AWS Secrets Manager."""
        from app_secrets.secrets_manager import SecretsManager
        return SecretsManager.get_instance().get_anthropic_api_key()

    @cached_property
    def discord_delivery_channel_id(self) -> int | None:
        """Discord 成果物投稿チャンネル ID を AWS Secrets Manager から取得する。"""
        try:
            from app_secrets.secrets_manager import SecretsManager
            return SecretsManager.get_instance().get_discord_delivery_channel_id()
        except Exception:
            return None

    @cached_property
    def discord_bot_token(self) -> str | None:
        """
        Discord ボットトークンを AWS Secrets Manager から取得する。
        未設定またはエラーの場合は None を返し、Discord 機能を無効化する。
        """
        try:
            from app_secrets.secrets_manager import SecretsManager
            return SecretsManager.get_instance().get_discord_token()
        except Exception:
            return None


# Singleton used across the application
settings = Settings()
