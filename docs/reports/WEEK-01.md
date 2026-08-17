# Weekly Report — Woche 1

**Datum:** 2026-08-17 (Kalenderwoche 34)
**Projekt:** May's Orders — AWS Serverless Order Management

## 1. Gesamtstatus

**ON TRACK** — Woche 1 (Analyse & Architektur) abgeschlossen. Checkpoint 1 bereit zur
menschlichen Prüfung. Noch keine AWS-Ressourcen erzeugt, kein Terraform-Apply.

## 2. Diese Woche implementierte Ergebnisse

| # | Ergebnis | Datei |
|---|----------|-------|
| 1 | Projekt-Skeleton + Git-Repo | `README.md`, Struktur |
| 2 | Business-/Technical-Requirements | `requirements/` |
| 3 | Assumptions & Constraints | `requirements/assumptions.md` |
| 4 | Order Lifecycle + Transition Matrix (18 Fälle) | `order-lifecycle/` |
| 5 | API-Design (4 Endpoints, Fehlerformat, Pagination) | `api/` |
| 6 | DynamoDB-Design (Single-Table, GSI, kein Scan) + Access Patterns | `database/` |
| 7 | Auth-Entscheidung (Cognito, HTTP API) + JWT-Flow | `security/authentication-decision.md` |
| 8 | IAM-Konzept (Least Privilege) | `security/iam-design.md` |
| 9 | Architektur-Entscheidungen (ADR-001…007) | `architecture/` |
| 10 | Monitoring-, Reliabibility-, Cost-Konzept | `monitoring/`, `reliability/`, `cost/` |
| 11 | Vier-Wochen-Plan + Test-/Kosten-/Recovery-Strategie | `docs/reports/` |
| 12 | Architekturdiagramm (SVG) | `architecture/architecture-diagram.svg` |

## 3. Geplante nächste Schritte (Woche 2)

1. Menschliche Prüfung von Checkpoint 1 (dieser Report).
2. Repo-Setup (Node/TypeScript, Test-Framework).
3. Terraform-Grundgerüst + `validate`/`plan`.
4. Cognito + API Gateway + Lambda (Core-Endpoints).
5. Deployment + Live-API-Tests (nach Freigabe).

## 4. Probleme / Risiken / Blocker

| # | Risiko | Status |
|---|--------|--------|
| 1 | AWS-Zugriff/Credentials noch nicht verifiziert | offen (vor Woche-2-Deployment klären) |
| 2 | GSI1-Hot-Partition bei sehr hoher Last | bewertet, Sharding dokumentiert (Woche 4) |
| 3 | Kosten über Free-Tier bei Live-Tests | durch Plan/Review minimiert; Billing-Alert optional |

**Blocker:** keine.

## 5. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| Build | NOT APPLICABLE (kein Code, Woche 1) |
| Unit-Tests | NOT RUN |
| Terraform validate/plan | NOT RUN |
| Live-API | NOT RUN |
| `git diff --check` | PASS |
| Secret-Audit | PASS |

## 6. AWS-Ressourcen

NONE — keine Ressourcen erzeugt (bewusst, laut Vorgabe).

## 7. Zeitplan-Einschätzung

Im Zeitplan. Vier-Wochen-Struktur (siehe `docs/reports/four-week-plan.md`) ist definiert;
Woche 2 kann nach Freigabe starten.

## 8. Git Checkpoint

- Branch: `main`
- Commit: `4515029` (Woche-1 + Merge origin/main)
- Push: SUCCESS
- Folge-Commits (Dokumentations-Transfer): werden in `docs/CHANGELOG.md` ergänzt

## 9. Organisatorische Punkte

- **Freigabe erforderlich:** Terraform-Apply und jede kostenrelevante Ressourcen-Anlage
  in Woche 2 nur nach expliziter menschlicher Freigabe.
- Offene Entscheidungen sind in den jeweiligen Docs markiert („Entscheidung offen").