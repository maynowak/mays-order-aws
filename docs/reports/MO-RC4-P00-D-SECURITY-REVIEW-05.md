# MO-RC4-P00-D — SECURITY REVIEW 05

**Status:** A — SECURITY REVIEW PASSED / MERGE REVIEW READY
**Datum:** 2026-11-14
**Review-Branch:** `review/mo-rc4-p00-d-security-05`
**Feature-HEAD:** `18cf541077ea19460f24ae342bfea233f5b544f3`
**Integration-HEAD:** `8a19d5a880d5bc9aa02e41529a8b7fa7d089cd14`

```text
MO-RC4-P00-D — SECURITY REVIEW PASSED / MERGE REVIEW READY
```

Keine CRITICAL/HIGH/MEDIUM-Findings. Zwei LOW Follow-ups und Testumgebungs-
Abweichungen; kein Merge-Blocker. Keine Produktänderung.

---

## 1. R1 — Kryptografie

| Prüfung | Ergebnis |
|---|---|
| HMAC-SHA256 aus `hmac`/`hashlib` | **PASS** |
| Exakt 32 Byte Schlüsselmaterial | **PASS** |
| Strikte Standard-Base64-Dekodierung | **PASS** |
| Base64url-Signatur ohne Padding | **PASS** |
| Konstantzeitvergleich (`compare_digest`) | **PASS** |
| Ungültige Signatur → fail-closed/false | **PASS** |
| Keine Schlüssel in Logs/Fehlern | **PASS** (keine Logs; Fehler enthalten nur Feldnamen) |
| Keine Eigenbau-Verschlüsselung | **PASS** — HMAC-only |

### Independently reproduced vector

```text
Envelope and key from HMAC-CONTRACT-03
HMAC-SHA256: 9793052f1a39915251c9a86c1fb61894fb8a2b4a857f4a7c19fc816ae772e79c
Signature:   l5MFLxo5kVJRyahsH7YYlPuKK0qFf0p8GfyBaudy55w
```

Reproduced with Python `hmac`/`hashlib`, independent of the implementation.

---

## 2. R2 — Envelope-Vertrag

| Prüfung | Ergebnis |
|---|---|
| `MOAPP || 0x01 || 0x01` | **PASS** |
| Big-Endian `u16`/`u32` | **PASS** |
| Byte-Längen statt Zeichenlängen | **PASS** |
| ASCII-Metadaten, 1…128 | **PASS** |
| Payload 1…1 MiB | **PASS** |
| Keine mehrdeutigen Feldkombinationen | **PASS** — Length-Prefix-Framing |
| Keine unbekannten/trailing Felder | **PASS** |
| `keyId`/`keyVersion` gebunden | **PASS** |
| Message-Type/Payload gebunden | **PASS** |
| Downgrade-Schutz | **PASS** — aktive/previous-Allowlist; no fallback |

---

## 3. R3 — Provider-Isolation

| Prüfung | Ergebnis |
|---|---|
| ENV unverändert | **PASS** |
| AWS_MANAGED unverändert | **PASS** |
| APP_MANAGED default-off | **PASS** |
| Keine request-seitige Provider-Auswahl | **PASS** |
| Keine Cross-Provider-Fallbacks | **PASS** |
| `verified_internal_signed` nicht aktiviert | **PASS** |
| Bestehende Orders unverändert | **PASS** |
| `AppManagedProvider.resolve()` fail-closed | **PASS** |
| `verifier()` nicht in Order-Pfad verdrahtet | **PASS** — `resolve_key/verifier` nur über AppManagedProvider |

---

## 4. R4 — Key-Kustodie

- Keine dauerhafte Speicherung in Git/Reports/Auditlogs/Terraform-State.
- Key-Material nur in-memory `AppManagedKey`; `repr` redigiert.
- Lokaler Loader/Material-Injection only; keine produktive Transportintegration.
- Keine AWS-Abhängigkeit, kein KMS.
- Keine automatische Rotation, Löschung oder Aktivierung.
- **PASS** für lokale Implementierung; produktiver Transport bleibt P00-F/Operations.

---

## 5. R5 — Testqualität

