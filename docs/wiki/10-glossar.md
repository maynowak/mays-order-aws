# 10 · Glossar

Die Begriffe sind so erklärt, dass du die Wiki ohne Vorwissen lesen kannst.
Technische Tiefe steht in den verlinkten Fachdokumenten.

| Begriff | Einfach erklärt | Warum wichtig |
|---|---|---|
| API Gateway HTTP API | Der „Empfang“ im Internet, der Anfragen an die Lambda weiterreicht | Prüft das JWT, bevor Code läuft |
| AWS | Amazon Cloud; hier laufen die optionalen Ressourcen | Kosten, Rechte und Region müssen bewusst gewählt werden |
| Backend / State | Terraform merkt sich im „State“, welche Ressourcen es verwaltet | Falscher State kann fremde Ressourcen treffen |
| Cognito / JWT | Anmeldedienst und signiertes Token („Ausweis“) | Identität, nicht AWS-Berechtigung |
| Consumer | Ein aufrufendes System (z. B. eine App), nicht der Endnutzer | Bestimmt, welche Orders sichtbar sind |
| DLQ (Dead-Letter Queue) | „Wartezimmer“ für Nachrichten, die nicht verarbeitet werden konnten | Fehler sichtbar machen, ohne sie zu verlieren |
| DynamoDB | AWS-Datenbank für die Orders | Wird über Schlüssel/Indizes gelesen, nicht per Vollscan |
| D8 / `directAWSGit` | Zwei CI/CD-Pipelines im AWS-Konto | D8 hat eine Approval-Stage; `directAWSGit` ist nicht push-getriggert |
| Erasure-Ledger | Nachweisliste über Löschungen | Fehlt derzeit; Restore kann Daten zurückbringen |
| GSI | Zusätzlicher Datenbank-Index | Macht Suche nach Owner/Verarbeitung möglich |
| HMAC | Signaturverfahren mit gemeinsamem Schlüssel | Schützt interne Payloads; nicht mit Benutzer-Login verwechseln |
| IaC | Infrastruktur als Code (hier Terraform) | Nachvollziehbar, wiederholbar, prüfbar |
| IAM | AWS-Rechte für Dienste/Rollen | Least Privilege; keine Access Keys als Login |
| Idempotenz | Derselbe Vorgang mehrfach ausgeführt hat denselben Effekt | Schutz vor Doppelverarbeitung |
| KMS | AWS-Schlüsseldienst | Optionale Verschlüsselung; Produktion separat freizugeben |
| Lambda | AWS-Funktion für API und Worker | Kein dauerhaft laufender Server |
| Module Builder | Erzeugt aus Modulen ein eigenständiges Terraform-Projekt | Wiederverwendung ohne Laufzeitabhängigkeit |
| `orders-service` | Fester Builder-Preset aus 7 Modulen | Wiederverwendbares Orders-Service-Modul |
| Owner / `subjectId` | Der Benutzer, dem eine Order gehört | Zugriff und Datenschutz |
| `orderType` | Routing-/Verarbeitungstyp (z. B. `generic`) | Steuert den Handler; **keine** Berechtigung |
| `orderDescription` | Optionaler Freitext (max. 1.024 Zeichen) | Kann PII enthalten; Privacy beachten |
| PII | Personenbezogene Daten | Datenschutz, Export, Löschung |
| PITR | Point-in-Time-Recovery für DynamoDB | Backup kann gelöschte Daten zurückbringen |
| Policy Gate | Regelprüfung des Terraform-Plans | Verhindert unerwünschte Änderungen vor Apply |
| RC | Release Candidate: geprüfte Vorabversion | Kein Produktionsfreigabe-Ersatz |
| Retention / TTL | Aufbewahrungsfrist/automatische Löschung | Derzeit bewusst deaktiviert |
| RIS | Mays Recruiting Intelligence System | Getrenntes System mit eigenem Pin |
| SKU | Positionskennung; hier freier String ohne Katalogprüfung | Eigene Konventionen möglich, aber kein Routing-Ersatz |
| Source-Fail | Pipeline scheitert schon beim Quell-Artefakt | Kein Build/Plan/Deploy; fail-closed |
| SQS | AWS-Warteschlange für asynchrone Arbeit | Entkopplung und Wiederholungen |
| Terraform Workspace | Logische State-Auswahl im Backend | Keine Zugriffsgrenze und kein Ersatz für Konten |
| TTL | Time-to-live, automatisches Ablaufen | Siehe Retention |

## Abkürzungen

| Abkürzung | Bedeutung |
|---|---|
| ADR | Architecture Decision Record |
| CI/CD | Continuous Integration / Continuous Delivery |
| DSGVO | Datenschutz-Grundverordnung |
| E2E | End-to-End-Test |
| GSI | Global Secondary Index |
| IaC | Infrastructure as Code |
| JWT | JSON Web Token |
| PII | Personally Identifiable Information |
| PITR | Point-in-Time Recovery |
| RC | Release Candidate |
| RIS | Mays Recruiting Intelligence System |
| SKU | Stock Keeping Unit (hier: freie Positionskennung) |
| SQS | Simple Queue Service |
| TTL | Time to Live |

Siehe außerdem `docs/learning/glossary.md` für das lernorientierte Projektglossar
und das [Dokumentationsportal](11-dokumentationsportal.md) für die Tiefe.
