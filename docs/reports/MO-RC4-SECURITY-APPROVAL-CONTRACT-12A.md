# MO-RC4-SECURITY-APPROVAL-CONTRACT-12A

**Approval Context Binding — Vertragsanalyse und Zielarchitektur**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `b3bcc3cf3794917dd58323f55e2baf0c63c4957a`
**Modus:** Read-only-Analyse; keine Produktcodeänderung, keine AWS-/Cognito-/HTTP-
Aufrufe, keine Terraform-Prozesse, kein Deploy/Destroy, kein Push/Merge.

**Status der vorgeschlagenen Architektur: `PROPOSED — NOT APPROVED`**

---

## 1. Executive Summary

Der bestehende Installer schützt Deploy und Destroy durch eine **Kette von
Vorprüfungen** (Plan-Manifest, Plan-Kontext, Version, State-Baseline,
Backup-Gate, Upgrade-Safety, Policy Gate) und eine **interaktive
Freigabe**. Die Freigabe selbst ist jedoch **kein dauerhaftes, an Plan,
Workspace und Operation gebundenes Evidence-Objekt**.

Kernbefunde:

- `ApprovalContext` existiert im Code, wird aber von der CLI **nicht**
  verwendet; die CLI fragt direkt `input()` ab oder überspringt den Prompt
  mit `--yes`.
- `ApprovalGate` ist nach der 11A-Korrektur instanziierbar, seine
  Safety-Check-Methoden sind jedoch überwiegend Platzhalter (`return True`).
  Die eigentlichen Prüfungen liegen in `installer/cli/main.py`.
- Plan und Workspace werden **vor** dem Approval-Prompt geprüft, aber nach
  dem Prompt nicht erneut gehasht/gebunden.
- Eine Freigabe besitzt heute **keine** Approval-ID, Ablaufzeit,
  Wiederverwendungsregel, Plan-Fingerprint-Bindung oder Audit-Evidence.
- `--yes` ist eine lokale Prompt-Unterdrückung, keine eigenständige
  Plan-/Workspace-Autorisierung.
- Das bestehende Plan-Manifest bindet eine Plan-Datei an Deployment-ID,
  Operation, Workspace, Backend und SHA-256. Es ist eine **starke
  Vorprüfung**, aber kein Approval-Vertrag.

**Empfehlung:** Ein separater, versionierter **ApprovalEvidence-Vertrag V2**
mit expliziter Bindung an Deployment-ID, Operation, Workspace,
Plan-Fingerprint und Ablaufzeit; Verifikation unmittelbar vor
`terraform apply`/Destroy. Keine automatische Aufwertung alter,
ungebundener Freigaben. SEC-06 wird damit als neue Vertragsentscheidung
vorgeschlagen, nicht als bereits implementiert dargestellt.

---

## 2. Ausgangsbasis und Git-Identität

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `b3bcc3cf3794917dd58323f55e2baf0c63c4957a` |
| 10A–10D | VERIFIED |
| 10E-A | PARTIAL — Defekte SEC-01…SEC-06 |
| 11A | SEC-01…SEC-05 korrigiert; SEC-06 offen |
| Working Tree | CLEAN |
| Testbaseline 11A | Installer 669, Builder 128, Lambda 337, E2E 16 = **1.150 PASS** |
| Live-E2E | 4 BLOCKED, nicht Teil der lokalen Regression |

11A-Korrekturen sind im aktuellen Code enthalten:
`ApprovalGate`-Duplikat entfernt, Deployment-/Planvalidierung korrigiert,
Plan-Match mit Fingerprint, Workspace-Root explizit.

---

## 3. Bestehender Approval-Datenvertrag

### 3.1 Tatsächliche Schnittstellen

