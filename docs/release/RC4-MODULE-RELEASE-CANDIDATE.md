# RC4 Module Release Candidate — Dossier

**Status:** **APPROVED FOR RELEASE — v0.6.0-rc.1**
**Release-Owner-Status:** **Q-12 APPROVED**
**Datum:** 2026-11-14
**Repository:** `maynowak/mays-order-aws`
**Branch:** `release/rc4-integration`
**Release-Commit:** durch den annotierten Tag `v0.6.0-rc.1` gebunden
**Deployment-Version im Teststack:** `0.2.0`
**Release-Label:** `v0.6.0-rc.1` — **APPROVED**

> Dieses Dossier dokumentiert die freigegebene Release-Entscheidung
> `v0.6.0-rc.1`. Es enthält keine zusätzliche Produktänderung und keine
> RIS-Integration. Die produktive Aktivierung bleibt separat gesperrt.

---

## 1. Version und Release-Identität

| Feld | Wert |
|---|---|
| RC4-Kandidat | Order-Modul + Teststack-Nachweise |
| Deployment-Version | `0.2.0` (Teststack `mays-orders-rc4-test`) |
| Release-Label | **`v0.6.0-rc.1`** — Q-12 APPROVED |
| Q-12-Verträglichkeit | Neue RC4-Feature-Generation; Deployment-Version bleibt separat |
| Alternative | `v0.5.0-rc.4` wurde nicht gewählt |
| Module-Builder-Version | `0.1.0` (`module_builder/__init__.py`) |
| RIS-Pin | `1dbb0cb` (RC3-code-identisch) |
| Owner-Status | **Q-12 APPROVED — v0.6.0-rc.1** |

**Entscheidungsstand:** Q-12 ist für `v0.6.0-rc.1` **APPROVED**. Die
Komponentenversionen bleiben unabhängig: Installer `0.1.0`, Module Builder
`0.1.0`, Deployment/Teststack `0.2.0`. Die produktive Aktivierung ist nicht
Teil dieser Release-Freigabe.

---

## 2. Vorgeschlagener Modulscope

Dieser Scope ist ein **Entscheidungsvorschlag**, keine eigenmächtige
Scope-Reduktion.

### 2.1 Verbindlich vorgeschlagen

- Order-API: `POST /orders`, `GET /orders`, `GET /orders/{orderId}`,
  `PATCH /orders/{orderId}/status`
- JWT-Owner-/Consumer-Autorisierung
- Statusmodell und Conditional Updates
- SQS-Worker, Batch-Fehler, DLQ/Redrive
- GSI2/GSI3 und Recovery
- Privacy inspect/export/erase, interner Invoke
- Consumer-Isolation
- Terraform-Module und Module Builder
- RC3-kompatible Body-/Default-Verträge (ohne Bestandsmigration)

### 2.2 Nicht Bestandteil des nachgewiesenen RC4-Modulscopes

- Weitere fachliche Handler außer `generic`
- HTTP-Idempotency-Key / Client-Deduplizierung
- Migration von RC3-Bestandsdaten ohne `subjectId`
- P00 KMS/Secrets-Manager/Retention als Produktivbetrieb
- RIS-Integration
- Produktionsfreigabe

Die Nichtaufnahme von P00 und der Legacy-Migration ist **genehmigungspflichtig**
und darf nicht als bereits beschlossen gelten.

### 2.3 P00-Abgrenzung (Entscheidungsvorschlag)

| Ebene | Vorgeschlagene Behandlung | Verbleibende Pflicht |
|---|---|---|
| A — Eigenständiges RC4-Modul | P00 wird **nicht als erfüllt** ausgewiesen; der Kandidat ist auf den verifizierten Order-Kern begrenzt | Scope-Begrenzung ist dokumentiert; P00-Produktionsanforderungen bleiben separat |
| B — Installation/Deployment | Teststack nutzt temporäre Konfiguration; keine dauerhafte Secret-/KMS-Haltung | Secret-Provider, KMS, Retention und Deployment-Gates bleiben offen |
| C — Produktiver Betrieb | **Nicht freigegeben** | P00 P-01…P-09/P-15, SEC-06, Retention, Rotation, Multi-Account-Reife |

Es werden keine Sicherheitsanforderungen gestrichen. Die Release-Freigabe
behauptet **keine** P00-Produktionserfüllung; P00-G Retention und die
produktive Secret-/KMS-Aktivierung bleiben separat gesperrt.

