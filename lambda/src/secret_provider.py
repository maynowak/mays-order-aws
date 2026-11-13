"""Mays Orders privacy secret provider foundation.

P00-B intentionally contains only the provider contract and the backwards-
compatible ENV implementation. Secrets Manager resource/IAM wiring (P00-C) and
APP_MANAGED key material/HMAC integration (P00-D) are separate packages.
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from errors import VALIDATION_ERROR, OrderError

ENV_PROVIDER = "env"
SECRETS_MANAGER_PROVIDER = "secretsmanager"
APP_MANAGED_PROVIDER = "app_managed"
SUPPORTED_PROVIDERS = (ENV_PROVIDER, SECRETS_MANAGER_PROVIDER, APP_MANAGED_PROVIDER)

ENV_SECRET_NAME = "PRIVACY_INTERNAL_SECRET"
PROVIDER_ENV = "PRIVACY_SECRET_PROVIDER"
SECRET_ID_ENV = "PRIVACY_SECRET_ID"
KMS_KEY_ARN_ENV = "PRIVACY_KMS_KEY_ARN"
APP_KEY_REF_ENV = "PRIVACY_APP_KEY_REF"
APP_KEY_ID_ENV = "PRIVACY_APP_KEY_ID"
APP_KEY_VERSION_ENV = "PRIVACY_APP_KEY_VERSION"
APP_MANAGED_AUTH_METHOD = "HMAC-SHA256"

_SECRET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9/_+=.@-]{1,512}$")
_SECRET_ARN_PATTERN = re.compile(
    r"^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]{1,512}$"
)
_KMS_KEY_ARN_PATTERN = re.compile(
    r"^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]{1,2048}$"
)


def validate_secret_reference(reference: str) -> str:
    """Validate an exact Secrets Manager ARN or a project-scoped name.

    Error messages never contain the supplied reference.
    """
    candidate = (reference or "").strip()
    if not candidate or any(char.isspace() for char in candidate):
        raise ProviderConfigurationError()
    if candidate.startswith("arn:"):
        if not _SECRET_ARN_PATTERN.fullmatch(candidate):
            raise ProviderConfigurationError()
    elif not _SECRET_NAME_PATTERN.fullmatch(candidate):
        raise ProviderConfigurationError()
    return candidate


def validate_kms_key_arn(key_arn: str) -> str:
    candidate = (key_arn or "").strip()
    if not candidate or not _KMS_KEY_ARN_PATTERN.fullmatch(candidate):
        raise ProviderConfigurationError()
    return candidate


def _non_empty(env: Mapping[str, str], name: str) -> str:
    value = (env.get(name) or "").strip()
    if not value:
        raise ProviderConfigurationError()
    return value


def _reject_non_empty(env: Mapping[str, str], name: str) -> None:
    if (env.get(name) or "").strip():
        raise ProviderConfigurationError()


def _validate_identifier(value: str, max_length: int = 256) -> str:
    candidate = (value or "").strip()
    if not candidate or len(candidate) > max_length:
        raise ProviderConfigurationError()
    if any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in candidate):
        raise ProviderConfigurationError()
    return candidate


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
class SecretReference:
    """Non-secret provider reference. Never contains secret material."""

    provider: str
    reference: str
    key_id: str | None = None
    key_version: str | None = None


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
    key_id: str | None = None
    key_version: str | None = None
    kms_key_arn: str | None = None

    def to_reference(self) -> SecretReference:
        return SecretReference(
            provider=self.provider,
            reference=self.reference,
            key_id=self.key_id,
            key_version=self.key_version,
        )

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SecretProviderConfig":
        env = os.environ if environ is None else environ
        provider = (env.get(PROVIDER_ENV) or ENV_PROVIDER).strip().lower()

        if provider not in SUPPORTED_PROVIDERS:
            raise ProviderConfigurationError()

        if provider == ENV_PROVIDER:
            # Avoid a silent mode confusion if a deployment carries a reference
            # for a different provider while still running the ENV default.
            for name in (
                SECRET_ID_ENV,
                APP_KEY_ID_ENV,
                APP_KEY_VERSION_ENV,
                APP_KEY_REF_ENV,
                KMS_KEY_ARN_ENV,
            ):
                _reject_non_empty(env, name)
            return cls(provider=ENV_PROVIDER, reference=ENV_SECRET_NAME)

        if provider == SECRETS_MANAGER_PROVIDER:
            _reject_non_empty(env, ENV_SECRET_NAME)
            _reject_non_empty(env, APP_KEY_ID_ENV)
            _reject_non_empty(env, APP_KEY_VERSION_ENV)
            _reject_non_empty(env, APP_KEY_REF_ENV)
            reference = validate_secret_reference(_non_empty(env, SECRET_ID_ENV))
            kms_key_arn = (env.get(KMS_KEY_ARN_ENV) or "").strip() or None
            if kms_key_arn is not None:
                kms_key_arn = validate_kms_key_arn(kms_key_arn)
            return cls(
                provider=SECRETS_MANAGER_PROVIDER,
                reference=reference,
                kms_key_arn=kms_key_arn,
            )

        if provider == APP_MANAGED_PROVIDER:
            _reject_non_empty(env, ENV_SECRET_NAME)
            _reject_non_empty(env, SECRET_ID_ENV)
            _reject_non_empty(env, KMS_KEY_ARN_ENV)
            reference = _validate_identifier(_non_empty(env, APP_KEY_REF_ENV))
            key_id = _validate_identifier(_non_empty(env, APP_KEY_ID_ENV))
            key_version = _validate_identifier(_non_empty(env, APP_KEY_VERSION_ENV))
            return cls(
                provider=APP_MANAGED_PROVIDER,
                reference=reference,
                key_id=key_id,
                key_version=key_version,
            )

        raise ProviderConfigurationError()


class SecretCache:
    """Process-local, non-persistent cache keyed by provider/reference/version.

    Errors are never cached: a failed load must be retried and fail closed,
    never silently resolved from an older value.
    """

    def __init__(self) -> None:
        self._values: dict[Hashable, SecretMaterial] = {}

    def get_or_load(
        self,
        key: Hashable,
        loader: Callable[[], SecretMaterial],
    ) -> SecretMaterial:
        if key in self._values:
            return self._values[key]
        material = loader()
        self._values[key] = material
        return material

    def invalidate(self) -> None:
        """Drop cached material; the next resolve performs a fresh load."""
        self._values.clear()


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


SecretsManagerFetcher = Callable[[str], Mapping[str, Any]]


class Boto3SecretsManagerFetcher:
    """Lazy boto3 adapter for AWS_MANAGED runtime fetching.

    No boto3 import or AWS call happens at module import. The client is created
    on first use and kept for the lifetime of this adapter (module-scoped in
    the production path); unit tests inject a fake client.
    """

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3  # type: ignore[reportMissingImports]  # provided by the Lambda runtime

            self._client = boto3.client(
                "secretsmanager",
                region_name=os.environ.get("AWS_REGION", "eu-central-1"),
            )
        return self._client

    def get_secret_value(self, secret_id: str) -> Mapping[str, Any]:
        return self._get_client().get_secret_value(SecretId=secret_id)

    def __call__(self, secret_id: str) -> Mapping[str, Any]:
        return self.get_secret_value(secret_id)


def _aws_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return ""
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return ""
    return str(error.get("Code") or "")


class SecretsManagerProvider:
    """Testable runtime-fetch adapter for the P00-C Secrets Manager wiring.

    P00-B deliberately does not create a boto3 client, IAM policy or secret
    resource. P00-C injects the real fetcher; unit tests inject a fake.
    """

    def __init__(
        self,
        config: SecretProviderConfig,
        fetcher: SecretsManagerFetcher | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher
        self._cache = SecretCache()

    def resolve(self) -> SecretMaterial:
        if self._fetcher is None:
            raise SecretUnavailable()
        key = (
            self._config.provider,
            self._config.reference,
            self._config.key_version or "",
            self._config.kms_key_arn or "",
        )
        return self._cache.get_or_load(key, self._load)

    def _load(self) -> SecretMaterial:
        try:
            response = self._fetcher(self._config.reference)  # type: ignore[misc]
        except SecretProviderError:
            raise
        except Exception as exc:
            code = _aws_error_code(exc)
            if code in ("ResourceNotFoundException", "ResourceNotFound"):
                raise SecretNotFound() from None
            if code in ("AccessDeniedException", "AccessDenied", "KMSAccessDeniedException"):
                raise SecretAccessDenied() from None
            raise SecretUnavailable() from None

        if not isinstance(response, Mapping):
            raise SecretInvalid()
        value = response.get("SecretString")
        if not isinstance(value, str) or not value:
            raise SecretInvalid()
        return SecretMaterial(
            provider=SECRETS_MANAGER_PROVIDER,
            value=value,
            key_id=self._config.key_id,
            key_version=self._config.key_version,
        )

    def invalidate(self) -> None:
        """Invalidate this provider's cache for a controlled rotation/deploy."""
        self._cache.invalidate()


