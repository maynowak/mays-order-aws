# MO-RC4-RELEASE-CANDIDATE-01

**RC4-Modul-Release-Entscheidung und Kandidaten-Dossier**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Analyse:** `614d06a4177bcbfb0ece484cebb8ddc03acac67f`
**Modus:** read-only Repository-Analyse, lokale nicht-mutierende Verifikation und
Dokumentation; keine AWS-/Terraform-/RIS-/Produktcode-Änderung, kein
Release-Tag, kein Push/Merge.

```text
RC4 MODULE RELEASE CONDITIONALLY READY
```

Der RC4-Order-Kern und der isolierte Teststack sind belegt. Eine **versionierte
RC4-Modulveröffentlichung** ist noch nicht möglich, weil Release-Label/Version
(Q-12), der verbindliche P00-Scope und die formale Release-/Scope-Autorisierung
offen sind. RIS und Produktion bleiben **NO-GO**.

---

## 1. Executive Summary

### Belegt

- Installer **669 PASS**
- Module Builder **128 PASS**
- Lambda **345 PASS**
- E2E lokal **32 PASS**
- Gesamt lokal **1.174 PASS**
- G3-FIX deployed/verified
- G3-LIVE-B1 PASS (DLQ, GSI3, Kompatibilität)
- Owner-/Consumer-Isolation live verified
- Privacy B2 **14 PASS, 1 SKIP**; X13 nicht als PASS
- B2-Cleanup und AWS-Rückbau verified

### Nicht entschieden oder nicht releasefähig

- Release-Label Q-12: `v0.5.0-rc.4` vs. `v0.6.0-rc.1`
- P00 KMS/Secrets/Retention: Scope nicht autorisiert; Implementierung fehlt
- Kein RC4-Release-Artefakt/Tag/Dossier-Freigabe vor diesem Auftrag
- SEC-06 Approval-Bindung offen
- Legacy-Order-Migration nicht entschieden
- Terraform-Teststack-Drift (2 `source_code_hash`-Änderungen)
- RIS pinnt RC3-Stand `1dbb0cb`; keine RC4-Consumer-Abnahme
- Produktionsfreigabe ausdrücklich BLOCKED

---

## 2. Release-Version — Entscheidung und offener Bedarf

### Bestehende Konventionen

- Release-Tags: `v0.5.0-rc.1`, `v0.5.0-rc.2`, `v0.5.0-rc.3`
- Deployment-Version im Teststack: `0.2.0`
- `installer/core/version_matrix.py`: `RC4_RELEASE_LABEL = "RC4 (Release-Label offen, Q-12)"`
- `MO-RC4-P00-OPEN-QUESTIONS.md` Q-12: Entscheidung vor P-14
- `module_builder/__init__.py`: Builder-Version `0.1.0`
- Kein `docs/release/RELEASE-v0.5.0-rc.4*` oder `v0.6.0-rc.1*`

### Bewertung

| Option | Passung | Bedingung |
|---|---|---|
| `v0.5.0-rc.4` | Fortsetzung der `rc.3`-Serie; passt zu einem **Order-Core-only**-RC4 | Formale Begrenzung des RC4-Scopes ohne P00 als Feature-Generation |
| `v0.6.0-rc.1` | Passt, wenn P00/KMS/Retention als neue Feature-Generation im RC4-Scope bleibt | P00 muss dann vor Release implementiert/abgeschlossen werden |

**Empfehlung:** `v0.6.0-rc.1` **nur**, wenn P00 als RC4-Feature-Generation
verbindlich bleibt. Wird RC4 ausdrücklich auf den nachgewiesenen Order-Kern
begrenzt, ist `v0.5.0-rc.4` konsistenter.

**Entscheidung dieses Auftrags:** **keine endgültige Versionsfestlegung.**
Die Empfehlung allein reicht nicht; Q-12 und der P00-Scope müssen durch den
verantwortlichen Release-Owner bestätigt werden.

---

## 3. RC4-Modulscope

### 3.1 Vorgeschlagener verbindlicher Scope

