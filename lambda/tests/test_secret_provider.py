import contextlib
import io
import json
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
    Boto3SecretsManagerFetcher,
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
    SecretsManagerProvider,
    create_secret_provider,
    get_default_secret_provider,
    log_secret_provider_failure,
    reset_default_secret_provider,
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

    def test_cache_isolates_different_identity_keys(self):
        cache = SecretCache()
        calls = []

        def load(value):
            calls.append(value)
            return SecretMaterial(provider="env", value=value)

        self.assertEqual(cache.get_or_load(("sm", "a"), lambda: load("a")).value, "a")
        self.assertEqual(cache.get_or_load(("sm", "b"), lambda: load("b")).value, "b")
        self.assertEqual(calls, ["a", "b"])


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
        config = SecretProviderConfig.from_environment(self._env())
        provider = SecretsManagerProvider(config, fetcher=None)
        with self.assertRaises(SecretUnavailable):
            provider.resolve()

    def test_default_secretsmanager_provider_uses_boto3_adapter(self):
        provider = create_secret_provider(self._env())
        self.assertIsInstance(provider, SecretsManagerProvider)
        self.assertIsNotNone(provider._fetcher)

    def test_boto3_fetcher_uses_injected_client_without_aws(self):
        calls = []
        kms_arn = self.KMS_ARN

        class FakeClient:
            def get_secret_value(self, **kwargs):
                calls.append(("get", kwargs))
                return {"SecretString": "from-fake-client"}

            def describe_secret(self, **kwargs):
                calls.append(("describe", kwargs))
                return {"KmsKeyId": kms_arn}

        fetcher = Boto3SecretsManagerFetcher(FakeClient())
        provider = SecretsManagerProvider(self._config(), fetcher.get_secret_value)
        material = provider.resolve()
        self.assertEqual(material.value, "from-fake-client")
        self.assertEqual(calls, [("get", {"SecretId": self.ARN})])

    def test_kms_binding_is_verified_through_describe_secret(self):
        calls = []

        def fetcher(reference):
            calls.append(("get", reference))
            return {"SecretString": "with-cmk"}

        def descriptor(reference):
            calls.append(("describe", reference))
            return {"KmsKeyId": self.KMS_ARN}

        provider = SecretsManagerProvider(
            self._config_with_kms(), fetcher, descriptor
        )
        self.assertEqual(provider.resolve().value, "with-cmk")
        self.assertEqual(
            calls,
            [("describe", self.ARN), ("get", self.ARN)],
        )

    def test_kms_binding_mismatch_fails_closed_without_fetch(self):
        def fetcher(reference):
            raise AssertionError("GetSecretValue must not run after mismatch")

        provider = SecretsManagerProvider(
            self._config_with_kms(),
            fetcher,
            lambda reference: {"KmsKeyId": self.KMS_ARN + "-other"},
        )
        with self.assertRaises(SecretInvalid):
            provider.resolve()

    def test_kms_binding_requires_descriptor(self):
        provider = SecretsManagerProvider(
            self._config_with_kms(),
            lambda reference: {"SecretString": "never"},
        )
        with self.assertRaises(SecretUnavailable):
            provider.resolve()

    def test_kms_descriptor_access_denied_is_redacted(self):
        provider = SecretsManagerProvider(
            self._config_with_kms(),
            lambda reference: {"SecretString": "never"},
            lambda reference: (_ for _ in ()).throw(_ClientError("AccessDeniedException")),
        )
        with self.assertRaises(SecretAccessDenied) as raised:
            provider.resolve()
        self.assertNotIn(self.ARN, str(raised.exception))

    def test_no_kms_config_does_not_call_descriptor(self):
        calls = []

        provider = SecretsManagerProvider(
            self._config(),
            lambda reference: {"SecretString": "without-cmk"},
            lambda reference: calls.append(reference) or {"KmsKeyId": self.KMS_ARN},
        )
        self.assertEqual(provider.resolve().value, "without-cmk")
        self.assertEqual(calls, [])

    def _config(self):
        return SecretProviderConfig.from_environment(self._env())

    def _config_with_kms(self):
        return SecretProviderConfig.from_environment(
            self._env(PRIVACY_KMS_KEY_ARN=self.KMS_ARN)
        )

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


