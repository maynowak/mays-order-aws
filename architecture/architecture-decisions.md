# Architecture Decisions — May's Orders

## ADR-001: Serverless-Kernarchitektur (API Gateway + Lambda + DynamoDB)

**Status:** ACCEPTED

### Problem

Ein Order-Management-System mit vier Endpunkten und klaren State-Transitions soll
kostengünstig, skalierbar und wartbar betrieben werden.

### Alternativen

| Option | Bewertung |
|--------|-----------|
| **A) Serverless: HTTP API + Lambda + DynamoDB** | Pay-per-use, automatisch skalierend, kein Server-Management. **GEWÄHLT** |
| B) EC2 (verwalteter Server) | Server-Patching, feste Kosten, manuelles Auto-Scaling, Overkill für 100–100k Orders/Tag |
| C) RDS (relational) | Kosten + Wartung; benötigt VPC/Subnets; kein relationales Modell gefordert |
| D) Fargate (Container) | Mehr Komplexität (Image-Build, ECS), kein Vorteil gegenüber Lambda hier |

### Entscheidung

Option A. Lambda-Funktion + DynamoDB sind vollständig verwaltete Services, skalieren
automatisch, sind kostenbewusst (Pay-per-Use, Free-Tier) und erfordern **keine VPC,
Subnets oder NAT Gateway**.

### Trade-offs

- Cold Starts: akzeptabel für Bestell-Backoffice-Latenz (erste Request einiger 100 ms).
- Lambda-Zeitlimit/Invocations sind begrenzt, für diese Workload irrelevant.
- Kein dauerhaft gehaltener Prozess → Zustand lebt ausschließlich in DynamoDB (stateless,
  gute Skalierung).

## ADR-002: DynamoDB Single-Table + GSI für Listing

**Status:** ACCEPTED (Begründung: `database/dynamodb-design.md`, `database/access-patterns.md`)

- Eine Tabelle `mays-orders`, Punktzugriffe über `pk`, Listing über GSI1 (`LIST` → `createdAt`).
- **Kein Scan** für irgendein Pattern.

## ADR-003: Cognito User Pool als Authentication

**Status:** ACCEPTED (Begründung: `security/authentication-decision.md`)

- Benutzeridentität via Cognito User Pool; JWT wird vom API Gateway `COGNITO_USER_POOLS`-Autorisator validiert.
- Kostenlos bis 50.000 MAU.
- Kein Custom-Authorizer, kein IAM für Benutzer.

## ADR-004: HTTP API (API Gateway V2) statt REST API

**Status:** ACCEPTED

- Native JWT-Autorisierung, ~70 % günstiger pro Request, ausreichendes Feature-Set.

## ADR-005: State Machine im Code statt Step Functions

**Status:** ACCEPTED (Woche 1)

| Kriterium | Step Functions | Code (Domain-Layer) |
|-----------|----------------|---------------------|
| Sichtbarkeit des Zustands | Als Ressource sichtbar | Im Code als Tabelle |
| Kosten | 4.000 State-Transitions kostenlos, danach 0,025 $/1.000 | 0 |
| Komplexität | Neuer Service, ASL-Definition, zusätzliches IAM | Eine Modul-Funktion, unit-testbar |
| Geeignet | Komplexe, langlaufende Prozesse | 6 Zustände, ein Request/Response |

6 Zustände, 6 gültige Übergänge, synchron — ein zusätzlicher AWS-Service wäre hier
**unnötige Komplexität** (Requirements C-03). Die State Machine wird als pure, unit-getestete
Funktion implementiert; DynamoDB Conditional Writes garantieren die atomare Durchsetzung.

**Wenn später nötig** (z. B. langlaufende Versand-Integration): Step Functions als
Migration dokumentiert.

## ADR-006: Keine zusätzlichen Services (SQS, EventBridge, VPC, NAT)

**Status:** ACCEPTED

- Kein Bedarf an asynchronem Messaging (synchroner Request/Response).
- Kein VPC: Lambda → DynamoDB läuft ohne VPC.
- Kein zusätzlicher Service wird ohne neue Architecture Decision ergänzt.

## ADR-007: On-Demand Capacity (vorläufig)

**Status:** PROPOSED (Entscheidung in Woche 4 mit Kosten-Daten finalisiert)

- On-Demand für schwankenden Test-/Demo-Verkehr; Quantifizierung Provisioned vs. On-Demand
  in `cost/cost-analysis.md`.

## Zusammenfassung Architektur

```text
Client
  │  Bearer JWT
  ▼
Cognito User Pool ──(JWT-Ausstellung)──┐
  ▲                                   │
  │ login/refresh                     ▼
  └────────────────── API Gateway (HTTP API, JWT-Autorisator)
                              │
                              ▼
                      Lambda (Order Handler)
                              │  IAM Execution Role (Least Privilege)
                              ▼
                        DynamoDB (mays-orders)
                              │
                              ▼
                          CloudWatch (Logs, Metriken, Alarme)
```

---

## ADR-008: Privacy-Secret-Management, Retention und Orphan-Cleanup

**Status:** PROPOSED (Auftragsbezeichnung war „ADR-007"; die Nummer 007 ist bereits durch
„On-Demand Capacity" belegt — siehe ADR-007 oben. Es gilt die bestehende Konvention:
fortlaufende Nummern in dieser Datei, kein separates `docs/adr/`.)

**Datum:** 2026-11-01 · **Basis:** RC3 (`086a8be`), Branch `feature/mo-rc4-kms-privacy-retention`

