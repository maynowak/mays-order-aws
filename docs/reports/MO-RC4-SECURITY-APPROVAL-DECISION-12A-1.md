# MO-RC4-SECURITY-APPROVAL-DECISION-12A-1

**ApprovalEvidence V2 — Entscheidungsvorbereitung und Implementierungsgrundlage**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `c96b6c45839173f5881e3ed52daa40ca9d103d7d`
**Modus:** Read-only-Analyse; keine Produktcodeänderung, keine AWS-/Cognito-/HTTP-
Aufrufe, keine Terraform-Mutation, kein Push/Merge.
**ADR-Status bleibt:** `PROPOSED — NOT APPROVED`

---

## 1. Executive Summary

Die bestehende CLI führt vor einer Mutation umfangreiche Vorprüfungen durch
(Plan-Manifest, SHA-256, Deployment-ID, Operation, Workspace, Version,
State-Baseline, Backup, Upgrade-Safety, Policy). Die **Freigabe** selbst ist
jedoch nur ein Prompt oder `--yes`; sie ist kein dauerhaftes, prüfbares
Evidence-Objekt. `ApprovalContext` wird von der CLI nicht verwendet.

Empfehlung: **separates ApprovalEvidence V2** mit expliziter Bindung an
Deployment-ID, Operation, Workspace und binären Plan-Fingerprint; Prüfung
unmittelbar vor Ausführung. `--yes` bleibt reine Prompt-Unterdrückung und
autorisiert ohne V2-Evidence keine Mutation. Für lokale Entwicklung ist
eine geschützte lokale Evidence ausreichend; für CI/multi-host ist eine
signierte bzw. vertrauenswürdig vermittelte Evidence erforderlich.

**Keine der Empfehlungen wird als genehmigt dargestellt.** Die Entscheidungen
in Abschnitt 14 benötigen eine ausdrückliche menschliche Freigabe.

---

## 2. Verifizierte Ist-Architektur

### 2.1 Ausgangsbasis

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `c96b6c45839173f5881e3ed52daa40ca9d103d7d` |
| 12A | VERIFIED — Vertragsanalyse |
| SEC-06 | CONTRACT GAP / NEEDS DECISION |
| Working Tree | CLEAN |
| Testbaseline | Installer 669, Builder 128, Lambda 337, E2E 16 = **1.150 PASS** |
| Live-E2E | 4 BLOCKED |

Die Baseline wurde im aktuellen Arbeitsstand erneut ausgeführt:

```text
Installer: 669 PASS
Builder:   128 PASS
Lambda:    337 PASS
E2E:        16 PASS
```

### 2.2 Reale Aufrufkette

Deploy:

```text
InstallerCLI.run
  -> _cmd_deploy
     -> validate_aws_context / allow_aws_operations
     -> get_deployment_context
     -> PlanDiscovery
     -> _verify_plan_manifest
          -> PlanManifest.load/verify
          -> sha256_file(plan) == manifest.plan_sha256
     -> _verify_version_binding
     -> _verify_state_baseline
     -> _verify_backup_gate
     -> _verify_upgrade_readiness
     -> _enforce_upgrade_safety
     -> PlanDiscovery.validate_plan_context
     -> copy plan to terraform/ (if from .mays-installer/runs)
     -> runner.verify_plan_integrity
     -> runner.verify_plan_context_match
     -> PlanMetadata.parse_filename
     -> plan summary / evaluate_plan_safety
     -> policy gate (unless dry-run)
     -> input() or --yes
     -> runner.apply(Path.cwd() / parsed.plan)
```

Destroy ist analog, mit:

- `require_manifest=False`, `allow_legacy_manifest=True`,
- `_verify_destroy_plan` über `terraform show -json`,
- Cleanup-Contract,
- eigenem Prompt `Proceed with DESTRUCTION?`,
- `runner.destroy(...)` (intern `terraform apply <plan>`).

### 2.3 Tatsächliche Freigabe

Die CLI verwendet **nicht** `ApprovalGate` oder `ApprovalContext`. Die reale
Entscheidung ist:

```python
if not parsed.yes:
    response = input("Proceed with deployment? [y/N]: ").strip().lower()
    if response not in ("y", "yes"):
        return 0
```

Damit gilt:

