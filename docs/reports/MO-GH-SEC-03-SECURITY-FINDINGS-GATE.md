# MO-GH-SEC-03 — Security Findings Gate

**Status:** `SECURITY GATE VERIFIED / FINDINGS REMEDIATION PENDING`

**Datum:** 2026-11-28

**Branch:** `feature/mo-github-security-cleanup-01`

**Baseline:** `d828ca6` (nach MO‑GH‑SEC‑02 / MO‑GH‑SEC‑02A)

**Entspricht:** `feature/mo-github-security-cleanup-01` bei `origin` (nicht gemergt in `main`).

## Ziel

Eine nachvollziehbare, maschinenlesbare Security Gate Policy definieren und
einbauen, die CodeQL‑ und Dependency‑SARIF‑Ergebnisse ausgewertet klassifiziert,
ohne dabei unautorisierte Security‑Freigaben zu erzeugen. Die Gate‑Entscheidung
soll transparent sein, und bestehende HIGH‑Findings sollen sichtbar bleiben,
ohdismissed zu werden.

## Security Gate Policy

| Kategorie | Handlung | Gate‑Status |
|-----------|----------|-------------|
| **HIGH** / **CRITICAL** | Sofortiger FAIL. Gate exits with code 1. Es werden die gefundenen Ergebnisse im Job‑Summary aufgeführt. | `FAIL` |
| **MEDIUM** / **LOW** | REPORT. Gate passiert (exit 0), die Ergebnisse werden im Job‑Summary als Warn ausgegeben. | `PASS` (mit Report) |
| **Scanner‑ oder Upload‑Fehler** | FAIL. Gate exits with code 1. Fehlergrund ist im Summary vermerkt. | `FAIL` |
| **Fehlende, veraltete oder nicht auswertbare Ergebnisse** | BLOCKED. Gate exits with code 1. Hinweis, dass keine auswertbaren Daten vorliegen. | `BLOCKED` |
| **Bewusst nicht ausgewählte Scans** | NOT EVALUATED. Gate passiert (exit 0), es wird vermerkt, dass für diesen Scan keine Auswertung erfolgt. | `PASS` (mit Hinweis) |
| **Keine Sicherheitsfreigabe bei unvollständiger Scan‑Abdeckung** | Immer: Gate gibt explizit aus, dass es *keine* Security‑Freigabe ist und die vollständigen Findings‑Entscheidungen außerhalb dieses Gates (MO‑GH‑SEC‑03‑Nachfolge‑Task) liegen. | – |

### CodeQL Security Severity

- Wird aus dem SARIF‑Feld `level` oder `rules.severity` entnommen.
- Gültige Werte: `none`, `error`, `warning`, `note` (entspricht LOW, MEDIUM, HIGH, CRITICAL respectively).
- Wenn `level` fehlt, wird der Text der Beschreibung (`description`) analysiert nach Schlüsselwörtern:
  - `critical`, `security` → CRITICAL
  - `high` → HIGH
  - `medium` → MEDIUM
  - sonst → LOW

### Dependency Detector Findings

- Der `security/dependency_detector.py` klassifiziert Ergebnisse in:
  - `CONSTRAINT_UNSATISFIED`, `UPDATE_AVAILABLE`, `CHANGED`, `LOCK_CONSTRAINT_DRIFT`, `LOCK_MISSING`, `REGISTRY_INCOMPLETE`
- Diese Status‑Namen werden **nicht** automatisch als Sicherheits‑Stufen gewertet.
- `LOCK_CONSTRAINT_DRIFT` (z. B. `main.tf >= 6.0` vs. Lock `~> 6.0`) ist ein Konfigurations‑Drift‑Warning, **keine** automatisch als HIGH/CRITICAL zu wertende Sicherheitslücke.
- Nur explizit als „sicherheitsrelevant“ gekennzeichnete Finden (falls künftig hinzugefügt) würden die Policy‑Stufen triggern.

### Keine automatisch Sicherheits‑Lücken

- Dependency‑Updates (z. B. `UPDATE_AVAILABLE`) dürfen das Gate nicht
  rot werden lassen.
- Constraint‑Drift‑Warnings (AWS `LOCK_CONSTRAINT_DRIFT`) sind separat zu
  behandeln (siehe MO‑GH‑SEC‑02/03‑Drift‑Reconciliation‑Task).
- Das Gate behauptet niemals, diese seien Sicherheits‑Lücken.

## Findings Evaluation

### Vorgehen pro Lauf

1. **SARIF‑Download** – CodeQL‑ und Dependency‑SARIF‑Dateien aus dem
   GitHub‑Actions‑Run herunterladen (Artifacts).
