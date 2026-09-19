# May's Orders — AWS Serverless Order Management System

> mays-order-aws — Design and implement a serverless backend for managing the complete lifecycle of customer orders.

Serverless Order-Management-System für den fiktiven Händler **OrderFlow GmbH**.

## Ziel

Implementierung eines vollständigen, dokumentierten und präsentierbaren AWS-Serverless-Projekts,
das den kompletten Lebenszyklus einer Bestellung abbildet:

```text
PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
```

inkl. definierter Cancellation-Pfade und Ablehnung ungültiger Statusübergänge.

## Architektur (Zielbild)

```text
Client
  │
  ▼
Authentication (Cognito, Entscheidung dokumentiert)
  │
  ▼
API Gateway (HTTP vs. REST, Entscheidung dokumentiert)
  │
  ▼
Lambda (Python 3.14, Handler: index.handler)
  │
  ▼
DynamoDB
  │
  ▼
CloudWatch
```

IAM regelt ausschließlich die Service-to-Service-Berechtigungen (Least Privilege).
Benutzer-Authentifizierung und AWS-Berechtigungen sind strikt getrennt.

## Repository-Struktur

```text
mays-orders/
├── README.md
├── Week-1/           Requirements & API/Data Design (Index)
├── Week-2/           Core Order Management API (Index)
├── Week-3/           Business Rules, Reliability & Security (Index)
├── Week-4/           Scalability, Cost, Well-Architected & Finalization (Index)
├── requirements/     Business-/Technical-Requirements, Assumptions
├── architecture/     Architekturdiagramm, Request Flow, Decisions
├── api/              API-Dokumentation, Endpoints, Test-Cases
├── order-lifecycle/  State Machine, Transition Rules
├── database/         DynamoDB-Design, Access Patterns
├── security/         IAM-Design
├── monitoring/       Monitoring-Design
├── reliability/      Konsistenz & Fehlerbehandlung
├── cost/             Kostenanalyse
├── terraform/        Infrastructure as Code (AWS)
├── tests/            Test-Ergebnisse
├── presentation/     Finale Präsentation
└── docs/reports/     Feature-/Task-Reports, Weekly Reports
```

## Projektstatus

| Status | Bedeutung |
|--------|-----------|
| `WEEK 1` | Analyse, Requirements, API, Architektur (dokumentiert) |
| `WEEK 2` | Core Implementation (Lambda/API Gateway/DynamoDB) |
| `WEEK 3` | Business Rules, Reliability, Security |
| `WEEK 4` | Professionalization (Skalierung, Kosten, Well-Architected) |

Aktueller Status: **WEEK 2 — COMPLETE** (Core Implementation: Terraform Infrastructure modularisiert in 6 Child Modules; Lambda/API Gateway/DynamoDB/Cognito/Monitoring implementiert).

## Wochen-Struktur

Die vier Projektwochen sind als physische Ordner mit Index-Dokumenten abgebildet. Jede
`Week-N/README.md` verlinkt die zugehörigen Fachdateien (die thematisch im Repository
abgelegt bleiben, um Querverweise und die Dokumentationsstruktur zu erhalten).

| Week | Fokus | Haupt-Artefakte |
|------|-------|-----------------|
| [`Week-1`](Week-1/README.md) | Requirements & API/Data Design | Requirements, Order Lifecycle, API, DynamoDB, ADR |
| [`Week-2`](Week-2/README.md) | Core Order Management API | Terraform (6 Module), Lambda (Python 3.14), Cognito, API Gateway |
| [`Week-3`](Week-3/README.md) | Business Rules, Reliability & Security | State Machine, Validation, IAM, Reliability |
| [`Week-4`](Week-4/README.md) | Scalability, Cost, Well-Architected & Finalization | Kostenanalyse, Skalierung, Test-Endbericht, Präsentation |

## Voraussetzungen (Prerequisites)

### Erforderlich (Required)