- `--yes` ist eine lokale Prompt-Unterdrückung.
- Es gibt keine Approval-ID, keine Zeitstempel, keine Ablaufzeit.
- Es gibt keine persistente Approval-Evidence.
- Es gibt keine Bindung an Plan-Fingerprint oder Workspace.
- `ApprovalGate` wird nur von `installer/cli/gui.py` importiert, dort nicht
  verwendet; seine Check-Methoden sind überwiegend Platzhalter.

### 2.4 Plan- und Workspace-Bindung heute

`PlanManifest` bindet bereits:

- `deployment_id`
- `operation`
- `region`
- `workspace`
- `backend`
- `state_key`
- `plan_file`
- `plan_sha256` (SHA-256 der rohen Plan-Datei)
- Versions-, State-, Backup- und Readiness-Metadaten

`PlanManifest.verify()` prüft Plan-Dateiname, SHA-256, Deployment, Operation,
Region, Workspace, Backend und State-Key. Das ist eine **starke
Vorprüfung**, aber kein Nachweis einer menschlichen/operativen Freigabe.

---

## 3. Trust-Modell

### 3.1 Vertrauensgrenzen im Ist-Zustand

```text
Operator / CI-Runner
        |
        v
Installer CLI (lokaler Prozess, AWS-Profil/Rolle)
        |
        v
Plan-Manifest + CLI-Vorprüfungen
        |
        v
Prompt / --yes
        |
        v
Terraform apply/destroy
```

Beobachtungen:

- Der Installer läuft unter dem Benutzer/CI-Rollenprofil, das auch
  Terraform-Zugriff hat. Ein kompromittierter Runner kann die CLI und
  lokale Dateien kontrollieren.
- Der CI-Buildspec übergibt `--yes` direkt (`ci/buildspecs/deploy.yml`,
  `destroy.yml`).
- `plan_artifact.json` enthält Planpfad und Metadaten; der Buildspec prüft
  Deployment-ID und Operation, aber nicht Plan-Fingerprint oder Workspace.
- Der Plan und sein Manifest liegen im CI-Artefakt; eine Vertrauensgrenze
  zwischen Planerzeugung und Apply ist nur durch CI-Artefakt-Integrität
  gegeben.
- Lokale Dateien im Run-Verzeichnis sind für den ausführenden Benutzer
  veränderbar; ohne Signatur ist eine lokale Evidence nicht
  kryptografisch nicht-abstreitbar.

### 3.2 A1 — Modelle

| Modell | Authentizität | Integrität | Autorisierung | Audit | Aufwand | Eignung |
|---|---|---|---|---|---|---|
| **A — lokale Operator-Freigabe** | lokale OS-Identität | lokale Dateirechte | nur lokal | begrenzt | niedrig | lokale Entwicklung |
| **B — signierte Evidence** | kryptografischer Signer | Signatur + Hash | Signer-Policy | gut | hoch | CI, mehrere Hosts, externe Approval-Quelle |
| **C — CI-vermittelte Freigabe** | CI-Identität/Rolle | CI-Artefakt + Hash | CI-Policy | gut, wenn CI vertrauenswürdig | mittel | kontrollierte Pipeline |

**Empfehlung:** Hybrid:

- **Lokal:** A + geschützte lokale Evidence (Dateirechte, Run-Directory,
  kurze Gültigkeit); keine Non-Repudiation-Behauptung.
- **CI:** C, aber die eigentliche Freigabe muss aus einer **vom
  ausführenden Runner getrennten** Quelle kommen; wenn das nicht garantiert
  ist, B (Signatur) oder ein externer Approval-Service.
- **Mehrere Hosts/externe Quelle:** B erforderlich; lokaler Verbrauchsspeicher
  ist kein globaler Replay-Schutz.

Eine Signatur allein ist kein Ersatz für eine definierte Freigabe-Policy:
Der Signer muss autorisiert sein, genau diese Operation/Plan/Workspace
freizugeben.

---

## 4. ApprovalEvidence V2 — Datenvertrag

### 4.1 Vorschlag

