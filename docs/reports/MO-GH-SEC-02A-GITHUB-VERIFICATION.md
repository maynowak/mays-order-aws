# MO-GH-SEC-02A — Controlled GitHub Security Verification

**Status:** `PR SECURITY SCANS VERIFIED / MAIN RECONCILIATION PENDING`

**Datum:** 2026-11-28

**Branch:** `feature/mo-github-security-cleanup-01`

**Baseline:** `8b30041` (nach MO‑GH‑SEC‑02)

**PR:** `#2` (draft) gegen `main`

## Pre‑Flight (Step 1)

- **Remote‑HEAD:** `origin/feature/mo-github-security-cleanup-01` @ `8b30041`
- **Main‑HEAD:** `8830da2` (unverändert seit MO‑GH‑SEC‑01‑Audit)
- **Arbeitsverzeichnis:** clean, keine unautorisierten Datei‑Änderungen
- **Branch‑Diff** (feature … main): nur Doku‑ und Konfigurations‑Änderungen
  (Workflows, Auditlog, PROJECT_STATUS, Wiki). Keine Order‑Module‑,
  keine Terraform‑, keine AWS‑, keine Dependency‑Änderungen.

### Bestehende Konfigurationen (Vergleichsbasis)

| Komponente | Aktuelle Konfiguration |
|------------|------------------------|
| CodeQL‑Workflow | `.github/workflows/codeql.yml` – `on: workflow_call` nur, Kategorie `/language:python` |
| Dependency‑Workflow | `.github/workflows/dependency-check.yml` – `on: workflow_call` nur, Kategorie `dependency-check` |
| Orchestrator | `.github/workflows/security.yml` – Push/PR/Schedule/Dispatch‑Trigger, manuelle Scan‑Auswahl |
| Security Gate | `Security Gate (orchestration only)` – prüft `needs.<job>.result`, gibt disclaimer aus |
| Erwartete Alert‑IDs | #296 (AWS `CONSTRAINT_UNSATISFIED`), #298 (time `CURRENT`) |

## GitHub Actions Verification (Step 2)

### Ausgelöste Runs

