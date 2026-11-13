"""Mays Orders privacy secret provider foundation.

P00-B intentionally contains only the provider contract and the backwards-
compatible ENV implementation. Secrets Manager resource/IAM wiring (P00-C) and
APP_MANAGED key material/HMAC integration (P00-D) are separate packages.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from errors import VALIDATION_ERROR, OrderError

ENV_PROVIDER = "env"
SECRETS_MANAGER_PROVIDER = "secretsmanager"
APP_MANAGED_PROVIDER = "app_managed"

ENV_SECRET_NAME = "PRIVACY_INTERNAL_SECRET"
PROVIDER_ENV = "PRIVACY_SECRET_PROVIDER"


class SecretProviderError(OrderError):
    """Safe, fail-closed provider error for the privacy trust boundary."""

    public_message = "Internal secret provider error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(VALIDATION_ERROR, message or self.public_message, 400)


class ProviderConfigurationError(SecretProviderError):
    public_message = "Internal secret provider configuration invalid"


class SecretNotConfigured(SecretProviderError):
    public_message = "Internal secret not configured"


class SecretNotFound(SecretProviderError):
    public_message = "Internal secret unavailable"


class SecretAccessDenied(SecretProviderError):
    public_message = "Internal secret access denied"


class SecretUnavailable(SecretProviderError):
    public_message = "Internal secret unavailable"


class SecretInvalid(SecretProviderError):
    public_message = "Internal secret invalid"


class AppKeyInvalid(SecretProviderError):
    public_message = "Internal APP key invalid"


class KeyVersionUnavailable(SecretProviderError):
    public_message = "Internal APP key version unavailable"


class SecretProvider(Protocol):
    """Minimal provider contract shared by ENV/AWS_MANAGED/APP_MANAGED."""

    def resolve(self) -> "SecretMaterial":
        ...


@dataclass(frozen=True)
class SecretMaterial:
    """Resolved secret material. ``value`` is never exposed by repr/logging."""

    provider: str
    value: str = field(repr=False)
    key_id: str | None = None
    key_version: str | None = None

    def __repr__(self) -> str:
        return (
            "SecretMaterial("
            f"provider={self.provider!r}, "
            f"key_id={self.key_id!r}, "
            f"key_version={self.key_version!r}, "
            "value=<redacted>)"
        )


@dataclass(frozen=True)
class SecretProviderConfig:
    """Resolved provider configuration; never contains a plaintext secret."""

    provider: str
    reference: str

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SecretProviderConfig":
        env = os.environ if environ is None else environ
        provider = (env.get(PROVIDER_ENV) or ENV_PROVIDER).strip().lower()

        if provider != ENV_PROVIDER:
            raise ProviderConfigurationError()

        # Avoid a silent mode confusion if a deployment carries a reference for
        # a different provider while still running the ENV default.
        conflicting = (
            "PRIVACY_SECRET_ID",
            "PRIVACY_APP_KEY_ID",
            "PRIVACY_APP_KEY_VERSION",
            "PRIVACY_APP_KEY_REF",
            "PRIVACY_KMS_KEY_ARN",
        )
        if any((env.get(name) or "").strip() for name in conflicting):
            raise ProviderConfigurationError()

        return cls(provider=ENV_PROVIDER, reference=ENV_SECRET_NAME)


class EnvSecretProvider:
    """Backwards-compatible implementation of the existing ENV trust boundary."""

    def __init__(
        self,
        config: SecretProviderConfig,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        self._environ = os.environ if environ is None else environ

    def resolve(self) -> SecretMaterial:
        value = self._environ.get(self._config.reference)
        if not value:
            raise SecretNotConfigured()
        return SecretMaterial(provider=ENV_PROVIDER, value=value)


def create_secret_provider(
    environ: Mapping[str, str] | None = None,
) -> SecretProvider:
    """Build the configured provider.

    P00-B only enables the ENV provider. Other providers are introduced by
    their separately approved packages; until then their configuration must
    fail closed rather than silently falling back to ENV.
    """

    env = os.environ if environ is None else environ
    config = SecretProviderConfig.from_environment(env)
    return EnvSecretProvider(config, env)
