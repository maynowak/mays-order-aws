# Release Gates — v0.5.0-rc.3

**Release-Gate-Report für `v0.5.0-rc.3` (Module Builder & RIS Integration)**

**Datum:** 2026-10-31
**Repository:** `maynowak/mays-order-aws`
**Branch:** `main`
**Release-Basis:** `v0.5.0-rc.2` → `5cf50a0`
**Dokumentations-Basis vor Packaging:** `ca1fa16`
**Tag-Ziel:** Packaging-Commit dieses Reports
(`git log -1 --format=%H` auf `main`; exakter SHA im Abschlussbericht von P07/P08)
**Entscheidung:** **GO für Release Candidate** · **BLOCKED für Produktion** (Privacy)

## 1. Gate-Matrix

| # | Gate | Status | Evidence | Referenz |
|---|---|---|---|---|
| G1 | Git-Integrität | ✅ VERIFIED LOCAL | `main` 49 Commits über rc.2, Integrationsbranch gemerged und erhalten, keine getrackten State-/Plan-Artefakte | `git log`, `git ls-files` |
| G2 | Working Tree | ✅ VERIFIED LOCAL | clean, `git diff --check` ohne Befund | lokal |
| G3 | Module Builder (Tests) | ✅ VERIFIED LOCAL | 90/90 PASS (2026-10-31 erneut ausgeführt) | `module_builder.tests.test_module_builder` |
| G4 | Module Builder (Generator) | ✅ VERIFIED LOCAL | `orders-service` generiert → `init` 0, `validate` PASS, `fmt -check` 0 | `/tmp`-Lauf, P06 §6 |
| G5 | Terraform (Root) | ✅ VERIFIED LOCAL | `init -backend=false` 0, `validate` PASS, `fmt -check` 0 | lokal |
| G6 | Lambda | ✅ VERIFIED LOCAL | 76/76 PASS; Artefakt-Determinismus (SHA-256 im Manifest) | `lambda/tests`, `build_zip.py` |
| G7 | Installer | ✅ VERIFIED LOCAL | 81/81 PASS | `installer.tests.test_installer` |
| G8 | Modulvertrag (orders-service) | ✅ VERIFIED LOCAL | 7 Module fest, 6 Inputs, 20 Outputs, MANAGED/EXTERNAL | `RELEASE-v0.5.0-rc.3.md` §4 |
| G9 | Security F-03 (SQS-Wildcard) | ✅ VERIFIED (lokal + Consumer) | keine `aws_sqs_queue_policy`, kein `Principal`-Statement; RIS: „RESOLVED (MO-Vertrag)" | `a2fb385`, P06 §5 |
| G10 | IAM-Portabilität (F-01/FIX-01/02) | ✅ VERIFIED (lokal + Consumer) | `lambda_execution_boundary` default `null`; Installation in Fremdkonto `262370457690` gelungen | `f3e78d0`, `a46b189` |
| G11 | SQS-Gate plan-stabil (GAP-06) | ✅ VERIFIED LOCAL | `count = var.sqs_enabled ? 1 : 0`, ARN bleibt Policy-Resource | `9627eb2` |
| G12 | RIS Consumer Acceptance | ✅ VERIFIED AWS E2E | `RIS-MO-RC-01` (2026-10-30): Plan 169 add → Apply → No-Op → 7/7 Live-Tests → Destroy → CLEAN | RIS-Report + `evidence/RIS-MO-RC-01-2026/*` |
| G13 | SQS → Worker → DynamoDB | ✅ VERIFIED AWS E2E | `PENDING → CONFIRMED`, Queue leer | `08-live-roundtrip.txt` |
| G14 | Terraform Apply / No-Op / Destroy | ✅ VERIFIED AWS E2E (Consumer-Konto) | Exit 0 / Exit 0 / Exit 0, Restbestand CLEAN | `04-…`, `05-…`, `09-…` |
| G15 | Code-Identität Pin ↔ Release | ✅ VERIFIED LOCAL | `git diff -w 1dbb0cb..main -- <code>` leer | P06 §4 |
| G16 | Privacy (Produktion) | ⛔ **BLOCKED** | Secret-Management/Rotation fehlt | `docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-*` |
| G17 | Multi-Account-Produktionsreife | ⚠️ NOT VERIFIED | nur ein Testkonto (`262370457690`) belegt | bewusst außerhalb RC-Scope |
| G18 | Tag / GitHub-Release | ⏳ NOT EXECUTED | menschliche Freigabe (P09) | — |