**Auftragsbezug:** MO-RC4-P01. Belege: `docs/reports/MO-RC4-P01-CONTRACT-INVENTORY.md`,
`MO-RC4-P01-ORPHAN-CLEANUP-DESIGN.md`, `MO-RC4-P01-SECRET-PROVIDER-DESIGN.md`,
`MO-RC4-P01-OPEN-QUESTIONS.md`.

### Kontext (belegte Befunde)

- `PRIVACY_INTERNAL_SECRET` wird nur aus der Lambda-Env gelesen (`order_service.py:114`) und
  von Terraform **nicht** provisioniert.
- Es gibt **keine** KMS-/Secrets-Manager-Ressourcen und **keine** `kms:`-Berechtigungen.
- Bestellungen haben **keinen** Nutzerbezug im API-Pfad (`index.py:143` übergibt kein
  `subject_id`), **keine** Retention-Felder und **keine** Fristen.
- Benutzerlöschung ist in keinem der fünf geprüften Szenarien unterstützt.
- RIS schreibt direkt in die MO-Tabelle (ohne `subjectId`, mit abweichendem `pk`-Muster).

### Entscheidungen (je einzeln, alle **PROPOSED**)

**D-1 — Wiederverwendung bestehender Benutzer-/Bestellverträge**
Ja. Es werden **keine** neuen Pflichtfelder eingeführt. Genutzt wird der vorhandene
`subjectId`-Mechanismus (Feld, GSI2) sowie der JWT-Claim `sub`. Der API-Body bleibt
unverändert (`customer`, `items`, `currency`).

**D-2 — Orphan Detection**
Verwaist = Nutzer nachweislich weg **und** Frist abgelaufen **und** nicht `RETAIN`.
Bestellungen **ohne** Nutzerbezug gelten **nicht** als verwaist. Nicht prüfbare Zuordnung
(EXTERNAL-Cognito, Fehler) ⇒ kein Löschen (fail-closed). Fremde Schreibpfade (RIS) sind
nur über ein Provenienzmerkmal von MO-Daten unterscheidbar.

**D-3 — Cleanup nach Benutzerlöschung**
Primär ein **idempotenter, dry-run-fähiger Prüflauf** (manuell auslösbar), ergänzt durch den
bestehenden `privacy/erase`-Auftrag. TTL ist **Beschleuniger**, **kein** Lösch-Nachweis.
Kein eventbasierter Trigger in RC4 (keine Cognito-Trigger vorhanden; EXTERNAL-Pools nicht
abgedeckt).

**D-4 — Retention-Verantwortung MO ↔ Consumer**
MO führt **Mechanik** (Felder, Fristdurchsetzung, Nachweis) und setzt Defaults;
der **Consumer** entscheidet über Fristen/`RETAIN` je Einsatz. Ohne Consumer-Vorgabe gilt
der MO-Default. Rechtliche Fristwerte sind durch den Betreiber zu bestätigen.

**D-5 — AWS_MANAGED als erste Secret-Implementierung**
Secrets Manager; Env enthält nur `PRIVACY_SECRET_ID` (ARN) und `PRIVACY_SECRET_PROVIDER`.
Kein Klartext in Env, Logs, Outputs oder State (`ephemeral`). IAM nur
`secretsmanager:GetSecretValue` auf exakten ARN. Kein stiller Fallback auf `env`.

**D-6 — APP_MANAGED als zweite Implementierung**
Extern bereitgestellter Schlüssel (32 Byte, Base64), **keyed authentication** (HMAC-SHA256,
`compare_digest`) und KDF über stdlib. **Keine Eigenbau-Chiffre** — echte
Datenverschlüsselung nur mit geprüfter Bibliothek oder KMS-Envelope (dann eigene ADR).

**D-7 — Geführte Rotation als spätere Phase**
Ablauf: Bereitstellung → Prüfung → Neuverschlüsselung → Wiederanlauf → Abschlussprüfung →
erst dann Alt-Schlüssel entfernen. Kein Automatismus, keine Rotation in RC4.

**D-8 — Rückwärtskompatibilität zu RC3**
Alle Erweiterungen sind additiv und per Default **AUS**. Ein Build mit RC3-Defaults muss
plan-identisch bleiben (keine neuen Ressourcen, gleiche Modul-Inputs/Outputs). Der
RIS-Pin (`1dbb0cb`) bleibt gültig; keine Pflichtfeld-/Vertragsänderung.

### Konsequenzen

- Positiv: Privacy-Pfad wird produktionsfähig, Löschpflichten werden nachweisbar,
  Portabilität bleibt (kein Konto-Default).
- Negativ/Kosten: neue AWS-Dienste (Secrets Manager, optional KMS) → Kosten und
  Betriebsaufwand; Policy-Gate-Allowlist muss kontrolliert erweitert werden.
- Offen: Q-01 (`subjectId` aus JWT), Q-03 (State-Vermeidung), Q-05 (Provenienz),
  Q-13 (APP_MANAGED-Krypto), Q-19 (Freigabe der Dienste), Q-06 (RIS-Abstimmung).
- **ADR-006** („keine zusätzlichen Services") wird durch diese ADR für
  **Sicherheitsdienste** (Secrets Manager, KMS) ausdrücklich ergänzt; ADR-006 bleibt als
  historische Produktentscheidung dokumentiert und sollte separat als „überholt" markiert
  werden (SQS existiert bereits).
