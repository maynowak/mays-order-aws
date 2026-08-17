# Business Requirements — OrderFlow GmbH

## 1. Geschäftskontext

**OrderFlow GmbH** ist ein fiktiver Händler, der Produkte online verkauft.
Das Bestell-Management-System **May's Orders** muss den vollständigen Lebenszyklus
einer Bestellung digital abbilden — von der Erstellung bis zur Lieferung — und
definierte Stornierungspfade unterstützen.

## 2. Kernanforderungen

| ID | Anforderung | Priorität |
|----|-------------|-----------|
| BR-01 | Bestellungen können angelegt werden (Order Creation) | MUST |
| BR-02 | Bestellungen können über ihre ID abgerufen werden (Order Retrieval) | MUST |
| BR-03 | Bestellungen können gelistet werden (Order Listing) | MUST |
| BR-04 | Der Status einer Bestellung kann entlang des definierten Lifecycles geändert werden | MUST |
| BR-05 | Der vollständige Order-Lifecycle `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` wird unterstützt | MUST |
| BR-06 | Definierte Stornierungspfade sind möglich (PENDING → CANCELLED, CONFIRMED → CANCELLED) | MUST |
| BR-07 | Ungültige Statusübergänge werden von der Anwendung erkannt und abgelehnt | MUST |
| BR-08 | Jede Bestellung erhält eine eindeutige Order-ID | MUST |
| BR-09 | Bestellungen enthalten mindestens Kundennachweis, Bestellpositionen und Gesamtbetrag | MUST |
| BR-10 | Änderungen am Bestellstatus sind nachvollziehbar (Timestamp) | SHOULD |
| BR-11 | Nur autorisierte Benutzer können auf das System zugreifen | MUST |
| BR-12 | Das System ist als AWS-Serverless-Lösung implementiert | MUST |
| BR-13 | Die Infrastruktur wird als Infrastructure as Code (Terraform) verwaltet | MUST |
| BR-14 | Das System erkennt konkurrierende Statusänderungen und erzeugt keinen inkonsistenten Zustand | MUST |

## 3. Nicht-funktionale Geschäftsanforderungen

| ID | Anforderung | Ziel |
|----|-------------|------|
| BNFR-01 | Skalierbarkeit: 100 → 1.000 → 10.000 → 100.000 Orders/Tag bewerten | MUST |
| BNFR-02 | Kostenbewusstsein für ein kleines Unternehmen | MUST |
| BNFR-03 | Verfügbarkeit durch serverlose Managed Services | SHOULD |
| BNFR-04 | Auslieferung als präsentierbares Projekt mit Dokumentation | MUST |

## 4. Erfolgskriterien

- Alle 4 API-Endpunkte (`POST /orders`, `GET /orders/{orderId}`, `GET /orders`, `PATCH /orders/{orderId}/status`) funktionieren.
- Alle in der State Transition Matrix definierten Übergänge verhalten sich korrekt (gültig → Erfolg, ungültig → Fehler).
- Konkurrierende Updates erzeugen keinen inkonsistenten Zustand (Conditional Writes).
- Infrastruktur vollständig per Terraform provisionierbar.
- Architekturentscheidungen sind begründet und mit Alternativen/Trade-offs dokumentiert.