---

## 3. Unterstützte Funktionen

- `generic` ist der einzige produktiv registrierte Handler
  (`lambda/src/order_handlers.py`).
- Namespaced `orderType` wird validiert; unbekannte Typen werden fail-closed
  abgelehnt, nicht als `generic` verarbeitet.
- Processing-Handler sind nur in Tests dynamisch registriert; die produktive
  Processing-Aktivierung ist nicht Teil des RC4-Nachweises.
- Privacy ist intern und nicht über eine öffentliche API-Route erreichbar.

---

## 4. API- und Integrationsverträge

| Vertrag | Quelle | Status |
|---|---|---|
| Vier Order-Routen, JWT | `api/endpoints.md`, `terraform/modules/api/main.tf` | PASS |
| Owner/Consumer bei GET/PATCH/LIST | `lambda/src/identity.py`, `order_service.py` | PASS |
| Legacy ohne Identität → 404 | `api/endpoints.md`, B1 live | PASS |
| `orderType` Default `generic` | `validation.py`, `order_handlers.py` | PASS |
| Privacy nur interner Invoke | `index.py`, B2 live | PASS |
| Kein HTTP-Idempotency-Key | `docs/phase2-async-order-ingest.md` | **nicht im RC4-Vertrag** |
| Module Builder `orders-service` | `MAYS-ORDERS-MODULE-CONTRACT-01.md` | PASS (7 Module) |

---

## 5. Sicherheitsgrenzen

- Owner = JWT-`sub`; Consumer = Issuer + Client.
- GET/PATCH/LIST fail-closed bei fehlender oder fremder Identität.
- Legacy ohne `subjectId`/`consumerId`: 404, keine Erfindung einer Identität.
- Privacy: internes Secret + IAM-Invoke; keine öffentliche Route.
- Consumer-Scope optional; B2 nutzt ihn explizit.
- Keine Secrets in Git/Report/State.
- AWS-owned DynamoDB-Verschlüsselung, SSE-SQS, SSE-S3; kein CMK.

**Produktionsgrenze:** P00 Secrets Manager/KMS/Retention und SEC-06 sind nicht
implementiert/entschieden.

---

## 6. Testnachweise

| Suite | Ergebnis |
|---|---:|
| Installer | **669 PASS** |
| Module Builder | **128 PASS** |
| Lambda | **345 PASS** |
| E2E lokal | **32 PASS** |
| **Gesamt** | **1.174 PASS** |
| B2 Live | **14 PASS, 1 SKIP** |

X13 ist ein SKIP (secret-absenter Stack nicht im selben Lauf reproduzierbar)
und wird nicht als PASS gewertet.

---

## 7. Live-Verifikation

