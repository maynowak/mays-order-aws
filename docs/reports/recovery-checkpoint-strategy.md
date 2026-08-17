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
5. aktuellen Feature-/Task-Report lesen (`docs/reports/`)
6. letzten COMPLETE-Checkpoint feststellen
7. **Nicht** aus alten Chat-/Terminal-Ausgaben rekonstruieren
8. nur mit dem nächsten offenen Step fortfahren

**Der Report ist die maßgebliche Recovery-Quelle.**

## 4. Statuskonvention im Report

| Status | Bedeutung |
|--------|-----------|
| COMPLETE | Implementiert + getestet + dokumentiert + gepusht |
| IN PROGRESS | begonnen, Checkpoint offen |
| BLOCKED | Hindernis, Ursache dokumentiert |
| NOT VERIFIED | Implementiert, aber nicht (live) getestet |
| NOT STARTED | noch nicht begonnen |

## 5. Report-Struktur (je Task)

Siehe Abschlussformat §21 der Projektvorgabe (Summary, Root Cause, Implementation,
Validation, Modified Files, AWS Resources, Cost Impact, Known Limitations, Git Checkpoint, Next Step).