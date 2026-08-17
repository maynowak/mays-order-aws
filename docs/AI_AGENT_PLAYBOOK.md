# AI Agent Playbook — May's Orders

Dieses Playbook definiert den wiederverwendbaren Workflow für AI-unterstütztes Software-Engineering
im **May's Orders**-Repository. Vor Implementierung, Reviews, Bug-Fixing oder Doku-Änderungen nutzen.

---

## Purpose

Reduziert Prompt-Wiederholung und schafft einen konsistenten, wartbaren Arbeitsprozess für AI-Agenten.

- Engineering-Regeln für AI-Assistenten
- Standard-Prompt-Struktur
- Minimal-invasiver Ausführungsworkflow
- Explizite Validierungserwartungen
- Konsistentes Abschlussformat

---

## Core Principles

### 1. Bestehende Architektur erhalten

Das Projekt besitzt dokumentierte Architekturentscheidungen (ADR-001…007) und fachliche Designs.
AI-Assistenten müssen erhalten:

- die dokumentierten ADR und Trade-offs (`architecture/architecture-decisions.md`)
- das State-Machine-Konzept (`order-lifecycle/`)
- das Datenmodell (`database/`)
- Least-Privilege-IAM-Design (`security/iam-design.md`)
- die Kosten- und Scope-Grenzen (`cost/`, `requirements/technical-requirements.md`)

Nicht als Greenfield behandeln.

### 2. Minimal-invasiv arbeiten

Nur Code/Doku ändern, die für die Aufgabe nötig sind. Nicht:

- Architektur ohne neue ADR ändern
- unnötige AWS-Services ergänzen
- unnötiges Refactoring
- Dependencies ohne Freigabe

### 3. Ursache zuerst bestätigen

Vor Änderungen die tatsächliche Ursache aus der aktuellen Implementierung ableiten.
Nicht annehmen, dass ein erfolgreicher Build/Deploy korrektes Verhalten beweist.

### 4. Wiederverwenden vor Erstellen

Bestehende Muster nutzen (Fehlerformat, Validierung, State-Machine-Tabelle, GSI-Query).
Neue Dateien nur, wenn die Architektur keinen passenden Ort bietet.

---

## Standard Workflow

### Step 1. Nur das Nötige lesen

Typische Reihenfolge:

1. `docs/PROJECT_STATUS.md`
2. betroffene Fachquelle (z. B. `api/endpoints.md`)
3. `docs/AGENTS.md` / `docs/AI_AGENT_PLAYBOOK.md` bei Regel-Fragen

### Step 2. Vor dem Editieren analysieren

Wahrscheinliche Ursache aus dem aktuellen Codepfad ableiten; verifizieren über
Datenquelle, Request/Response-Form, State-Transitions, Fehlerpfade.

### Step 3. Kleinste korrekte Änderung

Minimum, das die bestätigte Ursache behebt. Bestehende Abstraktionen bevorzugen.

### Step 4. Explizit validieren

Schmalste sinnvolle Validierung:

1. TypeScript/Build (`tsc --noEmit` / Build-Skript, sobald vorhanden)
2. Unit-Tests (State Machine, Validierung) — Woche 2+
3. `terraform validate` + `terraform plan` (Infrastruktur)
4. Live-API-Verifikation mit `curl` (nur nach Deployment)
5. `git diff --check`

### Step 5. Konsistent berichten

Abschlussformat siehe unten. Keine vagen Zusammenfassungen.

---

## Standard Prompt-Struktur

```text
Context
- Serverless-Backend (API GW + Lambda + DynamoDB), Terraform, Cognito
- Fokussierte Architektur; keine neuen Services ohne ADR
- Evidenzbasiert; Statuskonvention beachten

Task
- Exakt beschreiben

Constraints
- Dateien, die nicht geändert werden dürfen
- Keine unnötigen Services/Dependencies
- Minimal-invasiv

Validation
- Geforderte Prüfkommandos (Build, Tests, terraform validate/plan, curl)
- Erwartete Statuswerte

Output
- Gefordertes Abschlussformat
```

---

## Validation Policy

### Syntax-/Build-Validierung

Nach Quellcode-Änderungen:

```bash
npm run build        # bzw. tsc --noEmit (Woche 2)
npm test             # Unit-Tests
```

### Infrastruktur-Validierung

```bash
terraform init
terraform validate
terraform plan       # Review, kein blindes Apply
terraform apply      # NUR nach expliziter menschlicher Freigabe
```

### Live-API-Validierung

Wenn ein Endpoint berührt wird: nach Deployment mit `curl` gegen die tatsächliche
Invoke-URL testen. Ausdrücklich trennen:

- was per Build/Unit-Test verifiziert wurde
- was per Live-API-Call verifiziert wurde
- was Browser-Verifikation erfordert

**Nie behaupten, Endpoint-Verhalten sei bestätigt, wenn es nicht beobachtet wurde.**

### Evidence-Standard

Nur bestätigte Evidenz aus:

- aktuellem Quellcode
- Befehlsausgaben
- Live-Endpoint-Antworten

Keine Annahmen als Fakten ausgeben.

---

## Completion Format

### Summary

- was sich geändert hat

### Validation Status

- Build / Tests / Terraform / Live-API jeweils mit Status (PASS / NOT RUN / NOT APPLICABLE)

### Modified Files

- nur tatsächlich geänderte Dateien

### AWS Resources

- nur tatsächlich erzeugte/geänderte Ressourcen (sonst: NONE)

### Cost Impact

- falls relevant

### Known Limitations

- nicht verifizierte/offene Punkte

### Git Checkpoint

- Branch, Commit, Push-Status

### Next Step

- genau ein nächster Schritt

---

## Notes for Future AI Tasks

- Statuskonvention: ✅ COMPLETE / ⏳ PLANNED / 🔵 IN PROGRESS / 🟡 DESIGNED / 🚧 BLOCKED / ⚪ NOT VERIFIED.
- Fachquellen sind Single Source of Truth; nie widersprüchliche Zweitquellen erzeugen.
- Nach jedem Feature: `docs/reports/WEEK-NN.md` + `docs/PROJECT_STATUS.md` + `docs/CHANGELOG.md` aktualisieren.

Dieses Dokument ist der wiederverwendbare AI-Engineering-Playbook für das Repository.