| Baustein | Datei | Tatsächliche Rolle |
|---|---|---|
| `ApprovalContext` | `installer/core/approval.py` | Datenklasse; von der CLI **nicht** verwendet |
| `ApprovalGate` | `installer/core/approval.py` | öffentliche Sicherheitsklasse; `evaluate()` vorhanden; Check-Methoden Platzhalter |
| `verify_approval_context()` | `installer/core/approval.py` | prüft Pflichtfelder, Operation und `skip_approval` |
| `FailClosedGuard` | `installer/core/fail_closed.py` | Plan-/Deployment-/Lock-/AWS-State-Prüfungen |
| `FailClosedValidator` | `installer/core/fail_closed.py` | Deployment-, Plan- und AWS-Kontextvalidierung |
| `WorkspaceIntegrity` | `installer/core/workspace.py` | Pfadgrenzen/Workspace-Root |
| `PlanManifest` | `installer/core/plan_manifest.py` | bindet Plan-SHA-256, Deployment, Operation, Workspace, Backend |
| `_verify_plan_manifest` | `installer/cli/main.py` | reale Vorprüfung im CLI |
| `_verify_version_binding`, `_verify_state_baseline`, `_verify_backup_gate`, `_verify_upgrade_readiness`, `_enforce_upgrade_safety` | `installer/cli/main.py` | weitere Vorprüfungen |
| `TerraformRunner.verify_plan_integrity` / `verify_plan_context_match` | `installer/terraform/runner.py` | erneute Plan-/Kontextprüfung vor dem Apply |
| Approval-Prompt | `installer/cli/main.py` | `input(...)` bzw. `--yes`; **kein** Evidence-Objekt |

### 3.2 Datenmodell heute

`ApprovalContext`:

```text
deployment_id : str
operation     : str        # deploy|destroy
plan_file     : str
run_id        : str
auto_approve  : bool       # --yes
skip_approval : bool
```

Nicht enthalten: Workspace, Plan-SHA-256, Plan-Version, Approval-ID,
`approvedAt`, `expiresAt`, `approvedBy`, Evidence-Referenz, Signatur,
Replay-/Verbrauchsstatus.

`PlanManifest` enthält dagegen bereits:

```text
deployment_id, operation, region, workspace, backend, state_key,
plan_file, plan_sha256, plan_size, variables, version fields,
state_baseline, drift/noop/readiness, backup fields
```

Das Manifest ist eine **Plan-Identitätsbindung**, aber kein Nachweis, dass
ein Mensch/Operator genau diesen Plan freigegeben hat.

### 3.3 A2 — Eigenschaftsmatrix

| Eigenschaft | Im Modell | Bei Erstellung validiert | Vor Ausführung erneut geprüft | Bewertung |
|---|---|---|---|---|
| Deployment-ID | `ApprovalContext` ja; CLI-Kontext ja | CLI: Deployment-Kontext | Manifest/Plan-Kontext | vorhanden, aber nicht Approval-gebunden |
| Operation | `ApprovalContext.operation`; Manifest | CLI-Befehl + Manifest | Manifest + Destroy-Plan-Check | vorhanden, nicht als Evidence |
| Workspace | **nicht** in `ApprovalContext`; CLI/Manifest ja | Manifest `verify` | Manifest + Runner-Workspace | nicht Approval-gebunden |
| Plan-Fingerprint | **nicht** in `ApprovalContext`; Manifest `plan_sha256` | Manifest-Erstellung | Manifest + `verify_plan_integrity` | nicht Approval-gebunden |
| Plan-Version | **nicht** in `ApprovalContext`; PlanMetadata/Manifest | Manifest-Version | Version-Binding | nicht Approval-gebunden |
| Freigabezeitpunkt | **nicht vorhanden** | — | — | fehlt |
| Ablaufzeitpunkt | **nicht vorhanden** | — | — | fehlt |
| Freigabeidentität | **nicht vorhanden** | — | — | fehlt |
| Wiederverwendung | **keine Regel** | — | — | unbegrenzt innerhalb CLI-Aufruf |
| Approval-ID | **nicht vorhanden** | — | — | fehlt |
| Audit-Evidence | Run-Kontext/Manifest, **keine Approval-Evidence** | — | — | unvollständig |

### 3.4 Wichtige Ist-Aussage

`ApprovalGate` wird in der CLI **nicht** aufgerufen. Sie wird lediglich von
`installer/cli/gui.py` importiert und dort nicht verwendet. Die reale
Freigabeentscheidung ist:

```text
if not parsed.yes:
    response = input("Proceed with deployment? [y/N]: ")
    if response not in ("y", "yes"):
        return 0
```

Damit ist `--yes` heute faktisch eine vollständige lokale
Invocation-Freigabe, sofern alle vorgelagerten Prüfungen bestanden wurden.
Es ist **keine** an einen Plan-/Workspace-Fingerprint gebundene Freigabe.

---

## 4. Tatsächliche Aufrufkette

### 4.1 Deploy

