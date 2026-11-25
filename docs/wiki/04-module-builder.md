# 04 · Module Builder

> **Kurz erklärt:** Der Builder kopiert ausgewählte Bausteine in einen neuen
> Ordner. Du bekommst ein eigenes Terraform-Projekt — aber noch keine
> AWS-Umgebung.

## Was der Builder macht

Der Module Builder erstellt aus ausgewählten, versionierten Projektbausteinen
ein eigenständiges Terraform-Zielprojekt. Er übernimmt unter anderem
Terraform-Module, Root-Wiring, Policy-Dateien und erforderliche
Lambda-Build-Artefakte. Das Ergebnis ist ein überprüfbarer Projektordner;
**es ist noch keine AWS-Bereitstellung**.

## Auswahlmöglichkeiten

| Auswahl | Wofür sie gedacht ist |
|---|---|
| `complete` | vollständiger Stack mit Order-API, Authentifizierung, Datenbank, Lambda, Queue/Worker und optionalen Ergänzungen gemäß Projektkonfiguration |
| `orders-service` | festgelegte, wiederverwendbare Sieben-Modul-Komposition |
| `--modules` | explizite Auswahl; erforderliche Abhängigkeiten werden fail-closed geprüft |
| `--with-deps` | fügt benötigte transitive Abhängigkeiten deterministisch hinzu |

Der Modul-Katalog und die vom ausgecheckten Stand unterstützte CLI-Syntax sind
maßgeblich. Verwende vor einem Build `python3 -m module_builder --help` sowie
`python3 -m module_builder presets`.

Der Preset `orders-service` besteht aus genau sieben Modulen:
`api`, `cognito`, `dynamodb`, `iam`, `lambda`, `sqs`, `sqs_worker`. Er ist als
lokales Terraform-Modul gedacht; die Composition ist fest, keine freie Auswahl.

### Verifizierte CLI-Beispiele

```bash
python3 -m module_builder presets

python3 -m module_builder build \
  --target ./generated/my-orders \
  --project-name my-orders \
  --preset complete \
  --validate

# Freie Auswahl mit Pflicht-Abhängigkeiten (fail-closed):
python3 -m module_builder build \
  --target ./generated/orders-core \
  --project-name orders-core \
  --modules dynamodb,iam,lambda \
  --with-deps

# Upgrade-Vorschau / kontrolliertes Upgrade:
python3 -m module_builder upgrade --project ./generated/my-orders --dry-run
python3 -m module_builder upgrade --project ./generated/my-orders --apply
```

`--validate` führt `terraform fmt -check`, `init -backend=false` und `validate`
aus (read-only, kein AWS-Kontakt). `--force` überschreibt nur Builder-eigene
Dateien und löscht niemals fremde Dateien.

## Typischer Offline-Start

```bash
git clone https://github.com/maynowak/mays-order-aws.git
cd mays-order-aws
git checkout v0.6.0-rc.1

python3 -m module_builder presets
python3 -m module_builder --help

python3 -m module_builder build \
  --target ./generated/my-orders \
  --project-name my-orders \
  --preset complete \
  --validate
```

Die konkrete CLI-Version am Tag prüfen: neuere `main`-Änderungen können nach
dem Release-Tag hinzugekommen sein. Für ein wiederverwendbares Service-Modul
den `orders-service`-Preset wählen. Eine Modulauswahl nicht anhand des Namens
allein als sicher oder vollständig annehmen; die Dependency-Prüfung und den
erzeugten Inhalt kontrollieren.

## Nach dem Build

1. Das Manifest und die erzeugten Module prüfen.
2. Variablen, AWS-Konto, Region, Identity-Modus, State-Backend und Kosten
   verstehen.
3. Terraform formatieren, initialisieren und validieren.
4. Den erzeugten Plan mit dem Policy Gate auswerten.
5. Nur einen geprüften und ausdrücklich freigegebenen Plan bereitstellen.

Deterministische Builds helfen beim Vergleich: Die gleichen Eingaben sollen
identische Artefakte erzeugen. Das ersetzt weder Artifact-Integrity-Prüfung
noch eine Prüfung des tatsächlichen Zielprojekts.

## Upgrades

Der Builder schützt fremde Nutzerdaten und prüft Fingerprints/Upgrade-Kontext.
Ein Upgrade ist trotzdem eine Änderung am Zielprojekt. Vor Ausführung immer
die Upgrade-Vorschau (`--dry-run`), Drift- und Kompatibilitätsprüfung und das
Backup-/Recovery-Verfahren lesen. Release-Kompatibilität nicht aus der
Versionsnummer des Builders allein ableiten: Das Repository unterscheidet
Release-Label, Builder-Version, Installer-Version und Deployment-/Teststack-
Version.

## Was der Builder nicht macht

- Kein AWS-Deployment, kein `terraform apply`, kein State-Zugriff.
- Keine Laufzeit-Abhängigkeit des Zielprojekts zum Quellrepository.
- Keine Freigabe für Kosten, IAM oder Produktion; das bleibt beim Betreiber.
- Keine automatische Übernahme fremder Dateien oder Nutzerdaten.

### Quellen

- `module_builder/cli.py`, `module_builder/catalog.py`, `module_builder/spec.py`
- `docs/reports/MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01.md`
- `docs/reports/MAYS-ORDERS-MODULE-BUILDER-HARDENING-01.md`
- `docs/reports/MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01.md`
- `docs/reports/MAYS-ORDERS-MODULE-CONTRACT-01.md`
- `docs/MAYS_ORDERS_TERRAFORM_MODUL_INTEGRATION_TEST_GUIDE_2026-10-19.md`
- [Dokumentationsportal](11-dokumentationsportal.md)
