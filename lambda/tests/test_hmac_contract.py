import base64
import hashlib
import hmac
import unittest

from hmac_contract import (
    ALLOWED_MESSAGE_TYPES,
    HmacContractError,
    AppManagedKey,
    HmacVerifier,
    build_envelope,
    decode_key_material,
    decode_signature,
    parse_envelope,
    sign_envelope,
    verify_envelope,
)
from secret_provider import (
    APP_MANAGED_PROVIDER,
    AppKeyInvalid,
    AppManagedProvider,
    SecretProviderConfig,
    create_secret_provider,
)

KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
KEY_B64 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
KEY_BYTES = bytes.fromhex(KEY_HEX)
KEY_ID = "test-key-01"
KEY_VERSION = "v1"
MESSAGE_TYPE = "privacy.internal.v1"
PAYLOAD = b"example-payload"
ENVELOPE_HEX = (
    "4d4f4150500101000b746573742d6b65792d3031000276310013707269766163792e"
    "696e7465726e616c2e76310000000f6578616d706c652d7061796c6f6164"
)
HMAC_HEX = "9793052f1a39915251c9a86c1fb61894fb8a2b4a857f4a7c19fc816ae772e79c"
SIGNATURE = "l5MFLxo5kVJRyahsH7YYlPuKK0qFf0p8GfyBaudy55w"


class TestHmacEnvelope(unittest.TestCase):
    def test_published_vector_envelope_and_signature_are_exact(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        self.assertEqual(envelope.hex(), ENVELOPE_HEX)
        self.assertEqual(sign_envelope(KEY_BYTES, envelope), SIGNATURE)
        self.assertEqual(
            hmac.new(KEY_BYTES, envelope, hashlib.sha256).hexdigest(), HMAC_HEX
        )
        parsed = parse_envelope(envelope)
        self.assertEqual(parsed.key_id, KEY_ID)
        self.assertEqual(parsed.key_version, KEY_VERSION)
        self.assertEqual(parsed.message_type, MESSAGE_TYPE)
        self.assertEqual(parsed.payload, PAYLOAD)

    def test_valid_signature_verifies(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        self.assertTrue(verify_envelope(KEY_BYTES, envelope, SIGNATURE))

    def test_tampered_payload_fails(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD + b"X")
        self.assertFalse(verify_envelope(KEY_BYTES, envelope, SIGNATURE))

    def test_trailing_bytes_fail(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD) + b"X"
        with self.assertRaises(HmacContractError):
            parse_envelope(envelope)

    def test_truncated_envelope_fails(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        with self.assertRaises(HmacContractError):
            parse_envelope(envelope[:-1])

    def test_unknown_message_type_fails(self):
        with self.assertRaises(HmacContractError):
            build_envelope(KEY_ID, KEY_VERSION, "privacy.internal.v2", PAYLOAD)
        self.assertIn(MESSAGE_TYPE, ALLOWED_MESSAGE_TYPES)

    def test_unknown_protocol_fails_on_parse(self):
        envelope = bytearray(build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD))
        envelope[5] = 0x02
        with self.assertRaises(HmacContractError):
            parse_envelope(bytes(envelope))

    def test_non_ascii_metadata_fails(self):
        for field in ("key_id", "key_version", "message_type"):
            kwargs = {
                "key_id": KEY_ID,
                "key_version": KEY_VERSION,
                "message_type": MESSAGE_TYPE,
            }
            kwargs[field] = "tést"
            with self.subTest(field=field):
                with self.assertRaises(HmacContractError):
                    build_envelope(kwargs["key_id"], kwargs["key_version"], kwargs["message_type"], PAYLOAD)

    def test_payload_size_limits(self):
        with self.assertRaises(HmacContractError):
            build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, b"")
        with self.assertRaises(HmacContractError):
            build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, b"x" * (1024 * 1024 + 1))

    def test_ambiguous_field_combination_is_not_same_envelope(self):
        # Length prefixes keep the framing unambiguous; an empty version is rejected.
        with self.assertRaises(HmacContractError):
            build_envelope("test-key-01v1", "", MESSAGE_TYPE, PAYLOAD)
        normal = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        other = build_envelope("test-key-01v1", "v1", MESSAGE_TYPE, PAYLOAD)
        self.assertNotEqual(normal, other)


class TestHmacKeyAndSignature(unittest.TestCase):
    def test_key_material_round_trip(self):
        self.assertEqual(decode_key_material(KEY_B64), KEY_BYTES)

    def test_invalid_base64_and_length_fail(self):
        for value in ("AAEC", "", "not-base64!", "A" * 44):
            with self.subTest(value=value):
                with self.assertRaises(HmacContractError):
                    decode_key_material(value)

    def test_signature_decoding_is_strict_base64url_without_padding(self):
        self.assertEqual(len(decode_signature(SIGNATURE)), 32)
        for value in (SIGNATURE + "=", SIGNATURE[:-1], "not+base64", "", "A" * 44):
            with self.subTest(value=value):
                with self.assertRaises(HmacContractError):
                    decode_signature(value)

    def test_key_material_repr_is_redacted(self):
        key = AppManagedKey.from_base64(KEY_ID, KEY_VERSION, KEY_B64)
        self.assertNotIn(KEY_B64, repr(key))
        self.assertIn("<redacted>", repr(key))


