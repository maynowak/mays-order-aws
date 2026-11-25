# 01 · Produkt und Rollen

> **Kurz erklärt:** Dieses Projekt ist ein Baukasten für ein Bestellsystem in
> der Cloud — kein fertiges Produkt, das man ohne Betreiber- und
> Datenschutzentscheidungen einfach produktiv einschaltet.

## Was ist Mays-Orders-AWS?

Mays-Orders-AWS ist ein eigenständiges, serverloses Backend zur Verwaltung von
Bestellungen und zugehöriger Verarbeitung. Die Beispielorganisation
„OrderFlow GmbH“ ist fiktiv. Das Repository ist zugleich ein Lern- und
Engineering-Projekt: Es enthält Infrastruktur als Code, einen modularen
Generator, Laufzeitcode, Tests, Release-Nachweise und Betriebsdokumentation.

Das Projekt besteht aus vier sichtbaren Teilen:

1. **Order-Service:** API, Geschäftsregeln, Persistenz und asynchrone Arbeit.
2. **Terraform-Module:** AWS-Ressourcen als wiederverwendbare Komponenten.
3. **Module Builder:** Auswahl und Kopie von Modulen in ein separates Zielprojekt.
4. **Installer:** geprüfte Bedienung von Terraform-Plan, Deployment, State und
   Rückbau.

## Wer nutzt welche Teile?

| Rolle | Was die Person tut | Gute erste Seiten |
|---|---|---|
| Fachliche Leserin / Produktinteressierte | Funktionsumfang und Systemgrenzen einordnen | diese Seite, [Architektur](02-architektur.md) |
| API-Client-Entwickler | JWT verwenden, Orders anlegen/lesen und Statusänderungen integrieren | [Orders und API](03-orders-und-api.md), `api/endpoints.md` |
| Plattform- oder Cloud-Engineer | Module auswählen, Konfiguration prüfen und Infrastruktur bereitstellen | [Builder](04-module-builder.md), [Installer](05-installer.md) |
| Betreiber / Security-Verantwortliche | AWS-Konto, Identität, Rechte, Kosten, Freigaben und Rückbau prüfen | [Sicherheit](06-sicherheit-und-datenschutz.md), [Betrieb](07-betrieb-und-release.md) |
| Beitragende | Änderungen, Tests, Evidenz und Git-Checkpoint pflegen | [Entwicklung](08-entwicklung-und-qualitaet.md) |

## Was das Projekt leistet

- authentifizierte Order-Endpunkte;
- regelbasierte Statusänderungen und atomare Konkurrenzkontrolle;
- optionale asynchrone Verarbeitung über Queue und Worker;
- skalierbare AWS-Infrastruktur ohne selbst verwaltete Server;
- wiederverwendbare Modulzusammenstellungen;
- Schutzprüfungen für AWS-Identität, Projekt-/State-Kontext, Artefakte und
  Terraform-Plan;
- interne Privacy-Funktionen im Code, deren produktiver Einsatz separat
  freigegeben werden muss.

## Was die Dokumentation nicht behauptet

Ein grüner Unit-Test ist kein Live-AWS-Nachweis. Ein erfolgreicher Development-
Zyklus ist keine Produktionsfreigabe. Ein im `main` vorhandenes Feature ist
nicht notwendigerweise deployed. Der Release-Kandidat ist keine Zusicherung,
dass schon ein bestimmter produktiver Betreiber, Datenverarbeitungsvertrag,
Aufbewahrungsplan oder Bereitschaftsdienst besteht.

Mays-RIS und Mays-Orders-AWS sind getrennte Systeme mit getrennten Repositories,
Releases und Deployment-Pins. Die Wiki verwendet „RIS-Integration“ nur dort, wo
ein konkreter, versionsgebundener Integrationsnachweis existiert.

## Ein einfacher Vergleich

Man kann das Projekt als Baukasten verstehen: Die Terraform-Module sind die
Bauteile, der Module Builder stellt daraus ein eigenständiges Projekt zusammen,
und der Installer begleitet die Installation mit Prüfungen. Der eigentliche
Order-Service ist das Produkt, das dieses Projekt bereitstellen kann.

Weiter: [Architektur →](02-architektur.md) · [Begriffe →](10-glossar.md)
