# AGENTS.md — May's Orders (AWS Serverless Order Management)

Serverless order lifecycle (`PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`)
on AWS: **Cognito (JWT) → API Gateway HTTP API → Lambda (Python 3.14) → DynamoDB → CloudWatch**,
all provisioned via Terraform. Repo docs are mostly German; status enums are English.

## Read first

- `docs/AGENTS.md` — full project rules (per-topic sources of truth, checkpoint rule,
  evidence states, commit/push policy). Authoritative; this root file only summarizes.
- `docs/PROJECT_STATUS.md` — declared single source of truth for progress. May lag reality
  (dated header vs. newer work); verify against `git log` and update it after checkpoints.
- `docs/AI_AGENT_PLAYBOOK.md` — standard workflow for repeated agent tasks.
- Topic SoT: state machine `order-lifecycle/`, API contract `api/endpoints.md`,
  data model `database/`, ADRs `architecture/architecture-decisions.md`, IAM `security/`.

## Verified commands

```bash
# Lambda unit tests + build (from lambda/')
cd lambda
python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests   # 53 tests
python3 build_zip.py                                   # → dist/lambda.zip

# Installer unit tests (from repo root, ~25 s, 81 tests)
python3 -m unittest installer.tests.test_installer

# Seed-tool tests (28 tests; must cd — fails from repo root due to sys.path)
cd scripts && python3 -m unittest discover -s tests

# Terraform (from terraform/')
terraform init && terraform validate && terraform plan
```

Deployment lifecycle CLI: `./Mays-Order-AWS-installer {validate,plan,plan-destroy,deploy,destroy,state,output,identity,gui}`.
Safe by default: `DRY_RUN=true`, `ALLOW_AWS_OPERATIONS=false`. Real mutations require
`ALLOW_AWS_OPERATIONS=true`, `DRY_RUN=false`, `--yes`, **and** explicit human release.
Run artifacts land in `.mays-installer/runs/` (gitignored).

## Hard rules (details in `docs/AGENTS.md`)

- **No AWS mutations without explicit human approval** — `terraform apply`/`destroy`, paid
  resources, destructive operations. The Policy Gate (`terraform/policy/validate-plan.py`)
  runs between `plan` and `apply`; a FAIL must not be bypassed.
- **Never commit secrets.** AWS credentials live only in `~/.aws/`. Cognito = user auth;
  IAM = service-to-service only; never use IAM access keys as user login.
- **Evidence-based claims only.** Never state Build/Test/Deploy PASS without having run it.
  Use states: PLANNED / IMPLEMENTED / TESTED / VERIFIED / COMPLETE / BLOCKED / NOT TESTED.
- **Checkpoint after each released task:** Report → Tests → Build → `git status` →
  `git diff --check` → Secret-Audit → Commit → Push; keep `docs/PROJECT_STATUS.md` and the
  active `docs/features/F0XX-*.md` continuously updated (not just at the end).
- Git: `main` plus optional `feature/*` branches; Conventional Commits
  (`feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`, `chore:`).

## Environment & quirks

- Local `python3` (stdlib only) suffices for lambda unit tests — tests inject fake DynamoDB
  clients; there is **no** `requirements.txt` and boto3 must **not** be installed/bundled
  (the `python3.14` Lambda runtime provides it). Local Python version is irrelevant (3.12 works).
- AWS profile: installer CLI defaults to `mayaws`; README recommends `maysOrdersAiDeveloper`
  for the AI-developer workflow. Region is `eu-central-1` throughout.
- Terraform uses an S3 backend + DynamoDB lock (`terraform/backend.tf`) with workspaces;
  dry-run tooling uses `terraform init -backend=false`.
- `terraform/` accumulates artifacts: `*.tfplan`, `*.tfstate*`, and extensionless
  `tfplan`/`tfplan-par`. Only `terraform/*.tfplan` is gitignored — the extensionless files
  show up as untracked; never commit them. Same for the root-level `terraform.tfstate` (ignored).
- The Node.js/TypeScript lambda baseline was removed; it exists only in git history
  (`449cdd7`). Do not reintroduce `npm`/`vitest`.
- E2E tests (`tests/test_e2e_async_order.py`) require **deployed** infrastructure plus
  boto3/urllib3 and env (`AWS_PROFILE`, `COGNITO_CLIENT_ID`, `TEST_USER_EMAIL`,
  `TEST_USER_PASSWORD`, optional `API_BASE_URL`) — not a local verification step.

## Where the code is

Only four top-level dirs contain executable code — the rest (`api/`, `database/`,
`security/`, `Week-1..4/`, `docs/`, …) is documentation, however code-like the names look:

- `lambda/` — active order handler, entrypoint `src/index.py` (`index.handler`)
- `installer/` + `Mays-Order-AWS-installer` — deployment lifecycle CLI
  (layers: `cli/`, `core/`, `validation/`, `terraform/`, `run/`)
- `terraform/` — root module orchestrating 7 child modules in `terraform/modules/`
  (dynamodb, iam, lambda, cognito, api, monitoring, cloudtrail); `bootstrap/` provisions the
  state bucket/lock table; `policy/` is the Policy Gate
- `scripts/` — seed/cleanup tools + test harness; `tests/` — E2E only
