# MO-GIT-CONSOLIDATION-01 — Mays-Orders-AWS Git-Inventur

**Status:** `INVENTORY COMPLETE / SAFE CHECKS ONLY / NO DESTRUCTIVE ACTION`
**Datum:** 2026-11-14
**Hauptrepository:** `/home/dci-student/projects/Mays-Orders-AWS`
**Git-Common-Directory:** `/home/dci-student/projects/Mays-Orders-AWS/.git`
**RC4-Kandidat:** `release/rc4-integration` @ `720e4584e52356c57b62e18690bbac84f73723d6`
**RC4-Version:** `0.2.0` (Deployment-Version, kein Release-Tag)

## 1. Governance

- `AGENTS.md` und `docs/AI_AUDITLOG.md` gelesen.
- Keine Agenten oder Subagenten in diesem Auftrag gestartet; keine parallelen
  Schreibvorgänge.
- Alle 15 Git-Worktrees unter `/home/dci-student/projects/` waren vor und nach
  der Inventur **clean**.
- Keine Dateien gelöscht, verschoben, umbenannt oder zurückgesetzt.
- Keine Branch-/Tag-Löschung, kein Push, kein Main-Merge, kein
  Terraform-State-Move.

## 2. Gefundene Projektordner

Unter `/home/dci-student/projects/` existieren **16** Mays-Orders-AWS-Ordner:

| # | Pfad | Typ | Branch | HEAD | Status |
|---|---|---|---|---|---|
| 1 | `Mays-Orders-AWS` | Haupt-Clone, `.git` | `feature/mo-rc4-teststack-baseline-01` | `0756563` | clean |
| 2 | `Mays-Orders-AWS-final-01` | Worktree | `feature/mo-rc4-final-01` | `85ef5fb` | clean |
| 3 | `Mays-Orders-AWS-p00-b` | Worktree | `feature/mo-rc4-p00-b-secret-provider` | `f0ea3b8` | clean |
| 4 | `Mays-Orders-AWS-p00-b-review` | Worktree | `review/mo-rc4-p00-b-integration-01` | `182502b` | clean |
| 5 | `Mays-Orders-AWS-p00-c` | Worktree | `feature/mo-rc4-p00-c-aws-managed` | `08fde23` | clean |
| 6 | `Mays-Orders-AWS-p00-c-correction` | Worktree | `feature/mo-rc4-p00-c-correction-04` | `d3ce237` | clean |
| 7 | `Mays-Orders-AWS-p00-c-f01` | Worktree | `feature/mo-rc4-p00-c-f01-authorization-05` | `4342163` | clean |
| 8 | `Mays-Orders-AWS-p00-c-rereview` | Worktree | `review/mo-rc4-p00-c-security-06` | `60a462a` | clean |
| 9 | `Mays-Orders-AWS-p00-c-review` | Worktree | `review/mo-rc4-p00-c-security-03` | `41b8612` | clean |
| 10 | `Mays-Orders-AWS-p00-d` | Worktree | `feature/mo-rc4-p00-d-app-managed` | `18cf541` | clean |
| 11 | `Mays-Orders-AWS-p00-d-correction` | Worktree | `feature/mo-rc4-p00-d-correction-06` | `73bd07c` | clean |
| 12 | `Mays-Orders-AWS-p00-d-review` | Worktree | `review/mo-rc4-p00-d-security-05` | `b569702` | clean |
| 13 | `Mays-Orders-AWS-p00-e-baseline` | Worktree | `analysis/mo-rc4-p00-e-baseline-01` | `46c6e61` | clean |
| 14 | `Mays-Orders-AWS-p00-e-simple` | Worktree | `feature/mo-rc4-p00-e-simple` | `44c3900` | clean |
| 15 | `Mays-Orders-AWS-rc4-integration` | Worktree | `release/rc4-integration` | `720e458` | clean |
| 16 | `Mays-Orders-AWS02092026` | **kein Git-Repo** | — | — | Snapshot |

Zusätzlich existieren fünf Git-Worktrees außerhalb von `projects/` unter
`/tmp/opencode/`: `rc3-baseline` (detached), `rc3-version-marker`,
`rc4-apply-00125ee` (detached), `rc4-apply-ffbebe9` (detached) und
`rc4-upgrade-plan`. Alle sind clean.

`Mays-Orders-AWS02092026` enthält einen entpackten Quellbaum
`Mays-Orders-AWS02092026/Mays-Orders-AWS` ohne `.git`; daneben liegen mehrere
Top-Level-ZIP-Archive (`Mays-Orders-AWS02092026.zip`, `...180826.zip`,
`...withoutsqs.zip`, `...WithoutSQS.zip`, `Mays-Orders-AWS.zip`). Diese
Snapshots sind **keine Git-Repositories** und wurden nicht angefasst.

## 3. Git-Referenzen und RC4-Erreichbarkeit

Gemeinsame Referenzen aller Worktrees:

- **55 lokale Branches**
- **12 Remote-Branches** (`origin/...`)
- **20 Tags**
- **44 lokale Branches ohne Upstream**
- **22 Branches mit nicht gepushten Commits**
- **15 Worktree-Branches** unter `projects/`; keine hat einen Upstream.

Der RC4-Head `720e4584e52356c57b62e18690bbac84f73723d6` ist:

- als Commit-Objekt vorhanden,
- über `refs/heads/release/rc4-integration` erreichbar,
- **nicht** in `main` enthalten,
- **97 Commits** vor allen Remote-Refs (nicht gepusht),
- **188 Commits** vor `main`, 0 Commits hinter `main`.

