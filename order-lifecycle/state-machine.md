# Order State Machine — May's Orders

## 1. Zustände

| Zustand | Bedeutung |
|---------|-----------|
| `PENDING` | Bestellung wurde angelegt, noch nicht bestätigt (Ausgangszustand) |
| `CONFIRMED` | Bestellung ist vom Händler bestätigt |
| `PROCESSING` | Bestellung wird bearbeitet (Kommissionierung/Packen) |
| `SHIPPED` | Bestellung wurde versendet |
| `DELIVERED` | Bestellung wurde zugestellt (Endzustand) |
| `CANCELLED` | Bestellung wurde storniert (Endzustand) |

## 2. Zustandsübergänge

```text
          ┌───────────────┐
          ▼               │
        PENDING ────────► CONFIRMED ────────► PROCESSING ────────► SHIPPED ────────► DELIVERED
          │                │
          │                │
          ▼                ▼
       CANCELLED        CANCELLED
```

## 3. Gültige Übergänge (Erlaubt)

| Von | Nach | Begründung |
|-----|------|------------|
| `PENDING` | `CONFIRMED` | Händler bestätigt die eingegangene Bestellung |
| `PENDING` | `CANCELLED` | Unbestätigte Bestellung kann storniert werden (z. B. Kunde widerruft) |
| `CONFIRMED` | `PROCESSING` | Bestätigte Bestellung beginnt die Bearbeitung |
| `CONFIRMED` | `CANCELLED` | Bestätigte Bestellung kann noch storniert werden (Vorbereitung noch nicht gestartet) |
| `PROCESSING` | `SHIPPED` | Bearbeitete Bestellung wird versendet |
| `SHIPPED` | `DELIVERED` | Versendete Bestellung wird zugestellt |

## 4. Geschäftsregel-Begründung

Die Stornierung ist **bewusst auf `PENDING` und `CONFIRMED` beschränkt**.

Begründung:

1. **Sobald eine Bestellung in `PROCESSING` ist, wurden Ressourcen gebunden**
   (Kommissionierung, Verpackung, ggf. Versandvorbereitung).
   Eine späte Stornierung würde reale Betriebskosten verursachen.
2. **Einfachheit und Nachvollziehbarkeit:** Die Regel ist in einer kompakten
   Transition-Tabelle ausdrückbar, unit-testbar und für das Team eindeutig.
3. **Trade-off:** Real existieren spätere Stornierungen (z. B. Retoure nach Versand).
   Diese sind bewusst NICHT als Status-Übergang modelliert, sondern wären ein
   separater Prozess (z. B. neue Bestellung/Rückabwicklung), der nicht Teil des
   aktuellen Scope ist (siehe `requirements/technical-requirements.md`, Abgrenzung).
4. **Konsistenz im Wettlauf:** Die Transitionsregel wird als **DynamoDB Conditional Write**
   umgesetzt, sodass auch bei konkurrierenden Updates (z. B. User A → PROCESSING,
   User B → CANCELLED) genau ein Übergang gewinnt und nie ein ungültiger Zustand entsteht.

## 5. Terminologie

- **Endzustände:** `DELIVERED`, `CANCELLED` — keine weiteren Übergänge.
- **Idempotenz-Regel (Entscheidung offen):** Ob ein Übergang auf den *gleichen* Zielzustand
  (z. B. `PROCESSING → PROCESSING`) als No-Op oder als Fehler behandelt wird, wird in
  Woche 3 als Teil der State-Machine-Implementierung final getestet und dokumentiert.