class TestModuleCacheLifetime(unittest.TestCase):
    ARN_A = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:orders/a-AbCdEf"
    ARN_B = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:orders/b-AbCdEf"

    def setUp(self):
        reset_default_secret_provider()

    def tearDown(self):
        reset_default_secret_provider()

    def _env(self, reference):
        return {
            "PRIVACY_SECRET_PROVIDER": SECRETS_MANAGER_PROVIDER,
            "PRIVACY_SECRET_ID": reference,
        }

    def test_default_provider_is_shared_across_invocations(self):
        calls = []

        def fetcher(reference):
            calls.append(reference)
            return {"SecretString": "cached-secret"}

        first = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        second = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        self.assertIs(first, second)
        self.assertEqual(first.resolve().value, "cached-secret")
        self.assertEqual(second.resolve().value, "cached-secret")
        self.assertEqual(calls, [self.ARN_A])

    def test_config_change_replaces_provider_and_isolates_identity(self):
        calls = []

        def fetcher(reference):
            calls.append(reference)
            return {"SecretString": reference}

        first = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        second = get_default_secret_provider(self._env(self.ARN_B), fetcher)
        self.assertIsNot(first, second)
        self.assertEqual(first.resolve().value, self.ARN_A)
        self.assertEqual(second.resolve().value, self.ARN_B)
        self.assertEqual(calls, [self.ARN_A, self.ARN_B])

    def test_cache_invalidate_forces_fresh_fetch(self):
        calls = []

        def fetcher(reference):
            calls.append(reference)
            return {"SecretString": f"value-{len(calls)}"}

        provider = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        self.assertEqual(provider.resolve().value, "value-1")
        provider.invalidate()
        self.assertEqual(provider.resolve().value, "value-2")
        self.assertEqual(calls, [self.ARN_A, self.ARN_A])

    def test_reset_drops_module_provider(self):
        calls = []

        def fetcher(reference):
            calls.append(reference)
            return {"SecretString": "value"}

        first = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        reset_default_secret_provider()
        second = get_default_secret_provider(self._env(self.ARN_A), fetcher)
        self.assertIsNot(first, second)
        first.resolve()
        second.resolve()
        self.assertEqual(calls, [self.ARN_A, self.ARN_A])


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

    def test_provider_error_logs_only_safe_structured_fields(self):
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
        with patch.dict(
            os.environ,
            {"PRIVACY_SECRET_PROVIDER": "secretsmanager", "ORDERS_PROJECT_NAME": "mays-orders"},
            clear=False,
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(OrderError):
                    service._resolve_privacy_secret()
        self.assertEqual(stdout.getvalue(), "")
        line = stderr.getvalue().strip()
        payload = json.loads(line)
        self.assertEqual(payload["event"], "secret_provider_failure")
        self.assertEqual(payload["provider"], "secretsmanager")
        self.assertEqual(payload["errorClass"], "SecretAccessDenied")
        self.assertNotIn("arn:", line.lower())
        self.assertNotIn("raw-secret", line)
        self.assertNotIn("super-secret", line)

    def test_log_helper_does_not_include_secret_message(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            log_secret_provider_failure(SecretAccessDenied("raw-secret-value"), "secretsmanager")
        line = stderr.getvalue().strip()
        self.assertNotIn("raw-secret-value", line)
        self.assertIn("SecretAccessDenied", line)

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


class TestNonAsciiHardening(unittest.TestCase):
    class Provider:
        def __init__(self, value):
            self.value = value

        def resolve(self):
            return SecretMaterial(provider="env", value=self.value)

    def _service(self, secret):
        return create_order_service(
            "mays-orders",
            client=object(),
            secret_provider=self.Provider(secret),
        )

    def _context(self, token):
        return {
            "project": "mays-orders",
            "authorized": True,
            "privacy_inspect": True,
            "internal_token": token,
        }

    def test_non_ascii_token_returns_validation_error_not_500(self):
        service = self._service("ascii-secret")
        with patch.dict(os.environ, {"ORDERS_PROJECT_NAME": "mays-orders"}, clear=False):
            with self.assertRaises(OrderError) as raised:
                service._require_privacy_auth(self._context("tökén"), "privacy_inspect")
        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")
        self.assertEqual(raised.exception.http_status, 400)
        self.assertNotIn("tökén", str(raised.exception))

    def test_non_ascii_secret_returns_validation_error_not_500(self):
        service = self._service("sécret")
        with patch.dict(os.environ, {"ORDERS_PROJECT_NAME": "mays-orders"}, clear=False):
            with self.assertRaises(OrderError) as raised:
                service._require_privacy_auth(self._context("sécret"), "privacy_inspect")
        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")
        self.assertEqual(raised.exception.http_status, 400)

    def test_ascii_token_still_uses_constant_time_path(self):
        service = self._service("ascii-secret")
        with patch.dict(os.environ, {"ORDERS_PROJECT_NAME": "mays-orders"}, clear=False):
            service._require_privacy_auth(self._context("ascii-secret"), "privacy_inspect")

    def test_oversized_token_fails_closed(self):
        service = self._service("ascii-secret")
        with patch.dict(os.environ, {"ORDERS_PROJECT_NAME": "mays-orders"}, clear=False):
            with self.assertRaises(OrderError) as raised:
                service._require_privacy_auth(self._context("a" * 1025), "privacy_inspect")
        self.assertEqual(raised.exception.http_status, 400)


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
