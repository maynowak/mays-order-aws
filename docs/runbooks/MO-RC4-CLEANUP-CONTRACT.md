# Runbook — RC4 Test-Stack: Destroy- und Cleanup-Vertrag

**Gültig ab:** MO-RC4 (P02I-E2B)
**Zielgruppe:** Betrieb / Deployment-Verantwortliche mit AWS-Schreibrechten
**Status:** Vertrag dokumentiert · **kein Cleanup automatisiert**
**Letzte Prüfung:** 2026-11-02 (Code `86627e2`)

> **Grundregel:** `terraform destroy` ist **kein** Cleanup-Nachweis. Der Rückbau ist ein
> mehrstufiger, freigabepflichtiger Vorgang. Keine Löschung erfolgt „nach Namen" oder
> „nach Präfix" — die einzige Quelle ist der Terraform-State des Projekts.
>
> Dieses Runbook beschreibt den Vertrag. Es führt nichts aus.

---

## 1. Lifecycle (verbindliche Reihenfolge)

```text
Preflight  →  Plan  →  Review  →  Apply  →  E2E  →  Destroy-Plan  →
Destroy-Approval  →  Destroy-Apply  →  Residual-Audit  →  State-Cleanup  →  Final Verify
```

| Schritt | Artefakt / Nachweis |
|---|---|
| Preflight | `/tmp/opencode/MO-RC4-P02I-E2A-AWS-TARGET-PREFLIGHT.md` |
| Plan | `*.tfplan` + `*.manifest.json` (Account/Projekt/Region/Workspace/Backend/sha256) |
| Review | Plan-Summary + Policy-Gate + P02I-D-STOP-Liste |
| Apply | nur nach separater menschlicher Freigabe (`ALLOW_AWS_OPERATIONS=true`, `DRY_RUN=false`, `--yes`) |
| E2E | Testprotokoll im Run-Verzeichnis |
| Destroy-Plan | eigener `plan-destroy`-Lauf mit Manifest (Operation `destroy`) |
| Destroy-Approval | menschliche Freigabe, nie implizit |
| Destroy-Apply | `destroy --plan <artifact>` (Manifest wird geprüft) |
| Residual-Audit | `state list` **muss leer** sein; sonst Abbruch |
| State-Cleanup | nur nach eigener Freigabe, nur `env:/<project>/terraform.tfstate` |
| Final Verify | AWS-Leseprüfung + State-Prüfung |

---

## 2. Geschützte Ressourcen (niemals Teil eines RC4-Cleanups)

| Ressource | Grund |
|---|---|
| S3 `mays-orders-tfstate-central-240571105849` | gemeinsames Terraform-Backend aller Workspaces |
| DynamoDB `mays-orders-terraform-locks` | gemeinsame Lock-Tabelle (aktuell **fehlt** sie; Wiederherstellung separat) |
| RIS-State (`mays-ris-tf-state-dev`, `mays-ris-tf-lock`) | RIS-Eigentum |
| RIS-MO-Stack (`ris-dev-mays-orders-*`) | RIS-Eigentum, produktiv genutzt |
| CI-Rollen `mays-orders-development-ci-*` | CI-Infrastruktur |
| Pipelines `mays-orders-development-ci-cd`, `directAWSGit-Mays-Order-AWS` | CI/CD, nicht Teil des RC4-Stacks |
| Fremde Workspaces im gemeinsamen Bucket (`env:/mays-ris-*`, `env:/test-*`, `env:/mays-orders/*`) | nicht unser Eigentum |

Die Liste ist im Code als `PROTECTED_RESOURCES` / `PROTECTED_STATE_KEYS`
(`installer/core/cleanup_contract.py`) hinterlegt und wird getestet.

---

## 3. State-Identität (fail-closed)

Der Destroy-Pfad prüft vor dem Apply:

1. Backend-Vertrag lesbar und S3 (`terraform/backend.tf`).
2. State-Key = `env:/<project_name>/terraform.tfstate` — **exakt**.
3. Kein geschützter Key (`env:/mays-orders/...`, Default-Key, fremde Projekte).
4. Plan-Manifest (falls vorhanden): Account, Projekt, Environment, Region,
   Workspace, Backend, Operation `destroy`, sha256.

Abweichung ⇒ **Abbruch** (kein Apply).

---

## 4. Residual-Audit (Pflicht)

Nach dem Destroy führt der Installer `terraform state list` aus:

- **0 Ressourcen** → Cleanup-Vertrag erfüllt (State bleibt zunächst bestehen).
- **> 0 Ressourcen** → Abbruch mit Auflistung der Adressen. Kein automatisches
  Nachlöschen, kein `state rm`, kein Import.

Manuell zusätzlich zu prüfen (nur lesend), weil nicht jede Ressource im State
auftauchen muss:

| Bereich | Prüfung |
|---|---|
| DynamoDB | Tabelle `mays-orders-rc4` |
| Lambda | `mays-orders-rc4-handler`, `-sqs-worker`, `-cognito-backup-lambda` |
| SQS | `mays-orders-rc4-orders-queue`, `-dlq` |
| Cognito | Pool `mays-orders-rc4-users` |
| API Gateway | `mays-orders-rc4-api` |
| IAM | `mays-orders-rc4-*`-Rollen/Policies |
| Scheduler | `mays-orders-rc4-orders-*` |
| CloudWatch | Alarme/Dashboard `mays-orders-rc4-*` |
| CloudTrail | Trail `mays-orders-rc4-trail` |
| S3 | `mays-orders-rc4-cloudtrail-*`, `mays-orders-rc4-cognito-backup-*` inkl. Objektversionen |
| KMS | keine Ressource im Stack (falls künftig: Key/Alias prüfen) |
| Logs | `/aws/lambda/mays-orders-rc4-*` |

---

## 5. State-Cleanup (nur mit separater Freigabe)

Zulässig **ausschließlich**:

```text
s3://mays-orders-tfstate-central-240571105849/env:/mays-orders-rc4/terraform.tfstate
```

Voraussetzungen (alle):

1. Destroy erfolgreich abgeschlossen.
2. `state list` = 0 Ressourcen.
3. Residual-Audit ohne Treffer.
4. State-Identität bestätigt (exakter Key, richtiger Account/Region).
5. Gesonderte, dokumentierte Cleanup-Freigabe.

Verboten: Löschen des Buckets, der Lock-Tabelle, fremder State-Keys oder des
gesamten `env:/`-Präfixes.

---

## 6. Kein Präfix-basiertes Löschen

Der Installer enthält **keine** AWS-Delete-Aufrufe und **keine**
Namenspräfix-Schleifen. Löschungen entstehen ausschließlich über den
Terraform-Destroy-Plan aus dem Projekt-State. Diese Regel wird durch
`installer/tests/test_cleanup_contract.py` abgesichert.

---

## 7. Bekannte offene Voraussetzungen

| Voraussetzung | Status |
|---|---|
| Lock-Tabelle `mays-orders-terraform-locks` | **fehlt** (2026-10-18 gelöscht) → Remote-Plan/Destroy derzeit nicht möglich |
| Backend-Entscheidung (DynamoDB-Lock vs. `use_lockfile`) | offen, siehe P02I-E2B-Report §9 |
| CI/CD für RC4 | **blockiert** (Artefakt-Bucket fehlt, Pipeline auf `mays-orders` gepinnt) |
| Privacy/Secret-Management | **BLOCKED** (Produktion) |