- Order-API (`POST`, `GET`, `LIST`, `PATCH`)
- JWT-Owner-/Consumer-Isolation
- Statusmodell und Conditional Updates
- SQS-Worker, Batch-Fehler, DLQ/Redrive
- GSI2/GSI3/Recovery
- Privacy inspect/export/erase (intern, nicht öffentlich)
- Consumer-Isolation im Privacy-Pfad
- Terraform-Module und Module Builder `orders-service`
- RC3-kompatible Bodies ohne `orderType` (Default `generic`)

### 3.2 Nicht Bestandteil des nachgewiesenen Scopes

- Weitere produktive Handler außer `generic`
- HTTP-Idempotency-Key / API-Deduplizierung
- Migration von RC3-Bestandsdaten ohne `subjectId`
- P00 KMS/Secrets-Manager/Retention als Produktivbetrieb
- RIS-Integration
- Produktionsfreigabe

**Wichtig:** Die Nichtaufnahme von P00 und der Legacy-Migration ist ein
**Entscheidungsvorschlag**, keine bereits erteilte Scope-Reduktion. Ohne
ausdrückliche Autorisierung bleibt der RC4-Gesamtumfang offen.

---

## 4. P00-Scope — getrennte Ebenen

### A — Eigenständiges RC4-Modul

P00 KMS CMK, Secrets-Manager-Provider, Rotation und Retention sind **nicht**
im aktuellen Order-Modulcode implementiert. Für eine reine Code-/Modulfreigabe
können sie als Produktionsblocker dokumentiert werden; ob sie zum
Modul-Releaseumfang gehören, ist **nicht entschieden**.

**Status:** `OPEN` — Scope-/Release-Entscheidung erforderlich.

### B — Installation und Deployment

Der isolierte Teststack funktioniert mit einem temporären Env-Secret. Eine
dauerhafte Secret-/KMS-/Retention-Konfiguration fehlt. Ein produktives
Deployment-Gate ist damit nicht erfüllt.

**Status:** `PARTIAL` — Teststack ja, dauerhafte Konfiguration nein.

### C — Produktiver Betrieb

P00 ist für den produktiven Privacy-/Retention-Betrieb erforderlich:
Secret-Management/Rotation, KMS/CMK, Retention/TTL und Cancel-Retention sind
nicht implementiert. Zusätzlich sind SEC-06, Legacy-Migration und
Multi-Account-Reife offen.

**Status:** `BLOCKED` — keine Produktionsfreigabe.

**Keine stillschweigende Streichung:** P00 wird weder als erledigt noch als
vertraglich verschoben behandelt.

---

## 5. Release-Dossier

Erstellt:

`docs/release/RC4-MODULE-RELEASE-CANDIDATE.md`

Enthalten:

1. Version/Release-Identität
2. Modulscope
3. unterstützte Funktionen
4. API-/Integrationsverträge
5. Sicherheitsgrenzen
6. Testnachweise
7. Live-Verifikation
8. bekannte Einschränkungen
9. Terraform-Drift
10. RIS-Voraussetzungen
11. Produktionsblocker
12. Release-Gates
13. Go/No-Go-Entscheidung

---

## 6. Release Notes

`docs/RELEASE_NOTES.md` enthält jetzt einen klar markierten
**RC4 Module Candidate — NOT RELEASED**-Abschnitt mit:

- vorgeschlagenem Scope und Version-offen-Hinweis
- `generic` als einzigem produktiven Handler
- Legacy-404-Grenze
- HTTP-Idempotency-Key **nicht** im RC4-Vertrag
- Test-/Live-Nachweisen
- RIS-Einschränkungen
- ausdrücklichem Ausschluss einer Produktionsfreigabe

---

## 7. Terraform-Drift

Aus `MO-RC3-RC4-G3-LIVE-DEPLOY-01B.md`:

```text
0 to add, 2 to change, 0 to destroy
```

Betroffen:

```text
module.lambda.aws_lambda_function.handler
module.sqs_worker.aws_lambda_function.worker
```

Bewertung:

- Nur `source_code_hash`-Werte (`vW8nl…` → `FYTuDcz…`).
- Keine Struktur-, Key- oder Datenänderung.
- Keine Voraussetzung für die Modul-Codefreigabe.
- Nur Teststack-/Infrastruktur-Reconciliation.
- Kein Terraform Apply in diesem Auftrag.

