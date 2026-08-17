# AI Project Context — May's Orders

## Project

**May's Orders** — AWS Serverless Order-Management-System für den fiktiven Händler
**OrderFlow GmbH**. Backend-API + Infrastructure as Code; vollständiger Order-Lebenszyklus
mit validierten Statusübergängen.

## Current Project Status

- Woche 1 (Analyse & Architektur): **COMPLETE**
- Requirements / Lifecycle / API / DynamoDB / Auth / IAM / ADR / Monitoring / Reliability / Cost: **DESIGNED**
- Application Code: **NOT STARTED**
- AWS-Ressourcen: **NONE**
- Terraform: **DESIGN ONLY**
- Live-API: **NOT RUN**

Autoritative Quelle: **`docs/PROJECT_STATUS.md`** (nach jedem Checkpoint aktualisieren).

## AI-Assisted Development

AI wird als aktiver Entwicklungspartner genutzt (nicht nur Textgenerierung).

### Dokumentierte AI-Kollaborateure

- **DeepSeek V4 Flash Free (opencode)** — Woche-1-Analyse, Requirements, Architektur-Entscheidungen,
  API-/DB-/Security-/Cost-Design, Projektakte und Checkpoints.

### AI Working Agreement

Jeder AI-Assistent in diesem Repository sollte:

1. `docs/PROJECT_STATUS.md` lesen (aktueller Stand).
2. `docs/AGENTS.md` und relevante Fachquellen lesen.
3. `docs/AI_AGENT_PLAYBOOK.md` als Workflow nutzen.
4. Das Projektverständnis herstellen, bevor Änderungen vorgeschlagen werden.
5. Beobachtungen von Hypothesen trennen; nichts Unverifiziertes als Fakt ausgeben.
6. Kleine, reversible Änderungen machen.
7. Bestehende Architektur/Entscheidungen erhalten (ADR dokumentieren, nicht umgehen).
8. Evidenzbasiert validieren (Build/Tests/Live-API sauber unterscheiden).
9. Geänderte Dateien und Begründung zusammenfassen.

## Collaboration Model

**Human Developer — Maymilly Nowak**

- Product Owner
- finale technische Entscheidungen
- Test-/QA-Freigaben, Deployment-Entscheidungen
- Git-Checkpoints und Releases

**AI collaborators**

- unterstützen Analyse, Implementierung, Review, Dokumentation
- ersetzen keine menschliche QA oder finale Entscheidungen

## Development Principle

**Human observation → AI analysis → small technical change → validation → human review → Git checkpoint**

Jedes Feature folgt demselben iterativen Loop:

1. Ziel (menschlich)
2. Prompt-Formulierung
3. AI-Vorschlag
4. Technische Prüfung
5. Manuelle Anpassung
6. Test / Validierung
7. Re-Evaluation
8. Nächste Iteration