# MO-RC4-P00-D — HMAC Payload Contract

**Status:** PROPOSED — OWNER APPROVAL PENDING
**Datum:** 2026-11-14
**Scope:** APP_MANAGED signierte Nachrichten; keine Produktimplementierung.
**Reference:** `docs/reports/MO-RC4-P00-D-HMAC-CONTRACT-03.md`

> This contract is a proposal. It does not authorize implementation and does not
> change ENV/AWS_MANAGED behavior.

---

## 1. Existing Semantics (verified)

| Frage | Befund |
|---|---|
| Welche Nachricht wird heute authentifiziert? | Keine APP_MANAGED-HMAC-Nachricht |
| Wo wird HMAC berechnet? | Nirgends; `APP_MANAGED` ist nur eine P00-B-Metadaten-/Fail-closed-Grenze |
| Wo wird HMAC verifiziert? | Nirgends |
| Welche Felder gehören zur Nachricht? | Keine bestehende kanonische APP_MANAGED-Payload |
| Bestehende Orders/Tokens betroffen? | Nein; bestehende Privacy-Nutzung ist `internal_token`-Vergleich, keine HMAC-Signatur |
| Bestehende kanonische Serialisierung? | Nein |
| Rückwärtskompatibilität | APP_MANAGED ist additiv/default-off; keine bestehende Signatur wird umgestellt |

Belege: `lambda/src/secret_provider.py` (`AppManagedProvider.resolve`),
`lambda/src/order_service.py` (`_require_privacy_auth`, `internal_token`),
`lambda/src/identity.py` (`verified_internal_signed` ist definiert, aber nicht
implementiert). Es gibt **keine** vorhandenen APP_MANAGED-Signaturen, die
migriert werden müssten.

---

## 2. Proposed Wire Format

All integer length fields are unsigned big-endian. The input is a byte string,
not a human-readable concatenation.

```text
ENVELOPE =
  MAGIC                 5 bytes   "MOAPP"
  PROTOCOL_VERSION      1 byte    0x01
  ALGORITHM             1 byte    0x01 (HMAC-SHA256)
  KEY_ID_LEN            u16
  KEY_ID                KEY_ID_LEN bytes, ASCII
  KEY_VERSION_LEN       u16
  KEY_VERSION           KEY_VERSION_LEN bytes, ASCII
  MESSAGE_TYPE_LEN      u16
  MESSAGE_TYPE          MESSAGE_TYPE_LEN bytes, ASCII
  PAYLOAD_LEN           u32
  PAYLOAD               PAYLOAD_LEN bytes, opaque
```

### Field rules

- `MAGIC` must equal `4d4f415050` (`MOAPP`).
- `PROTOCOL_VERSION = 0x01`; unknown versions fail closed.
- `ALGORITHM = 0x01` (HMAC-SHA256); unknown algorithms fail closed.
- `KEY_ID`: 1…128 ASCII characters, `[A-Za-z0-9._-]`.
- `KEY_VERSION`: 1…128 ASCII characters, `[A-Za-z0-9._-]`.
- `MESSAGE_TYPE`: 1…128 ASCII characters, `[A-Za-z0-9._-]`.
- `PAYLOAD`: 1…1,048,576 bytes; opaque to the envelope. Payload semantics are
  declared by `MESSAGE_TYPE`.
- No unknown/trailing bytes; no optional fields; missing/duplicate fields fail.
- No implicit separators; every variable field has an explicit length prefix.
- Empty key ID/version/message type or empty payload fails.
- The signature is `HMAC-SHA256(key, ENVELOPE)`, 32 bytes. Its wire encoding
  (hex/base64) is a **separate Owner decision**.

### Key material

- Externally supplied key material: exactly 32 bytes after decoding.
- Standard Base64 with required padding; strict decoding (`validate=True`),
  no whitespace, no URL-safe variant unless separately approved.
- Invalid Base64, wrong decoded length, empty material or missing key metadata
  → fail closed.
- Key values never appear in logs, errors, reports or audit logs.

