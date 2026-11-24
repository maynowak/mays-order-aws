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

*Nachtrag Q-10 (2026-11-13):* Status bleibt **ACCEPTED**. ADR-008 ist die neue
Architecture Decision für Secrets Manager und KMS; ADR-006 bleibt für alle übrigen
Services gültig. Es werden keine weiteren Dienste pauschal freigegeben.

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

**Status:** ACCEPTED (Owner-Freigabe Q-10 am 2026-11-13; Bedingungen C-01…C-07
vollständig eingearbeitet — siehe Umsetzungstabelle unten)

**Hinweis zur Nummer:** Die Auftragsbezeichnung war „ADR-007"; die Nummer 007 ist bereits
durch „On-Demand Capacity" belegt — siehe ADR-007 oben. Es gilt die bestehende Konvention:
fortlaufende Nummern in dieser Datei, kein separates `docs/adr/`.

**Datum:** 2026-11-01 · **Basis:** RC3 (`086a8be`), Branch `feature/mo-rc4-kms-privacy-retention`

**Owner-Freigabe:** 2026-11-13 (Q-10) · Branch `release/rc4-integration` · Ausgangs-HEAD
`dd4879951c19a60400d3b4fb7a01d394600a4a90`

**Q-09 Limited Amendment (2026-11-14):** `secretsmanager:DescribeSecret` is
approved only for the same explicitly approved secret ARN(s), only for
customer-CMK metadata verification; no wildcard and no DDB/SQS CMK extension.
F-01 remains `CONTRACT AMENDED / RE-REVIEW PENDING` until independent
re-review.

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

### Entscheidungen (je einzeln, alle **ACCEPTED**; Q-10-Freigabe 2026-11-13)

**D-1 — Wiederverwendung bestehender Benutzer-/Bestellverträge**
Ja. Es werden **keine** neuen Pflichtfelder eingeführt. Genutzt wird der vorhandene
`subjectId`-Mechanismus (Feld, GSI2) sowie der JWT-Claim `sub`. Der API-Body bleibt
unverändert (`customer`, `items`, `currency`).

*Nachtrag MO-ORDER-DESCRIPTION-01 (2026-11-23, implementiert, additiv):* Der API-Body
wird um das **optionale** Feld `orderDescription` erweitert (String, 1–1.024 Zeichen
nach Trimmen; keine Steuerzeichen außer TAB/LF/CR, keine Unicode-Zeilentrenner/
Surrogates). Es werden **keine** neuen Pflichtfelder eingeführt; Identität, Routing,
Preisberechnung und `items` bleiben unverändert. Nicht angegebene Beschreibungen
bleiben abwesend (kein Default, keine Migration). Details: `api/endpoints.md`.

*Nachtrag P02A (2026-11-01, implementiert, additiv):* Consumer, Owner und Actor sind
getrennt (`consumerId`, `ownerType`, `ownerId`, `actorType`, `actorId`,
`identityVersion`). Consumer = `cognito:<issuer>#<client>`, Owner/Actor = `sub`.
Agenten-/Dienst-Delegation bleibt **BLOCKED**, bis ein verifizierter Delegationsvertrag
entschieden ist; der kanonische Schlüssel ist kollisionsfrei (Längenpräfixe) und wird
**nicht** als neuer DynamoDB-Schlüssel eingeführt (GSI2/Privacy bleiben unverändert).

*Nachtrag P02B (2026-11-01, implementiert, additiv):* Jede Bindung trägt einen
`identityVerification`-Kontext (`verified_jwt`; `verified_internal_signed` ist definiert,
aber **nicht** implementiert). `resolve_internal_order_identity` verweigert Bindungen ohne
verifizierten Kontext und lehnt Owner≠Actor ab. RIS-Direktschreibungen bleiben
**BLOCKED** (MO kann sie technisch nicht validieren; benötigt V-1/V-3 und RIS-Umsetzung).
Privacy-Funktionen akzeptieren einen **optionalen** `consumerId`-Scope, der nur
einschränkt; echte Mehr-Consumer-Isolation auf Indexebene ist **BLOCKED** (GSI2 unverändert).

**D-2 — Orphan Detection**
Verwaist = Nutzer nachweislich weg **und** Frist abgelaufen **und** nicht `RETAIN`.
Bestellungen **ohne** Nutzerbezug gelten **nicht** als verwaist. Nicht prüfbare Zuordnung
(EXTERNAL-Cognito, Fehler) ⇒ kein Löschen (fail-closed). Fremde Schreibpfade (RIS) sind
nur über ein Provenienzmerkmal von MO-Daten unterscheidbar.

