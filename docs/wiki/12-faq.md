# 12 · Häufige Fragen (FAQ)

Diese Seite beantwortet die Fragen, die man beim ersten Kontakt stellt — ohne
Cloud-Vorwissen. Für Details führen die Links in die Tiefe.

## Was ist Mays-Orders-AWS?

Ein Beispiel-Backend für Bestellungen: Eine App meldet einen Benutzer an,
legt eine Bestellung an, liest sie wieder, ändert den Status und kann Arbeit
asynchron verarbeiten. Die Infrastruktur wird mit Terraform beschrieben; ein
Builder kann daraus ein eigenständiges Projekt erzeugen.

## Kann ich das sofort produktiv nutzen?

**Nein.** Der aktuelle Stand ist ein Release Candidate (`v0.6.0-rc.1`). Es gibt
kein Produktionsdeployment, keine freigegebene Retention und keine produktive
Privacy-Aktivierung. Für einen echten Einsatz braucht es Betreiber-, Security-
und Datenschutz-Freigaben.

## Was kostet das?

Das Repository selbst ist Code. Kosten entstehen erst durch AWS-Ressourcen in
deinem Konto (Lambda, DynamoDB, API Gateway, SQS, Logs, ggf. Cognito). Die Wiki
nennt keine Preise; prüfe die AWS-Preisliste und dein eigenes Kostenprofil.
Der dokumentierte Development-Zyklus wurde nach dem Test wieder abgebaut.

## Welche Daten werden gespeichert?

- `customer.name` / `customer.email` (personenbezogen),
- `items` mit `sku`, `quantity`, `unitPrice` (Positionsdaten; SKU kann freier
  Text sein),
- `orderDescription` (optionaler Freitext, PII-Potenzial),
- technische Identitäts-/Status-/Verarbeitungsfelder.

Details und Löschverhalten: [Sicherheit und Datenschutz](06-sicherheit-und-datenschutz.md).

## Was passiert bei einer Löschanfrage?

Der Code enthält interne Funktionen für Inspect, Export, Erase und Anonymize.
`ERASE` löscht das Item, `ANONYMIZE` entfernt u. a. `customer`-PII, `subjectId`,
Indexschlüssel und `orderDescription`. Es gibt aber **kein Erasure-Ledger**;
Backups/PITR können Daten zurückbringen, und einige Identitätsfelder bleiben
pseudonym am Item. Das ist keine automatische DSGVO-Konformität.

## Wie setze ich es auf?

Zwei Wege:

1. **Module Builder:** erzeugt ein eigenständiges Terraform-Projekt
   (`complete` oder `orders-service`), ohne AWS-Mutation.
2. **Installer:** prüft Kontext, Plan, State und Artefakte; `deploy`/`destroy`
   sind echte AWS-Mutationen und brauchen menschliche Freigabe.

Siehe [Module Builder](04-module-builder.md) und [Installer](05-installer.md).

## Was ist der Unterschied zu Mays-RIS?

Mays-RIS ist ein separates System mit eigenem Repository, eigenem Release und
eigenem Deployment-Pin. Ein Mays-Orders-Release aktualisiert RIS **nicht**
automatisch. Die aktuelle RIS-Anbindung ist ein separater Vertrag; der RIS-Pin
bleibt laut Release Notes `1dbb0cb` (RC3).

## Warum gibt es so viele Testzahlen?

Weil unterschiedliche Dinge geprüft werden: Unit-Tests, Installer-Sicherheits-
gates, Policy Gate, E2E und AWS-Live-Tests. Eine hohe Zahl ist kein
Produktionsnachweis. Die Wiki nennt deshalb immer den Kontext (lokal, AWS-
Development, Produktion) und verlinkt den Report.

## Was ist ein Release Candidate?

Eine Vorabversion, die für einen bestimmten Prüfstand freigegeben ist — nicht
automatisch für Produktion. Der Git-Tag bindet einen Code-Commit; spätere
Doku-Commits ändern den Tag nicht.

## Muss ich Techniker sein, um die Wiki zu lesen?

Nein. Starte mit [Produkt und Rollen](01-produkt-und-rollen.md), dann
[Orders und API](03-orders-und-api.md) und [Sicherheit](06-sicherheit-und-datenschutz.md).
Begriffe findest du im [Glossar](10-glossar.md); die Tiefe im
[Dokumentationsportal](11-dokumentationsportal.md).

## Wo finde ich die verbindlichen Details?

Immer in den kanonischen Dokumenten, nicht in dieser FAQ:
`api/endpoints.md`, `docs/PROJECT_STATUS.md`, `docs/RELEASE_NOTES.md`,
`docs/roadmap/ROADMAP.md` und die verlinkten Reports.