```text
InstallerCLI.run()
  -> InstallationContext + RunDirectory
  -> _cmd_deploy()
     -> context.validate_aws_context()
     -> allow_aws_operations check
     -> context.get_deployment_context()
     -> PlanDiscovery (falls kein --plan)
     -> _verify_plan_manifest(... DEPLOY, require_manifest=True)
          -> PlanManifest.load()
          -> manifest.verify(plan, deployment_id, region, workspace, backend, operation)
          -> sha256_file(plan) == manifest.plan_sha256
     -> _verify_version_binding()
     -> _verify_state_baseline()
     -> _verify_backup_gate()
     -> _verify_upgrade_readiness()
     -> _enforce_upgrade_safety()
     -> PlanDiscovery.validate_plan_context()
     -> ggf. Kopie des Plans nach terraform/
     -> runner.verify_plan_integrity()
     -> runner.verify_plan_context_match()
     -> PlanMetadata.parse_filename()
     -> Plan-Summary + evaluate_plan_safety()
     -> Policy Gate (falls nicht dry-run)
     -> Approval-Prompt / --yes
     -> runner.apply(Path.cwd() / parsed.plan)
```

### 4.2 Destroy

Analog, mit folgenden Abweichungen:

- `_verify_plan_manifest(... DESTROY, require_manifest=False,
  allow_legacy_manifest=True)` erlaubt Legacy-Manifeste ohne
  Versionsbindung.
- `_verify_destroy_plan()` prüft über `terraform show -json`, dass es
  tatsächlich ein Destroy-Plan ist.
- Cleanup-Contract prüft das State-Ziel.
- Approval-Prompt `Proceed with DESTRUCTION?`, dann
  `runner.destroy(...)` (intern `terraform apply <plan>`).

### 4.3 Übergänge, Daten und Prüfungen

| Übergang | Funktion | Daten | Sicherheitsentscheidung | Fehlerverhalten | Tests |
|---|---|---|---|---|---|
| CLI → Context | `run`, `_create_context` | Profil, Region, Projekt, Workspace | Workspace = Projektname; `default` verboten | ValueError/Fail | `test_installer`, `test_parallel_isolation` |
| Context → Plan | `_cmd_plan` | Plan-Datei, Manifest, Run-ID | Plan muss erzeugt/gefunden werden | Return 1 | Plan-/Manifest-Tests |
| Plan → Integrity | `_verify_plan_manifest`, `PlanManifest.verify` | SHA-256, Deployment-ID, Operation, Workspace, Backend | Bindung an Manifest | Return false | `test_plan_manifest`, Upgrade-Tests |
| Plan → Version | `_verify_version_binding` | Ziel-/Ist-Version, Commit, Dirty | Versionsbindung | Return false | `test_version_binding` |
| Plan → State | `_verify_state_baseline` | Serial, Lineage, Fingerprint | State-Drift blockiert | Return false | Drift-/State-Tests |
| Plan → Backup | `_verify_backup_gate` | Backup-ARN, Evidence, State-Fingerprint | Upgrade-Backup verifiziert | Return false | Backup-Gate-Tests |
| Plan → Safety | `_enforce_upgrade_safety`, `evaluate_plan_safety` | Plan-JSON, Findings | Delete/Replace blockiert | Return 1 | Upgrade-Safety-Tests |
| Plan → Approval | `input()` / `parsed.yes` | **keine** Plan-/Workspace-Bindung | lokal ja/nein | Return 0 bei nein | 10A/10E-Tests |
| Approval → Apply | `runner.apply` | `parsed.plan` | keine erneute Approval-Prüfung | TerraformResult | 10A mocked |

**Zentrale Lücke:** Der Approval-Prompt liegt **nach** den Vorprüfungen,
aber es gibt keine erneute Plan-/Workspace-/Approval-Bindung unmittelbar
vor `apply`/`destroy`. Zudem verwendet `apply` `parsed.plan`, während die
Integritätsprüfung ggf. eine Kopie `terraform_plan_file` geprüft hat.

---

## 5. Bedrohungsmodell