`feature/mo-rc4-final-01` ist bereits in `release/rc4-integration` enthalten.
Es fehlen keine Branch-Referenzen für die vorhandenen Worktree-HEADs. Es
wurden deshalb **keine neuen Refs angelegt**; die vorhandene Historie bleibt
unverändert.

## 4. Terraform-State und Backend

| Datei/Referenz | Befund |
|---|---|
| `Mays-Orders-AWS/terraform.tfstate` | lokal, **0 Ressourcen**, serial 1 |
| `Mays-Orders-AWS/ci/iam/terraform.tfstate` | lokal, **14 Ressourcen**, serial 59 |
| `Mays-Orders-AWS/ci/iam/terraform.tfstate.backup` | lokal, 14 Ressourcen, serial 56 |
| `Mays-Orders-AWS/ci/pipeline/terraform.tfstate` | lokal, **7 Ressourcen**, serial 100 |
| `Mays-Orders-AWS/ci/pipeline/terraform.tfstate.backup` | lokal, 7 Ressourcen, serial 98 |
| `terraform/backend.tf` | S3 `mays-orders-tfstate-central-240571105849`, Locking `mays-orders-terraform-locks`, Prefix `env:` |
| Integration `.terraform/terraform.tfstate` | Backend-Konfiguration, 0 Ressourcen |

Die lokalen CI-States (`ci/iam`, `ci/pipeline`) werden **nicht** verschoben oder
gelöscht. Der RC4-Stack `mays-orders-rc4` wurde zuvor kontrolliert deployed und
vollständig zerstört; sein Workspace-State ist leer.

## 5. Reports und Artefakte

| Worktree | `docs/reports` | `.mays-installer/runs` |
|---|---:|---:|
| `Mays-Orders-AWS` | 228 | 189 |
| `Mays-Orders-AWS-rc4-integration` | 296 | 25 |
| `Mays-Orders-AWS-final-01` | 293 | 5 |
| übrige RC4-Worktrees | 275–292 | 0–7 |
| `/tmp/opencode/*` | 186–269 | 2–46 |

Die Run-Verzeichnisse sind gitignored und enthalten lokale Test-/Plan-Artefakte.
Sie sind nicht Teil der Git-Historie.

## 6. Empfohlene Zielstruktur

**Ein Hauptrepository, zwei aktive Worktrees:**

1. `/home/dci-student/projects/Mays-Orders-AWS` — canonical `.git`,
   langfristig auf `release/rc4-integration` (oder nach Freigabe auf `main`).
2. `/home/dci-student/projects/Mays-Orders-AWS-rc4-integration` — aktiver
   RC4-Release-Worktree, aktuell `720e458`.

Alle übrigen Feature-/Review-/Analysis-Worktrees sind abgeschlossene
Entwicklungsspuren. Sie sollten erst nach ausdrücklicher Freigabe entfernt
werden; ihre Branches bleiben im gemeinsamen Repository erhalten.

Der nicht-Git-Snapshot `Mays-Orders-AWS02092026` und die ZIP-Archive sind
Backups, keine Repositories. Sie sollten nach Prüfung außerhalb des
Projektordners archiviert oder nach Freigabe entfernt werden.

## 7. Nach Freigabe entfernbare Worktrees

Nicht automatisch entfernt; nur Kandidaten:

- `Mays-Orders-AWS-final-01`
- `Mays-Orders-AWS-p00-b`, `-p00-b-review`
- `Mays-Orders-AWS-p00-c`, `-p00-c-correction`, `-p00-c-f01`,
  `-p00-c-review`, `-p00-c-rereview`
- `Mays-Orders-AWS-p00-d`, `-p00-d-correction`, `-p00-d-review`
- `Mays-Orders-AWS-p00-e-baseline`, `-p00-e-simple`
- `/tmp/opencode/rc3-baseline`, `rc3-version-marker`,
  `rc4-apply-00125ee`, `rc4-apply-ffbebe9`, `rc4-upgrade-plan`

Vor einem `git worktree remove` ist jeweils zu prüfen:
Branch-Ref erhalten, Worktree clean, keine unpushed Commits, keine lokalen
Run-Artefakte/States benötigt.

## 8. Offene Risiken

1. **Release nicht auf `main`:** `release/rc4-integration` ist 188 Commits vor
   `main`; Main-Merge bleibt separat freizugeben.
2. **Release nicht gepusht:** 97 Commits vor allen Remote-Refs; kein Push.
3. **Viele alte Branches:** 55 lokal, 44 ohne Upstream; vor dem Aufräumen
   Branch-Matrix und unpushed Commits prüfen.
4. **Lokale CI-States:** `ci/iam` (14) und `ci/pipeline` (7) enthalten
   Ressourcen; nicht mit RC4-State verwechseln und nicht verschieben.
5. **Detached Worktrees:** Drei `/tmp`-Worktrees sind detached; ihre Commits
   sind über bestehende Branches erreichbar, sollten aber vor Entfernung
   separat dokumentiert werden.
6. **Nicht-Git-Snapshot:** `Mays-Orders-AWS02092026` hat keine Historie und
   kann nicht als Clone konsolidiert werden.
7. **Separater AWS-Teststack:** `mays-orders-rc4-test` bleibt bestehen und ist
   nicht Teil dieser Git-Konsolidierung.

**Ergebnis:** Ein gemeinsames Hauptrepository mit 15 Projekt-Worktrees und
einem nicht-Git-Snapshot ist dokumentiert. Der RC4-Kandidat ist sicher über
`release/rc4-integration` erreichbar. Es wurden keine destruktiven Schritte
ausgeführt; Worktree-Bereinigung, Main-Merge und Push benötigen Freigabe.