- **Git** — Versionskontrolle und die dokumentierten Review-/Commit-Checkpoints.
- **Terraform** — Version `>= 1.5.0` (Constraint `required_version` in `terraform/main.tf`); AWS-Provider `~> 6.0` (`hashicorp/aws`).
- **Python 3** — für lokale Tests, Package-Build (`lambda/build_zip.py`) und Validierung (`compileall`, `unittest`). Nur Standardbibliothek nötig; `boto3` wird von der Lambda-Runtime bereitgestellt und muss lokal **nicht** installiert sein. Der Lambda-Runtime im Ziel-Account ist **`python3.14`** (`index.handler`) — das ist keine lokale Python-Version-Anforderung.
- **AWS-Konto** — Ziel-Account, in dem Terraform die Infrastruktur anlegt.

### AWS-Zugang & Identität

- **AWS CLI** mit einem konfigurierten **Named Profile**. Empfohlener Profil-Name: **`maysOrdersAiDeveloper`** (Quelle: `docs/ai-developer-profile.md`).
- Der Profil-Name ist eine **Empfehlung**; ein vorhandenes AWS-CLI-Profil darf stattdessen genutzt werden.
- Credentials werden **außerhalb** des Repositories verwaltet (`~/.aws/`) und dürfen **niemals** committet werden (keine Access Keys, Secret Keys oder Tokens im Repo).
- Das Profil ist für den **AI-Developer-Workflow** vorgesehen. Human- und AI-Developer-Identität sind **getrennte Konzepte**; menschliche Freigabe bleibt vor jedem kontrollierten `terraform apply`/`destroy` erforderlich.
- Das Profil **umgeht NICHT** IAM, Permissions Boundaries oder den Policy Gate.

Deployment erfordert ausreichende **IAM-Berechtigungen** für die von Terraform verwalteten Ressourcen (DynamoDB, IAM, Lambda, Cognito, API Gateway, CloudWatch, CloudTrail, S3). Eine generic `AdministratorAccess`-Policy ist **nicht** vorausgesetzt — die erforderlichen Berechtigungen werden target-seitig über AWS IAM festgelegt.

### Region

Default-Region: **`eu-central-1`** (Europe/Frankfurt), konfiguriert über `var.aws_region` (`terraform/variables.tf`, `terraform/main.tf`). Single-Region-Projekt — **kein** Multi-Region-Deployment.

### Repository-Setup & Validierung

Reine Lese-/Validierungsbefehle (deployen keine Infrastruktur):

```bash
# Identität sicher prüfen (read-only)
aws sts get-caller-identity --profile maysOrdersAiDeveloper

# Terraform validieren
cd terraform && terraform init && terraform validate

# Lambda-Code testen & bauen
cd lambda && python3 -m compileall -q src tests
cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests -v
cd lambda && python3 build_zip.py
```

### Mays-Order-AWS-installer (Deployment Lifecycle CLI)

Der **`Mays-Order-AWS-installer`** ist ein eigenständiger CLI-Wrapper für den vollständigen
Terraform-Deployment-Lifecycle mit H1-Security-Hardening.

**Features:**
- Validierung vor jedem Schritt (AWS Profile, Region, Account, Terraform Config)
- Plan-Generierung & Safety-Analyse
- Policy Gate Integration
- Human Approval Gate (`--yes` zum Überspringen)
- Plan Integrity & Context Match (Region/Account/Profile)
- Dry-Run Mode Standard (`DRY_RUN=true`, `ALLOW_AWS_OPERATIONS=false`)
- Auto-Detection des neuesten Plans (`--plan` optional)

**Usage:**
```bash
# Installer aus Projekt-Root
./Mays-Order-AWS-installer --help

# Read-only Validierung & Planning
./Mays-Order-AWS-installer validate
./Mays-Order-AWS-installer plan
./Mays-Order-AWS-installer plan-destroy

# Mutation (erfordert explizite Freigabe)
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false
./Mays-Order-AWS-installer deploy --yes      # auto-detects latest plan
./Mays-Order-AWS-installer destroy --yes     # auto-detects latest destroy plan

# Oder expliziter Plan-Pfad
./Mays-Order-AWS-installer deploy --plan .mays-installer/runs/.../plans/deploy.tfplan --yes
```