| ID | Szenario | Heutige Wirkung | Risiko |
|---|---|---|---|
| SEC06-T01 | Plan-Swap nach Freigabe | Manifest-Hash wird vor dem Prompt geprüft; keine erneute Prüfung nach Prompt; `apply` nutzt Originalpfad | **HOCH** — TOCTOU/Dateipfad |
| SEC06-T02 | Workspace-Swap | Manifest und `TerraformRunner` prüfen Workspace vor Ausführung; Approval selbst ungebunden | **MITTEL** — bei gleicher Invocation geschützt, nicht als Evidence |
| SEC06-T03 | Operation-Swap (APPLY → DESTROY) | Getrennte CLI-Befehle und Manifest-Operation; keine Approval-Evidence | **MITTEL** — Invocation-getrennt, aber kein Nachweis |
| SEC06-T04 | Deployment-Swap | Deployment-Kontext/Manifest prüfen; Approval ungebunden | **MITTEL** |
| SEC06-T05 | Replay | Keine Approval-ID, Ablaufzeit oder Verbrauchsmarkierung; `--yes` beliebig wiederholbar | **HOCH** bei Einführung persistenter Evidence ohne Regeln |
| SEC06-T06 | TOCTOU | Hash/Prüfung vor Prompt; danach keine Revalidierung; Apply-Pfad kann vom geprüften Pfad abweichen | **HOCH** |
| SEC06-T07 | Manipulierte Approval-Evidence | Heute keine Evidence-Datei; zukünftige lokale Datei wäre manipulierbar | **MITTEL** — Designfrage |
| SEC06-T08 | Legacy-Fallback | Destroy erlaubt Legacy-Manifest; Approval ohne Bindung würde bei naiver Migration als gültig gelten | **HOCH** — Muss DENY sein |
| SEC06-T09 | `--yes`-Fehlinterpretation | `--yes` überspringt nur Prompt, wird aber als vollständige Freigabe wahrgenommen | **HOCH** — Trust-Boundary unklar |

**Keine dieser Aussagen ist ein Nachweis, dass ein Angriff erfolgreich war.**
Es handelt sich um Vertrags-/Designlücken.

---

## 6. Zielvertrag — ApprovalEvidence V2 (Vorschlag)

### 6.1 Empfohlenes Datenmodell

```json
{
  "schemaVersion": 2,
  "approvalId": "apr_<opaque-unique-id>",
  "deploymentId": "240571105849:mays-orders:test",
  "operation": "APPLY",
  "workspace": "mays-orders",
  "planFingerprint": "sha256:<64-hex>",
  "planFormatVersion": "1.2",
  "approvedAt": "2026-11-11T21:00:00Z",
  "expiresAt": "2026-11-11T21:30:00Z",
  "approvedBy": "<trusted-local-or-ci-identity>",
  "approvalMethod": "interactive|ci-approval|signed-evidence",
  "evidenceReference": "run/<run-id>/approval.json",
  "nonce": "<unique-nonce>",
  "signature": "<optional; only if trust key exists>"
}
```

### 6.2 Pflichtfelder

| Feld | Pflicht | Kanonisierung / Prüfung |
|---|---|---|
| `schemaVersion` | ja | exakt `2`; unbekannt → DENY |
| `approvalId` | ja | eindeutig, nicht wiederverwendbar |
| `deploymentId` | ja | `DeploymentId.parse`/kanonische Form |
| `operation` | ja | `APPLY` oder `DESTROY` |
| `workspace` | ja | exakt `terraform_workspace`; nie leer/`default` |
| `planFingerprint` | ja für planbasierte Operationen | SHA-256 über die **exakt ausgeführte Plan-Datei** |
| `approvedAt` | ja | UTC, nicht in der Zukunft |
| `expiresAt` | ja | UTC, kurzlebig; Ablauf → DENY |
| `approvedBy` | ja | vertrauenswürdige Identität, keine PII |
| `approvalMethod` | ja | definierter Vertrauensweg |
| `evidenceReference` | ja für Audit | unveränderliche Run-Referenz |
| `nonce` | ja | Replay-Schutz |
| `signature` | abhängig vom Trust-Modell | ohne Key-Infrastruktur **nicht** als kryptografisch authentisch bezeichnen |
| `planFormatVersion` | optional | aus Plan-JSON, nur Diagnose |

`planFingerprint` wird über die **rohen Plan-Bytes** berechnet
(`sha256_file`), nicht über eine nachträglich serialisierte JSON-Darstellung.
Wenn ein Plan-JSON verwendet wird, muss zusätzlich ein separater
`planJsonFingerprint` definiert werden; beide dürfen nicht vermischt werden.

### 6.3 C1 — Sicherheitsinvarianten