- **23/23** HMAC-Tests PASS.
- Lambda **428 PASS**.
- Positivvektor exakt reproduziert.
- Manipulierte Payload, Key-ID/Version, unbekannte Version, Protokollwechsel,
  Base64/Länge, trailing bytes, Downgrade, Message-Type, Provider-Isolation,
  Redaction und Packaging abgedeckt.

### Finding R5-L01 — LOW: kein expliziter „falscher Schlüssel“-Test

Es wird ein falscher Schlüssel nicht direkt getestet: `test_signature_mismatch`
ändert die Signatur, nicht das Schlüsselmaterial. Der Code ist fail-closed
(`compare_digest`), aber ein Test mit Key A signiert / Key B mit gleicher
`keyId`/`keyVersion` verifiziert fehlt. **Follow-up, kein Merge-Blocker.**

### INFO

- `HMAC_SHA256` ist als Konstante vorhanden, aber nicht separat im Runtime-Pfad
  verwendet.
- Previous-Version-Zeitfenster wird bewusst nicht in P00-D implementiert;
  P00-F bleibt zuständig.
- `decode_key_material` enthält eine redundante URL-safe-Vorprüfung; funktional
  fail-closed.

---

## 6. R6 — Dependency-Detector-Failure

**Klassifikation: TEST HARNESS DEFECT (mit ENVIRONMENT DEPENDENCY).**

- `installer/tests/test_installer.py:1435` uses
  `cwd="/home/dci-student/projects/Mays-Orders-AWS"` and expects
  `returncode == 1` (changes detected).
- The primary worktree is currently clean (`git status` empty) and
  `security/dependency_detector.py` returns exit `0` with
  `"status": "DEPENDENCIES_CURRENT"`.
- The test is not hermetic and does not use the current feature worktree.
- Reproduction without P00-D: the same clean primary state produces the same
  failure; P00-D changes are in a different worktree and do not affect the
  installer/security tree.
- No AWS-live call required. **Not a PRODUCT REGRESSION.**
- No changes to the primary worktree were made.

---

## 7. R7 — Packaging

```text
lambda/dist/lambda.zip
45.676 Bytes
SHA-256 b70e5c945f917545d9ac9174dc6823a4d5473ebb069b88f449f420c0e62aa4ff
13 Module
hmac_contract.py enthalten
Source/ZIP 13/13 byte-identisch
Rebuild byte-identisch
```

No secrets in ZIP; test vectors are synthetic public values.

---

## 8. Test-Evidence Summary

| Suite | Ergebnis |
|---|---:|
| Lambda | **428 PASS** |
| HMAC contract | **23 PASS** |
| Installer | **667 PASS** |
| Installer live profile | **1 DEFERRED** |
| Installer dependency detector | **1 TEST HARNESS FAILURE** |
| Module Builder | **128 PASS** |
| E2E local | **32 PASS** |
| Seed | **28 PASS** |

The two installer exceptions are not P00-D product defects and are not counted
as PASS.

---

## 9. Findings / Empfehlung

| ID | Severity | Finding | Merge blocker |
|---|---|---|---|
| R5-L01 | LOW | Missing direct wrong-key test | NO |
| R6-L01 | LOW | Non-hermetic dependency-detector test (primary worktree + clean state) | NO |
| INFO-1 | INFO | `HMAC_SHA256` constant/URL-safe precheck minor cleanup | NO |
| INFO-2 | INFO | Previous-version time window intentionally P00-F | NO |

**Merge recommendation: PASS for P00-D code merge.** Deployment remains
blocked by P00-F/rotation, production key transport and the open installer
environment tests. No production activation.

---

## 10. Git / Grenzen

```text
Review branch: review/mo-rc4-p00-d-security-05
Review HEAD:   18cf541077ea19460f24ae342bfea233f5b544f3
Feature HEAD:  18cf541077ea19460f24ae342bfea233f5b544f3
Integration:   8a19d5a880d5bc9aa02e41529a8b7fa7d089cd14
Working Tree:  CLEAN
```

No product code changes, no merge/push/deploy, no AWS-live/Terraform action,
no RIS/Jobsearch change.

**STOP before merge/deployment.**
