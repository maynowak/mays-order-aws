import contextlib
import io
import os
import unittest
from unittest.mock import patch

from errors import OrderError
from order_service import create_order_service
from secret_provider import (
    APP_MANAGED_AUTH_METHOD,
    APP_MANAGED_PROVIDER,
    ENV_PROVIDER,
    SECRETS_MANAGER_PROVIDER,
    AppKeyInvalid,
    EnvSecretProvider,
    ProviderConfigurationError,
    SecretAccessDenied,
    SecretCache,
    SecretInvalid,
    SecretMaterial,
    SecretNotConfigured,
    SecretNotFound,
    SecretProviderConfig,
    SecretReference,
    SecretUnavailable,
    create_secret_provider,
)


class TestEnvSecretProvider(unittest.TestCase):
    def test_default_provider_resolves_existing_env_secret(self):
        env = {"PRIVACY_INTERNAL_SECRET": "existing-secret"}
        provider = create_secret_provider(env)
        material = provider.resolve()
        self.assertEqual(material.provider, "env")
        self.assertEqual(material.value, "existing-secret")
        self.assertIsNone(material.key_id)
        self.assertIsNone(material.key_version)

    def test_missing_env_secret_fails_closed(self):
        provider = create_secret_provider({})
        with self.assertRaises(SecretNotConfigured):
            provider.resolve()

    def test_empty_env_secret_fails_closed(self):
        provider = create_secret_provider({"PRIVACY_INTERNAL_SECRET": ""})
        with self.assertRaises(SecretNotConfigured):
            provider.resolve()

    def test_explicit_env_provider_is_supported(self):
        provider = create_secret_provider(
            {
                "PRIVACY_SECRET_PROVIDER": "env",
                "PRIVACY_INTERNAL_SECRET": "secret",
            }
        )
        self.assertEqual(provider.resolve().value, "secret")

    def test_conflicting_reference_is_rejected(self):
        provider_errors = (
            {"PRIVACY_SECRET_ID": "arn:aws:secretsmanager:eu-central-1:123456789012:secret:x"},
            {"PRIVACY_APP_KEY_REF": "external-ref"},
            {"PRIVACY_APP_KEY_ID": "key-id"},
            {"PRIVACY_APP_KEY_VERSION": "1"},
            {"PRIVACY_KMS_KEY_ARN": "arn:aws:kms:eu-central-1:123456789012:key/abc"},
        )
        for conflicting in provider_errors:
            with self.subTest(conflicting=conflicting):
                env = {"PRIVACY_INTERNAL_SECRET": "secret", **conflicting}
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(env)

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider(
                {
                    "PRIVACY_SECRET_PROVIDER": "unknown",
                    "PRIVACY_INTERNAL_SECRET": "secret",
                }
            )

    def test_secret_material_repr_redacts_value(self):
        material = SecretMaterial(provider="env", value="do-not-log")
        self.assertNotIn("do-not-log", repr(material))
        self.assertIn("<redacted>", repr(material))

    def test_config_contains_no_secret_value(self):
        config = SecretProviderConfig.from_environment(
            {"PRIVACY_INTERNAL_SECRET": "do-not-store"}
        )
        self.assertEqual(config.provider, "env")
        self.assertEqual(config.reference, "PRIVACY_INTERNAL_SECRET")
        self.assertNotIn("do-not-store", repr(config))


class TestProviderContract(unittest.TestCase):
    def test_config_maps_to_non_secret_reference(self):
        config = SecretProviderConfig(
            provider="app_managed",
            reference="external-ref",
            key_id="key-1",
            key_version="v1",
        )
        reference = config.to_reference()
        self.assertEqual(
            reference,
            SecretReference(
                provider="app_managed",
                reference="external-ref",
                key_id="key-1",
                key_version="v1",
            ),
        )
        self.assertNotIn("value", repr(reference).lower())

    def test_cache_returns_material_without_second_load(self):
        cache = SecretCache()
        calls = []
        expected = SecretMaterial(provider="env", value="cached")

        def load():
            calls.append(1)
            return expected

        self.assertIs(cache.get_or_load(("env", "PRIVACY_INTERNAL_SECRET"), load), expected)
        self.assertIs(cache.get_or_load(("env", "PRIVACY_INTERNAL_SECRET"), load), expected)
        self.assertEqual(calls, [1])

    def test_cache_does_not_cache_failed_loads(self):
        cache = SecretCache()
        calls = []

        def load():
            calls.append(1)
            if len(calls) == 1:
                raise SecretAccessDenied()
            return SecretMaterial(provider="env", value="after-retry")

        with self.assertRaises(SecretAccessDenied):
            cache.get_or_load("key", load)
        material = cache.get_or_load("key", load)
        self.assertEqual(material.value, "after-retry")
        self.assertEqual(calls, [1, 1])


class _ClientError(Exception):
    def __init__(self, code):
        super().__init__("provider failure")
        self.response = {"Error": {"Code": code, "Message": "provider failure"}}