*P00-Zuordnung (C-07):* P00-G spezifiziert die Orphan-Detection und ihr Fail-closed-
Verhalten. P00-G enthält **keine** automatische Löschung, keinen Backfill und keinen
RIS-Schreibpfad; die Ausführung bleibt ein separater, Owner-gated Vorgang. Bestandsdaten
ohne Retention bleiben Q-14; RIS-Koordination bleibt außerhalb von P00.

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
Secrets Manager; Env enthält ausschließlich nicht-geheime Referenzen:
`PRIVACY_SECRET_PROVIDER`, `PRIVACY_SECRET_ID` (ARN/Name) und — nur bei explizit
aktivierter CMK — `PRIVACY_KMS_KEY_ARN` (Key-ARN, kein Secret-Wert). Kein Klartext in Env,
Logs, Outputs oder State (`ephemeral`). IAM ist least privilege:
`secretsmanager:GetSecretValue` auf dem exakten Secret-ARN; zusätzlich
`secretsmanager:DescribeSecret` auf demselben exakten Secret-ARN, ausschließlich
zur Verifikation der CMK-Metadaten (`KmsKeyId`), wenn `PRIVACY_KMS_KEY_ARN`
explizit gesetzt ist; `kms:Decrypt` nur bei aktivierter CMK auf dem exakten
Key-ARN. Kein `Resource: "*"`, kein stiller Fallback auf `env`. Die
CMK-Aktivierung bleibt eine separate Entscheidung (Q-04/Q-09).

**D-6 — APP_MANAGED als zweite Implementierung**
Extern bereitgestellter Schlüssel (32 Byte, Base64), **keyed authentication** (HMAC-SHA256,
`compare_digest`) und KDF über stdlib. **Keine Eigenbau-Chiffre** — echte
Datenverschlüsselung nur mit geprüfter Bibliothek oder KMS-Envelope (dann eigene ADR).

*P00-D Local Contract (2026-11-14):* HMAC-Payload ist `MOAPP || 0x01 || 0x01`
mit length-prefixed `keyId`/`keyVersion`/`messageType`/`payload`; `keyId` und
`keyVersion` sind kryptografisch gebunden. Signatur ist Base64url ohne Padding.
Message-Type-Allowlist: `privacy.internal.v1`. 32-Byte-Key, strikte
Standard-Base64-Dekodierung, Constant-Time-Vergleich, Fail-closed. Die lokale
Implementierung aktiviert APP_MANAGED nicht im Order-Pfad; Rotation, Widerruf
und Environment-Recycle bleiben P00-F.

**D-7 — Geführte Rotation als spätere Phase**
Ablauf: Bereitstellung → Prüfung → Neuverschlüsselung → Wiederanlauf → Abschlussprüfung →
erst dann Alt-Schlüssel entfernen. In RC4 gibt es **keinen automatischen Rotator und keine
automatische Rotation**. Eine **dokumentierte manuelle Rotation** als Betriebsverfahren ist
zulässig; Umfang, Übergangsfenster und Verantwortlichkeit bleiben Q-11. Alte
Schlüssel/Versionen werden nicht automatisch gelöscht.

**D-8 — Rückwärtskompatibilität zu RC3**
Alle Erweiterungen sind additiv und per Default **AUS**. Ein Build mit RC3-Defaults muss
plan-identisch bleiben (keine neuen Ressourcen). Der bestehende `orders-service`-Vertrag
bleibt in Inputs und Outputs unverändert; neue gehärtete Module werden nur über eine
explizite Auswahl bzw. ein separates Preset angeboten, dessen genaue Platzierung Q-03
bleibt. Neue optionale Variablen dürfen den Default-Plan nicht verändern. Der RIS-Pin
(`1dbb0cb`) bleibt gültig; keine Pflichtfeld-/Vertragsänderung.

### Konsequenzen

- Positiv: Privacy-Pfad wird produktionsfähig, Löschpflichten werden nachweisbar,
  Portabilität bleibt (kein Konto-Default).
- Negativ/Kosten: neue AWS-Dienste (Secrets Manager, optional KMS) → Kosten und
  Betriebsaufwand; Policy-Gate-Allowlist muss kontrolliert erweitert werden.
- Historische P01-Fragen: Die frühere Kurzliste verwendete P01-Nummern, die nicht mit dem
  P00-Register übereinstimmen. Die eindeutige Zuordnung steht in der Tabelle unten; die
  offenen P00-Entscheidungen stehen ausschließlich im P00-Decision-Register.