| ID | Invariante | Technischer Prüfpunkt | Fehlerverhalten | Test | Bestehende Zuordnung |
|---|---|---|---|---|---|
| INV-01 | Deployment-ID stimmt | Evidence vs. `DeploymentContext.deployment_id` | DENY | SEC06-02 | Manifest `verify` |
| INV-02 | Operation stimmt | Evidence vs. `PlanOperation` des Aufrufs | DENY | SEC06-03 | Manifest/CLI |
| INV-03 | Workspace stimmt | Evidence vs. `context.terraform_workspace` | DENY | SEC06-04 | Manifest/Runner |
| INV-04 | Plan-Fingerprint stimmt | Evidence vs. `sha256_file(plan)` | DENY | SEC06-05 | Manifest/`verify_plan_integrity` |
| INV-05 | Fehlende Bindungsdaten | Pflichtfelder/Format | DENY | SEC06-06 | neu |
| INV-06 | Ungültig/abgelaufen | Zeit + Status | DENY | SEC06-07 | neu |
| INV-07 | Planänderung | erneuter Hash unmittelbar vor Ausführung | DENY | SEC06-10 | teilweise Manifest |
| INV-08 | Keine unkontrollierte Wiederverwendung | Approval-ID/Nonce/Verbrauch | DENY | SEC06-12 | neu |
| INV-09 | Prüfung unmittelbar vor Ausführung | Gate direkt vor `runner.apply/destroy` | DENY | SEC06-11 | neu |
| INV-10 | Fehler → DENY | Exception/ungültige Rückgabe | DENY | SEC06-11 | FailClosedGuard |

### 6.4 C2 — Vertrauensmodell

| Stufe | Bedeutung | Bewertung |
|---|---|---|
| 1. `--yes` | lokale Prompt-Unterdrückung | **keine** eigenständige Evidence, keine Planbindung |
| 2. Operator-Prompt | bestätigte lokale Zustimmung | an aktuelle Invocation gebunden, nicht persistent |
| 3. ApprovalEvidence | technisch prüfbare Datei/Objekt | nur so vertrauenswürdig wie Herkunft/Signatur |
| 4. Plan-gebundene Evidence | Evidence + exakter Plan-Fingerprint | Ziel für Apply/Destroy |

Ohne Signatur/Trust-Key ist eine lokale Evidence-Datei **integritäts- und
zugriffsgeschützt**, aber nicht kryptografisch nicht-abstreitbar. Diese
Grenze muss im Vertrag ausdrücklich stehen. `--yes` darf nicht automatisch
zu Stufe 3/4 aufgewertet werden.

---

## 7. Migrationsvarianten

| Variante | Sicherheit | Aufwand | Testbarkeit | Rückwärtskompatibilität | CLI | Gespeicherte Freigaben | Deployments | Audit | Rollback |
|---|---|---|---|---|---|---|---|---|---|
| A — `ApprovalContext` erweitern | mittel; Kontext bleibt flüchtig | niedrig | gut | hoch, aber Felder optional = Legacy-Risiko | klein | keine persistente Evidence | keine Änderung | schwach | einfach, aber unsicherer Fallback |
| B — versionierter Approval-Vertrag V2 | hoch bei Pflichtfeldern | mittel | sehr gut | kontrolliert; alte ungebundene = DENY | neues `--approval-file`/`approve` | neue V2-Datei; V1 explizit legacy | unverändert bis nächste Mutation | gut | V2 deaktivieren, keine Downgrade-Freigabe |
| C — separater Approval-Evidence-Vertrag | hoch; klare Trennung | mittel–hoch | sehr gut | V2-Datei separat; Legacy DENY | neuer Dienst/Modul | eigenes `ApprovalEvidence` | unverändert | sehr gut | Modul deaktivieren, DENY bleibt |

**Empfehlung:** **Variante C mit Schema-Version 2** — ein separates
`ApprovalEvidence`-Modul/Artefakt, das die Bindung prüft, ohne
`ApprovalContext` mit flüchtiger UI-Logik zu überladen. Das entspricht
inhaltlich B, trennt aber Verantwortlichkeit und Audit klar.

### D1 — Legacy-Approvals

- Bestehende `ApprovalContext`-Objekte ohne `planFingerprint`/`workspace`
  sind **keine** gültigen V2-Freigaben.