```json
{
  "schemaVersion": 2,
  "approvalId": "apr_<opaque-id>",
  "deploymentId": "240571105849:mays-orders:test",
  "operation": "APPLY",
  "workspace": "mays-orders",
  "planFingerprint": "sha256:<64-hex>",
  "planFormatVersion": "1.2",
  "approvedAt": "2026-11-12T10:00:00Z",
  "expiresAt": "2026-11-12T10:15:00Z",
  "approvedBy": "<trusted-principal>",
  "approvalMethod": "interactive|ci-approval|signed-evidence",
  "evidenceReference": "run/<run-id>/approval.json",
  "nonce": "<unique-nonce>",
  "policyVersion": "approval-policy-v1",
  "stateBaselineFingerprint": "sha256:<64-hex>",
  "signature": {
    "algorithm": "ed25519|rsa-pss-sha256|hmac-sha256",
    "keyId": "<key-id>",
    "value": "<base64>"
  }
}
```

`signature` ist nur erforderlich, wenn die Vertrauensgrenze sie verlangt
(CI/multi-host/extern). Für eine rein lokale Operator-Freigabe kann sie
fehlen; dann muss die Evidence als lokal-integritätsgeschützt, nicht als
kryptografisch authentisch gekennzeichnet werden.

### 4.2 Feldvertrag

| Feld | Typ | Pflicht | Erzeuger / Herkunft | Validierung / Kanonisierung | Fehler | Datenschutz |
|---|---|---|---|---|---|---|
| `schemaVersion` | int | ja | Approval-Werkzeug | exakt `2`; unbekannt → DENY | DENY | keiner |
| `approvalId` | string | ja | Approval-Werkzeug | `apr_` + UUID/ULID; eindeutig | DENY | keiner |
| `deploymentId` | string | ja | DeploymentContext | `DeploymentId.parse`; kanonisch | DENY | keine PII |
| `operation` | enum | ja | Approval-Werkzeug | `APPLY`/`DESTROY`; exakt | DENY | keiner |
| `workspace` | string | ja | `terraform_workspace` | nicht leer, nicht `default`, exakt | DENY | keiner |
| `planFingerprint` | string | ja (planbasiert) | Plan-Hasher | `sha256:<64 hex>`; rohe Plan-Bytes | DENY | keiner |
| `planFormatVersion` | string | optional | Terraform/Plan-JSON | nur Diagnose/Policy | DENY bei unbekannter Pflichtversion | keiner |
| `approvedAt` | UTC ISO-8601 | ja | vertrauenswürdige Zeitquelle | UTC, nicht in der Zukunft | DENY | keiner |
| `expiresAt` | UTC ISO-8601 | ja | Approval-Policy | > `approvedAt`, begrenzte Dauer | DENY | keiner |
| `approvedBy` | string | ja | OS-/CI-/Signer-Identität | nicht leer, definierter Trust-Raum | DENY | minimieren |
| `approvalMethod` | enum | ja | Approval-Werkzeug | `interactive`/`ci-approval`/`signed-evidence` | DENY | keiner |
| `evidenceReference` | string | ja | Run-/Audit-Speicher | auflösbar, unveränderlich | DENY | keiner |
| `nonce` | string | ja | CSPRNG | eindeutig, ausreichende Länge | DENY | keiner |
| `policyVersion` | string | ja | Approval-Policy | unterstützte Version | DENY | keiner |
| `stateBaselineFingerprint` | string | optional/Policy | Installer | SHA-256 der State-Baseline | DENY bei Pflicht | keiner |
| `signature` | object | bedingt | Signer | Algorithmus/Key/Policy | DENY | keine Secrets |

### 4.3 Keine impliziten Defaults

- Fehlende Pflichtfelder → **DENY**.
- Unbekannte `schemaVersion` → **DENY**.
- Unbekannte Operation → **DENY**.
- Fehlender/ungültiger Fingerprint → **DENY**.
- Leerer/`default`-Workspace → **DENY**.
- `expiresAt` in der Vergangenheit oder zu weit in der Zukunft → **DENY**.
- Legacy-/V1-Struktur ohne Bindung → **DENY**; keine automatische Aufwertung.

---

## 5. CLI- und `--yes`-Semantik

### 5.1 Empfohlene Matrix

| Modus | Semantik |
|---|---|
| Interaktiver APPLY | Kontextgebundene Freigabe erforderlich; Prompt erzeugt Evidence für genau diese Plan-Fingerprint/Workspace/Operation |
| Interaktiver DESTROY | Separate Freigabe mit `operation=DESTROY` und Destroy-Plan-Fingerprint |
| `--yes` ohne Evidence | **DENY** für mutierende Operationen |
| `--yes` mit gültiger Evidence | **ALLOW** nach vollständiger Prüfung; `--yes` überspringt nur den Prompt |
| CI ohne vertrauenswürdige Freigabe | **DENY** |
| Lesende Operation (`plan`, `state`, `output`, `identity`) | Keine mutierende Approval-Evidence erforderlich |
| Legacy-Aufruf ohne Evidence | **DENY** für APPLY/DESTROY |