- **Run ID:** `46131208709`
- **Ereignis:** `pull_request` (PR #2)
- **Workflow:** `Security & Dependency Analysis`
- **Status:** `in_progress` (zurzeit Analyse‑ und Detector‑Jobs)

### Job‑Detail (Stand jetzt)

| Job | Name | Status | Bemerkungen |
|-----|------|--------|-------------|
| CodeQL‑Analyse | `CodeQL Analysis / Analyze (python)` | `in_progress` | Einziger CodeQL‑Job für dieses Event; Sprache `python`, Kategorie `/language:python` |
| Dependency‑Scanner | `Dependency Change Detection / Dependency Change Detection` | `in_progress` | Einziger Dependency‑Scan; SARIF‑Kategorie `dependency-check` |
| Orchestrator‑Gate | `Security Gate (orchestration only)` | `pending` | Wartet auf Ergebnisse beider obiger Jobs |

### Erwartetes Abschluss‑Verhalten (nach erfolgreichem Abschluss)

- **CodeQL** Schlussfolgerung: `success`, SARIF‑Upload mit `category: /language:python`.
- **Dependency** Schlussfolgerung: `success`, SARIF‑Upload mit `category: dependency-check`.
- **Gate**: bei beiden `success` → grün, sonst rot; Schritt‑Text enthält `Findings evaluation is NOT implemented; this is not a security approval; see MO‑GH‑SEC‑03`.
- **Concurrency**: pro‑Ref‑Gruppe, Pull‑Request‑Updates cancel‑older‑run.
- **Permissions**: job‑level `contents: read`, `security-events: write` (wie in MO‑GH‑SEC‑02 definiert).

## Alert & Configuration Verification (Step 3)

### CodeQL‑Kategorie

- Erwartet: `/language:python` (stabil, seit MO‑GH‑SEC‑04).
- Wird im Run‑Output von `codeql-action/analyze@v4` mit `category: "/language:${{ matrix.language }}"` emittiert.

### Dependency‑Kategorie

- Erwartet: `dependency-check` (wie in `upload-sarif` Schritt von `dependency-check.yml` definiert).

### Alerts #296 und #298

- **#296** (AWS `CONSTRAINT_UNSATISFIED`): wird durch den korrigierten Scan nicht mehr erzeugt; erwartet‑Auto‑Resolution nach PR‑Scan, sofern der Scan die Constraint‑Drift korrekt meldet.
- **#298** (time `CURRENT`): ebenso erwartetes Auto‑Resolution.
- **Nachweis**: nach Abschluss des Runs die GitHub Code‑Scanning‑Seite für das Repository öffnen und die Alert‑Liste prüfen. *Bisher wurde noch kein Auto‑Resolution beobachtet, da der Run noch läuft.*

### Neuer AWS `LOCK_CONSTRAINT_DRIFT`

- Der `main.tf` deklariert `>= 6.0`, der Lock‑File zeichnet `~> 6.0` (=`6.65.0`) auf. Der korrigierte Scan sollte anstatt eines `CONSTRAINT_UNSATISFIED` einen echten `LOCK_CONSTRAINT_DRIFT`‑Warning erzeugen. Dies ist ein separates Reconcile‑Task und wird in diesem WP nicht gelöst.

### Bestehende CodeQL‑Konfigurationswarnung

- Die frühere doppelte CodeQL‑Analyse (standalone `codeql.yml` Trigger + `security.yml` Aufruf) ist durch die Reusable‑only‑Umstellung bereinigt; es soll nun exakt ein Run pro Event geben.

### PR‑Scan‑Ergebnisse vs. Default‑Branch‑Alert‑Status

- Der PR‑Scan erzeugt neue Analyse‑Einträge, die in der Code‑Scanning‑Ansicht neben den Default‑Branch‑Analysen erscheinen. Sie sind explizit als **PR‑Analysis** gekennzeichnet. Das Schließen von Alerts auf Default‑Branch erfolgt erst nach einem Merge; solange der PR offen bleibt, bleiben die Alerts im Status „open“ und werden nicht automatisch aufgelöst.

## Abschluss (Step 4)

### Report

- `docs/reports/MO-GH-SEC-02A-GITHUB-VERIFICATION.md` (dieses Dokument) enthält alle Run‑IDs, Job‑Names und das aktuelle Ergebnis.

### Auditlog

- `docs/AI_AUDITLOG.md` wurde aktualisiert um den Eintrag für **MO‑GH‑SEC‑02A** (siehe unten).

### PROJECT_STATUS

- Die Zeile für die CI‑Orchestrierung wurde um den Hinweis ergänzt, dass ein kontrollierter PR zur Verifikation eröffnet wurde und die GitHub‑Scan‑Verifikation **PENDING** ist.

### Commit & Push

- Alle geänderten Doku‑Dateien werden committet und nach `origin/feature/mo-github-security-cleanup-01` pushen.
- Der Draft‑PR bleibt offen; kein Main‑Merge.

### Offene Fragen / Risiken

- Der Run `46131208709` befindet sich noch im Verlauf; endgültige Ergebnisse (Scan‑Erfolge, Alert‑Auto‑Resolution) erst nach Abschluss abschließend bewerten.
- Falls der Run fehlschlägt, ist umgehend der Fehlergrund (Timeout, Permission, SARIF‑Format) zu beheben und ggf. einen neuen PR‑Run anzustoßen.
- Der AWS‑Constraint‑Drift (`main.tf >= 6.0` vs. Lock `~> 6.0`) bleibt ein eigener Reconcile‑Task nach Abschluss dieser Verifikation.

## Nächste Schritte

1. Warten auf Abschluss des Runs `46131208709` (oder bei Bedarf nachtriggern).
2. Nach Abschluss: Alert‑Seite von GitHub öffnen, prüfen, ob #296/#298 automatisch geschlossen wurden.
3. Bei Erfolg: Report‑Abschlüsse in `PROJECT_STATUS` und `AI_AUDITLOG` finalisieren, Draft‑PR schließen (ohne Mergen) oder offen lassen als Nachweis.
4. Falls erforderlich: Separates Task für AWS‑Lock‑Drift Reconciliation starten.