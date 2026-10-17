# MAYS-ORDERS-MODULE-BUILDER-HARDENING-01

**Checkpoint:** MAYS-ORDERS-MODULE-BUILDER-HARDENING-01
**Datum:** 2026-10-17
**Baseline:** main `995f912` (Builder Foundation)
**Arbeitspakete:** F1 (Cognito-Backup-Artefakt reproduzierbar) · F2 (Policy-Gates in generierte Projekte)
**Orchestrierung:** 2 parallele read-only Research-Subagents (Evidence-Berichte A/B), sequenzielle Implementierung, separate Commits je Arbeitspaket
**Status:** F1 VERIFIED · F2 VERIFIED · Gesamt GREEN

## 1. Research-Ergebnisse (Phase 1, Subagent-Evidence)

### Researcher A — Herkunft cognito_backup.zip
- Artefakt war **nie in Git getrackt** (`.gitignore dist/`), 14 983 B, sha256 `492b0c54…`, lokal gebaut 2026-09-27 (versehentlich inkl. `__pycache__/*.pyc` und Tests).
- **Quelle existiert im Repo:** Package `cognito_backup/` (Repo-Root, Commits `a60820d`+`d83bb22`) und Handler `lambda/cognito_backup_handler.py` (Commit `e90a701`).
- **Kritische Diskrepanz:** committed Handler las `AWS_REGION`; das deployed-erprobte Zip (passend zur Terraform-Env `MY_AWS_REGION`, Commit `3ad583d`) liest `MY_AWS_REGION` (AWS_REGION ist in Lambda reserviert).
- Kein Build-Skript existierte; die COGNITO-BACKUP-03-Reports dokumentieren keine Zip-Provenance. *Korrektur zum Foundation-Report: die Aussage „keine .py-Quelle im Repo" war unvollständig — Quelle existiert, nur der Handler-Stand fehlte.*

### Researcher B — Policy-Gate-Portierbarkeit
- `terraform/policy/` = selbstenthaltenes Paar: `validate-plan.py` (296 Zeilen, **stdlib-only, offline**) + `resource-policy.json`; `POLICY_PATH` ist dateirelativ → an jedem Ort lauffähig.
- Exit-Codes: 0=PASS, 1=FAIL (blockiert Deploy im Installer vor Approval), 2=Usage. Kein Umgehen möglich (das `--no-policy-check`-Flag des Installers ist nachweislich tot/unkonsumiert).
- Einzige mays-spezifische Logik (Z. 98, `mays-`-Präfix-Strenge) ist für Fremdprojekte inert; `resource-policy.json` trägt `"project": "mays-orders"` → Substitution erforderlich.
- Nicht portabel: die Installer-Aufrufstelle (Repo-Root-Annahme) — für generierte Projekte wird das Gate daher als eigenständiges Skript dokumentiert, nicht über den MO-Installer orchestriert.

## 2. F1 — Reproduzierbarer Cognito-Backup-Build (VERIFIED)

**Maßnahmen (evidenzbasiert, keine Spekulation):**
1. `lambda/cognito_backup_handler.py` auf den deployed-erprobten Stand gebracht: `AWS_REGION` → `MY_AWS_REGION` — die committed Quelle ist jetzt **byte-identisch mit dem historischen Zip-Inhalt**.
2. Neues Build-Skript `lambda/build_cognito_backup_zip.py` (Spiegel der `build_zip.py`-Konventionen): packt Handler + `cognito_backup/`-Package; **deterministisch** (feste Zip-Timestamps 1980-01-01); schließt `__pycache__` und Tests aus (Artefakt-Konvention wie lambda.zip).
3. Artefakt neu gebaut und **in Git getrackt** (`git add -f`, wie lambda.zip) → Frisch-Clones können bauen.
4. Module Builder übernimmt jetzt **Quelle + Build-Skript** ins generierte Projekt (`cognito_backup/`, Handler, Skript).

**Reproduzierbarkeits-Beweis (Einmal-Evidence):**
- Historisches Zip vs. Neubau: **alle 8 Runtime-Dateien byte-identical** (Differenz nur: entfernte .pyc/tests + fixe Timestamps).
- Neubau **im generierten Projekt** ergibt exakt denselben sha256 wie im Quell-Repo: `8312d9993485c4736dbb0a3267ea325e2eda6a6cced3ab92cf583aa24766d8fa` — permanenter Unit-Test (`test_cognito_backup_artifact_reproducible_in_target`).
- Package-Tests laufen: `test_manifest.py`, `test_restore.py` → PASS (Quelle validiert).
- Bekannte Folge, dokumentiert: neuer Artefakt-Hash → `source_code_hash`-Änderung; ein künftiger `plan` zeigt ein Lambda-Update der Backup-Automation. **Kein apply durchgeführt.**