### 5.2 `--yes` ist keine Freigabe

Die Begriffe sind zu trennen:

- **Prompt-Unterdrückung:** `--yes` verhindert nur `input()`.
- **Zustimmung:** eine lokale Handlung eines Operators.
- **Autorisierung:** eine definierte Policy/Identität erlaubt die Operation.
- **Nachweis:** eine prüfbare Evidence belegt die Autorisierung.

`--yes` ersetzt weder Plan-/Workspace-Bindung noch Evidence.

### 5.3 Bestehende Workflows

Konkret betroffen:

- `ci/buildspecs/deploy.yml` — `installer.cli.main deploy ... --yes`
- `ci/buildspecs/destroy.yml` — `installer.cli.main destroy ... --yes`
- `README-old.md` und `docs/INSTALLER-LIFECYCLE.md` — dokumentierte
  `--yes`-Beispiele.
- `AGENTS.md` — `--yes` plus explizite menschliche Freigabe.
- Keine weiteren Shell-Wrapper mit mutierendem `--yes` gefunden.

Der CodeBuild-Deploy-Buildspec prüft Deployment-ID und Operation, aber
**nicht** Plan-Fingerprint/Workspace/Approval-Evidence. Nach V2 würden diese
Pipelines ohne neue Evidence **blockiert**. Die Migration ist eine
Entscheidung, keine stillschweigende Änderung.

---

## 6. Planbindung und TOCTOU

### 6.1 Planidentität

| Schritt | Tatsächliche Datei/Quelle |
|---|---|
| Plan-Erzeugung | `terraform plan -out=<saved_plan>`; Manifest `plan_sha256` |
| Plan-Validierung | `_verify_plan_manifest` auf `plan_file` (Original) |
| Kopie | bei Pfad mit `.mays-installer/runs/` → `terraform/<name>` |
| Integritätsprüfung | `runner.verify_plan_integrity`; derzeit **kein Hash**, nur `show_plan`/Run-Pfad |
| Kontextprüfung | `runner.verify_plan_context_match` auf kopierten/relativen Pfad |
| Approval | keine Planbindung |
| Ausführung | `runner.apply(Path.cwd() / parsed.plan)` — **Originalpfad** |

**Befund:** Die geprüfte Kopie und die tatsächlich ausgeführte Datei können
auseinanderfallen. `verify_plan_integrity` hasht die Datei nicht erneut.
Damit ist ein Plan-Swap nach der Manifest-Prüfung möglich.

### 6.2 Fingerprint-Vertrag

Empfehlung: **SHA-256 über die exakten Bytes der binären Terraform-Plan-Datei,
die ausgeführt wird.** `PlanManifest.plan_sha256` verwendet bereits
`sha256_file`; das ist kompatibel.

Plan-JSON (`terraform show -json`) ist für semantische Prüfungen sinnvoll
(Operation, Ressourcen, Safety), ersetzt aber nicht den Hash der
ausführbaren Binärdatei. Zwei Fingerprints sind klar zu benennen:

- `planFingerprint` = binäre Plan-Datei (Ausführungsbindung),
- `planJsonFingerprint` = Plan-JSON (nur Policy/Analyse, optional).

### 6.3 Ausführungsinvariante

> Nur der freigegebene, geprüfte und unveränderte Terraform-Plan darf
> ausgeführt werden.

| Variante | Schutz | Symlinks | Race | CI | Bewertung |
|---|---|---|---|---|---|
| A — Hash unmittelbar vor Ausführung | gut gegen statischen Austausch | nur mit `O_NOFOLLOW`/`lstat` | Rest-Race zwischen Hash und Terraform-Open | gut | notwendig, nicht allein ausreichend |
| B — geschützte unveränderliche Ausführungskopie | hoch, wenn private Dir + exakt dieselbe Datei | kontrollierbar | geringer, aber kein perfekter Schutz ohne FD-Übergabe | gut | **empfohlen** |
| C — isolierte Ausführungsumgebung | hoch | kontrollierbar | am geringsten | aufwändig | für Hochsicherheit |

