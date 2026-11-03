# Sicherheit und IAM für PartiQL-Diagnosen

**Grundsatz:** Diagnosezugriff ist **lesend**, rollengetrennt und möglichst eng.
Die Anwendungsrolle (Lambda) wird **nicht** erweitert; Diagnosen laufen über eine
separate Rolle und nur in freigegebenen Umgebungen.

## 1. Benötigte IAM-Aktionen

| Aktion | Zweck | Erforderlich? |
|---|---|---|
| `dynamodb:PartiQLSelect` | Ausführung von `SELECT` im PartiQL-Editor | ja |
| `dynamodb:GetItem` | Punktzugriff (auch als Teil eines PartiQL-Plans) | ja |
| `dynamodb:Query` | Key-/Indexabfragen (GSI1/GSI2/GSI3) | ja |
| `dynamodb:Scan` | vollständige Tabellen-/Indexlesung | **nein** (bewusst nicht erteilen) |
| `dynamodb:DescribeTable` | Metadaten/Indexprüfung | optional |
| `dynamodb:PartiQLInsert` / `PartiQLUpdate` / `PartiQLDelete` | schreibende Statements | **niemals** |
| `dynamodb:PutItem` / `UpdateItem` / `DeleteItem` / `BatchWriteItem` | Schreibzugriff | **niemals** |

**Wichtig:** `PartiQLSelect` ist keine Garantie für einen günstigen Plan. Je nach
Abfrage plant DynamoDB intern `GetItem`, `Query` oder `Scan`. Wer `Scan` nicht
erteilt, verhindert unbeabsichtigte Volltabellenlesungen — nicht-key-basierte
Abfragen schlagen dann fehl (erwünscht).

## 2. Ressourcen-ARNs

Leserechte nur auf Tabelle und die tatsächlich benötigten Indizes:

```text
arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>
arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>/index/gsi1
arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>/index/gsi2
arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>/index/gsi3
arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>-restore-*
```

`<ACCOUNT_ID>` ist ein Platzhalter, keine echte Kontonummer. Restore-Tabellen
(`<TABLE_NAME>-restore-<timestamp>`) sind **nicht produktiv**; Lesezugriff nur
für Diagnose/Freigabe, niemals automatische App-Bindung.

## 3. Rollentrennung

- **Keine** Änderung an `terraform/modules/iam/main.tf` (Lambda-Rolle) und
  `terraform/modules/sqs-worker/iam.tf`.
- Diagnose-Rolle ist eine menschliche Operator-Rolle (SSO/Role-Switch), kein
  Service-Prinzipal der Anwendung.
- Kein `AdministratorAccess`, kein `dynamodb:*`, kein `Resource: "*"`.
- Schreibende Aktionen sind auch nicht „temporär“ zu erteilen.

## 4. Mandanten- und Partnerisolation

IAM kann **keine** Mandantenisolation auf Item-Ebene erzwingen. Die fachliche
Isolation erfolgt in der Anwendung:

- `subjectId` (Owner) und `consumerId` (`cognito:<issuer>#<client>`).
- GET/PATCH prüfen Owner **und** Consumer; fehlende Identität → 404
  (`api/endpoints.md`, `lambda/src/order_service.py`).
- Ein `SELECT` mit `WHERE`-Filter ist **keine** Autorisierung: Die Diagnose-Rolle
  sieht alle Items der Tabelle, unabhängig von `consumerId`.

**Konsequenz:** Diagnosezugriff ist auf freigegebene Personen/Umgebungen zu
beschränken. Für Produktionsdaten ist eine gesonderte Freigabe nötig; lieber in
einer Restore-/Testtabelle diagnostizieren.

## 5. Datenschutz (DSGVO)

- `customer.name`/`customer.email` sind personenbezogen; `subjectId`, `ownerId`,
  `actorId` sind pseudonym, aber personenbeziehbar.
- Nur benötigte Attribute projizieren; `SELECT *` vermeiden.
- Keine Exporte, Screenshots oder Tickets mit PII; Ergebnisse nicht in Logs
  kopieren.
- Anonymisierte Orders (`customer = ANONYMIZED`, `subjectId` entfernt) nicht
  re-identifizieren.
- Ein Restore kann gelöschte/anonymisierte Daten zurückbringen. Vor jedem
  Cutover müssen Löschungen erneut angewendet werden (P3E); ein PartiQL-`SELECT`
  ist **kein** Lösch- oder Konformitätsnachweis.

## 6. Auditierbarkeit

- CloudTrail zeichnet Management-Events auf; DynamoDB-`GetItem`/`Query` sind
  Datenzugriffe und nur mit Data-Events sichtbar (nicht Standard).
- Diagnose-Sitzungen daher organisatorisch dokumentieren (Wer, wann, welche
  Tabelle, Zweck).
- Ergebnisse mit Zeitstempel und Tabellen-ARN ablegen, ohne PII.

## 7. Grenzen

- Kein vollständiger Migrationsnachweis per PartiQL (nur Stichproben).
- Keine Isolation durch SQL-Filter oder bloße IAM-Leserechte.
- Keine Aussage über DSGVO-Konformität ohne technische und organisatorische
  Nachweise.
