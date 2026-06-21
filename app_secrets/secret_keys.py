"""
Secret name and field constants for AWS Secrets Manager.

Naming convention
-----------------
  SecretName  : the full secret path stored in AWS Secrets Manager
  SecretField : the JSON field key inside a given secret

Never hard-code values here — only logical identifiers.
Actual secret values live exclusively in AWS.
"""

from __future__ import annotations


class SecretName:
    """AWS Secrets Manager secret paths."""

    # Anthropic / Claude API credentials
    ANTHROPIC = "multiagent-rag/anthropic"

    # Vector store / database credentials (future use)
    VECTOR_DB = "multiagent-rag/vector-db"

    # External service keys (future use)
    EXTERNAL_SERVICES = "multiagent-rag/external-services"


class SecretField:
    """JSON field names within each secret payload."""

    # Fields inside SecretName.ANTHROPIC
    ANTHROPIC_API_KEY = "api_key"

    # Fields inside SecretName.VECTOR_DB
    VECTOR_DB_HOST     = "host"
    VECTOR_DB_PORT     = "port"
    VECTOR_DB_USER     = "username"
    VECTOR_DB_PASSWORD = "password"
    VECTOR_DB_NAME     = "database"

    # Fields inside SecretName.EXTERNAL_SERVICES
    DISCORD_BOT_TOKEN = "discord_bot_token"