---

## 3. Key Binding and Verification

The HMAC input binds:

- protocol version;
- algorithm;
- exact `keyId`;
- exact `keyVersion`;
- message type;
- payload bytes.

Verification rules:

1. Parse the envelope with exact lengths; reject trailing/missing bytes.
2. Reject unknown protocol/algorithm.
3. Look up `keyId`/`keyVersion` only in the trusted configured key set; never
   load an arbitrary key from request metadata.
4. Accept only the active version, or one previous version inside an explicit
   Owner-approved transition window.
5. Reject unknown or expired `keyVersion`; no fallback to an older/unknown key.
6. Compute HMAC-SHA256 over the exact envelope bytes and compare in constant
   time.
7. No fallback to ENV/AWS_MANAGED; provider selection is server configuration.

A downgrade attempt is detected by the expected active/previous version policy,
and by the fact that protocol/algorithm/key metadata are part of the HMAC input.
Changing any field invalidates the signature.

---

## 4. Test Vectors

Synthetic, public test key (not a real key):

```text
KEY (hex): 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
KEY (base64): AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=
KEY_ID: test-key-01
KEY_VERSION: v1
MESSAGE_TYPE: privacy.internal.v1
PAYLOAD: example-payload
```

### Valid vector

```text
ENVELOPE (hex):
4d4f4150500101000b746573742d6b65792d3031000276310013707269766163792e696e7465726e616c2e76310000000f6578616d706c652d7061796c6f6164

HMAC-SHA256 (hex):
9793052f1a39915251c9a86c1fb61894fb8a2b4a857f4a7c19fc816ae772e79c
```

### Negative/rejection vectors

| ID | Mutation | Expected |
|---|---|---|
| TV-02 | Payload `example-payloadX` | Signature mismatch; reject |
| TV-03 | `keyId=test-key-02` | Signature mismatch; reject |
| TV-04 | `keyVersion=v2` with active v1 | Reject (unexpected version) |
| TV-05 | `keyVersion=v9` | Reject unknown version |
| TV-06 | Protocol `0x02` | Reject unknown protocol |
| TV-07 | Key ID `test-key-01v1`, empty version, same message | Reject; different length-prefixed bytes, no ambiguity |
| TV-08 | Payload bytes not valid UTF-8 where message type requires UTF-8 | Reject by payload semantics |
| TV-09 | Key Base64 `AAEC` (wrong decoded length) | Reject |
| TV-10 | Key Base64 with whitespace/invalid alphabet | Reject |
| TV-11 | Old version outside transition window | Reject (downgrade) |
| TV-12 | Missing/trailing field bytes | Reject |

Reference HMACs for altered envelopes are **not** acceptance values; they are
evidence that a one-byte change produces a different MAC. Exact values are in
the companion report.

---

## 5. Compatibility

- `ENV`: unchanged; no HMAC path.
- `AWS_MANAGED`: unchanged; no HMAC path.
- `APP_MANAGED`: new, additive, default-off.
- No existing order, token, signature or API contract is migrated.
- No automatic migration or fallback.
- Existing `internal_token` semantics remain unchanged.

---

## 6. Open Owner Decisions

| ID | Decision | Proposed |
|---|---|---|
| Q11-T1 | Transition-window start | Explicit activation timestamp |
| Q11-T2 | Revocation / existing signatures | Immediate version disable + forced environment recycle; define re-signing |
| Q11-T3 | Key metadata binding | Yes, in canonical envelope |
| Q11-T4 | Payload canonicalization | Length-prefixed envelope above |
| Q11-T5 | Key deletion/retention | Owner/Operator; no automatic deletion |
| Q11-T6 | P00-D/P00-F boundary | P00-F owns rotation/transition/revocation |
| Q11-O5 | Existing signature treatment | Owner decision |
| — | Signature wire format (hex/base64) | Owner decision |
| — | Exact non-AWS key transport/loader | Owner/Infrastructure decision |

**No decision in this document is approved.**