---

## 8. RIS-Integration

Voraussetzungen für einen späteren RIS-Kandidaten:

1. RC4-Commit/Tag verbindlich pinnen (nicht `1dbb0cb`).
2. RC4-Consumer-Vertrag gegen den Pin testen.
3. Owner-/Consumer- und Legacy-Semantik abstimmen.
4. Privacy-Scope/Secret-Betrieb für RIS klären.

Aktueller Stand: **RIS NO-GO**, da kein RC4-Pin und keine Consumer-Abnahme
vorliegen. `1dbb0cb` ist RC3-code-identisch.

---

## 9. Neue Gate-Matrix

| Anforderung | Vertragsquelle | Implementierung | Testnachweis | RC4-Pflicht? | Status |
|---|---|---|---|---|---|
| Release-Label/-Version | Q-12; `version_matrix.py` | offen; kein RC4-Release | — | JA | **OPEN** |
| Modulscope/P00 | P00-Plan; G1 | P00 nicht implementiert, keine autorisierte Reduktion | — | OFFEN | **OPEN** |
| Module Builder/orders-service | Modulvertrag | 7 Module stabil | 128 PASS | JA | **PASS** |
| Order-API/Statusmodell | `api/endpoints.md` | implementiert | 345 + 32 PASS | JA | **PASS** |
| Owner/Consumer-Isolation | P02H/Identity | implementiert | Live VERIFIED | JA | **PASS** |
| SQS/Worker/DLQ | P02C/B1 | implementiert | Live PASS | JA | **PASS** |
| GSI3/Recovery | P02I/B1 | implementiert | Live PASS | JA | **PASS** |
| Privacy inspect/export/erase | P02/B2 | implementiert | 14 PASS, 1 SKIP | JA, soweit Scope | **PARTIAL** |
| Consumer-Isolation | P02B/B2 X12 | implementiert | Live PASS | JA | **PASS** |
| RC3/RC4-Kompatibilität | G2/B1 | implementiert | Live PASS begrenzt | JA | **PASS** |
| Legacy-Migration | P02A/API | 404, keine Migration | lokal/live | OFFEN | **OPEN** |
| HTTP-Idempotency-Key | API/phase2 | Worker-Idempotenz; kein HTTP-Key | Worker-Tests | NEIN | **NOT REQUIRED FOR RC4** |
| SEC-06 | 11A/12A-1/ADR | V2 PROPOSED | 48 Installer-Tests | Deployment/Produktion | **OPEN** |
| P00 KMS/Secrets/Retention | P00 | nicht implementiert | keine P00-Tests | OFFEN | **OPEN** |
| Handler-Registry | P02E | `generic` only | Registry-/Worker-Tests | Nur `generic` | **PASS** |
| Terraform-Drift | DEPLOY-01B | 0 add / 2 change | Plan read-only | NEIN für Modul | **PARTIAL** |
| RIS-Pin/Consumer | Release Notes/RIS | `1dbb0cb`; kein RC4 | historisch | Für C | **BLOCKED** |
| CI/CD/Main-Gate | 13A/directAWSGit | kein RC4-Gate | lokal only | Für C/D | **BLOCKED** |

---

## 10. Go-/No-Go-Entscheidungen

### A — RC4-Modul

**CONDITIONAL GO.**

Bedingungen:

1. Q-12-Version entscheiden.
2. P00-Scope autorisieren oder P00 implementieren.
3. RC4-Gate-/Dossier-Freigabe durch den Release-Owner.
4. Terraform-Drift-Entscheidung dokumentieren.

Bei verbindlichem P00-Scope: **NO-GO** bis P00 umgesetzt ist.

### B — RC4-Teststack

**GO.**

Der isolierte Teststack ist verifiziert; Cleanup/Rückbau ist nachgewiesen.
X13 bleibt SKIP.

### C — RIS-Integration

**NO-GO.**

Kein RC4-Pin, keine RC4-Consumer-Abnahme, RIS bleibt auf RC3 `1dbb0cb`.