**Empfehlung:** B + A: Plan in ein privates, nicht von anderen Benutzern
beschreibbares Run-Verzeichnis kopieren, `chmod` restriktiv, `lstat`/Symlink-
Ablehnung, Hash der Kopie unmittelbar vor Ausführung, **dieselbe Kopie**
ausführen. Ein Hash allein schließt die Race zwischen Hash und
Terraform-Open nicht; diese Restunsicherheit muss dokumentiert werden.

### 6.4 Pre-Execution-Gate

Empfohlene Reihenfolge:

1. Planidentität bestimmen (Originalpfad, Run-ID, Manifest).
2. Planintegrität gegen Manifest/SHA-256 validieren.
3. Evidence laden und Schema/Pflichtfelder prüfen.
4. Deployment-ID, Operation, Workspace vergleichen.
5. `approvedAt`/`expiresAt`/Nonce/Replay prüfen.
6. Ausführungskopie erstellen und gegen Austausch schützen.
7. Hash der Ausführungskopie unmittelbar vor Ausführung erneut prüfen.
8. Evidence atomar verbrauchen (falls Einmalverwendung).
9. Ausschließlich die geprüfte Kopie ausführen.

Bei Fehlern/unklarem Ergebnis: keinen automatischen Retry mit derselben
Evidence; Status konservativ als „verbraucht/unklar“ behandeln und neue
Freigabe verlangen.

---

## 7. Ablaufzeit und Replay-Schutz

### 7.1 Empfehlung

- **Maximale Gültigkeit:** 15 Minuten (konfigurierbar 5–30; Entscheidung).
- **Zeitquelle:** UTC `datetime.now(timezone.utc)`; keine lokale Zeitzone.
- **Clock-Skew:** ±60 Sekunden; `approvedAt` nicht > now+60 s;
  `expiresAt` muss > `approvedAt` sein.
- **Approval-ID:** `apr_` + UUIDv4/ULID; eindeutig.
- **Nonce:** mindestens 128 Bit CSPRNG.
- **Verbrauch:** Approval-ID/Nonce nach erfolgreicher Prüfung atomar als
  verbraucht markieren; Status `consumed` vor dem Runner-Aufruf.
- **Retry:** nach Verbrauch keine Wiederverwendung; bei unklarem
  Terraform-Ergebnis neue Freigabe/Reconciliation.
- **Fehler:** fehlender/nicht erreichbarer Verbrauchsspeicher → **DENY**.

### 7.2 Replay-Speicher

| Variante | Lokal | Mehrere Hosts/CI | Bewertung |
|---|---|---|---|
| geschützte lokale Datei | ja, atomar via `O_EXCL`/Lock | **nein** | lokal ausreichend, kein globaler Schutz |
| SQLite | ja, Transaktion | nein | gute lokale Atomarität |
| CI-verwalteter Zustand | bedingt | ja, wenn zentral | runner-/pipelineabhängig |
| externer Approval-Service | nein | ja | bester globaler Schutz, Aufwand |

Ein lokaler Verbrauchsspeicher ist **kein globaler Replay-Schutz**. Für
mehrere CI-Runner ist ein zentraler Store oder eine serverseitige
Approval-ID-Prüfung erforderlich.

---

## 8. Legacy-Migration

- V2 wird für neue APPLY/DESTROY verpflichtend.
- V1/legacy Evidence ohne Plan-/Workspace-Bindung → **DENY**; keine
  automatische Aufwertung.
- Bestehende Infrastruktur bleibt unverändert; nur zukünftige Mutationen
  benötigen V2.
- Lesende Operationen bleiben unverändert.
- Bestehende Plan-Manifeste bleiben für die Planintegrität gültig, ersetzen
  aber keine Approval-Evidence.
- Migration:
  1. V2-Evidence/Validator implementieren (12B).
  2. Lokale Tests und Negativtests.
  3. CI-Kompatibilität prüfen; neue Freigabequelle definieren.
  4. Bestehende `--yes`-Calls migrieren.
  5. Legacy-Mutationen hart ablehnen.
  6. Audit-/Run-Evidence schreiben.
- Rollback: V2-Gate deaktivieren, aber **nicht** auf ungebundene Freigaben
  zurückfallen; im Zweifel Mutationen stoppen.

### Destroy