class AppManagedProvider:
    """P00-D boundary: validates key metadata, but does not resolve/HMAC keys.

    The external key loader and HMAC verification are intentionally absent in
    P00-B. Selecting APP_MANAGED before P00-D therefore fails closed.
    """

    auth_method = APP_MANAGED_AUTH_METHOD

    def __init__(self, config: SecretProviderConfig) -> None:
        self._config = config

    def resolve(self) -> SecretMaterial:
        raise AppKeyInvalid()


def _build_provider(
    config: SecretProviderConfig,
    env: Mapping[str, str],
    secretsmanager_fetcher: SecretsManagerFetcher | None,
) -> SecretProvider:
    if config.provider == ENV_PROVIDER:
        return EnvSecretProvider(config, env)
    if config.provider == SECRETS_MANAGER_PROVIDER:
        fetcher = secretsmanager_fetcher
        if fetcher is None:
            fetcher = Boto3SecretsManagerFetcher().get_secret_value
        return SecretsManagerProvider(config, fetcher)
    if config.provider == APP_MANAGED_PROVIDER:
        return AppManagedProvider(config)
    raise ProviderConfigurationError()


def create_secret_provider(
    environ: Mapping[str, str] | None = None,
    secretsmanager_fetcher: SecretsManagerFetcher | None = None,
) -> SecretProvider:
    """Build the configured provider without any implicit fallback.

    ENV is the backwards-compatible default. Secrets Manager runtime fetching
    uses the lazy boto3 adapter unless a test injects a fetcher. APP_MANAGED
    validates key metadata but remains a P00-D implementation and fails closed.
    """

    env = os.environ if environ is None else environ
    config = SecretProviderConfig.from_environment(env)
    return _build_provider(config, env, secretsmanager_fetcher)