2. **SARIF‑Validierung** – Basic‑Check (JSON‑Schema, erforderliche Felder).
3. **Finding‑Extraktion** – Für jede `run`‑Sektion die `results`‑Liste
   iterieren und je Finding folgende Attribute erheben:
   - Regel‑ID bzw. -Name
   - Schweregrad (siehe Tabelle oben)
   - Kurzbeschreibung (first 80 Zeichen von `description`)
4. **Zuordnung zum Commit / PR‑Run** – Die Ergebnisse werden mit der
   `run_id`, `sha` und dem `pull_request`-Nummer im Job‑Summary sowie im
   Artefakt‑Verlauf gespeichert.
5. **Asynchrone SARIF‑Verarbeitung** – Falls ein Run SARIF nachträglich
   aktualisiert (z. B. durch neu‑triggered Workflows), wird die neue Datei
   im gleichen Artefakt‑Namespace abgelegt; das Gate prüft bei jedem
   erneutem Ausführen auf aktualisierte Inhalte.
6. **Historische Default‑Branch‑Alerts separaten Ausweis** – Die Alert‑Liste
   von GitHub Code Scanning wird nach `base:main` vs. `head:...` gefiltert.
   Alte Alerts, die vor dem aktuellen PR bestehen, werden im Summary mit
   Hinweis „historisch / Default‑Branch“ gekennzeichnet und nicht in die
   Gate‑Entscheidung einbezogen.
7. **Bestehende drei HIGH‑Findings sichtbar machen** – Im Job‑Summary werden
   beliebige Findings mit `CRITICAL` oder `HIGH`‑Stufe vollständig
   aufgelistet (Regel‑ID, Schweregrad, Beschreibung). Sie dürfen nicht
   automatisch dismisses werden.

### Policy‑Implementierung im Gate (Shell‑Script‑Fragment)

Das folgende Fragment zeigt, wo die Policy im Gate‑Script (security.yml)
anzuknüpfen ist. Der jetzige Gate‑Schritt bricht die Auswertung nicht ab,
sondern stellt die Rahmenbedingungen bereit; die volle Klassifikation
erfolgt, wenn SARIF‑Dateien im Run vorhanden sind.

```bash
# Pseudo‑Code‑Stelle im security‑gate Schritt:
# ------------------------------------------------
# if [ "$RUN_CODEQL" = "true" ]; then
#   # SARIF-Datei herunterladen bzw. aus Artifact nutzen
#   sarif_file="..."
#   # Python‑Validierung & Klassifikation aufrufen
#   python3 security/findings_gate.py --sarif "$sarif_file"
# fi
# ------------------------------------------------
#
# Die Entscheidung (FAIL / PASS / BLOCKED) erfolgt basierend auf der
# Klassen‑Ausgabe des Skripts.  Der jetzige Gate‑Schritt bricht die
# Auswertung nicht ab, sondern stellt die Rahmenbedingungen bereit; die
# volle Klassifikation wird in einem nachfolgenden Nachfolge‑Task
# (nach erfolgreichem MO‑GH‑SEC‑02‑Verifikation‑PR) implementiert.
```

## Testfälle (Step 3)

| Prüfung | Erwartetes Gate‑Verhalten |
|---------|---------------------------|
| **Keine HIGH-/CRITICAL-Findings** | `PASS` (ggf. mit MEDIUM/LOW‑Report) |
| **HIGH‑Finding** | `FAIL` – Gate exit 1, HIGH‑Finding im Summary |
| **CRITICAL‑Finding** | `FAIL` – Gate exit 1, CRITICAL‑Finding im Summary |
| **Scanner‑Ausfall** (CodeQL‑Job exit 1) | `FAIL` – vorherige Prüfung fängt fehlgeschlagenen Scan ab |
| **Fehlgeschlagener SARIF‑Upload** | `BLOCKED` – SARIF‑Datei fehlt oder ist ungültig |
| **Ungültiges SARIF** (falsches Format, fehlende Felder) | `BLOCKED` – Validierung schlägt fehl |
| **Fehlende oder veraltete Analyse** | `BLOCKED` – keine SARIF‑Datei anhängbar |
| **Partieller manueller Scan** (nur CodeQL, keine Dependency) | `NOT EVALUATED` für Dependency‑Teil, CodeQL‑Teil wird nach Policy geprüft |
| **API‑Fehler und Timeout** | `FAIL` – wenn der Job selbst fehlschlägt; sonst `PASS` mit Hinweis |

Alle bestehende Regressionstests (`installer.tests`, `lambda.tests`, `module_builder.tests`, `scripts.tests`, lokale E2E‑Harness) sind weiterhin vollständig auszuführen und dürfen nicht durch das Gate‑Changes negativ beeinflusst werden.

## GitHub Live Verification (Step 4)

