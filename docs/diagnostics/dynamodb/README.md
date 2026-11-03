# DynamoDB PartiQL — Order-Diagnose

**Zweck:** Schreibgeschützte Diagnose der Mays-Orders-Tabelle im DynamoDB-PartiQL-Editor
(DynamoDB Console → Explore table items → PartiQL). Das Paket hilft, einzelne Orders zu
prüfen, Indexzugriffe zu verstehen und spätere Backup-/Restore-/Migrationsarbeiten
vorzubereiten.

> **Kein Migrationswerkzeug.** PartiQL liefert Stichproben, keine vollständige
> Konsistenzprüfung. Ein Datenabgleich „Restore vs. Ziel“ ist ohne vollständige
> Key-Inventur nicht bewiesen.

## 1. Voraussetzungen

- Lesender Zugriff auf die Tabelle und die genannten Indizes (siehe
  [`security-and-iam.md`](security-and-iam.md)).
- Bekannter Tabellenname (`<TABLE_NAME>`, z. B. der Terraform-`project_name`).
- Bekannter Order-Schlüssel (`pk`/`sk`) für Punktabfragen.
- Keine Schreibrechte nötig; alle Abfragen dieses Pakets sind `SELECT`.

## 2. Tabellenname einsetzen

Ersetze in allen Abfragen:

| Platzhalter | Bedeutung |
|---|---|
| `<TABLE_NAME>` | DynamoDB-Tabellenname (`project_name`) |
| `<RESTORE_TABLE_NAME>` | Restore-Tabelle (`<TABLE_NAME>-restore-<timestamp>`) |
| `<ORDER_PK>` | vollständiger Partition-Key einer Order |
| `<ORDER_ID>` | Order-ID (`ord_` + 24 Hex-Zeichen) |
| `<SUBJECT_ID>` | Owner-`sub` aus dem JWT (kein Klartextnamen) |
| `<FROM_ISO>` / `<TO_ISO>` | ISO-8601-Zeitgrenzen (UTC), z. B. `2026-11-01T00:00:00Z` |
| `<REGION>` | AWS-Region (nur in IAM-Beispielen) |
| `<ACCOUNT_ID>` | AWS-Konto (Platzhalter, nur in IAM-Beispielen) |

Beispiel: `"<TABLE_NAME>"` → `"mays-orders-rc4"`.

## 3. Passende Schlüssel ermitteln

Das tatsächliche Schlüsselmuster ist **nicht** das im Design-Doc genannte `ORDER#…`:

| Schlüssel | Implementiertes Muster | Status |
|---|---|---|
| `pk` | `ord_` + `orderId` (orderId = `ord_` + 24 Hex) → `ord_ord_<24hex>` | VERIFIED im Code |
| `sk` | `#ORDER` | VERIFIED |
| `gsi1pk` | `LIST` | VERIFIED |
| `gsi1sk` | `createdAt` (ISO-8601) | VERIFIED |
| `gsi2pk` | `SUBJECT#<subjectId>` | VERIFIED |
| `gsi2sk` | `ord_` + `orderId` + `#` + `createdAt` | VERIFIED |
| `gsi3pk` | `PROCESSING#RUNNING` | VERIFIED |
| `gsi3sk` | Claim-Zeitpunkt (ISO-8601) | VERIFIED |

Details und Belege: [`schema-reference.md`](schema-reference.md).

RIS- oder Legacy-Schreibpfade können abweichende `pk`-Muster verwenden. Ohne Beleg
keine einheitliche Struktur annehmen.

## 4. Abfrage im PartiQL-Editor ausführen

1. DynamoDB-Konsole → **Explore table items** → **PartiQL**.
2. Tabellenname wählen.
3. Abfrage aus einer `.partiql`-Datei kopieren, Platzhalter ersetzen.
4. **Run** — ausschließlich lesende Statements.
5. Ergebnisse nicht ungeprüft exportieren (siehe §8).

## 5. Ergebnisse sicher interpretieren

- `SELECT` mit `pk` + `sk` ist ein Punktzugriff (günstig).
- Eine Abfrage über `gsi1pk`/`gsi2pk` ist ein Indexzugriff; die Projektion bestimmt,
  welche Attribute direkt zurückkommen.
- **GSI3 ist `KEYS_ONLY`**: liefert nur Schlüssel; Details erfordern einen zweiten
  `GetItem`-Zugriff über die Basistabelle.
- Leere Ergebnisse bei `gsi2` können bedeuten: Order existiert nicht **oder** wurde
  anonymisiert (GSI2-Schlüssel werden entfernt) — nicht vorschnell als „gelöscht“ deuten.

## 6. Scan- und Kostenrisiken

- **Key-basiert** (`pk`/`sk` oder GSI-PK) ist der günstige Regelfall.
- **Scan** (Filter auf nicht indizierte Attribute wie `status` ohne Key) liest die
  Tabelle bzw. den Index vollständig und kann bei großen Tabellen teuer und langsam sein.
- `LIMIT` begrenzt **das Ergebnis**, nicht die gelesene Datenmenge — es ist **keine**
  Kostengarantie.
- `SELECT *` ist bei Orders zu vermeiden (PII, große Items, unnötige Kapazität).
  Verwende explizite Projektionen.
- Große Zeitfenster über GSI1 immer mit `BETWEEN` auf `gsi1sk` einschränken.

## 7. Datenschutzgrenzen

- `customer.name`, `customer.email` sowie Identitäts-/Ergebnisattribute können
  personenbezogene Daten enthalten.
- Keine vollständigen Datensätze als Standardausgabe, keine Screenshots mit PII,
  keine Weitergabe außerhalb des freigegebenen Kreises.
- Mandanten-/Partnerisolation ist **fachlich** (Owner + Consumer), nicht durch
  IAM-Leserechte oder SQL-Filter garantiert; siehe
  [`security-and-iam.md`](security-and-iam.md).

## 8. Restore-Tabellen untersuchen

Restore-Tabellen heißen `<TABLE_NAME>-restore-<timestamp>` und sind **nicht** produktiv.
Vergleiche gezielt einzelne Schlüssel und nicht sensible Metadaten
([`restore-comparison.partiql`](restore-comparison.partiql)). Einzelne Treffer beweisen
keine vollständige Migration.

## 9. Grenzen der Migrationsvalidierung

- PartiQL liefert Stichproben, keine vollständige Key-Inventur.
- Vollständige Validierung benötigt einen separaten, freigegebenen Abgleich
  (z. B. Key-Set-Diff, Counts je Status/Consumer) — siehe P3-Planung.
- Erasure/Anonymisierung kann Restore-Daten betreffen: vor einem Cutover müssen
  Löschungen erneut angewendet werden (P3E).

## 10. Dateien

| Datei | Inhalt |
|---|---|
| `schema-reference.md` | Belegtes Schema, Schlüssel, GSIs, PII-Attribute |
| `order-lookup.partiql` | Punktzugriff per `pk`/`sk` |
| `order-status.partiql` | Status-/Zeitprüfung (key-basiert, ohne Scan) |
| `gsi-diagnostics.partiql` | GSI1/GSI2/GSI3-Abfragen |
| `subject-diagnostics.partiql` | Subject-/Consumer-Prüfung, Erasure-Hinweise |
| `restore-comparison.partiql` | Stichproben Restore vs. Ziel |
| `security-and-iam.md` | IAM-Minimalrechte, Isolation, Grenzen |
