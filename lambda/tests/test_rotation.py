"""P00-F tests: explicit APP_MANAGED rotation window and revocation."""

from __future__ import annotations

import base64
import unittest
from datetime import datetime, timedelta, timezone

from hmac_contract import (
    AppManagedKey,
    HmacContractError,
    MESSAGE_TYPE_PRIVACY_INTERNAL_V1,
    build_envelope,
    sign_envelope,
)
from secret_provider import (
    APP_MANAGED_PROVIDER,
    AppKeyInvalid,
    AppManagedProvider,
    ProviderConfigurationError,
    SecretProviderConfig,
    create_secret_provider,
)

KEY_ID = "rotation-key-01"
ACTIVE_VERSION = "v2"
PREVIOUS_VERSION = "v1"
ACTIVE_B64 = base64.b64encode(bytes(range(32))).decode("ascii")
PREVIOUS_B64 = base64.b64encode(bytes(reversed(range(32)))).decode("ascii")
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
PAYLOAD = b"rotation-payload"


class RotationTestCase(unittest.TestCase):
    def _env(self, **overrides):
        env = {
            "PRIVACY_SECRET_PROVIDER": APP_MANAGED_PROVIDER,
            "PRIVACY_APP_KEY_REF": "external/key-ref",
            "PRIVACY_APP_KEY_ID": KEY_ID,
            "PRIVACY_APP_KEY_VERSION": ACTIVE_VERSION,
            "PRIVACY_APP_PREVIOUS_KEY_ID": KEY_ID,
            "PRIVACY_APP_PREVIOUS_KEY_VERSION": PREVIOUS_VERSION,
            "PRIVACY_APP_ROTATION_STARTED_AT": (NOW - timedelta(hours=1)).isoformat(),
            "PRIVACY_APP_ROTATION_UNTIL": (NOW + timedelta(hours=1)).isoformat(),
        }
        env.update(overrides)
        return env

    def _provider(self, **overrides):
        return create_secret_provider(
            self._env(**overrides),
            app_key_material=ACTIVE_B64,
            app_previous_key_material=PREVIOUS_B64,
        )


class TestRotationConfiguration(RotationTestCase):
    def test_partial_previous_configuration_fails_closed(self):
        for field in (
            "PRIVACY_APP_PREVIOUS_KEY_ID",
            "PRIVACY_APP_PREVIOUS_KEY_VERSION",
            "PRIVACY_APP_ROTATION_STARTED_AT",
            "PRIVACY_APP_ROTATION_UNTIL",
        ):
            with self.subTest(field=field):
                env = self._env()
                env.pop(field)
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(env)

    def test_rotation_window_is_capped_at_24_hours(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider(
                self._env(
                    PRIVACY_APP_ROTATION_UNTIL=(NOW + timedelta(hours=25)).isoformat()
                )
            )

    def test_reversed_or_equal_window_is_rejected(self):
        for started, until in (
            (NOW, NOW),
            (NOW, NOW - timedelta(minutes=1)),
        ):
            with self.subTest(started=started, until=until):
                with self.assertRaises(ProviderConfigurationError):
                    create_secret_provider(
                        self._env(
                            PRIVACY_APP_ROTATION_STARTED_AT=started.isoformat(),
                            PRIVACY_APP_ROTATION_UNTIL=until.isoformat(),
                        )
                    )

    def test_same_active_and_previous_version_is_rejected(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider(
                self._env(PRIVACY_APP_PREVIOUS_KEY_VERSION=ACTIVE_VERSION)
            )

    def test_rotation_fields_are_rejected_for_non_app_providers(self):
        with self.assertRaises(ProviderConfigurationError):
            create_secret_provider(
                {
                    "PRIVACY_INTERNAL_SECRET": "env-secret",
                    "PRIVACY_APP_PREVIOUS_KEY_ID": KEY_ID,
                }
            )


class TestRotationVerifier(RotationTestCase):
    def _signed(self, version: str, material_b64: str) -> tuple[bytes, str]:
        envelope = build_envelope(
            KEY_ID, version, MESSAGE_TYPE_PRIVACY_INTERNAL_V1, PAYLOAD
        )
        key = AppManagedKey.from_base64(KEY_ID, version, material_b64)
        return envelope, sign_envelope(key.material, envelope)

    def test_previous_key_is_accepted_only_inside_window(self):
        provider = self._provider()
        verifier = provider.rotation_verifier(NOW)
        for version, material in (
            (ACTIVE_VERSION, ACTIVE_B64),
            (PREVIOUS_VERSION, PREVIOUS_B64),
        ):
            with self.subTest(version=version):
                envelope, signature = self._signed(version, material)
                self.assertTrue(verifier.verify(envelope, signature))

        expired = self._provider().rotation_verifier(NOW + timedelta(hours=2))
        old_envelope, old_signature = self._signed(PREVIOUS_VERSION, PREVIOUS_B64)
        with self.assertRaises(HmacContractError):
            expired.verify(old_envelope, old_signature)

        active_envelope, active_signature = self._signed(ACTIVE_VERSION, ACTIVE_B64)
        self.assertTrue(expired.verify(active_envelope, active_signature))

    def test_unknown_version_is_rejected(self):
        verifier = self._provider().rotation_verifier(NOW)
        envelope, signature = self._signed("v9", ACTIVE_B64)
        with self.assertRaises(HmacContractError):
            verifier.verify(envelope, signature)

    def test_missing_previous_material_fails_closed_inside_window(self):
        provider = create_secret_provider(
            self._env(),
            app_key_material=ACTIVE_B64,
        )
        with self.assertRaises(AppKeyInvalid):
            provider.rotation_verifier(NOW)

    def test_without_previous_config_only_active_is_accepted(self):
        env = self._env()
        for field in (
            "PRIVACY_APP_PREVIOUS_KEY_ID",
            "PRIVACY_APP_PREVIOUS_KEY_VERSION",
            "PRIVACY_APP_ROTATION_STARTED_AT",
            "PRIVACY_APP_ROTATION_UNTIL",
        ):
            env.pop(field)
        provider = create_secret_provider(env, app_key_material=ACTIVE_B64)
        verifier = provider.rotation_verifier(NOW)
        active, active_sig = self._signed(ACTIVE_VERSION, ACTIVE_B64)
        old, old_sig = self._signed(PREVIOUS_VERSION, PREVIOUS_B64)
        self.assertTrue(verifier.verify(active, active_sig))
        with self.assertRaises(HmacContractError):
            verifier.verify(old, old_sig)


class TestRevocation(RotationTestCase):
    def test_revoke_fails_closed_without_hot_reload(self):
        provider = self._provider()
        self.assertEqual(provider.resolve_key().key_version, ACTIVE_VERSION)
        provider.revoke()
        with self.assertRaises(AppKeyInvalid):
            provider.resolve_key()
        with self.assertRaises(AppKeyInvalid):
            provider.rotation_verifier(NOW)
        with self.assertRaises(AppKeyInvalid):
            provider.resolve_previous_key()

    def test_provider_repr_does_not_expose_material(self):
        provider = self._provider()
        text = repr(provider)
        self.assertNotIn(ACTIVE_B64, text)
        self.assertNotIn(PREVIOUS_B64, text)


if __name__ == "__main__":
    unittest.main()
