"""
SecretsManager — AWS Secrets Manager client with in-memory cache.

Usage
-----
    sm = SecretsManager.get_instance()

    # Fetch a single string secret
    raw = sm.get_secret(SecretName.ANTHROPIC)

    # Fetch one field from a JSON secret
    api_key = sm.get_field(SecretName.ANTHROPIC, SecretField.ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app_secrets.secret_keys import SecretField, SecretName

logger = logging.getLogger(__name__)


class _CachedEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl_seconds: int) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl_seconds

    @property
    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class SecretsManagerError(Exception):
    """Raised when a secret cannot be fetched or parsed."""


class SecretsManager:
    """
    Thread-safe, singleton wrapper around boto3 Secrets Manager.

    Parameters
    ----------
    region_name : AWS region where secrets are stored.
    cache_ttl   : Seconds before a cached value is re-fetched. Default 300 s.
    profile_name: Optional AWS CLI profile (useful in local dev).
    """

    _instance: SecretsManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        region_name: str,
        cache_ttl: int = 300,
        profile_name: str | None = None,
    ) -> None:
        session = boto3.session.Session(profile_name=profile_name)
        self._client = session.client(
            service_name="secretsmanager",
            region_name=region_name,
        )
        self._cache: dict[str, _CachedEntry] = {}
        self._cache_ttl = cache_ttl
        self._mu = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton factory
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> SecretsManager:
        """
        Return (and lazily create) the process-wide singleton.
        Configuration is read from environment variables:
            AWS_REGION       — required
            AWS_PROFILE      — optional, for local dev
            SECRET_CACHE_TTL — optional, seconds (default 300)
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    import os
                    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
                    if not region:
                        raise SecretsManagerError(
                            "AWS_REGION environment variable is not set."
                        )
                    cls._instance = cls(
                        region_name=region,
                        cache_ttl=int(os.environ.get("SECRET_CACHE_TTL", "300")),
                        profile_name=os.environ.get("AWS_PROFILE"),
                    )
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_secret(self, secret_name: str) -> str:
        """
        Return the raw secret string for *secret_name*.
        Raises SecretsManagerError on any failure.
        """
        with self._mu:
            entry = self._cache.get(secret_name)
            if entry and not entry.is_expired:
                return entry.value

        value = self._fetch_raw(secret_name)

        with self._mu:
            self._cache[secret_name] = _CachedEntry(value, self._cache_ttl)

        return value

    def get_secret_json(self, secret_name: str) -> dict[str, Any]:
        """
        Parse the secret as JSON and return a dict.
        Raises SecretsManagerError if the value is not valid JSON.
        """
        raw = self.get_secret(secret_name)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SecretsManagerError(
                f"Secret '{secret_name}' is not valid JSON: {exc}"
            ) from exc

    def get_field(self, secret_name: str, field: str) -> str:
        """
        Return a single *field* from a JSON secret.
        Raises SecretsManagerError if the field is missing.
        """
        data = self.get_secret_json(secret_name)
        if field not in data:
            raise SecretsManagerError(
                f"Field '{field}' not found in secret '{secret_name}'. "
                f"Available fields: {list(data.keys())}"
            )
        return data[field]

    def invalidate(self, secret_name: str | None = None) -> None:
        """
        Evict a specific secret (or the entire cache) so the next
        call re-fetches from AWS.
        """
        with self._mu:
            if secret_name:
                self._cache.pop(secret_name, None)
            else:
                self._cache.clear()

    # ------------------------------------------------------------------
    # Convenience shortcuts
    # ------------------------------------------------------------------

    def get_anthropic_api_key(self) -> str:
        return self.get_field(SecretName.ANTHROPIC, SecretField.ANTHROPIC_API_KEY)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_raw(self, secret_name: str) -> str:
        logger.debug("Fetching secret '%s' from AWS Secrets Manager.", secret_name)
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            raise SecretsManagerError(
                f"Failed to fetch secret '{secret_name}' ({code}): {exc}"
            ) from exc

        # AWS returns either SecretString or SecretBinary
        if "SecretString" in response:
            return response["SecretString"]

        # Binary secrets are base64-decoded by boto3 automatically
        import base64
        return base64.b64decode(response["SecretBinary"]).decode("utf-8")
