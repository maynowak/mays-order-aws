import os
import unittest
from unittest.mock import patch

from errors import OrderError
from order_service import create_order_service
from secret_provider import (
    EnvSecretProvider,
    ProviderConfigurationError,
    SecretAccessDenied,
    SecretMaterial,
    SecretNotConfigured,
    SecretProviderConfig,
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
