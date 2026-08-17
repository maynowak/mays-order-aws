# Feature Progress Template — verbindlich für aktive Features

> **Regel:** Während der Bearbeitung eines Features/Tasks wird der Arbeitsstand **fortlaufend**
> in der zugehörigen Feature-Dokumentation (`docs/features/FXXX-*.md`) aktualisiert —
> nicht erst am Ende. Der Chatverlauf ist KEINE Recovery-Quelle.
>
> Diese Struktur gilt ab sofort für alle zukünftigen May's-Orders-Features und -Tasks.

## Progress-Block (im aktiven Feature-Dokument zu pflegen)

```text
Feature:
F004 — Order Creation

Status:
🔄 IN PROGRESS

Current Task:
T004-04 — DynamoDB persistence

Completed Tasks:
- T004-01 Request model             ✅
- T004-02 Validation                ✅
- T004-03 Order ID generation       ✅

In Progress:
- T004-04 DynamoDB persistence      🔄

Pending Tasks:
- T004-05 API integration
- T004-06 Error handling
- T004-07 Automated tests
- T004-08 Live API verification

Changes Made:
- DynamoDB repository created
- PutItem operation implemented

Tests:
- Unit tests: NOT RUN YET

Validation:
- TypeScript check: PENDING

Known Issues:
- None

Blockers:
- None

Current Checkpoint:
- Local working state — not yet committed

Next Step:
- Run unit tests → typecheck → validation
```

## Nach Abschluss eines einzelnen Tasks

```text
T004-04
Status: COMPLETE

Tests:
PASS

Validation:
PASS

Feature:
IN PROGRESS

Next:
T004-05 API integration
```

## Nach Abschluss des gesamten Features

```text
F004 — Order Creation
Status: COMPLETE

Voraussetzungen:
✅ Implementation abgeschlossen
✅ relevante Tests durchgeführt
✅ Validation durchgeführt
✅ Dokumentation aktualisiert
✅ bekannte Probleme dokumentiert
✅ Git-Checkpoint erstellt
✅ Push erfolgreich
```

## Maßstab für Zwischen-Updates

Spätestens nach jedem sinnvollen Arbeitsschritt aktualisieren:

```text
Analyse abgeschlossen · Datei/Komponente geändert · Teilfeature implementiert
Testgruppe abgeschlossen · Fehler identifiziert · Fehler behoben
Architekturentscheidung getroffen · AWS-Konfiguration vorbereitet
Dokumentation aktualisiert
```

> **Kann ein anderer Agent nach einem Absturz erkennen, was bereits erledigt wurde und
> wo weitergearbeitet werden muss?** Wenn nein → Status aktualisieren.

## Absturz-Recovery (aus der Feature-Doku ableitbar)

```text
Was war das aktive Feature?
        ↓
Welcher Task war aktiv?
        ↓
Was wurde bereits geändert?
        ↓
Welche Tests wurden durchgeführt?
        ↓
Was ist noch offen?
        ↓
Gab es einen Fehler?
        ↓
Was ist der nächste Schritt?
```

Wenn der Zustand nicht sicher feststellbar ist:

```text
UNKNOWN / NEEDS VERIFICATION
```

dokumentieren und den Zustand prüfen — niemals raten.