**Environment Variables:**
| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `AWS_PROFILE` | `mayaws` | AWS CLI Profile (überschreibbar via `--profile`) |
| `AWS_REGION` | `eu-central-1` | AWS Region |
| `ALLOW_AWS_OPERATIONS` | `false` | **true** für deploy/destroy/state push |
| `DRY_RUN` | `true` | **false** für echte AWS-Mutationen |

**H1 Hardening aktiv:**
- `--yes` überspringt **nur** den interaktiven Prompt (nicht Validation/Policy/Safety)
- Plan Context Match prüft Region/Account vor apply
- State push klassifiziert als MUTATING (braucht `ALLOW_AWS_OPERATIONS=true`)
- Keine Secrets in Logs/Artefakten; Plan-Sanitization aktiv

---

### Policy Gate & Deployment-Workflow

```text
terraform plan  →  Policy Gate  →  menschliche Freigabe  →  terraform apply
```

Der **Policy Gate** (`terraform/policy/`, `docs/TERRAFORM_POLICY_GATE.md`) ist ein projektinterner
Governance-Check **zwischen** `plan` und `apply`. Er ist Projekt-Governance und **ersetzt nicht**
die AWS-IAM-Autorisierung; ein `FAIL` darf nicht umgangen werden.

## Workflow-Garantien

- Test-first / evidenzbasierte Ergebnisse — nichts wird behauptet, ohne getestet zu sein.
- Checkpoints nach jedem Schritt (Report → Tests → Build → `git status` → `git diff --check` → Commit → Push).
- Recovery ausschließlich über die Feature-/Task-Reports (`docs/reports/`).
- Keine Secrets, keine API Keys im Source, keine unnötigen AWS-Services.
- Kostenbewusst: Free-Tier beachten, keine dauerhaft laufenden Ressourcen ohne Begründung.

## Dokumentation (Woche 1)

Die Woche-1-Dokumentation liegt in den jeweiligen Unterordnern. Einstieg:

- [Business Requirements](requirements/business-requirements.md)
- [Technical Requirements](requirements/technical-requirements.md)
- [Assumptions & Constraints](requirements/assumptions.md)
- [Order State Machine](order-lifecycle/state-machine.md)
- [State Transition Rules](order-lifecycle/transition-rules.md)
- [API Endpoints](api/endpoints.md)
- [DynamoDB Access Patterns](database/access-patterns.md)
- [Architecture Decisions](architecture/architecture-decisions.md)
- [Networking](architecture/networking.md) — Ist (Serverless) vs. Produktions-Ziel (VPC/Subnetz/AZ/CIDR)
- [Vier-Wochen-Plan](docs/reports/four-week-plan.md)

## Projektakte (`docs/`)

- [Project Status](docs/PROJECT_STATUS.md) — zentraler Entwicklungsstand (Single Source of Truth)
- [Project Portfolio](docs/PROJECT_PORTFOLIO.md) — vollständiger Projektweg
- [Changelog](docs/CHANGELOG.md)
- [AGENTS](docs/AGENTS.md) — Projektübersicht & Regeln für AI-/menschliche Mitarbeit
- [Features](docs/features/README.md) — Feature-/Task-Dokumentation (F001–F011)
- [Weekly Reports](docs/reports/) — `WEEK-01…04.md`
- [Documentation Transfer Report](docs/reports/documentation-transfer-report.md)
- [Terraform Policy Gate](docs/TERRAFORM_POLICY_GATE.md) — Pre-Apply-Governance
- [AI Developer Profile](docs/ai-developer-profile.md) — empfohlene AWS-CLI-Identität für den AI Developer
- [Industry-Standard Evolution](docs/roadmap/future-extensions.md) — Ausbau zu Produktions-/Industrie-Standards
