# MO-RC4-P00-D — HMAC CONTRACT 03

**Status:** A — HMAC CONTRACT PREPARED / OWNER APPROVAL PENDING
**Datum:** 2026-11-14
**Branch:** `release/rc4-integration`
**HEAD:** `69960e717a1e91be56c27f39aa0b69c70bab8c07`
**Contract:** `docs/contracts/MO-RC4-P00-D-HMAC-PAYLOAD-CONTRACT.md`
**Modus:** Technische Vertragsspezifikation; keine Produktimplementierung.

```text
MO-RC4-P00-D — HMAC CONTRACT PREPARED / OWNER APPROVAL PENDING
```

---

## 1. Bestehende Semantik

**Es gibt heute keinen APP_MANAGED-HMAC.** Verifiziert:

- `AppManagedProvider.resolve()` ist eine P00-B-Metadaten-/Fail-closed-Grenze.
- `order_service._require_privacy_auth` nutzt einen `internal_token`-Vergleich,
  keine HMAC-Signatur.
- `identity.py` definiert `verified_internal_signed`, implementiert es aber
  nicht.
- Es existieren keine kanonische APP_MANAGED-Payload, keine HMAC-Berechnung,
  keine HMAC-Verifikation und keine bestehenden APP_MANAGED-Signaturen.
- Bestehende Orders/Tokens werden nicht umgestellt; APP_MANAGED ist additiv und
  default-off.

---

## 2. Vorgeschlagenes Payload-Format

**Status: PROPOSED — OWNER APPROVAL PENDING**

```text
MOAPP || 0x01 || 0x01 ||
u16(len(keyId)) || keyId ||
u16(len(keyVersion)) || keyVersion ||
u16(len(messageType)) || messageType ||
u32(len(payload)) || payload
```

- `MOAPP`: 5 ASCII-Bytes.
- Protokollversion `0x01`, Algorithmus `0x01` (HMAC-SHA256).
- Längenfelder big-endian.
- `keyId`, `keyVersion`, `messageType`: ASCII, 1…128 Zeichen,
  `[A-Za-z0-9._-]`.
- `payload`: opak, 1…1,048,576 Bytes, Semantik über `messageType`.
- Keine optionalen/doppelten/unbekannten Felder; keine trailing bytes.
- Längenpräfixe verhindern mehrdeutige Konkatenationen.
- HMAC-SHA256 über exakt diese Bytes; Signatur 32 Bytes.
- Signatur-Wire-Format (hex/base64) bleibt Owner-Entscheidung.

---

## 3. Key Binding / Downgrade-Schutz

- `keyId`, `keyVersion`, Protokollversion, Algorithmus, Message-Type und
  Payload sind Teil des HMAC-Inputs.
- Verifikation sucht `keyId`/`keyVersion` ausschließlich in der vertrauenswürdigen
  Konfiguration; keine beliebige Request-Auswahl.
- Nur aktive Version oder eine vorherige innerhalb des expliziten
  Übergangsfensters.
- Unbekannte/abgelaufene Version → fail-closed.
- Kein Provider-/ENV-/AWS_MANAGED-Fallback.
- Änderung eines Feldes ändert die HMAC-Bytes; Downgrade-Versuche werden
  abgelehnt.
- Key-Material: exakt 32 Byte nach strikter Standard-Base64-Dekodierung;
  ungültiges Base64/Länge/leer → fail-closed.

---

## 4. Testvektoren

Synthetischer öffentlicher Testschlüssel (kein realer Schlüssel):

```text
KEY (hex): 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
KEY (base64): AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=
KEY_ID: test-key-01
KEY_VERSION: v1
MESSAGE_TYPE: privacy.internal.v1
PAYLOAD: example-payload
```

Gültiger Vektor:

```text
ENVELOPE (hex):
4d4f4150500101000b746573742d6b65792d3031000276310013707269766163792e696e7465726e616c2e76310000000f6578616d706c652d7061796c6f6164

HMAC-SHA256 (hex):
9793052f1a39915251c9a86c1fb61894fb8a2b4a857f4a7c19fc816ae772e79c
```

