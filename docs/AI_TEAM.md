# AI Team — May's Orders

## Human Developer

**Maymilly Nowak**

- Product Owner
- definiert Ziele und Vision
- finale technische Entscheidungen
- Test-/QA- und Freigabe-Entscheidungen
- Git-Checkpoints und Releases
- Deployment-Entscheidungen (insbesondere `terraform apply`-Freigabe)

## AI Collaborators

**DeepSeek V4 Flash Free (opencode)**

- Woche-1-Analyse und Projektakte (Requirements, Architektur, API, DB, Security, Cost)
- Feature-/Task-Dokumentation
- Dokumentations-Transfer nach Mays-Jobsearch-Muster
- geplant W2–W4: Implementierung, Tests, Deployment-Support, Präsentation

## Working Agreement

- AI-Beiträge sind Vorschläge.
- Der Mensch verifiziert alles gegen die reale Umgebung (Build, Tests, Live-API, Terraform-Plan/Apply).
- AI committet/pusht nur mit ausdrücklicher Freigabe.
- AI legt nie Secrets offen oder loggt sie.
- AI erfindet keine Tests, Ergebnisse, AWS-Ressourcen oder Commit-IDs.

## Collaboration Loop

**Human idea → AI proposal → technical check → human review → Git checkpoint**

## Recovery

Bei Unterbrechung: `docs/PROJECT_STATUS.md` + `docs/reports/` (WEEK-01…04) sind die
maßgebliche Quelle. Details: `docs/reports/recovery-checkpoint-strategy.md`.