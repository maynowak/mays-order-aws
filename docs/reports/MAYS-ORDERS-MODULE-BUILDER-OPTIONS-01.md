# MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01

**Dokumenttyp:** Nachtrags-Assessment „Mays-Orders als Modul-Builder/Baukasten anbieten"
**Datum:** 2026-10-17
**Baseline:** Remote main `f7dcceb` · folgt auf `MAYS-ORDERS-MODULE-USAGE-ASSESSMENT-01.md`
**Methode:** Read-only Portabilitäts-Verifizierung an `terraform/modules/`
**Status:** DECISION PENDING — **keine Umsetzung** ohne Freigabe (User-Bewertung: „Angebote klingen gut", Stop)

## 1. Verifizierte Portabilitäts-Befunde (Code-Evidence)

| Prüfling | Befund | Baukasten-Konsequenz |
|---|---|---|
| `modules/lambda/main.tf:13–14` | Artifact per **`var.filename`** injiziert (`filename = var.filename`, `source_code_hash = filebase64sha256(var.filename)`) | ✓ portabel — Konsument liefert eigenes Zip |
| `modules/cognito_backup/main.tf` | Artifact-Pfad **`${path.root}/../lambda/dist/cognito_backup.zip` hardcodiert** | ✗ bricht bei externem Modul-Sourcing → Fix per `var.filename` (Muster lambda), **0,5 PT** |
| `modules/sqs`, `modules/sqs_worker` | **0 eigene Variablen / 0 Outputs** (Root-Verdrahtung) | ✗ Refactoring nötig, **2–3 PT** |
| Kernmodule (dynamodb, cognito, api, iam, lambda, monitoring) | eigene variables/outputs, Naming aus `project_name` | ✓ mit Doku-Arbeit katalogreif |

## 2. Angebotsstufen („Modul-Builder")

### Stufe A — Ganz-Stack als EIN Meta-Modul · **2–3 PT**
Konsument sourct das Root als Modul (`git::https://github.com/maynowak/mays-order-aws.git//terraform?ref=vX`)
mit Feature-Toggles; erhält kompletten Order-Service unter eigenem `project_name`.
Work: Toggles konsolidieren (`enable_api`, `enable_sqs`, `enable_monitoring`,
`enable_backup` — `enable_cognito_backup(_automation)`/`monitoring_enabled` existieren
bereits), Provider-/Backend-Doku für Konsumenten-Root (Backend-Block gilt nur im
Root des Konsumenten), README + 1 Example.
**Für wen:** „Ich will einfach Order-Processing haben." — Sofort einsetzbar für RIS-Entlastung.

### Stufe B — Echter Baukasten (Modul-Katalog) · **7–10 PT** (MVP 5 Kernmodule: 5–7 PT)
Einzelmodule frei kombinierbar via Git-Tags (`?ref=`), Konsument verdrahtet
Outputs→Inputs selbst. Work:
1. sqs/sqs_worker-Refactoring (2–3 PT)
2. cognito_backup-Pfad-Fix (0,5 PT)
3. README + `examples/` je Modul (Kern-5 ≈ 2,5 PT; Rest ≈ 2 PT)
4. Interface-Doku Outputs→Inputs (0,5–1 PT)
5. Versions-Tags + Modul-CHANGELOG (0,5–1 PT)
6. Test-Harness je Example — validate + Mini-Plan (1–2 PT)
**Für wen:** Teams, die eigene Stacks aus MO-Bausteinen komponieren.

### Stufe C — Registry-Produktisierung · **3–5 PT + laufende Pflege**
Private Terraform Registry / CI-Publishing, SemVer je Modul, Support- und
Kompatibilitätspolitik. Erst sinnvoll ab **mehreren** konsumierenden Teams.

### Bonus-Fix (hilft überall) · **0,5 PT**
Optionales S3-Artifact-Sourcing für Lambda (`s3_bucket`/`s3_key` alternativ zu
`filename`) — macht alle Module vom lokalen Zip-Pfad unabhängig.

## 3. Governance-Regel (Bestandteil jedes Angebots)

Die RIS-Lektion wird Vertragsbestandteil:
- **MO-API = die Schnittstelle** für Order-Funktionalität (versioniert, tenant-isoliert —
  siehe MODULE-USAGE-ASSESSMENT S2);
- bei reinen Infra-Modulen (z. B. Cognito, DynamoDB): **Outputs = die Schnittstelle**;
- **Tabellen-Direktzugriffe durch Konsumenten sind ausgeschlossen** (GATE-6-Bypass
  darf sich nicht wiederholen);
- Installer bleibt der einzige Lebenszyklus-Weg für Ganz-Stack-Instanzen (Stufe A).

## 4. Einordnung

- Stufe B ist die ausgebaute Form von **S3 (Modul-Sourcing)** aus dem
  MODULE-USAGE-ASSESSMENT (dort 5–8 PT; hier präzisiert inkl. Katalog-Doku: 7–10 PT).
- Stufe A entspricht **S1 (Deployable Unit)**, aber als sourcebares Modul statt
  Repo-Klon — die saubere Antwort auf das RIS-Anti-Pattern (pinned Clone + lokaler State).
- Reihenfolge-Empfehlung: **A zuerst** (2–3 PT, sofortiger Nutzen), **B als MVP-Katalog**
  danach, **C nur beiMulti-Team-Bedarf**.

## 5. Entscheidung

**PENDING.** User-Feedback 2026-10-17: „die Angebote klingen gut" + „stop" —
kein Start ohne explizite Freigabe. Nächster Schritt nach Freigabe: Stufe A
(Toggles + Konsumenten-Doku + Example), danach Stufe-B-MVP (5 Kernmodule).

---

*Keine AWS-Mutationen, keine Implementierung. Alle Befunde code-verifiziert
(read-only); Aufwände sind Engineering-Einschätzungen.*