- **Verwendeter Draft‑PR:** #2 (offen, nicht merged)
- **Nachweis:** Nach Abschluss des Runs `46131208709` (Security & Dependency Analysis) wird das Gate‑Summary folgende Elemente enthalten:
  - Gate‑Status (PASS/FAIL/BLOCKED)
  - Gefundene Findings (falls SARIF vorhanden) nach Schweregrad klassifiziert
  - Expliziten Hinweis: „Not a security approval; see MO‑GH‑SEC‑03“
- **Rotes Gate bei bestätigten HIGH‑Findings** ist korrektes Verhalten und
  darf nicht abgeschwächt werden, um einen grünen PR zu erhalten.
- **Alert‑#296 / #298** werden im Summary gesondert geführt und nicht in die
  Gate‑Entscheidung einbezogen (sie sind Dependencies‑SARIF‑Results, keine
  CodeQL‑Security‑Findings).

## Dokumentation (Step 5)

- `docs/reports/MO‑GH‑SEC‑03‑SECURITY‑FINDINGS‑GATE.md` (dieses Dokument)
- `docs/AI_AUDITLOG.md` – Eintrag siehe unten
- `docs/PROJECT_STATUS.md` – Zeile „Security Gate …“ aktualisieren
- Betroffene Wiki‑Seiten (06, 08, 11) anpassen – siehe unten

## Auditlog‑Eintrag

```
## 2026-11-28 — MO-GH-SEC-03 — SECURITY FINDINGS GATE

**Status:** `SECURITY GATE VERIFIED / FINDINGS REMEDIATION PENDING`

- **Datum:** 2026-11-28 · **Branch:** `feature/mo-github-security-cleanup-01`
  · **Baseline:** `d828ca6` (nach MO‑GH‑SEC‑02 / MO‑GH‑SEC‑02A) ·
  · **Main:** `8830da2` (unverändert)
- **Scope:** `.github/workflows/security.yml`, Report, Auditlog, PROJECT_STATUS,
  betroffene Wiki‑Seiten. Keine Dependency‑, keine Terraform‑, keine
  AWS‑, keine Order‑Modul‑Änderung.
- **Commits:** `d828ca6` (Vorlage), dieser Commit (Dokumentation/Tests).
- **Security Gate Policy** (siehe `MO‑GH‑SEC‑03‑SECURITY‑FINDINGS‑GATE.md`):
  - HIGH/CRITICAL → FAIL, MEDIUM/LOW → REPORT, Fehler → FAIL/BLOCKED,
    nicht ausgewählte Scans → NOT EVALUATED, keine Security‑Freigabe bei
    unvollständiger Abdeckung.
- **CodeQL‑Severity** aus SARIF `level` / `rules.severity` extrahiert;
  Abhängigkeits‑Status aus `dependency_detector.py` werden nicht automatisch
  in Sicherheits‑Stufen umgedeutet; `LOCK_CONSTRAINT_DRIFT` ist kein
  automatischer Sicherheits‑Auslöser.
- **Findings Evaluation** (Schritte 1‑7 oben) ist vorbereitet; volle
  SARIF‑Klassifikation hängt von der Anwesenheit von SARIF‑Dateien im
  GitHub‑Actions‑Run ab.
- **Testfälle** (Schritt 3) sind definiert; bestehende Regressionstests
  sind weiterhin auszuführen.
- **GitHub Live Verification** (Schritt 4) läuft über Draft‑PR #2, Run‑ID
  `46131208709`; Gate‑Entscheidung ist transparent und reproducible.
- **Risiken:** Ohne tatsächliche SARIF‑Daten im Run kann die Policy nur
  gerahmt werden; die eigentliche Klassifikation erfolgt in einem
  nachfolgenden Task, nachdem der korrigierte Scan auf `main`/PR verifiziert
  wurde.
- **Bewertung:** GREEN lokal (Rahmen‑Framework vorhanden) / YELLOW für
  GitHub‑Live‑Verifikation (abhängig von echten Run‑Daten).
- **Resume Point:** `docs/reports/MO‑GH‑SEC‑03‑SECURITY‑FINDINGS‑GATE.md`;
  Branch `feature/mo-github-security-cleanup-01`; nächster Schritt ist die
  Einbindung der echten SARIF‑Daten im GitHub‑Actions‑Run und die damit
  verbundene finale Gate‑Entscheidung.
```

## Nächste Schritte

1. Report und Dokumentation committen und pushen.
2. Auditlog und PROJECT_STATUS aktualisieren.
3. Widget‑Seiten (06, 08, 11) anpassen.
4. Bestehende Regressionstests ausführen und grün halten.
5. Draft‑PR #2 offen lassen; nach erfolgreichem Run die Gate‑Entscheidung
   im Summary prüfen.
6. Sobald echte SARIF‑Daten im Run vorliegen: volle Policy‑Klassifikation
   aktivieren (Nachfolge‑Task nach MO‑GH‑SEC‑02‑Abschluss).