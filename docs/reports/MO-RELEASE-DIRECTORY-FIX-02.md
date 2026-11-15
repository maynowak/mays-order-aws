# MO-RELEASE-DIRECTORY-FIX-02 — Sechs Dokumente verschoben

**Status:** `A — SIX FILES RELOCATED · REFERENCES VERIFIED · MAIN INTEGRATED`
**Datum:** 2026-11-15
**Branch:** `docs/mo-release-directory-fix-02`
**Base main:** `96cafc55410a074be391d18f6552ba16c0c86dba`
**Pull Request:** #1 — MERGED

## 1. Ausgangsstand

- `main` und `origin/main`: `96cafc5`
- Working Tree vor der Arbeit: clean
- Keine neuen Worktrees
- Release-Tag `v0.6.0-rc.1`: unverändert `5bc154e`

## 2. Altpfad → Neupfad

| Altpfad | Neupfad |
|---|---|
| `docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` | `docs/adr/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` |
| `docs/release/MO-RC4-P00-DECISION-REGISTER.md` | `docs/adr/MO-RC4-P00-DECISION-REGISTER.md` |
| `docs/release/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` | `docs/reports/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` |
| `docs/release/MO-RC4-P00-DEPENDENCY-GRAPH.md` | `docs/roadmap/MO-RC4-P00-DEPENDENCY-GRAPH.md` |
| `docs/release/MO-RC4-P00-EXECUTION-PLAN.md` | `docs/roadmap/MO-RC4-P00-EXECUTION-PLAN.md` |
| `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` | `docs/roadmap/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` |

Alle sechs Dateien wurden mit `git mv` verschoben; Dateinamen blieben unverändert.
Keine Zieldatei existierte bereits. Keine Datei liegt mehr unter `docs/release/`.

## 3. Referenzen

Aktuelle Referenzen wurden angepasst:

- `architecture/architecture-decisions.md`
- `docs/release/README.md`
- `docs/roadmap/MO-RC4-P00-DEPENDENCY-GRAPH.md`
- `docs/roadmap/MO-RC4-P00-EXECUTION-PLAN.md`
- `docs/PROJECT_STATUS.md`

Historische Reports und `docs/AI_AUDITLOG.md` wurden **nicht** umgeschrieben.
Ihre alten Pfade bleiben als historische Nachweise erhalten. Die
Altpfad-Tabelle in diesem Bericht und in `docs/release/README.md` stellt die
Zuordnung her.

## 4. Dokumentationskorrektur

- `docs/release/README.md` beschreibt jetzt die verbleibende Release-Struktur
  und die sechs verschobenen Dokumente.
- `docs/reports/MO-RELEASE-DIRECTORY-CONSOLIDATION-01.md` enthält einen
  datierten Korrekturvermerk; der ursprüngliche Bericht wurde nicht
  rückwirkend verfälscht.
- `docs/PROJECT_STATUS.md` verweist auf die sechs Relokationen.

## 5. Validierung

| Prüfung | Ergebnis |
|---|---|
| Sechs Dateien am neuen Ort | **PASS** |
| Keine der sechs Dateien mehr unter `docs/release/` | **PASS** |
| Aktuelle Markdown-Links | **PASS** |
| Historische Referenzen erhalten | **PASS** |
| Offizielle Release-PDFs unverändert | **PASS** (`RELEASE-v0.6.0-rc.1.pdf` SHA-256 `165bf8b3…`; Detailpaket `968a9276…`) |
| Release-Tag unverändert | **PASS** (`5bc154e`) |
| Produktcode/Terraform/AWS unverändert | **PASS** |
| `git diff --check` | **PASS** |

Die fünf bereits dokumentierten fehlenden v0.4.0-Bilder bleiben als
vorbestehende historische Lücke bestehen.

## 6. Git

- Move-Commit: `b183200f44466334fe1e9fd4ddc9834388eb0f57`
- Report-/Audit-Commit: dieser Commit
- Remote-Feature-Branch: `docs/mo-release-directory-fix-02`
- Pull Request: **#1**
- Pull Request #1 wurde über GitHub regulär gemerged (`--merge`)
- Merge-Commit: `cd3f5fd56e45065aceff5cfe184b866622ebf5bd`
- Remote-`main`: `cd3f5fd56e45065aceff5cfe184b866622ebf5bd`
- Kein Force-Push, kein Tag-Rewrite, kein Deployment

## 7. Grenzen

- Keine Änderungen an Produktcode, Terraform oder AWS
- Keine neuen Worktrees oder Unterverzeichnisse
- Keine Änderung an GitHub-Release oder Release-Assets
- Kein Main-Merge vor erfolgreicher PR-Prüfung