## 3. F2 — Policy-Gate in generierte Projekte (VERIFIED)

**Maßnahmen:**
1. `validate-plan.py` **verbatim** ins generierte Projekt (`terraform/policy/`) — nachweislich ohne Repo-Abhängigkeit lauffähig.
2. `resource-policy.json` mit **Projektnamen-Substitution**: `"project": "<Konsumenten-Name>"` → das Gate erzwingt den Namespace des Konsumenten (S3/IAM/API-GW/Cognito `<project>-*`).
3. **Keine stille Aufweichung** — permanenter Test sichert: Region `eu-central-*`, Pflicht-Tags `[Project, Maker, Environment]`, Production-Verbot und Typ-Allowlist bleiben unverändert.
4. Generiertes README: Pflicht-Abschnitt „Policy-Gate (vor jedem apply)" mit Aufruf, Exit-Codes und FAIL-nicht-umgehen-Regel.

**Positiv-/Negativtests (gegen das GENERIERTE Gate, live + permanent):**
- Positiv (valider Minimal-Plan, Region `eu-central-1`): Exit **0** PASS ✓
- Negativ Region `us-east-1`: Exit **1** FAIL ✓ („Terraform apply MUST NOT proceed…")
- Negativ nicht erlaubter Typ (`aws_redshift_cluster`): Exit **1** ✓
- Negativ fehlendes Pflicht-Tag: Exit **1** ✓

## 4. Testresultate (alle real ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Builder-Unit-Tests (inkl. 7 neuer: Layout-Quellen, Artefakt-Rebuild im Target, Policy-Dateien, Policy-Substitution, 3 Negativtests + Positivtest) | **30/30 PASS** |
| Live-Build `--validate` (60 Dateien, terraform fmt/init/validate) | PASS |
| Live-Policy-Gate gegen generiertes Projekt (Positiv + Negativ) | PASS (Exit 0 / 1) |
| Artefakt-Rebuild im generierten Projekt | deterministisch, sha256 identisch `8312d999…` |
| Builder-Determinismus (zwei Läufe, ohne Manifest/init-Artefakte) | Bäume identisch ✓ |
| Installer-Regression | **129/129 PASS** |
| Lambda-Regression | **76/76 PASS** |
| Cognito-Backup-Package-Tests (Quellvalidierung) | PASS |
| Secrets/States/Plans im Builder-Output | keine ✓ |
| AWS-Mutationen / apply / destroy / RIS / States | **KEINE** (nur read-only) |

## 5. Review (Phase 4)

| Kriterium | Urteil | Evidence |
|---|---|---|
| Reproduzierbarkeit | ✓ | Byte-Identität der 8 Runtime-Dateien; deterministischer Rebuild im Ziel (Test + Live) |
| Sicherheit | ✓ | Keine AWS-Mutation; Policy-FAIL blockiert (Negativtests Exit 1); keine Policy-Aufweichung (Regel-Erhalt-Test); Privacy bleibt BLOCKED |
| Rückwärtskompatibilität | ✓ | Builder-CLI unverändert; alle bestehenden Tests grün; Quelle: handler auf deployed-Stand aligniert (Terraform-Env-Konfiguration wird erst durch zukünftigen Plan sichtbar — kein apply erfolgt) |
| Builder-Isolation | ✓ | Keine Repo-Referenzen im Output (bestehender Test); Policy wird kopiert, nicht gesourct; Gate offline lauffähig |
| Test-Evidence | ✓ | 30/129/76 + Live-Nachweise, alle in diesem Report dokumentiert |

## 6. Commits (separate Arbeitspakete)

| Commit | Paket |
|---|---|
| `92be267` | **F1** — Handler-Fix, Build-Skript, deterministisches Artefakt (getrackt), Builder-Quell-Übernahme, Tests |
| `da80271` | **F2** — Policy-Gate-Kopie + Substitution + README + Positiv-/Negativtests |
| (folgt) | Bericht + AI_AUDITLOG |

## 7. Offene Punkte

1. **Plan B** (freigegeben in Foundation, noch nicht beauftragt): freie Modulauswahl (`--modules`), Preset `minimal`, S3-Artefakt-Sourcing, `cognito_backup`-Pfad auf `var.filename` umstellen.
2. Terraform-Umgebungsvariable des Backup-Lambdas: der deployte Bestand läuft mit dem alten Zip — bei nächstem (separat freizugebenden) Deploy wird das neue Artefakt (identischer Runtime-Inhalt, saubererer Build) aktiv.
3. Künftiger Plan zeigt `source_code_hash`-Update der Backup-Lambda(s) — erwartete, dokumentierte Folge; kein Handlungsbedarf ohne Deploy.
4. `--no-policy-check`-Flag des MO-Installers ist tot (unkonsumiert) — außerhalb dieses Checkpoints; Aufräum-Kandidat.