- Keine automatische Aufwertung; **DENY**.
- Erneute Freigabe mit aktuellem Plan/Fingerprint erforderlich.
- Destroy-Legacy-Manifeste bleiben nur für die Planprüfung tolerant; die
  Approval-Evidence muss trotzdem V2 sein.

### D2 — Bestehende Deployments

- Bereits bereitgestellte Infrastruktur wird nicht angefasst.
- Nur zukünftige APPLY/DESTROY benötigen V2.
- Lesende Operationen (`state`, `output`, `identity`, `plan` mit
  `-backend=false`) bleiben unverändert.
- Keine automatische Migration von Freigaben.

### D3 — Rollback

- V2-Gate kann deaktiviert werden, aber **nicht** auf ungebundene
  Approval-Evidence zurückfallen.
- Bei Rollback bleibt die sichere Alternative: keine Mutation ohne neue
  V2-Freigabe, oder Betrieb stoppen.
- Kein automatisches Downgrade auf `--yes` als Vollfreigabe.

---

## 8. Teststrategie für 12B

| Test-ID | Szenario | Erwartung |
|---|---|---|
| SEC06-01 | Passender Deployment-/Ops-/Workspace-/Fingerprint-Kontext | ALLOW |
| SEC06-02 | Falsche Deployment-ID | DENY |
| SEC06-03 | Falsche Operation (APPLY vs. DESTROY) | DENY |
| SEC06-04 | Falscher Workspace | DENY |
| SEC06-05 | Falscher Plan-Fingerprint | DENY |
| SEC06-06 | Fehlender Fingerprint/fehlende Pflichtfelder | DENY |
| SEC06-07 | Abgelaufene Freigabe | DENY |
| SEC06-08 | Manipulierte/ungültige Evidence | DENY |
| SEC06-09 | Legacy-Approval ohne Bindung | DENY |
| SEC06-10 | Planänderung nach Freigabe | DENY |
| SEC06-11 | Exception/ungültige Rückgabe im Approval-Gate | DENY |
| SEC06-12 | Wiederverwendung/Replay | gemäß beschlossenem Vertrag; Default DENY |

Zusätzliche Testklassen:

- **Unit:** Parser, Kanonisierung, Zeit-/Ablaufprüfung, Fingerprint,
  Signaturstatus, Pflichtfelder, unbekannte Schema-Version.
- **CLI-Komponente:** `deploy`/`destroy` mit Fake-Runner; kein
  `apply`/`destroy` bei DENY; gültige Evidence genau einmal.
- **TOCTOU:** Plan nach Approval verändern; Gate vor Ausführung erneut
  hashen; `apply` darf nur geprüfte Datei verwenden.
- **Replay:** gleiche `approvalId`/Nonce zweimal; Verbrauchsmarkierung.
- **Legacy:** V1/ohne Bindung → DENY, keine stille Aufwertung.
- **`--yes`:** ohne V2-Evidence → DENY; mit gültiger Evidence → nur
  Prompt überspringen.
- **Mutationen:** Bindung entfernen, Ablauf entfernen, Fingerprint entfernen,
  Fehlerpfad neutralisieren; jeweils zuständiger Test FAIL.
- **Regression:** Installer/Builder/Lambda/E2E-Harness; keine Live-E2E.
- **Coverage:** ApprovalEvidence-Modul und CLI-Gate separat messen; keine
  künstlichen Ziele.

---

## 9. Entscheidungsvorlage

### 9.1 EXISTING

- Vorprüfungen: PlanManifest, Version, State, Backup, Safety, Policy.
- `ApprovalContext` mit Deployment-ID, Operation, Plan-Dateiname, Run-ID,
  `auto_approve`; nicht CLI-integriert.
- `ApprovalGate` mit Platzhalter-Checks; nicht im CLI-Pfad.
- `--yes` überspringt den Prompt; keine persistente Approval-Evidence.
- Plan-Manifest bindet SHA-256, Deployment, Operation, Workspace.

### 9.2 PROPOSED

- Separates `ApprovalEvidence` V2 (Schema 2) mit Pflichtfeldern aus
  Abschnitt 6.
- Neues `approve`-Kommando oder `--approval-file`; Evidence wird im
  Run-Verzeichnis gespeichert.
- `deploy`/`destroy` prüfen Evidence **unmittelbar vor** `apply`/`destroy`;
  bei Fehler/fehlender Evidence: DENY.