**Legende:** VERIFIED LOCAL = lokal real ausgeführt · VERIFIED AWS E2E = durch
RIS-Evidence belegt · NOT VERIFIED/NOT EXECUTED = nicht durchgeführt · BLOCKED = Voraussetzung fehlt.

## 2. Erneut ausgeführt am 2026-10-31 (keine AWS-Aufrufe)

```
cd lambda && python3 -m compileall -q src tests && PYTHONPATH=src python3 -m unittest discover -s tests
  → Ran 76 tests ... OK
python3 -m unittest module_builder.tests.test_module_builder
  → Ran 90 tests ... OK
python3 -m unittest installer.tests.test_installer
  → Ran 81 tests ... OK
cd terraform && terraform init -backend=false && terraform validate && terraform fmt -check -recursive
  → init exit 0 · Success! The configuration is valid. · fmt-check exit 0
```

Nicht ausgeführt (bewusst): `terraform plan/apply/destroy` gegen AWS, RIS-Retests.

## 3. Offene Findings

| ID | Finding | Schwere für RC | Schwere für Produktion |
|---|---|---|---|
| F-01 | Explizit gesetzter Boundary-ARN nicht cross-account-portabel (Default `null`) | keiner | Betriebsfrage/Consumer |
| — | Privacy-Produktivbetrieb ohne Secret-Management | keiner | **BLOCKER** |
| — | Multi-Account-Reife nur exemplarisch (1 Testkonto) | keiner | offen |
| — | RIS-Pin `1dbb0cb` statt Release-Commit | keiner (code-identisch) | kosmetisch |
| — | EXTERNAL-Cognito: id/arn/group = `null`; Migration nicht automatisiert | keiner | dokumentierte Entscheidung |
| — | Builder ohne Backend (Consumer konfiguriert selbst) | keiner | Betriebshinweis |
| — | Collision-Ownership namensbasiert (Phase 2 offen); S3 `mays-orders-ci-artifacts-dev` ungeklärt | keiner | offen |

## 4. Release-Artefakte

| Artefakt | Pfad |
|---|---|
| Release-Dossier (Markdown) | `docs/release/RELEASE-v0.5.0-rc.3.md` |
| Release-Dossier (PDF) | `docs/release/RELEASE-v0.5.0-rc.3.pdf` |
| Gate-Report | `docs/release/RELEASE-GATES-v0.5.0-rc.3.md` |
| Release Notes (Kurzform) | `docs/RELEASE_NOTES.md` |
| Changelog-Eintrag | `docs/CHANGELOG.md` |
| Packaging-Bericht | `docs/reports/MO-RC3-P07-P08-RELEASE-PACKAGING.md` |
| RC.3-Verifikation | `docs/reports/MO-RC3-P00…P06-*.md` |
| RIS-Evidence | RIS-Repo: `docs/reports/RIS-MO-RC-01-CONSUMER-ACCEPTANCE.md` + `evidence/RIS-MO-RC-01-2026/` |
| Lambda-Artefakt | `lambda/dist/lambda.zip` (`b1018a3b…`) |

## 5. Entscheidung

| Dimension | Entscheidung |
|---|---|
| **Release Candidate v0.5.0-rc.3** | **GO** — alle RC-Gates PASS/VERIFIED, Code-Identität zum E2E-Stand belegt |
| **Produktionsfreigabe** | **BLOCKED** — Privacy/Secret-Management; Multi-Account-Reife nicht belegt |

## 6. Empfohlene Tag- und Release-Kommandos (menschlich, P09)

```bash
# im Repo maynowak/mays-order-aws auf main, Working Tree clean
RELEASE_COMMIT="$(git rev-parse HEAD)"     # Packaging-Commit (dieser Report)
printf '%s\n' "$RELEASE_COMMIT"            # zur Protokollierung

git tag -a v0.5.0-rc.3 "$RELEASE_COMMIT" -m "v0.5.0-rc.3 — Module Builder & RIS Integration"
git push origin v0.5.0-rc.3

gh release create v0.5.0-rc.3 \
  --title "v0.5.0-rc.3 — Module Builder & RIS Integration" \
  --notes-file docs/release/RELEASE-v0.5.0-rc.3.md \
  --prerelease \
  --target main
```

**Hinweis:** Tag und Release sind in P07/P08 **nicht** erstellt worden. Sie erfordern die
ausdrückliche menschliche Freigabe für P09.