| Nachweis | Ergebnis |
|---|---|
| RC4-Teststack Apply `0.1.0→0.2.0` | 2 create / 7 update / 0 delete / 0 replace |
| G3-FIX | deployed, `FYTuDcz…` |
| G3-LIVE-B1 | DLQ, GSI3, Kompatibilität PASS |
| Owner-/Consumer-Isolation | IDENTITY-01 PASS |
| Privacy B2 | 14 PASS, 1 SKIP |
| Cleanup/Rückbau | Tabelle/GSI3/Queues/Cognito 0, IAM/Secret/Env zurückgebaut |
| CodeSha | unverändert `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |

Keine Live-Tests wurden in diesem Dossier wiederholt.

---

## 8. Bekannte Einschränkungen

1. Release-Label: **`v0.6.0-rc.1` APPROVED**; Release-Artefakt/Tag wird durch diesen Release-Commit gebildet. P00-G Retention bleibt deaktiviert.
2. P00 KMS/Secrets/Retention nicht implementiert; Scope nicht formal entschieden.
3. SEC-06 Approval-Bindung offen.
4. Legacy-Bestand ohne Identität bleibt 404; keine Migration.
5. HTTP-Idempotency-Key nicht implementiert und nicht vertraglich gefordert.
6. Produktiv nur `generic`; keine weiteren Handler.
7. Terraform-Drift: zwei `source_code_hash`-Änderungen nicht angewendet.
8. RIS pinnt RC3-Stand `1dbb0cb`; keine RC4-Consumer-Abnahme.
9. Produktionsfreigabe bleibt ausdrücklich BLOCKED.

---

## 9. Terraform-Drift-Bewertung

Aus `MO-RC3-RC4-G3-LIVE-DEPLOY-01B.md`:

```text
0 to add, 2 to change, 0 to destroy
```

Betroffen:

```text
module.lambda.aws_lambda_function.handler
module.sqs_worker.aws_lambda_function.worker
```

Beide Änderungen sind `source_code_hash`-Reconciliation des bereits deployed
G3-FIX-Artefakts. Sie sind **keine Struktur-/Datenänderung** und für die
Modul-Codefreigabe nicht erforderlich. Ein Apply ist eine spätere
Teststack-/Infrastrukturmaßnahme; kein Apply in diesem Auftrag.

---

## 10. RIS-Integrationsvoraussetzungen

- RC4-Commit/Tag muss verbindlich gepinnt werden; `1dbb0cb` ist RC3.
- RC4-Consumer-Vertrag muss gegen den neuen Pin getestet werden.
- Owner-/Legacy-Semantik und Privacy-Scope müssen RIS-seitig abgestimmt werden.
- Keine RIS-Installation/-Änderung in diesem Auftrag.
- Solange diese Punkte offen sind: **RIS NO-GO**.

---

## 11. Produktionsblocker

- P00 KMS/Secrets/Retention/Rotation nicht implementiert.
- `PRIVACY_INTERNAL_SECRET` nur Env-basiert; kein dauerhafter Secret-Provider.
- SEC-06 Approval-Bindung nicht implementiert.
- Keine Retention/TTL; PITR-/Backup-Erasure-Frage offen.
- Legacy-Migration nicht entschieden.
- Multi-Account-/RIS-Produktionsreife nicht belegt.
- CI/CD- und Main-Release-Gates nicht abgeschlossen.
- `README`/Release-Gates führen Produktion weiterhin als **BLOCKED**.

---

## 12. Release-Gates

| Gate | Status | Evidenz |
|---|---|---|
| Lokale Tests | **PASS** | 1.174 PASS |
| G3-FIX | **PASS** | deployed/verified |
| G3-LIVE-B1 | **PASS** | DLQ/GSI3/Kompatibilität |
| Owner-Isolation | **PASS** | IDENTITY-01 |
| Privacy B2 | **PARTIAL** | 14 PASS, 1 SKIP |
| B2 Cleanup | **PASS** | 0/0/0/0, Rückbau |
| Terraform-Drift | **PARTIAL** | 0 add / 2 change, kein Apply |
| RC4-Version | **APPROVED** | `v0.6.0-rc.1`; Q-12 |
| P00-Scope | **OPEN** | Plan, keine Entscheidung |
| SEC-06 | **OPEN** | V2 PROPOSED |
| Legacy-Migration | **OPEN** | 404, keine Migration |
| RIS-Pin | **BLOCKED** | `1dbb0cb` (RC3) |
| Produktionsfreigabe | **BLOCKED** | P00/SEC-06/Retention |

---

## 13. Go-/No-Go-Entscheidung

| Bereich | Entscheidung |
|---|---|
| **RC4-Modul** | **APPROVED — v0.6.0-rc.1** — Code/Teststack belastbar; Release-Label Q-12 entschieden |
| **RC4-Teststack** | **GO** — isoliert verifiziert, Cleanup/Rückbau nachgewiesen |
| **RIS-Integration** | **NO-GO** — kein RC4-Pin/Consumer-Nachweis |
| **Produktion** | **NO-GO** — P00/SEC-06/Retention/CI-CD offen |

Die Release-Version ist entschieden. Produktion, RIS-Integration und
produktive Secret-/Retention-Aktivierung bleiben separat gesperrt.

### 13.1 Release-Owner-Entscheidungsvorlage

| Entscheidung | Vorgeschlagener Wert |
|---|---|
| Release-Version | `v0.6.0-rc.1` (APPROVED) |
| RC4-Modulscope | Verifizierter Order-Kern |
| P00 | Nicht als erfüllt ausgewiesen; Produktionsanforderungen bleiben |
| RIS-Integration | Nicht freigegeben |
| Produktion | Nicht freigegeben |
| Veröffentlichung | **Autorisiert** — Branch + annotierter Tag |

**Status:**

```text
RELEASE APPROVED — v0.6.0-rc.1
```

Die Release-Freigabe betrifft die Veröffentlichung des RC4-Branches und des
annotierten Tags. Sie ist **keine** Freigabe für Produktion, RIS-Integration
oder die Aktivierung von P00-G Retention.