class TestSecretsManagerProvider(unittest.TestCase):
    ARN = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:orders/privacy-AbCdEf"
    KMS_ARN = "arn:aws:kms:eu-central-1:123456789012:key/11111111-2222-3333-4444-555555555555"

    def _env(self, **overrides):
        return {
            "PRIVACY_SECRET_PROVIDER": SECRETS_MANAGER_PROVIDER,
            "PRIVACY_SECRET_ID": self.ARN,
            **overrides,
        }

    def test_accepts_arn_and_valid_name(self):
        for reference in (self.ARN, "orders/privacy", "orders+privacy@v1"):
            with self.subTest(reference=reference):
                config = SecretProviderConfig.from_environment(
                    self._env(PRIVACY_SECRET_ID=reference)
                )
                self.assertEqual(config.provider, SECRETS_MANAGER_PROVIDER)
                self.assertEqual(config.reference, reference)

    def test_accepts_valid_optional_kms_arn(self):
        config = SecretProviderConfig.from_environment(
            self._env(PRIVACY_KMS_KEY_ARN=self.KMS_ARN)
        )
        self.assertEqual(config.kms_key_arn, self.KMS_ARN)

    def test_rejects_missing_reference(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider({"PRIVACY_SECRET_PROVIDER": SECRETS_MANAGER_PROVIDER})

    def test_rejects_plaintext_env_secret(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider(
                self._env(PRIVACY_INTERNAL_SECRET="must-not-be-used")
            )

    def test_rejects_app_configuration(self):
        for extra in (
            {"PRIVACY_APP_KEY_REF": "ref"},
            {"PRIVACY_APP_KEY_ID": "id"},
            {"PRIVACY_APP_KEY_VERSION": "1"},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(self._env(**extra))

    def test_rejects_invalid_reference_and_kms_arn(self):
        invalid = (
            {"PRIVACY_SECRET_ID": "*"},
            {"PRIVACY_SECRET_ID": "contains space"},
            {"PRIVACY_SECRET_ID": "arn:aws:secretsmanager:eu-central-1:123:secret:x"},
            {"PRIVACY_KMS_KEY_ARN": "not-a-key-arn"},
        )
        for extra in invalid:
            with self.subTest(extra=extra):
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(self._env(**extra))

    def test_runtime_fetch_success_and_cache(self):
        calls = []

        def fetcher(reference):
            calls.append(reference)
            return {"SecretString": "resolved-secret"}

        provider = create_secret_provider(self._env(), fetcher)
        first = provider.resolve()
        second = provider.resolve()
        self.assertEqual(first.value, "resolved-secret")
        self.assertIs(first, second)
        self.assertEqual(calls, [self.ARN])

    def test_missing_runtime_adapter_fails_closed(self):
        provider = create_secret_provider(self._env())
        with self.assertRaises(SecretUnavailable):
            provider.resolve()

    def test_provider_errors_are_classified_without_raw_details(self):
        cases = (
            ("ResourceNotFoundException", SecretNotFound),
            ("AccessDeniedException", SecretAccessDenied),
            ("AccessDenied", SecretAccessDenied),
            ("KMSAccessDeniedException", SecretAccessDenied),
            ("InternalServiceError", SecretUnavailable),
        )
        for code, expected in cases:
            with self.subTest(code=code):
                provider = create_secret_provider(
                    self._env(),
                    lambda reference, code=code: (_ for _ in ()).throw(_ClientError(code)),
                )
                with self.assertRaises(expected) as raised:
                    provider.resolve()
                self.assertNotIn(self.ARN, str(raised.exception))
                self.assertNotIn("raw-secret", str(raised.exception))

    def test_generic_provider_exception_is_redacted(self):
        def fetcher(reference):
            raise RuntimeError("raw-secret-value from provider")

        provider = create_secret_provider(self._env(), fetcher)
        with self.assertRaises(SecretUnavailable) as raised:
            provider.resolve()
        self.assertNotIn("raw-secret-value", str(raised.exception))
        self.assertNotIn(self.ARN, str(raised.exception))

    def test_invalid_or_binary_secret_is_rejected(self):
        for response in (
            {},
            {"SecretString": ""},
            {"SecretBinary": b"binary"},
            "not-a-mapping",
        ):
            with self.subTest(response=response):
                provider = create_secret_provider(self._env(), lambda reference, response=response: response)
                with self.assertRaises(SecretInvalid):
                    provider.resolve()


class TestAppManagedProviderContract(unittest.TestCase):
    def _env(self, **overrides):
        return {
            "PRIVACY_SECRET_PROVIDER": APP_MANAGED_PROVIDER,
            "PRIVACY_APP_KEY_REF": "external/key-ref",
            "PRIVACY_APP_KEY_ID": "key-1",
            "PRIVACY_APP_KEY_VERSION": "v1",
            **overrides,
        }

    def test_valid_key_metadata_is_accepted(self):
        config = SecretProviderConfig.from_environment(self._env())
        self.assertEqual(config.provider, APP_MANAGED_PROVIDER)
        self.assertEqual(config.reference, "external/key-ref")
        self.assertEqual(config.key_id, "key-1")
        self.assertEqual(config.key_version, "v1")
        self.assertEqual(config.to_reference().key_version, "v1")

    def test_missing_key_metadata_is_rejected(self):
        for name in (
            "PRIVACY_APP_KEY_REF",
            "PRIVACY_APP_KEY_ID",
            "PRIVACY_APP_KEY_VERSION",
        ):
            with self.subTest(name=name):
                env = self._env()
                env.pop(name)
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(env)

    def test_conflicting_provider_values_are_rejected(self):
        for extra in (
            {"PRIVACY_INTERNAL_SECRET": "plaintext"},
            {"PRIVACY_SECRET_ID": "orders/privacy"},
            {"PRIVACY_KMS_KEY_ARN": "arn:aws:kms:eu-central-1:123456789012:key/x"},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(self._env(**extra))

    def test_invalid_key_identifiers_are_rejected(self):
        for field in ("PRIVACY_APP_KEY_REF", "PRIVACY_APP_KEY_ID", "PRIVACY_APP_KEY_VERSION"):
            with self.subTest(field=field):
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(self._env(**{field: "has whitespace"}))

    def test_app_managed_resolution_is_fail_closed_in_p00_b(self):
        provider = create_secret_provider(self._env())
        self.assertEqual(provider.auth_method, APP_MANAGED_AUTH_METHOD)  # type: ignore[attr-defined]
        with self.assertRaises(AppKeyInvalid):
            provider.resolve()


class TestSecurityHardening(unittest.TestCase):
    def test_request_context_cannot_select_provider_or_reference(self):
        class Provider:
            def resolve(self):
                return SecretMaterial(provider="env", value="expected-secret")

        service = create_order_service(
            "mays-orders",
            client=object(),
            secret_provider=Provider(),
        )
        context = {
            "project": "mays-orders",
            "authorized": True,
            "privacy_inspect": True,
            "internal_token": "expected-secret",
            "secretProvider": "secretsmanager",
            "secretReference": "arn:aws:secretsmanager:eu-central-1:123456789012:secret:evil",
        }
        with patch.dict(os.environ, {"ORDERS_PROJECT_NAME": "mays-orders"}, clear=False):
            service._require_privacy_auth(context, "privacy_inspect")

    def test_provider_error_does_not_log_secret(self):
        class FailingProvider:
            def resolve(self):
                raise SecretAccessDenied()

        service = create_order_service(
            "mays-orders",
            client=object(),
            secret_provider=FailingProvider(),
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(OrderError):
                service._resolve_privacy_secret()
        self.assertNotIn("secret", stdout.getvalue().lower())
        self.assertNotIn("secret", stderr.getvalue().lower())

    def test_backend_exception_cause_is_not_exposed(self):
        def fetcher(reference):
            raise RuntimeError("raw-secret-value")

        provider = create_secret_provider(
            {
                "PRIVACY_SECRET_PROVIDER": SECRETS_MANAGER_PROVIDER,
                "PRIVACY_SECRET_ID": "orders/privacy",
            },
            fetcher,
        )
        with self.assertRaises(SecretUnavailable) as raised:
            provider.resolve()
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn("raw-secret-value", str(raised.exception))

    def test_invalid_reference_error_does_not_echo_reference(self):
        bad_reference = "bad reference with secret-value"
        with self.assertRaises(ProviderConfigurationError) as raised:
            create_secret_provider(
                {
                    "PRIVACY_SECRET_PROVIDER": SECRETS_MANAGER_PROVIDER,
                    "PRIVACY_SECRET_ID": bad_reference,
                }
            )
        self.assertNotIn(bad_reference, str(raised.exception))


class TestOrderServiceSecretProviderIntegration(unittest.TestCase):
    def test_order_service_uses_injected_env_provider(self):
        provider = EnvSecretProvider(
            SecretProviderConfig(provider="env", reference="PRIVACY_INTERNAL_SECRET"),
            {"PRIVACY_INTERNAL_SECRET": "injected-secret"},
        )
        service = create_order_service("mays-orders", client=object(), secret_provider=provider)
        self.assertEqual(service._resolve_privacy_secret(), "injected-secret")

    def test_order_service_maps_provider_errors_to_fail_closed_order_error(self):
        class FailingProvider:
            def resolve(self):
                raise SecretAccessDenied()

        service = create_order_service(
            "mays-orders",
            client=object(),
            secret_provider=FailingProvider(),
        )
        with self.assertRaises(OrderError) as raised:
            service._resolve_privacy_secret()
        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")
        self.assertNotIn("arn:", str(raised.exception).lower())

    def test_default_provider_keeps_os_environ_semantics(self):
        with patch.dict(os.environ, {"PRIVACY_INTERNAL_SECRET": "patched-secret"}, clear=True):
            service = create_order_service("mays-orders", client=object())
            self.assertEqual(service._resolve_privacy_secret(), "patched-secret")


if __name__ == "__main__":
    unittest.main()