- `--yes` bleibt reine Prompt-Unterdrückung; ohne V2-Evidence keine
  Mutation.
- Plan-Fingerprint wird aus derselben Datei berechnet, die ausgeführt wird;
  Pfadkonsistenz ist Pflicht.
- Ablaufzeit, Nonce, Approval-ID und Einmalverbrauch.
- Legacy: DENY; erneute Freigabe erforderlich.

### 9.3 DECISION REQUIRED

1. **Trust-Modell:** Reicht lokale OS-/CI-Identität, oder ist eine
   Signatur mit separatem Key (KMS/HSM/CI-Secret) erforderlich?
2. **`--yes`-Semantik:** Darf `--yes` mit gültiger V2-Evidence den Prompt
   überspringen, oder bleibt ein separater `approve`-Schritt Pflicht?
3. **Ablaufdauer:** z. B. 15/30/60 Minuten; wer legt sie fest?
4. **Replay-Speicher:** Wo wird der Verbrauch atomar markiert (Run-Datei,
   Lock, externer Store)?
5. **Planformat:** roher Terraform-Plan vs. Plan-JSON; welcher Fingerprint
   ist der kanonische?
6. **Interaktive Freigabe:** erzeugt sie persistente Evidence oder nur
   flüchtige Invocation-Evidence?
7. **CI-Migration:** Wie werden bestehende `--yes`-Pipelines auf
   `--approval-file`/`approve` migriert?
8. **Legacy-Destroy:** Wird Legacy-Manifest weiterhin akzeptiert, aber nur
   mit V2-Approval?
9. **Evidence-Aufbewahrung:** Wie lange, wo, mit welchen Zugriffsrechten?
10. **Signatur-/Key-Rotation:** Falls Signatur: Key-Owner, Rotation,
    Revocation.

Ohne diese Entscheidungen darf 12B nicht implementiert werden.

---

## 10. Offene Fragen

- Ist `--yes` in CI als menschliche Freigabe akzeptiert oder nur als
  technische Prompt-Unterdrückung?
- Welche Identität ist `approvedBy` bei lokalem CLI versus CI?
- Muss ein Approval auch für `terraform plan` gelten? (Vorschlag: nein;
  nur mutierende Apply/Destroy.)
- Wie wird ein Plan nach `terraform show -json` gegen das gerenderte
  Plan-JSON gebunden, ohne zwei divergierende Fingerprints?
- Soll die Evidence im Run-Verzeichnis oder im Plan-Manifest gespeichert
  werden?
- Ist eine Signatur ohne neue Secrets-/KMS-Infrastruktur überhaupt
  vertrauenswürdig? Wenn nein: Entscheidung für lokale Integrität statt
  Non-Repudiation.

---

## 11. Auswirkungen auf 12B

- Neue Datei/Modul: `installer/core/approval_evidence.py` (Vorschlag).
- Neue CLI-Option/Kommando: `--approval-file` bzw. `approve`.
- `_cmd_deploy`/`_cmd_destroy`: Gate unmittelbar vor Runner-Aufruf;
  kein Apply/Destroy bei DENY.
- Pfadkonsistenz: verifizierte Plan-Datei == ausgeführte Plan-Datei.
- Tests: SEC06-01…12, Unit-/CLI-/Mutationen, Legacy, TOCTOU.
- Keine AWS-Live-Tests in 12A/12B ohne separate Freigabe.
- Keine Änderung an Terraform-Modulen oder IAM.

---

## 12. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| Produktcodeänderung in 12A | **NEIN** |
| AWS-/Cognito-/HTTP-Aufruf | **NEIN** |
| Terraform Apply/Destroy/Import | **NEIN** |
| Deploy-/Destroy-Ausführung | **NEIN** |
| Backup/Restore | **NEIN** |
| Secrets/Tokens/PII im Bericht | **NEIN** |
| Architektur als implementiert dargestellt | **NEIN** — PROPOSED |

---

## 13. Git-Abschluss

Vorgesehen:

```text
Commit: docs(rc4): propose plan-bound approval security contract
Dateien: docs/reports/MO-RC4-SECURITY-APPROVAL-CONTRACT-12A.md
         docs/adr/ADR-RC4-APPROVAL-CONTEXT-BINDING.md
         docs/AI_AUDITLOG.md
```

Kein Push, kein Merge. Commit-SHA und CLEAN-Status werden nach dem Commit
verifiziert.