class TestHmacVerifier(unittest.TestCase):
    def _key(self, key_id=KEY_ID, version=KEY_VERSION):
        return AppManagedKey.from_base64(key_id, version, KEY_B64)

    def test_active_key_verifies(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        self.assertTrue(HmacVerifier(self._key()).verify(envelope, SIGNATURE))

    def test_wrong_key_id_fails(self):
        envelope = build_envelope("test-key-02", KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        with self.assertRaises(HmacContractError):
            HmacVerifier(self._key()).verify(envelope, SIGNATURE)

    def test_unknown_or_unapproved_version_fails(self):
        envelope = build_envelope(KEY_ID, "v2", MESSAGE_TYPE, PAYLOAD)
        with self.assertRaises(HmacContractError):
            HmacVerifier(self._key()).verify(envelope, SIGNATURE)

    def test_previous_version_requires_explicit_allow(self):
        envelope = build_envelope(KEY_ID, "v1", MESSAGE_TYPE, PAYLOAD)
        active = self._key(version="v2")
        previous = self._key(version="v1")
        with self.assertRaises(HmacContractError):
            HmacVerifier(active, previous, allow_previous=False).verify(envelope, SIGNATURE)
        self.assertTrue(
            HmacVerifier(active, previous, allow_previous=True).verify(envelope, SIGNATURE)
        )

    def test_signature_mismatch_is_false_not_accepted(self):
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        self.assertFalse(HmacVerifier(self._key()).verify(envelope, SIGNATURE[:-1] + "A"))

    def test_different_key_material_with_same_metadata_fails(self):
        # R5-L01: valid, distinct 32-byte key; same keyId/keyVersion and envelope.
        other_key_b64 = "//79/Pv6+fj39vX08/Lx8O/u7ezr6uno5+bl5OPi4eA="
        other_key = AppManagedKey.from_base64(KEY_ID, KEY_VERSION, other_key_b64)
        envelope = build_envelope(KEY_ID, KEY_VERSION, MESSAGE_TYPE, PAYLOAD)
        signature = sign_envelope(KEY_BYTES, envelope)
        self.assertTrue(HmacVerifier(self._key()).verify(envelope, signature))
        self.assertFalse(HmacVerifier(other_key).verify(envelope, signature))
        self.assertNotEqual(self._key().material, other_key.material)


class TestAppManagedKeyBoundary(unittest.TestCase):
    def _config(self):
        return SecretProviderConfig.from_environment(
            {
                "PRIVACY_SECRET_PROVIDER": APP_MANAGED_PROVIDER,
                "PRIVACY_APP_KEY_REF": "external/key-ref",
                "PRIVACY_APP_KEY_ID": KEY_ID,
                "PRIVACY_APP_KEY_VERSION": KEY_VERSION,
            }
        )

    def test_resolve_key_validates_material_without_activating_bearer_auth(self):
        provider = AppManagedProvider(self._config(), key_material=KEY_B64)
        key = provider.resolve_key()
        self.assertEqual(key.key_id, KEY_ID)
        self.assertEqual(key.key_version, KEY_VERSION)
        with self.assertRaises(AppKeyInvalid):
            provider.resolve()

    def test_loader_is_injected_and_no_aws_dependency(self):
        provider = AppManagedProvider(self._config(), key_loader=lambda: KEY_B64)
        self.assertEqual(provider.resolve_key().material, KEY_BYTES)

    def test_missing_or_invalid_material_fails_closed(self):
        for kwargs in ({}, {"key_material": ""}, {"key_material": "AAEC"}):
            with self.subTest(kwargs=kwargs):
                provider = AppManagedProvider(self._config(), **kwargs)
                with self.assertRaises(AppKeyInvalid):
                    provider.resolve_key()

    def test_factory_accepts_local_material_but_keeps_default_resolution_fail_closed(self):
        provider = create_secret_provider(
            {
                "PRIVACY_SECRET_PROVIDER": APP_MANAGED_PROVIDER,
                "PRIVACY_APP_KEY_REF": "external/key-ref",
                "PRIVACY_APP_KEY_ID": KEY_ID,
                "PRIVACY_APP_KEY_VERSION": KEY_VERSION,
            },
            app_key_material=KEY_B64,
        )
        self.assertEqual(provider.resolve_key().material, KEY_BYTES)
        with self.assertRaises(AppKeyInvalid):
            provider.resolve()


if __name__ == "__main__":
    unittest.main()