_default_provider: SecretProvider | None = None
_default_provider_key: tuple[Any, ...] | None = None
_default_provider_lock = threading.Lock()


def get_default_secret_provider(
    environ: Mapping[str, str] | None = None,
    secretsmanager_fetcher: SecretsManagerFetcher | None = None,
) -> SecretProvider:
    """Return the process-wide provider for one Lambda execution environment.

    The cache is keyed by provider, exact reference, key metadata, KMS reference
    and an injected-fetcher identity. A changed configuration replaces the
    provider; errors are never cached. ``reset_default_secret_provider`` is a
    controlled invalidation hook for rotation/deployment or tests.
    """

    env = os.environ if environ is None else environ
    config = SecretProviderConfig.from_environment(env)
    fetcher_identity = id(secretsmanager_fetcher) if secretsmanager_fetcher is not None else None
    key = (
        config.provider,
        config.reference,
        config.key_id,
        config.key_version,
        config.kms_key_arn,
        fetcher_identity,
    )
    global _default_provider, _default_provider_key
    with _default_provider_lock:
        if _default_provider is None or _default_provider_key != key:
            _default_provider = _build_provider(config, env, secretsmanager_fetcher)
            _default_provider_key = key
        return _default_provider


def reset_default_secret_provider() -> None:
    """Drop the module-level provider/cache (controlled rotation/tests only)."""
    global _default_provider, _default_provider_key
    with _default_provider_lock:
        _default_provider = None
        _default_provider_key = None