- Separate `operation=DESTROY`-Evidence.
- Eigener Destroy-Plan-Fingerprint.
- Keine Übernahme einer APPLY-Evidence.
- Legacy-Destroy ohne V2 → **DENY**.
- `--yes` allein → **DENY**.
- Keine stillschweigende Ausnahme für alte Deployments.

---

## 9. Evidence-Aufbewahrung und Schlüsselverwaltung

### 9.1 Aufbewahrung

- Evidence im Run-Verzeichnis oder einem auditierbaren Artefakt speichern;
  keine Secrets/Tokens/Passwörter.
- Benötigt: `approvalId`, `deploymentId`, `operation`, `workspace`,
  Plan-Fingerprint, Zeitstempel, `approvedBy`, Methode, Ergebnis.
- PII minimieren: `approvedBy` als technische Principal-ID, nicht als
  Klarname/E-Mail, sofern nicht betrieblich erforderlich.
- Aufbewahrungsfrist: **keine pauschale rechtliche Frist erfinden**;
  sie ist eine Betreiber-/Compliance-Entscheidung.
- Widerruf: neue Evidence/Status `revoked`; laufende Ausführung separat
  behandeln (kein Rollback durch Widerruf).

### 9.2 Signaturentscheidung

| Vertrauensgrenze | Signatur | Begründung |
|---|---|---|
| Gleicher lokaler Benutzer | nicht zwingend | OS-Benutzer ist Trust-Boundary; Dateirechte + kurze Gültigkeit |
| Getrennte lokale Prozesse/Benutzer | empfohlen | Manipulationsschutz/Authentizität |
| CI-Runner | **erforderlich oder äquivalente vertrauenswürdige Quelle** | Runner kann lokale Dateien/Keys lesen |
| Mehrere Hosts | **erforderlich** | gemeinsame Authentizität/Replay |
| Externer Approval-Service | Signatur/authentifizierte Übertragung | Herkunftsnachweis |

Key-Management (falls Signatur): eigener Key-Owner, Rotation, Revocation-
Liste, kein Key im Repo/Log, keine Secrets in Evidence. Ohne Key-
Infrastruktur darf lokale Evidence nicht als kryptografisch authentisch
bezeichnet werden.

---

## 10. Test- und Abnahmespezifikation für 12B

| ID | Szenario | Erwartung |
|---|---|---|
| V2-01 | Gültige Evidence (Deployment/Operation/Workspace/Fingerprint) | ALLOW |
| V2-02 | Falsche Deployment-ID | DENY |
| V2-03 | Falsche Operation | DENY |
| V2-04 | Falscher Workspace | DENY |
| V2-05 | Falscher Plan-Fingerprint | DENY |
| V2-06 | Fehlender Fingerprint | DENY |
| V2-07 | Abgelaufene Evidence | DENY |
| V2-08 | Ungültige Authentizität/Signatur | DENY |
| V2-09 | Legacy-Evidence ohne Bindung | DENY |
| V2-10 | Plan-Austausch nach Approval | DENY |
| V2-11 | Doppelte Verwendung/Replay | DENY |
| V2-12 | Verbrauchsspeicher nicht erreichbar | DENY |
| V2-13 | `--yes` ohne Evidence | DENY |
| V2-14 | APPLY-Evidence für DESTROY | DENY |
| V2-15 | Exception/ungültige Rückgabe im Gate | DENY |
| V2-16 | Gültiger Destroy-Kontext | ALLOW |

Zusätzlich:

- Unit: Schema, Pflichtfelder, Kanonisierung, Zeit, Fingerprint, Signatur.
- CLI: Fake-Runner; kein `apply`/`destroy` bei DENY; genau eine Ausführung
  bei ALLOW; `--yes` ohne Evidence DENY.
- TOCTOU: Plan nach Approval ändern; geprüfte Kopie vs. Ausführung.
- Replay: gleiche Approval-ID/Nonce; atomarer Verbrauch.
- CI-Migration: Buildspec-Simulation ohne externe Aktionen.
- Mutationen: Bindung, Ablauf, Fingerprint, Fehlerpfad entfernen; Tests FAIL.
- Regression: Installer/Builder/Lambda/E2E; keine Live-E2E.
- Coverage: ApprovalEvidence/Gate separat; keine künstlichen Ziele.

---

## 11. Entscheidungsmatrix

