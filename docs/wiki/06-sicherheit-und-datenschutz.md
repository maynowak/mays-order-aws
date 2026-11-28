# 06 · Sicherheit und Datenschutz

> **Kurz erklärt:** Der Code kann Daten auskunften, exportieren und löschen.
> Ob und wie das produktiv genutzt werden darf, ist eine separate Entscheidung;
> diese Wiki behauptet keine DSGVO-Konformität.

> Diese Seite beschreibt technische Funktionen und bekannte Freigabegrenzen.
> Sie ist keine Rechtsberatung und keine Erklärung der DSGVO-Konformität.

## Sicherheitsprinzipien

- Benutzer authentifizieren sich mit Cognito/JWT; AWS-Dienstrechte laufen über
  IAM-Rollen.
- Zugriff wird nicht allein aus einem gültigen Login abgeleitet: Eigentümer-
  und Consumer-Kontext wird geprüft.
- IAM folgt dem Least-Privilege-Prinzip und verwendet enge Ressourcen-ARNs.
- Installer prüft Kontext, Plan, State, Terraform-Policy und Artefaktintegrität.
- Die CI orchestriert CodeQL und den Dependency-Scan über `security.yml`;
  der aktuelle `Security Gate (orchestration only)` prüft nur die Ausführung,
  **nicht** die Findings. Die vollständige Findings-Auswertung ist
  MO-GH-SEC-03 und noch nicht implementiert.
- Es werden keine Zugangsdaten oder Secret-Werte in Git eingecheckt.
- Ein Release/Modul-Tag aktualisiert kein unabhängiges Consumer-Projekt
  automatisch.

## Privacy-Funktionen

Das Order-Modul enthält interne Funktionen für **Inspect**, **Export** und
**Erase/Anonymize** in einer abgesicherten internen Vertrauensgrenze. Ihre
Fähigkeiten sind in Lambda- und Integrationstests dokumentiert. Es gibt daraus
keinen Schluss auf eine öffentliche Datenschutz-API oder eine freigegebene
Produktivbedienung.

Technische Funktionen können Betreiberpflichten unterstützen, bestimmen aber
nicht automatisch:

- den konkreten Zweck und die Rechtsgrundlage;
- verantwortliche Stelle, Auftragsverarbeitung und Empfänger;
- Aufbewahrungsdauer und gesetzliche Ausnahmen;
- den Umgang mit Backups, Logs, Wiederherstellung und Nebenwirkungen;
- einen Prozess für Betroffenenanfragen und menschliche Kontrolle.

### Datenkategorien und Erasure-Verhalten

| Feld/Kategorie | Einordnung | Inspect/Export | ANONYMIZE | ERASE |
|---|---|---|---|---|
| `customer.name`, `customer.email` | personenbezogen | ja | auf `ANONYMIZED`/`anonymized@example.com` gesetzt | Item wird gelöscht |
| `orderDescription` | Freitext, PII-Potenzial | ja | Attribut wird entfernt | Item wird gelöscht |
| `subjectId`, `gsi2pk`, `gsi2sk` | Owner-/Indexbindung, pseudonym | ja (Referenz) | entfernt | Item wird gelöscht |
| `ownerId`, `actorId`, `consumerId` | Identitätsbindung, pseudonym | ja | **bleiben** (vorbestehende Grenze) | Item wird gelöscht |
| `result`, `processingError`, `processingAttemptId` | Verarbeitung, kann Fach-/PII-Daten enthalten | ja | entfernt | Item wird gelöscht |
| `gsi3pk`, `gsi3sk` | Claim-Index | nein | entfernt | Item wird gelöscht |
| `items[].sku`, `quantity`, `unitPrice` | Positionsdaten; SKU kann freier Text sein | ja | bleiben | Item wird gelöscht |

Wichtige Grenzen:

- Nach `ANONYMIZE` ist die Order nicht mehr über GSI2 auffindbar; `GET` liefert
  404. `ownerId`/`actorId`/`consumerId` können jedoch eine vorbestehende
  Rest-Verknüpfung zum Benutzer ermöglichen — kein vollständiger
  Re-Identifikationsschutz.
- Ein Erasure-Ledger ist nicht implementiert; Backups/PITR können gelöschte oder
  anonymisierte Daten wiederbringen. Vor Restore/Cutover sind Löschungen erneut
  anzuwenden.
- `orderDescription` und freie `sku`-Konventionen sind keine Einladung, unnötige
  personenbezogene oder sensible Daten zu speichern. Siehe
  `api/endpoints.md` §2.1.1 und [Orders und API](03-orders-und-api.md).

## Retention und Secrets

Der aktuelle RC4-Stand lässt Retention/TTL wegen offener fachlicher Fragen
bewusst deaktiviert. Produktions-Secrets, optionale KMS-/Secrets-Manager-
Konfiguration und operative Aktivierung sind separate Freigabe-Gates. Die
Entwicklung von Secret-Providern und Rotationsmechanik ist nicht mit der
Freigabe ihres produktiven Betriebs gleichzusetzen.

**Produktions-Privacy und Produktionsdeployment sind BLOCKED/nicht erfolgt.**
Keinen Secret-Wert zu Testzwecken in Doku, Chat, Logs oder CLI-History
einfügen.

## Datenminimierung in der API

`customer.name`, `customer.email` und `orderDescription` können personenbezogen
sein. Freitext nur mit erforderlichen Informationen füllen. Tokens, interne
Secrets, unnötige Gesundheits-/Bewerbungsdaten oder sonstige sensible Inhalte
gehören nicht in SKU oder Beschreibung.

`orderDescription` ist optional, maximal 1.024 Zeichen nach Trimmen; es wird
bei Privacy-Inspect/-Export berücksichtigt und durch ANONYMIZE entfernt. Die
kompakte Order-Liste enthält dieses Feld nicht. Vor Client-Rollout prüfen, ob
F012 in der Zielumgebung tatsächlich deployed wurde.

## Sicherheits-Check vor einem Einsatz

1. Release-Tag und Git-Commit kontrollieren.
2. AWS-Konto, Identität, Region, Projekt/Workspace und Backend kontrollieren.
3. Datenkategorien und Testdaten bewusst festlegen.
4. IAM- und Terraform-Plan sowie Policy-Gate-Ergebnis prüfen.
5. Kosten, Backup, Recovery, Logs und Retention für genau diese Umgebung
   bewerten.
6. Menschliche Freigabe für jeden Apply, Destroy oder Produktionsbetrieb
   einholen.
7. Evidence versioniert sichern und offene Punkte sichtbar lassen.

### Quellen

- `security/`, `docs/security/`
- `docs/diagnostics/dynamodb/security-and-iam.md`
- `docs/reports/MAYS-ORDERS-DSGVO-*.md`
- `docs/reports/MO-RC4-P00-*.md`
- `docs/reports/MO-ORDER-DESCRIPTION-01…05`
- `docs/roadmap/ROADMAP.md`
- `docs/RELEASE_NOTES.md`
- [Dokumentationsportal](11-dokumentationsportal.md)
