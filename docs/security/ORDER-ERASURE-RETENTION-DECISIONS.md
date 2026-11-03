# Order-Erasure — Retention- und Lösch-Entscheidungen (P3E-01)

**Status:** Entscheidungsvorlage. **Alle Fristen sind OFFEN.** Es werden keine
gesetzlichen Fristen erfunden und keine TTL konfiguriert.

---

## 1. Ausgangslage (belegt)

| Datenklasse | Ist-Zustand | Beleg |
|---|---|---|
| Order-Daten | DynamoDB Single-Table, keine Retention-Felder/TTL | `terraform/modules/dynamodb/main.tf` |
| Erasure-Ledger | **nicht vorhanden** | P3E-Analyse |
| On-Demand-Backup | **nicht vorhanden** (P3A nur lokal) | `docs/ORDER-BACKUP-LIFECYCLE.md` |
| PITR | Terraform `enabled = true`, AWS-Fenster nicht verifiziert | `main.tf:108-110` |
| Restore-Tabellen | **nicht vorhanden** | P3A/P3B |
| Diagnose-/Evidenzdateien | lokal im Run-Verzeichnis, keine Frist | `.mays-installer/runs/` |
| CloudWatch Logs | Retention über `log_retention_days` konfigurierbar | Terraform |
| CloudTrail | Management-Events, kein Lifecycle definiert | `docs/reports/BACKUP-01...` |

ADR-008 (Retention/Privacy) ist **PROPOSED**, nicht umgesetzt. Es gibt keine
Löschfristen, keine TTL und kein Ledger.

---

## 2. Entscheidungsmatrix

| Datenklasse | Zweck | Aufbewahrung | Löschung | Entscheidung |
|---|---|---|---|---|
| Order-Daten | Fachlicher Betrieb | **OFFEN** | Zu definieren (Erasure/Retention) | **OPEN** |
| Erasure-Ledger | Restore-Schutz/Nachweis | **OFFEN** (mind. so lange wie Backups) | Zu definieren, append-only | **OPEN** |
| On-Demand-Backup | Recovery | **OFFEN** | Zu definieren (manuell/Lifecycle) | **OPEN** |
| PITR | Recovery | AWS-Fenster **prüfen** | AWS-Lifecycle | **OPEN** |
| Restore-Tabelle | Migration/Recovery | **OFFEN** | Nach validiertem Cutover | **OPEN** |
| Diagnose-/Evidenzdateien | Audit/Nachweis | **OFFEN** | Zu definieren | **OPEN** |
| CloudWatch Logs | Betrieb/Audit | `log_retention_days` (bestehend) | Log-Group-Lifecycle | **EXISTING, fachlich prüfen** |
| CloudTrail | Audit | unbegrenzt (Ist) | kein Lifecycle | **OPEN** |

**Keine Zelle darf ohne fachlich-rechtliche Freigabe als Frist interpretiert werden.**

---

## 3. Erforderliche Entscheidungen

| ID | Frage | Entscheider | Status |
|---|---|---|---|
| R-01 | Aufbewahrungsfrist Order-Daten (aktiv) | Betreiber/Recht | OPEN |
| R-02 | Frist für Erasure-Ledger (muss Backups überdauern) | Recht/Technik | OPEN |
| R-03 | Aufbewahrung/Löschung On-Demand-Backups | Betrieb/Recht | OPEN |
| R-04 | PITR-Fenster und Wiederherstellungsstrategie | Betrieb | OPEN (AWS prüfen) |
| R-05 | Lebensdauer Restore-Tabellen | Betrieb | OPEN |
| R-06 | Aufbewahrung von Diagnose-/Evidenzdateien | Audit/Betrieb | OPEN |
| R-07 | Löschverfahren für Ledger-Einträge (nur nach Frist) | Technik/Recht | OPEN |
| R-08 | Key-Rotation und Aufbewahrung alter HMAC-Schlüssel | Security | OPEN |
| R-09 | Umgang mit gelöschten PII in Backups/Restores | Recht/Technik | OPEN |
| R-10 | Nachweisformat für Betroffenenrechte | Recht | OPEN |

---

## 4. Löschmechanik (Entwurf, nicht implementiert)

- **Aktive Order:** ERASE = `DeleteItem` (bestehend); ANONYMIZE = Felder entfernen
  (bestehend). Ein Ledger-Eintrag dokumentiert Entscheidung + Anwendung.
- **Ledger:** append-only; Löschung nur nach R-02 und mit Nachweis. Ein Ledger, das
  zusammen mit der Order-Tabelle restauriert wird, ist als Schutz ungeeignet.
- **Backups/PITR:** Ein Restore kann gelöschte PII wiederherstellen. Vor jedem
  produktiven Restore muss P3E-Reconciliation laufen; ein Backup ist **keine**
  DSGVO-Ausnahme.
- **Restore-Tabellen:** nach erfolgreicher Prüfung/Cutover löschen; bis dahin
  isoliert und ohne App-Bindung.
- **Evidenz:** nur Metadaten; keine Order-Inhalte/PII.
- **TTL:** **nicht konfigurieren**, solange R-01/R-02 offen sind.

---

## 5. DSGVO-Risiken

| Risiko | Bewertung | Maßnahme |
|---|---|---|
| Zweckbindung Ledger | Ledger dient Lösch-/Restore-Nachweis | Zweck dokumentieren, keine Werbung/Analytics |
| Datenminimierung | Order-IDs + pseudonyme Subject-Refs | keine Payloads, keine Namen/E-Mails |
| Zugriffsschutz | Ledger enthält pseudonyme personenbezogene Daten | eigene Rolle, Least Privilege, Audit |
| Integrität | Selbst-Hash ist keine Signatur | unabhängiger Store, Zugriffskontrolle |
| Löschbarkeit | Ledger soll Backups überdauern | Frist/Löschverfahren R-02/R-07 |
| Backup-Retention | PII in Backups | R-03/R-09, keine Pauschalaussage |
| Wiederherstellung gelöschter Daten | hohes Risiko | Reconciliation + Re-Erase vor Cutover |
| Pseudonymisierung | HMAC bleibt personenbeziehbar | Key-Management, Rotation, keine Anonymitätsbehauptung |
| Betroffenenrechte | Auskunft/Löschung | Ledger als Nachweis, keine Roh-Subjects |
| Nachweisbarkeit | keine Signatur/keine Persistenz | P3E-01 nur Plan; produktiver Store offen |

**Keine DSGVO-Konformität behaupten.** Die abschließende Bewertung von Fristen und
Rechtsgrundlagen bleibt eine fachlich-rechtliche Entscheidung.

---

## 6. Empfehlung (ohne Entscheidung vorwegzunehmen)

1. R-02 vor jeder produktiven Ledger-Persistenz entscheiden; Ledger muss länger als
   das längste Backup/PITR-Fenster verfügbar sein.
2. Ledger unabhängig von der Order-Tabelle speichern (Option C/B).
3. Erst danach P3B-Restore und P3E-Reconciliation produktiv verdrahten.
4. Keine TTL, bis R-01/R-02 freigegeben sind.
5. Löschungen im Ledger nur als neue, geprüfte Ereignisse dokumentieren; keine
   stillen Löschungen.
