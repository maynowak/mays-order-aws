"""APP_MANAGED versioned HMAC envelope and verification.

P00-D contract:
  MOAPP || protocol 0x01 || algorithm 0x01 ||
  u16(len(keyId)) || keyId ||
  u16(len(keyVersion)) || keyVersion ||
  u16(len(messageType)) || messageType ||
  u32(len(payload)) || payload

No encryption is implemented here. HMAC-SHA256 provides authentication only.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field

MAGIC = b"MOAPP"
PROTOCOL_VERSION = 0x01
ALGORITHM_HMAC_SHA256 = 0x01
HMAC_SHA256 = "HMAC-SHA256"
MESSAGE_TYPE_PRIVACY_INTERNAL_V1 = "privacy.internal.v1"
ALLOWED_MESSAGE_TYPES = frozenset({MESSAGE_TYPE_PRIVACY_INTERNAL_V1})
KEY_BYTES = 32
SIGNATURE_BYTES = 32
MAX_METADATA_BYTES = 128
MAX_PAYLOAD_BYTES = 1024 * 1024

_METADATA_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SIGNATURE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class HmacContractError(ValueError):
    """Safe fail-closed contract error; never contains key material."""


@dataclass(frozen=True)
class HmacEnvelope:
    key_id: str
    key_version: str
    message_type: str
    payload: bytes = field(repr=False)
    raw: bytes = field(repr=False)

    def __repr__(self) -> str:
        return (
            "HmacEnvelope("
            f"key_id={self.key_id!r}, "
            f"key_version={self.key_version!r}, "
            f"message_type={self.message_type!r}, "
            "payload=<redacted>, raw=<redacted>)"
        )


def _validate_metadata(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise HmacContractError(f"{label} must be a string")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError:
        raise HmacContractError(f"{label} is invalid") from None
    if not value or len(encoded) > MAX_METADATA_BYTES:
        raise HmacContractError(f"{label} is invalid")
    if not _METADATA_RE.fullmatch(value):
        raise HmacContractError(f"{label} is invalid")
    return value


def _validate_payload(payload: object) -> bytes:
    if not isinstance(payload, (bytes, bytearray)):
        raise HmacContractError("payload must be bytes")
    value = bytes(payload)
    if not value or len(value) > MAX_PAYLOAD_BYTES:
        raise HmacContractError("payload length is invalid")
    return value


def build_envelope(
    key_id: str,
    key_version: str,
    message_type: str,
    payload: bytes | bytearray,
    *,
    protocol_version: int = PROTOCOL_VERSION,
    algorithm: int = ALGORITHM_HMAC_SHA256,
) -> bytes:
    key_id = _validate_metadata(key_id, "keyId")
    key_version = _validate_metadata(key_version, "keyVersion")
    message_type = _validate_metadata(message_type, "messageType")
    if message_type not in ALLOWED_MESSAGE_TYPES:
        raise HmacContractError("messageType is not allowed")
    if protocol_version != PROTOCOL_VERSION:
        raise HmacContractError("protocol version is not supported")
    if algorithm != ALGORITHM_HMAC_SHA256:
        raise HmacContractError("algorithm is not supported")
    payload_bytes = _validate_payload(payload)

    key_id_bytes = key_id.encode("ascii")
    key_version_bytes = key_version.encode("ascii")
    message_type_bytes = message_type.encode("ascii")
    return (
        MAGIC
        + bytes((PROTOCOL_VERSION, ALGORITHM_HMAC_SHA256))
        + struct.pack(">H", len(key_id_bytes))
        + key_id_bytes
        + struct.pack(">H", len(key_version_bytes))
        + key_version_bytes
        + struct.pack(">H", len(message_type_bytes))
        + message_type_bytes
        + struct.pack(">I", len(payload_bytes))
        + payload_bytes
    )


def _read_uint(data: bytes, offset: int, size: int) -> tuple[int, int]:
    end = offset + size
    if end > len(data):
        raise HmacContractError("truncated envelope")
    value = int.from_bytes(data[offset:end], "big")
    return value, end


def _read_field(data: bytes, offset: int, size: int, label: str) -> tuple[bytes, int]:
    length, offset = _read_uint(data, offset, size)
    end = offset + length
    if length == 0 or end > len(data):
        raise HmacContractError(f"{label} is invalid")
    return data[offset:end], end


def parse_envelope(envelope: bytes | bytearray) -> HmacEnvelope:
    if not isinstance(envelope, (bytes, bytearray)):
        raise HmacContractError("envelope must be bytes")
    data = bytes(envelope)
    if len(data) < len(MAGIC) + 2 + 2 + 2 + 2 + 4:
        raise HmacContractError("truncated envelope")
    offset = 0
    if data[offset : offset + len(MAGIC)] != MAGIC:
        raise HmacContractError("invalid magic")
    offset += len(MAGIC)
    if data[offset] != PROTOCOL_VERSION:
        raise HmacContractError("protocol version is not supported")
    if data[offset + 1] != ALGORITHM_HMAC_SHA256:
        raise HmacContractError("algorithm is not supported")
    offset += 2

    key_id_raw, offset = _read_field(data, offset, 2, "keyId")
    key_version_raw, offset = _read_field(data, offset, 2, "keyVersion")
    message_type_raw, offset = _read_field(data, offset, 2, "messageType")
    payload_length, offset = _read_uint(data, offset, 4)
    if payload_length == 0 or payload_length > MAX_PAYLOAD_BYTES:
        raise HmacContractError("payload length is invalid")
    payload = data[offset : offset + payload_length]
    if len(payload) != payload_length:
        raise HmacContractError("truncated envelope")
    offset += payload_length
    if offset != len(data):
        raise HmacContractError("trailing bytes are not allowed")

    try:
        key_id = key_id_raw.decode("ascii")
        key_version = key_version_raw.decode("ascii")
        message_type = message_type_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise HmacContractError("metadata encoding is invalid") from None
    _validate_metadata(key_id, "keyId")
    _validate_metadata(key_version, "keyVersion")
    _validate_metadata(message_type, "messageType")
    if message_type not in ALLOWED_MESSAGE_TYPES:
        raise HmacContractError("messageType is not allowed")
    return HmacEnvelope(
        key_id=key_id,
        key_version=key_version,
        message_type=message_type,
        payload=payload,
        raw=data,
    )


def decode_key_material(value: str | bytes) -> bytes:
    if not isinstance(value, (str, bytes)):
        raise HmacContractError("key material is invalid")
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            raise HmacContractError("key material is invalid") from None
    if not value or _SIGNATURE_RE.fullmatch(value) is None:
        # Key material uses standard Base64; reject URL-safe/whitespace forms.
        if not re.fullmatch(r"^[A-Za-z0-9+/]+={0,2}$", value or ""):
            raise HmacContractError("key material is invalid")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HmacContractError("key material is invalid") from None
    if len(raw) != KEY_BYTES:
        raise HmacContractError("key material length is invalid")
    # Require canonical standard Base64 with normal padding.
    if base64.b64encode(raw).decode("ascii") != value:
        raise HmacContractError("key material encoding is not canonical")
    return raw


def validate_key_material(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != KEY_BYTES:
        raise HmacContractError("key material length is invalid")
    return value


def sign_envelope(key_material: bytes, envelope: bytes | HmacEnvelope) -> str:
    key = validate_key_material(key_material)
    raw_envelope = envelope.raw if isinstance(envelope, HmacEnvelope) else bytes(envelope)
    parse_envelope(raw_envelope)
    digest = hmac.new(key, raw_envelope, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def decode_signature(signature: str) -> bytes:
    if not isinstance(signature, str) or not signature or "=" in signature:
        raise HmacContractError("signature is invalid")
    if _SIGNATURE_RE.fullmatch(signature) is None:
        raise HmacContractError("signature is invalid")
    padding = "=" * (-len(signature) % 4)
    try:
        raw = base64.urlsafe_b64decode(signature + padding)
    except (binascii.Error, ValueError):
        raise HmacContractError("signature is invalid") from None
    if len(raw) != SIGNATURE_BYTES:
        raise HmacContractError("signature length is invalid")
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != signature:
        raise HmacContractError("signature encoding is not canonical")
    return raw


def verify_envelope(
    key_material: bytes,
    envelope: bytes | HmacEnvelope,
    signature: str,
) -> bool:
    key = validate_key_material(key_material)
    raw_envelope = envelope.raw if isinstance(envelope, HmacEnvelope) else bytes(envelope)
    # Re-parse even for an HmacEnvelope object so a forged dataclass instance
    # cannot select a key using metadata that differs from the signed bytes.
    parsed = parse_envelope(raw_envelope)
    supplied = decode_signature(signature)
    expected = hmac.new(key, parsed.raw, hashlib.sha256).digest()
    return hmac.compare_digest(supplied, expected)


@dataclass(frozen=True)
class AppManagedKey:
    key_id: str
    key_version: str
    material: bytes = field(repr=False)

    @classmethod
    def from_base64(cls, key_id: str, key_version: str, material: str) -> "AppManagedKey":
        return cls(
            key_id=_validate_metadata(key_id, "keyId"),
            key_version=_validate_metadata(key_version, "keyVersion"),
            material=decode_key_material(material),
        )

    def __repr__(self) -> str:
        return (
            "AppManagedKey("
            f"key_id={self.key_id!r}, "
            f"key_version={self.key_version!r}, "
            "material=<redacted>)"
        )


class HmacVerifier:
    """Versioned verifier with a trusted active/previous key allowlist.

    P00-D does not implement rotation or a transition window. Callers may pass
    a previous key only when an Owner-approved transition is active; P00-F owns
    that lifecycle decision.
    """

    def __init__(
        self,
        active: AppManagedKey,
        previous: AppManagedKey | None = None,
        *,
        allow_previous: bool = False,
    ) -> None:
        if previous is not None and (
            previous.key_id == active.key_id
            and previous.key_version == active.key_version
        ):
            raise HmacContractError("previous key must differ from active key")
        self._active = active
        self._previous = previous
        self._allow_previous = allow_previous

    def _select_key(self, envelope: HmacEnvelope) -> AppManagedKey:
        if (
            envelope.key_id == self._active.key_id
            and envelope.key_version == self._active.key_version
        ):
            return self._active
        if (
            self._allow_previous
            and self._previous is not None
            and envelope.key_id == self._previous.key_id
            and envelope.key_version == self._previous.key_version
        ):
            return self._previous
        raise HmacContractError("key version is not allowed")

    def verify(self, envelope: bytes | HmacEnvelope, signature: str) -> bool:
        raw_envelope = envelope.raw if isinstance(envelope, HmacEnvelope) else bytes(envelope)
        parsed = parse_envelope(raw_envelope)
        selected = self._select_key(parsed)
        return verify_envelope(selected.material, parsed, signature)


__all__ = [
    "ALGORITHM_HMAC_SHA256",
    "ALLOWED_MESSAGE_TYPES",
    "AppManagedKey",
    "HmacContractError",
    "HmacEnvelope",
    "HmacVerifier",
    "MAGIC",
    "MESSAGE_TYPE_PRIVACY_INTERNAL_V1",
    "PROTOCOL_VERSION",
    "build_envelope",
    "decode_key_material",
    "decode_signature",
    "parse_envelope",
    "sign_envelope",
    "validate_key_material",
    "verify_envelope",
]
