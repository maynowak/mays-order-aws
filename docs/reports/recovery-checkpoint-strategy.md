# Recovery- & Checkpoint-Strategie — May's Orders

## 1. Checkpoint-Regel (nach jedem abgeschlossenen Step)

Ein Step ist erst **COMPLETE**, wenn folgendes erledigt und **gepusht** wurde:

```text
1. Feature-/Task-Report aktualisieren      (docs/reports/)
2. Tests ausführen                          (siehe test-strategy.md)
3. Build ausführen
4. git status prüfen
5. git diff --check ausführen
6. Secret-Audit (grep auf Keys/Passwörter)
7. Commit erstellen (klare, kontextbezogene Message)
8. Push durchführen
9. Erst dann nächsten Step beginnen
```

## 2. BLOCKED / FAILED

Bei `BLOCKED` oder `FAILED`:

1. Ursache dokumentieren (in den Report).
2. Report aktualisieren.
3. Commit/Push des dokumentierten Zustands.
4. **STOP** — nicht weiterarbeiten, warten auf menschliche Entscheidung.

## 3. Absturz-/Recovery-Regel

Bei Absturz von IDE, Terminal oder Agent:

1. `git status`
2. aktuellen Branch prüfen
3. `git rev-parse HEAD`
4. Remote-Stand prüfen (`git log origin/main..HEAD`, `git status -sb`)
5. `docs/PROJECT_STATUS.md` lesen (aktueller Gesamtstand)
6. aktiven Feature-Report lesen (`docs/features/FXXX-*.md` — enthält laufenden Arbeitsstand)
7. aktiven Task identifizieren (Current Task / In Progress)
8. letzten dokumentierten Arbeitsschritt feststellen (Changes Made, Tests, Validation)
9. Tests/Validation anhand der Dokumentation prüfen
10. **Nicht** aus alten Chat-/Terminal-Ausgaben oder aus dem Gedächtnis rekonstruieren
11. nur mit dem nächsten offenen Step fortfahren

Wenn der Zustand nicht sicher feststellbar ist: `UNKNOWN / NEEDS VERIFICATION`
dokumentieren und den Zustand prüfen — niemals raten.

**Der semantische Arbeitsstand in der Feature-Dokumentation ist die maßgebliche
Recovery-Quelle** (Git allein zeigt nicht, was innerhalb eines Prompts halb fertig war).

## 3.1 Laufende Fortschrittsdokumentation

- Während eines längeren Prompts wird der Fortschritt **fortlaufend** in der Feature-Doku
  aktualisiert (siehe `docs/features/_progress-template.md`).
- Spätestens nach jedem sinnvollen Arbeitsschritt (Analyse, Dateiänderung, Teilfeature,
  Testgruppe, Fehler gefunden/behoben, Architekturentscheidung, AWS-Konfiguration, Doku-Update).
- Status nie künstlich auf COMPLETE setzen: `Task: COMPLETE` + `Feature: IN PROGRESS`,
  solange das Feature noch bearbeitet wird.
- Nach jedem Prompt (auch bei vorzeitigem Abbruch) den Zwischenstand in der Feature-Doku hinterlassen.

## 4. Statuskonvention im Report

| Status | Bedeutung |
|--------|-----------|
| COMPLETE | Implementiert + getestet + dokumentiert + gepusht |
| IN PROGRESS | begonnen, Checkpoint offen |
| BLOCKED | Hindernis, Ursache dokumentiert |
| NOT VERIFIED | Implementiert, aber nicht (live) getestet |
| NOT STARTED | noch nicht begonnen |
| UNKNOWN / NEEDS VERIFICATION | Zustand nicht sicher feststellbar → prüfen, nicht raten |

## 5. Report-Struktur (je Task)

Siehe Abschlussformat §21 der Projektvorgabe (Summary, Root Cause, Implementation,
Validation, Modified Files, AWS Resources, Cost Impact, Known Limitations, Git Checkpoint, Next Step).