| Entscheidung | Varianten | Empfehlung | Begründung | Freigabe |
|---|---|---|---|---|
| Trust-Modell | A/B/C | Hybrid: A lokal, C CI, B bei externer/mehr-Host-Grenze | Trust-Boundary und Runner-Kompromittierung | **JA** |
| V2-Datenvertrag | integriert/separat | separates `ApprovalEvidence` V2 | klare Audit-/Testgrenze | **JA** |
| `--yes` | bisher/V2-gebunden | nur Prompt-Unterdrückung; ohne Evidence DENY | keine versteckte Freigabe | **JA** |
| Fingerprint | binär/JSON | binäre Plan-Datei SHA-256; JSON nur ergänzend | Ausführungsbindung | **JA** |
| TOCTOU | A/B/C | B + A (private Kopie + Rehash) | Race-Restrisiko dokumentiert | **JA** |
| Ablaufdauer | 5/15/30/60 min | 15 min, konfigurierbar | kurze Gültigkeit | **JA** |
| Replay-Speicher | Datei/SQLite/CI/extern | lokal SQLite/Datei; CI/extern zentral | lokaler Store ist nicht global | **JA** |
| Legacy-Migration | tolerieren/ablehnen | mutierende Legacy-Freigaben DENY | keine Aufwertung | **JA** |
| Destroy | APPLY teilen/eigene | eigene DESTROY-Evidence + Plan-Fingerprint | keine Operationsübernahme | **JA** |
| Signatur | nie/bedingt/immer | bedingt: CI/multi-host/extern erforderlich | Trust-Grenze | **JA** |

**Keine Zeile ist APPROVED.** Alle Entscheidungen benötigen eine explizite
menschliche Freigabe.

---

## 12. Offene Fragen

1. Ist die lokale OS-Identität für `approvedBy` ausreichend?
2. Welche CI-Freigabequelle ist vertrauenswürdig, wenn der Runner kompromittiert
   sein kann?
3. Wird `--yes` mit Evidence erlaubt oder bleibt ein separater `approve`-Schritt
   Pflicht?
4. 15 Minuten Gültigkeit oder andere Policy?
5. Wo liegt der zentrale Replay-Store für mehrere CI-Runner?
6. Roh-Plan vs. Plan-JSON: welcher Fingerprint ist kanonisch?
7. Persistente interaktive Evidence oder nur flüchtig?
8. Wie werden bestehende `--yes`-Pipelines migriert?
9. Wird Legacy-Destroy weiterhin akzeptiert, aber nur mit V2-Approval?
10. Signatur-Key-Owner/Rotation/Revocation?
11. Aufbewahrungsfrist und Zugriffsrechte für Evidence?
12. Wie wird ein unklares Terraform-Ergebnis nach Verbrauch behandelt?

---

## 13. Voraussetzungen für 12B

- Menschliche Freigabe der Entscheidungen in Abschnitt 11.
- Aktualisierte ADR (weiterhin PROPOSED, dann ggf. ACCEPTED).
- Definiertes Trust-Modell und Key-Management.
- Definiertes Replay-/Ablaufmodell.
- Definiertes Pre-Execution-Gate und Plan-Kopierstrategie.
- Testmatrix V2-01…V2-16 plus Unit/CLI/Mutation/TOCTOU.
- CI-Migrationsplan ohne externe Seiteneffekte.
- Keine AWS-/Terraform-Mutation in der Implementierungsphase ohne separate
  Freigabe.

---

## 14. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| Produktcodeänderung | **NEIN** |
| Bestehende Tests geändert | **NEIN** |
| AWS-/Cognito-/HTTP-Aufruf | **NEIN** |
| Terraform Apply/Destroy/Import | **NEIN** |
| CI-Workflow mit externen Effekten | **NEIN** |
| Secrets/Keys erzeugt/gespeichert | **NEIN** |
| ADR als genehmigt dargestellt | **NEIN** — PROPOSED |

---

## 15. Git-Abschluss

Vorgesehen:

```text
Commit: docs(rc4): define approval evidence v2 security decisions
Dateien: docs/reports/MO-RC4-SECURITY-APPROVAL-DECISION-12A-1.md
         docs/adr/ADR-RC4-APPROVAL-CONTEXT-BINDING.md
         docs/AI_AUDITLOG.md
```

Kein Push, kein Merge. Commit-SHA und CLEAN-Status werden nach dem Commit
verifiziert.
