# MAYS-ORDERS-MODULE-USAGE-ASSESSMENT-01

**Dokumenttyp:** Bewertung „Mays-Orders als Modul" — Verwendungsmöglichkeiten, Aufwandsschätzung, Aufbau-Plan
**Datum:** 2026-10-17
**Baseline:** Remote main `3c87c7e` · Release `v0.5.0-rc.2`
**Methode:** Read-only Code-/Doku-Analyse (Terraform-Module, Lambda-Handler, Installer, RIS-KonsumNachweise)
**Klassifikation:** ASSESSMENT — keine Implementierung, keine AWS-Mutation

---

## 1. Executive Summary

Mays-Orders-AWS ist **strukturell näher an einem wiederverwendbaren Modul, als
der aktuelle RIS-Konsum vermuten lässt**: 11 Terraform-Kindmodule, konsequente
Namensableitung aus `project_name`, 19 Root-Variablen, 15 Outputs, und ein
Installer, der Parallelinstallationen (Workspace-Isolation, Collision-Preflight,
Policy Gate) bereits **in Produktion bewiesen** hat (Privacy-Testinstallation
lief parallel zum Hauptprojekt).

**Zwei echte Lücken** stehen der Wiederverwendung im Weg:

1. **Kein Tenant-Feld** im Order-Datensatz (von RIS GATE-6 selbst festgestellt:
   „Tenant-Feld serverseitig absent") — Multi-Consumer-Betrieb über eine
   gemeinsam genutzte Instanz ist ohne Isolation nicht vertretbar.
2. **Modul-Hygiene-Defizite:** `sqs`/`sqs_worker` haben keine eigenen
   variables/outputs (hart am Root verdrahtet); `cognito_backup`-Module sind
   bereits abschaltbar (gutes Vorbild).

Zudem konsumiert RIS die MO-DynamoDB-Tabelle **direkt** (eigene API frontet die
Tabelle) statt über die MO-API — ein Contract-Bypass, den jeder modulare Aufbau
beenden muss.

**Empfehlung (Kurzfassung):** Stufe 1 — MO als *deployable Unit* über den
bestehenden Installer productisieren (**2–4 PT**); Stufe 2 — Shared-Service-
Betrieb mit Tenant-Isolation und versioniertem API-Contract (**8–14 PT**);
Modul-Sourcing (S3) nur bei echtem Bedarf (**5–8 PT**).

## 2. Ist-Analyse: Modulreife (Evidence)

### 2.1 Struktur

| Baustein | Befund | Bewertung |
|---|---|---|
| Kindmodule | 11: dynamodb, iam, lambda, cognito, api, cloudtrail, monitoring, sqs, sqs_worker, cognito_backup(+automation) | breit, klar getrennt |
| Modul-Hygiene | core-Module mit eigenen variables.tf/outputs.tf (z. B. lambda 11 Var/4 Out, monitoring 17/8, api 6/5) | **gut** |
| Ausnahmen | `modules/sqs`, `modules/sqs_worker`: **0 eigene Variablen/Outputs** (Root-Verdrahtung) | **Refaktor nötig für S3** |
| Naming | Durchgehend aus `var.project_name` abgeleitet (Pool `${project}-users`, Table `${project}`, Rollen `${project}-handler-role`, Tags `Project=${project}`) | **sehr gut** — Parallelinstanzen kollisionsfrei möglich |
| Schalter | `enable_cognito_backup(_automation)`, `monitoring_enabled`, `dashboard_enabled`, `seed_example_data` | optionale Bestandteile vorhanden |
| Outputs | 15 (API-Endpoint, Pool-/Client-IDs, Table, IAM-Rollen, Lambda-ARNs) | Konsumenten-Integration vorbereitet |
| Installer | `--project-name` → Workspace-Isolation (S3-State je Projekt), Preflight-Gates, Collision-Preflight (`aws_project_collision`), Plan-Metadaten, `--guide` | **bewiesen** (privacy-test parallel betrieben und sauber abgebaut) |

### 2.2 Verhalten & Verträge

- **API-Contract** (dokumentiert, live verifiziert): `POST /orders` → 201 +
  `ord_*` + PENDING; `GET /orders/{id}`; `PATCH /orders/{id}/status`;
  6-Status-State-Machine mit definierten Cancellation-Pfaden; JWT auf allen
  Routen. Keine formale Versionierung des Contracts (noch).
- **Tenant-Isolation: nicht vorhanden.** Der Order-Datensatz hat kein
  Projekt-/Tenant-Feld; GSI1 (List) und GSI2 (Privacy/subjectId) kennen keine
  Consumer-Dimension. RIS musste Isolation deshalb selbst sicherstellen.
- **Privacy-Funktionen:** intern, invoke-only, Produktion **BLOCKED** (kein
  Secret-Management/Rotation) — für Konsumenten aktuell nicht verfügbar.
- **Status Quo RIS (Anti-Pattern, dokumentiert):** gepinnter MO-Clone, **lokaler
  State**, Default-Projektname, und ein eigener API-Layer mit **Direktzugriff
  auf die MO-Tabelle** (GATE-3/GATE-6) — genau das Muster, das den
  Kollisions-Incident verursachte und den Datensatz dem MO-Contract entzieht.

## 3. Verwendungsszenarien

### S1 — Deployable Unit über den Installer („eine Instanz pro Konsument")

Konsument deployt MO unter **eigenem Projektnamen** in eigenem Workspace via
unseren Installer; danach sein eigenes Stack-Modul **verbraucht die Outputs**
(API-Endpoint, Pool-ID, Table-Name).

- Stand: **technisch heute möglich** (Privacy-Test = bewiesener Blaupausen-Lauf).
- Grenzen: pro Konsument ein voller Stack (Kosten im Free-Tier vernachlässigbar,
  aber Betriebsaufwand je Instanz); keine Daten-Trennung nötig, da je Instanz
  eigene Tabelle/Pool existieren.
- Aufwand: **2–4 PT** (Productisierung, s. §4).

### S2 — Shared Service (eine MO-Instanz, viele Konsumenten via API)

MO läuft **einmal** als Backend-Service; Konsumenten rufen ausschließlich die
MO-API auf (JWT je Konsumenten-Service-Identität). Das ist das Zielbild für RIS.

- Voraussetzungen: **Tenant-Feld + Isolation** (Pflicht), versionierter
  API-Contract, Service-Auth für Konsumenten (Maschinen-Identität statt User-
  Login), Multi-Consumer-Monitoring.
- RIS-seitig: Umstellung des Adapters von Tabellen-Direktzugriff auf MO-API.
- Aufwand: **8–14 PT** gesamt (s. §4).

### S3 — Terraform-Modul-Sourcing (Kindmodule im Konsumenten-Stack)

Konsumenten sourcen einzelne MO-Kindmodule (git source, getaggte Version) in
ihrem eigenen Root-Stack.

- Voraussetzungen: `sqs`/`sqs_worker`-Refactoring, Modul-READMEs/Beispiele,
  Versions-Tags je Modul, Test-Harness.
- Risiko: Kopplung an MO-Interna; Updates schwer kontrollierbar. Nur sinnvoll,
  wenn Konsumenten MO-Ressourcen in eigene Stacks integrieren müssen.
- Aufwand: **5–8 PT** (s. §4).

### S4 — Status Quo RIS (pinned Clone, lokaler State, Tabellen-Direktzugriff)

**Nicht empfohlen.** Dokumentiert im Handoff-Report
(`MAYS-ORDERS-RIS-HANDOFF-MO-INSTALLATION-01.md`, Optionen A–C zur Überführung).
Sollte durch S1 oder S2 ersetzt werden.

## 4. Aufwandsschätzung (Personen-Tage, PT)

### Stufe 1 — S1 productisieren: **2–4 PT**

| # | Work-Item | PT | Quelle/Evidence |
|---|---|---|---|
| 1.1 | Konsumenten-Guide (Deployment via Installer, Parameter, Outputs-Verbrauch, Auth-Bootstrap, eigene Backup-Entscheidung) | 0,5–1 | `docs/INSTALLER_GUIDE.md` erweitern |
| 1.2 | Instanz-Smoke-E2E als Checkliste/Script (Login→Order→Status→Cleanup) aus bestehender E2E ableiten | 0,5–1 | `tests/test_e2e_async_order.py` existiert |
| 1.3 | Release-/Modul-Versionierung dokumentieren (Tag je MO-Stand, Konsument pinnst Tag; `--deployment-version` je Konsument) | 0,5 | Plan-Metadaten vorhanden |
| 1.4 | Policy-Gate-Regelwerk je Konsumenten-Projekt prüfen/ergänzen | 0,5–1 | `terraform/policy/` vorhanden |

### Stufe 2 — S2 Shared Service: **8–14 PT** (inkl. RIS-Seite)

| # | Work-Item | PT | Anmerkung |
|---|---|---|---|
| 2.1 | **Tenant-Feld** im Order-Datensatz (`tenantId` o. `projectId`), Validierung, GSI-Anpassung, Migration bestehender Daten | 2–3 | größter Einzelposten; GATE-6-Fund bestätigt die Lücke |
| 2.2 | **Isolation durchsetzen**: List/Get/Patch/Privacy am Tenant scopen (inkl. Tests: Cross-Tenant-Zugriff muss fail-closed) | 1–2 | baut auf 2.1 auf |
| 2.3 | **API-Contract-Versionierung** (Version-Header/Pfad + Changelog + Tests; `api/endpoints.md` als SoT fortführen) | 1–2 | Konsumenten-Update-Sicherheit |
| 2.4 | **Service-Auth** für Konsumenten (Cognito-Client-Rolle/Maschinen-Identität je Konsument; kein User-Login im Service-Pfad) | 1–2 | Security-SoT `security/` erweitern |
| 2.5 | Multi-Consumer-Ops: Monitoring-Dimension `tenantId`, Alarm-Politik, Kosten-Zuordnung via Tags | 1–2 | `monitoring`-Modul ist vorbereitet |
| 2.6 | RIS-Seite: Adapter von Tabellen-Direktzugriff auf **MO-API** umstellen + Tests | 2–3 | RIS-Budget; beendet den Contract-Bypass |

### Optional S3 — Modul-Sourcing: **5–8 PT** (nur bei Bedarf)

| # | Work-Item | PT |
|---|---|---|
| 3.1 | `sqs`/`sqs_worker`: eigene variables/outputs, Entkopplung vom Root | 2–3 |
| 3.2 | Modul-READMEs + `examples/` je Modul (dynamodb/cognito/api zuerst) | 1–2 |
| 3.3 | Versions-Tags je Modul-Stand + git-Source-Pinning-Doku | 0,5 |
| 3.4 | Modul-Test-Harness (validate + Mini-Plan je Modul in CI) | 1–2 |

### Separate Blocker-Position (nur falls ein Konsument Privacy benötigt)

**Produktives Secret-Management/Rotation** (Secrets Manager + IAM + Runtime-
Retrieval + E2E) bleibt **BLOCKED** und ist **nicht Bestandteil der Schätzung
für S1/S2-Kern**; Erfahrungswert aus Roadmap: **5–8 PT** extra.

## 5. Aufbau-Empfehlung (Zielarchitektur)

```text
Stufe 1 (jetzt):  Konsument A ──installer(project=A)──> eigene MO-Instanz A
                  Konsument B ──installer(project=B)──> eigene MO-Instanz B
                  (Workspace-Isolation + Collision-Preflight, bewiesen)

Stufe 2 (Ziel):   Konsumenten (RIS, …) ──API (v1, JWT je Service-Identität)──>
                  EINE MO-Service-Instanz (Tenant-isoliert, versionierter Contract)
                  ── niemals Tabellen-Direktzugriff ──

Modulgrenzen:     MO-API = einzige verbindliche Schnittstelle
                  Terraform-Kindmodule = Implementierungsdetail
                  Outputs (api_gateway_endpoint, pool/client) = Integrationsvertrag
```

**Konstruktionsprinzipien:**

1. **Contract-First:** `api/endpoints.md` + State-Machine bleiben Single Source
   of Truth; Änderungen nur mit Versionssprung + Tests.
2. **Tenant-Pflicht ab Stufe 2:** kein Datensatz ohne `tenantId`; jede Query am
   Tenant gescoped; Cross-Tenant-Zugriff fail-closed (gleiche Disziplin wie
   Privacy-Autorisierung).
3. **Namen bleiben projektabgeleitet** (`${project}-*`) — zusammen mit dem
   Collision-Preflight ist die Instanz-Zuordnung dann eindeutig.
4. **Installer als einziger Lebenszyklus-Weg:** Preflight → Plan → Policy Gate →
   Freigabe → Deploy; kein Konsument deployt MO-Teile manuell.
5. **Privacy bleibt intern/BLOCKED**, bis Secret-Management umgesetzt ist —
   unabhängig vom Modul-Status.

## 6. Risiken und Voraussetzungen

| Risiko | Bewertung | Mitigation |
|---|---|---|
| RIS-Direktzugriff auf die Tabelle läuft weiter | hoch (Contract-Bypass, Schema-Kopplung) | 2.6 zügig; MO-API als einzige Schnittstelle vertraglich festlegen |
| Tenant-Migration bestehender MO-Daten | mittel | Offline-Migrationsskript + Doppel-Write-Phase oder Snapshot-Wiederherstellung |
| Contract-Breaking durch MO-Weiterentwicklung | mittel | 2.3 (Versionierung) vor weiteren Feature-Releases |
| Kosten je Extra-Instanz (S1) | gering | serverless, Free-Tier; Monitoring-Alarme prüfen |
| Privacy-Aktivierungsdruck durch Konsumenten | mittel | BLOCKED-Status dokumentiert; Secret-Management als separates Gate |
| Modul-Kopplung bei S3 | gering–mittel | nur mit Versions-Tags + Test-Harness anbieten |

## 7. Empfehlung & Roadmap

1. **Sofort (0 PT):** S4 (RIS-Status-quo) als veraltet erklären — Handoff-Report
   ist ausgeliefert; RIS-Entscheidung zu Option A/B dort anhängig.
2. **Stufe 1 (2–4 PT):** MO als deployable Unit productisieren
   (Konsumenten-Guide + Smoke-Checkliste + Versionierungs-Disziplin).
   Damit ist „eine saubere Instanz je Konsument" sofort verfügbar.
3. **Stufe 2 (8–14 PT):** Shared Service mit Tenant-Isolation — der eigentliche
   „Modul"-Wert für RIS; Reihenfolge: 2.1/2.2 (Tenant) → 2.3 (Versionierung)
   → 2.4 (Service-Auth) → 2.5 (Ops) → parallel RIS 2.6.
4. **S3 (5–8 PT):** nur auf konkrete Anfrage; sqs/sqs_worker-Refactoring ist
   dann der erste Schritt.
5. **Privacy-Produktivbetrieb:** separat freizugeben, 5–8 PT, bleibt BLOCKED.

## 8. Evidence-Anhang

- Modulstruktur/Naming: `terraform/main.tf` (11 Module), `terraform/variables.tf`
  (19 Var.), `terraform/outputs.tf` (15 Out.), `modules/cognito/main.tf:9,29,33`,
  `modules/dynamodb/main.tf:12,83`, `modules/iam/main.tf:67–74`
- Modul-Hygiene-Defizit: `modules/sqs/`, `modules/sqs_worker/` (0 Var/0 Out)
- Tenant-Lücke: kein `tenant`-Match in `lambda/src/*.py`; RIS GATE-6:
  „Tenant-Feld serverseitig absent (Isolation unsererseits)"
- Installer-Beweis für Parallelinstanzen: Workspaces `mays-orders-privacy-test`
  (aufgebaut, E2E-verifiziert, abgebaut; Reports MAYS-ORDERS-PRIVACY-*) und
  `mays-order-par` (Workspace existierte)
- RIS-Konsum & Incident: `GATE-3-MO-LIVE-INSTALLATION-AND-VERIFICATION-01.md`,
  `GATE-6-ORDERS-PORT-REAL-MAYS-ORDERS-ADAPTER-01.md`,
  `MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01.md`,
  `MAYS-ORDERS-RIS-HANDOFF-MO-INSTALLATION-01.md`
- Privacy-BLOCKED: `docs/release/RELEASE-v0.5.0-rc.2.md` §11–12

---

*Keine AWS-Mutationen, keine Secrets, keine State-Inhalte. Aufwandsschätzung ist
eine engineering-Einschätzung auf Basis der referenzierten Evidence; keine Zusagen.*