- **ADR-006** („keine zusätzlichen Services") bleibt **ACCEPTED**. ADR-008 ist die neue
  Architecture Decision für **Secrets Manager und KMS** und erfüllt damit die
  ADR-006-Anforderung „kein zusätzlicher Service ohne neue ADR" ausschließlich für diese
  Sicherheitsdienste. Es gibt keine Statusänderung an ADR-006 und keine pauschale Freigabe
  weiterer Services.

### Historische P01-Fragen → P00-Zuordnung (C-01)

Die historischen P01-Nummern werden **nicht** in P00-Nummern umnummeriert. Diese Tabelle
macht die Bedeutung eindeutig und verhindert eine Verwechslung mit dem P00-Register:

| Historische P01-Frage | Bedeutung | P00-Zuordnung | Behandlung |
|---|---|---|---|
| Q-01 | `subjectId` aus dem JWT | keine 1:1-Entsprechung; P00 Q-01 ist RC3-Tag/Baseline | durch P02A/P02B implementiert; historisch geschlossen |
| Q-03 | Secret ohne Klartext im Terraform-State | P00 Q-02 (Backend), Q-08 (Referenz/Fetch), Q-09 (Policy Gate); P00 Q-03 ist Modulplatzierung | in P00 aufgegangen |
| Q-05 | Provenienzfeld für RIS-Schreibpfade | keine 1:1-Entsprechung; P00 Q-05 ist `tenantId`; Q-14 betrifft nur Bestandsdaten | außerhalb P00; separater RIS-Pfad |
| Q-13 | APP_MANAGED-Krypto | P00 Q-10/D-6; Rotation/Versionen zusätzlich Q-11; P00 Q-13 ist AWS-Testkonto | durch ADR-008 D-6 entschieden; Q-11 offen |
| Q-19 | Freigabe der Dienste (Secrets Manager/KMS) | P00 Q-10 | durch Q-10 am 2026-11-13 freigegeben |
| Q-06 | RIS-Koordination | keine 1:1-Entsprechung; P00 Q-06 ist Retention-Frist; Q-14 betrifft nur Bestandsdaten | außerhalb P00; separater RIS-Pfad |

**Abgrenzung:** P00 Q-03, Q-05, Q-06 und Q-13 sind **nicht** die historischen P01-Fragen
gleicher Nummer. Für historische Fragen ohne 1:1-Entsprechung wird keine P00-ID
erfunden; sie sind ausdrücklich als „keine Entsprechung“ markiert. Maßgeblich sind
ausschließlich die Definitionen im `docs/adr/MO-RC4-P00-DECISION-REGISTER.md`.

### Umsetzung der Owner-Klarstellungen C-01…C-07

| ID | Klarstellung | Umsetzung in ADR-008 | Nachweis |
|---|---|---|---|
| C-01 | Historische Fragen eindeutig zuordnen | Tabelle „Historische P01-Fragen → P00-Zuordnung" | keine alten Q-Nummern mehr als offene P00-Fragen |
| C-02 | Optionale `PRIVACY_KMS_KEY_ARN`-Referenz | D-5: ausschließlich nicht-geheime Referenzen, optionaler Key-ARN | kein Secret-Wert in Env/State |
| C-03 | Least-Privilege-IAM | D-5: `GetSecretValue` exakt; `DescribeSecret` nur bei CMK-Metadatenprüfung auf demselben exakten Secret-ARN; `kms:Decrypt` nur bei CMK, exakter ARN; kein Wildcard | IAM-Regel im Contract §6; Q-09 Amendment 2026-11-14 |
| C-04 | Manuelle Rotation ohne Auto-Rotator | D-7: kein Automatismus; dokumentierte manuelle Rotation; Q-11 offen | Q-11 bleibt separat |
| C-05 | `orders-service`-Vertrag unverändert | D-8: bestehender Vertrag unverändert; gehärtete Module separat; Q-03 offen | Default-Plan bleibt unverändert |
| C-06 | ADR-006 tatsächlicher Status | ADR-006 bleibt `ACCEPTED`; ADR-008 ist die neue ADR nur für Secrets Manager/KMS | keine Statusänderung, keine pauschale Freigabe |
| C-07 | Orphan-Detection zuordnen | D-2: P00-G spezifiziert Detection/Fail-closed; keine automatische Löschung/Backfill/RIS | Q-14 und RIS bleiben separat |