Weitere Vektoren (keine echten Schlüssel):

| ID | Mutation | Erwartung |
|---|---|---|
| TV-01 | Gültiger Vektor | Akzeptiert |
| TV-02 | Payload + `X` | HMAC mismatch, reject |
| TV-03 | `keyId=test-key-02` | HMAC mismatch, reject |
| TV-04 | `keyVersion=v2` bei aktiver v1 | Reject |
| TV-05 | `keyVersion=v9` | Unknown version, reject |
| TV-06 | Protokoll `0x02` | Unknown protocol, reject |
| TV-07 | `keyId=test-key-01v1`, leere Version | Reject; andere Length-Prefix-Bytes |
| TV-08 | Ungültige Zeichenkodierung im Payload | Reject durch Message-Type-Semantik |
| TV-09 | Base64 `AAEC` (3 Byte) | Invalid length, reject |
| TV-10 | Base64 mit Whitespace/ungültigem Alphabet | Reject |
| TV-11 | Alte Version außerhalb Fenster | Reject |
| TV-12 | Fehlende/trailing Felder | Reject |

---

## 5. Kompatibilität

- `ENV` unverändert.
- `AWS_MANAGED` unverändert.
- `APP_MANAGED` neu, additiv, default-off.
- Keine bestehenden Order-/Token-/Signaturänderungen.
- Keine automatische Migration.
- Keine Änderung bestehender Signaturen ohne separate Freigabe.

---

## 6. Q-11-Entscheidungsblatt

**Alle Punkte PROPOSED — nicht APPROVED.**

| ID | Vorschlag | Status |
|---|---|---|
| T1 | Übergangsfenster beginnt bei expliziter Aktivierung der neuen Version | PROPOSED |
| T2 | Kompromittierte Version sofort deaktivieren; technische Wirkung via P00-F-Environment-Recycle; bestehende Signaturen als kompromittiert behandeln | PROPOSED |
| T3 | `keyId`/`keyVersion` im HMAC-Input binden | PROPOSED |
| T4 | Length-prefixed, versionierte HMAC-Payload wie oben | PROPOSED |
| T5 | Keine automatische Schlüssellöschung; Retention/Q-14 beachten | PROPOSED |
| T6 | Rotation/Widerruf/Transition bleiben P00-F | PROPOSED |

Zusätzlich:

- maximal eine aktive und eine vorherige Version;
- reguläres Übergangsfenster maximal 24 Stunden;
- keine automatische Rotation in P00-D;
- keine neue AWS-Abhängigkeit.

### Offene Owner-Fragen

1. Exakte Signatur-Wire-Kodierung (hex/base64).
2. Sichtbarkeit/Behandlung bereits ausgestellter Signaturen nach Ablauf.
3. Konkreter Key-Transport/-Kustode ohne AWS.
4. Payload-Message-Type-Semantik und Produktionsnutzung (P00-D vs. späterer Consumer).
5. Retention/Löschung alter Signaturen und Keys.

---

## 7. P00-D / P00-F

**P00-D:** Payload-Envelope, Metadatenbindung, Key-Material-Validierung,
HMAC-SHA256, versionierte Verifikation, Fail-closed, lokale Testvektoren.

**P00-F:** Rotation, Aktivierung, Übergangsfenster, Widerruf,
Cache-/Environment-Recycle, Löschung.

Keine P00-F-Funktionalität in P00-D.

---

## 8. Git / Grenzen

```text
Branch:        release/rc4-integration
HEAD:          69960e717a1e91be56c27f39aa0b69c70bab8c07
Working Tree:  CLEAN
Product code:  NONE
AWS/Terraform: NONE
Merge/Push:    NONE
Deployment:    NONE
RIS/Jobsearch: NONE
```

Keine Tests ausgeführt, da ausschließlich Dokumentation geändert wird.

**STOP vor Produktimplementierung.**