### D — Produktion

**NO-GO.**

P00 KMS/Secrets/Retention, SEC-06, Retention, Legacy-Migration,
Multi-Account-Reife und CI/CD-Gates sind offen.

---

## 11. Minimaler Maßnahmenplan

| # | Mangel | Quelle | Minimaländerung | Dateien | Test | Größe | Abhängigkeit |
|---|---|---|---|---|---|---|---|
| 1 | Version offen | Q-12 | Release-Owner entscheidet Label; Mapping dokumentieren | `docs/release/*`, `docs/RELEASE_NOTES.md`, `version_matrix.py` | Doku-/Mapping-Test | S | Governance |
| 2 | P00-Scope offen | P00/G1 | P00 in Scope nehmen oder Reduktion autorisieren | `docs/reports/MO-RC4-P00-*` | Scope-Review | M/L | 1 |
| 3 | Keine formale RC4-Gate-Freigabe | P-14 | Dossier/Gates vom Release-Owner freigeben | `docs/release/*` | Gate-Review | S | 1,2 |
| 4 | Terraform-Drift | DEPLOY-01B | Reconciliation separat entscheiden | `docs/reports/*` | read-only Plan | S | Betrieb |
| 5 | Legacy-404 | P02A/API | Grenze in Notes dokumentieren oder Migration entscheiden | Release Notes | Contract-Review | S | 1 |
| 6 | RIS-Pin | Release Notes | RC4-Pin + Consumer-Test | RIS separat | RIS-Tests | M | 1,3 |
| 7 | SEC-06 | ADR/12A-1 | V2 entscheiden/implementieren oder Deployment sperren | `installer/core/*`, ADR | V2-01…16 | M/L | Governance |
| 8 | P00 produktiv | P00 | KMS/Secrets/Retention/Rotation | Lambda/Terraform/Policy | P00-Tests | L | 2 |
| 9 | CI/CD/Main | 13A/directAWSGit | Auto-Apply-Risiko schließen | CI/Policy | Pipeline-/Policy-Test | M | Governance |

Nicht aufgenommen: neue Handler, neue Privacy-Route, neue Architekturphase,
HTTP-Idempotency-Key ohne Vertrag.

---

## 12. Git / Evidence

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor Analyse | `614d06a4177bcbfb0ece484cebb8ddc03acac67f` |
| Working Tree vor Analyse | CLEAN |
| Lokale Tests | 1.174 PASS |
| B2 Live | 14 PASS, 1 SKIP |
| AWS-Mutationen | keine |
| Terraform Apply | keiner |
| RIS-Änderung | keine |
| Release-Tag/Release | keiner |

---

## 13. Offene Fragen und Risiken

1. Ist P00 verbindlich im RC4-Modulscope?
2. Gilt `v0.5.0-rc.4` oder `v0.6.0-rc.1`?
3. Wird die Legacy-404-Grenze akzeptiert oder eine Migration gefordert?
4. Wird SEC-06 als Deployment-Gate vor RC4 verlangt?
5. Wer schließt das `directAWSGit`-Auto-Apply-Risiko?
6. Wann wird RIS auf einen RC4-Pin umgestellt?
7. Wird die Teststack-Drift vor einer späteren Infrastrukturmaßnahme
   angeglichen?

---

## 14. Abschlussstatus

```text
RC4 MODULE RELEASE CONDITIONALLY READY
```

- **RC4-Modul:** CONDITIONAL GO
- **RC4-Teststack:** GO
- **RIS-Integration:** NO-GO
- **Produktion:** NO-GO

**STOP — keine automatische Hochstufung, kein Release-Tag, keine
Veröffentlichung, keine RIS-Integration, kein Push/Merge.**

---

## 15. Commits / Working Tree

| Feld | Wert |
|---|---|
| Dossier-/Release-Notes-Commit | `21638bc43793937bda49ba85ec939cc406c26837` |
| Entscheidungsbericht-Commit | `48948a80f91a436cf2e75a34326c4d3868f1aa5b` |
| Working Tree nach Commit | CLEAN |

Keine Produkt-, Test-, Terraform-, AWS- oder RIS-Änderung.
