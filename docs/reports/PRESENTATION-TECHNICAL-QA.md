# May's Orders — Presentation Technical Q&A

> Vorbereitungsdokument für die Projektbesprechung/Präsentation (Freitag).
> Reiner Dokumentations-Nachzug auf Basis des aktuellen Repository-Stands
> (`main` = `6933680`, 2026-08-18). Keine neue Implementierung, kein
> `terraform apply`, keine AWS-Ressourcen erzeugt.
>
> **Status-Tasks:** T011-01…T011-07 COMPLETE · T011-08 PLANNED (Freigabe
> erforderlich) · T011-09 OPTIONAL (Entscheidung).

## Project Context

May's Orders ist ein serverloses Order-Management-System für den fiktiven
Händler **OrderFlow GmbH**. Es bildet den Lebenszyklus einer Bestellung ab
(`PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`, inkl. definierter
Cancellation-Pfade).

**Schulische Vorgabe vs. technische Umsetzung — sauber getrennt:**

| Ebene | Inhalt |
|-------|--------|
| **Schulische Vorgabe** | Projektauftrag, Architekturrahmen (serverless, AWS, REST-API, Order-Lifecycle). Die konkreten Projektanforderungen liegen außerhalb dieses Repos. |
| **Technische Umsetzung** | Konkrete Wahl der AWS-Services, Terraform-IaC, Lambda-Runtime **Python 3.14**, HTTP API V2, Cognito-JWT, DynamoDB Single-Table. Alles ist im Repo dokumentiert und umgesetzt. |
| **Technische Alternative** | Z. B. FastAPI (Python Web Framework) als Alternative zu API Gateway + Lambda — **nicht** Bestandteil des Projekts, siehe unten. |

Es wird **nicht** behauptet, dass die Schule FastAPI oder eine bestimmte Runtime
vorgeschrieben hat — solche Aussagen sind in den Projektunterlagen nicht belegt.

## Current Architecture

```text
Client (HTTP + JSON + JWT)
   ↓
API Gateway (HTTP API V2)          ── mays-orders-api
   ↓ JWT-Authorizer (Cognito)
API Gateway → Lambda (Python 3.14) ── mays-orders-handler (index.handler)
   ↓
OrderService (boto3 / DynamoDB)    ── mays-orders (Table + GSI1)
```

- **Auth (wer ist der Benutzer):** Cognito (User Pool, App Client, Gruppe `staff`).
- **Autorisierung an der API:** JWT-Authorizer im API Gateway (Issuer = Cognito,
  Audience = Client-ID).
- **Backend-Logik:** Lambda `mays-orders-handler`, `runtime = python3.14`,
  Handler `index.handler`, ZIP `lambda/dist/lambda.zip`.
- **Daten:** DynamoDB Single-Table `mays-orders` (PK `pk`, SK `sk`, GSI1).
- **IaC:** Terraform (`terraform/`), AWS-Provider `~> 6.0` (6.60.0).

Plan (T011-07, read-only): **16 to add, 0 to change, 0 to destroy** —
Klassifikation A) EXPECTED/CLEAN. `terraform apply` **nicht** ausgeführt.

## Node.js vs Python 3.14

### Historischer Stand

Die **ursprüngliche** Lambda-Implementierung (T011-04) verwendete
**Node.js/TypeScript** (`nodejs22.x`, esbuild-Bundle, `dist/lambda.zip`
~156 KB, Vitest 45/45).

### Migration

Die Lambda-Implementierung wurde **funktional identisch** auf **Python 3.14**
migriert (Branch `feature/lambda-python-314`): `python3.14`, boto3,
`build_zip.py`, `dist/lambda.zip` ~6,6 KB, unittest 49/49. Grund laut
Migrationsbericht: Umstellung des aktiven Lambda-Stands auf die
Python-3.14-Runtime mit boto3 (von der Lambda-Runtime bereitgestellt),
reproduzierbarem ZIP-Build und einheitlicher Python-Codebasis. Terraform-
Änderung war **ausschließlich** `runtime = "nodejs22.x" → "python3.14"`.

Im Cleanup (T011-04-CLEANUP) wurde die Node.js/TypeScript-Baseline (Sources,
Tests, `package.json`, `tsconfig.json`, `vitest.config.ts`) aus dem aktiven
Lambda-Projekt entfernt.

### Aktueller Stand

AWS Lambda verwendet aktuell:

- **Runtime:** `python3.14`
- **Handler:** `index.handler` (`index.py` am ZIP-Root)
- **Package:** `lambda/dist/lambda.zip` (6 Python-Module, `python3 build_zip.py`)

**Node.js/TypeScript ist kein Bestandteil des aktuellen Lambda-Deployments.**

Die historische Baseline bleibt über Git-Historie (Commit `449cdd7`, Branch
`feature/lambda-python-314`) und die Reports (`LAMBDA-PYTHON-3.14-MIGRATION.md`,
`T011-04-PYTHON-CLEANUP.md`) vollständig nachvollziehbar.

**Wichtiger Hinweis:** Keine unbelegten Aussagen (z. B. „Python ist schneller",
„Python ist immer billiger"). Tatsächlich gemessene/belegte Werte:

| Metrik | Node-Baseline (historisch) | Python 3.14 (aktuell) | Beleg |
|--------|---------------|-------------|-------|
| ZIP-Größe | ~156 KB | ~6,6 KB (6.779 Bytes) | gemessen |
| Unit-Tests | 45/45 (Vitest) | 49/49 (unittest) | ausgeführt |
| Cold Start / Init / Duration / Memory | **nicht gemessen** | **nicht gemessen** | kein apply, keine Invocation |

Performance-/Kostenvergleiche zur Laufzeit sind **nicht gemessen** und **nicht
aus dem Projektstand ableitbar** (keine AWS-Ressourcen erzeugt).

## FastAPI vs API Gateway

**FastAPI ist eine technische Alternative, kein Bestandteil des Projekts.**
Sie ist im Repository nicht vorhanden und wird **nicht implementiert**.

| Aspekt | FastAPI (Alternative) | API Gateway + Lambda (Projekt) |
|--------|-----------------------|--------------------------------|
| Rolle | Python-Web-Framework (ASGI) | Serverless-API-Layer + Serverless-Compute |
| Routing | Decorator-basiert (`@app.get(...)`) | HTTP API V2 Routes (REST-Konvention) |
| Request-Validierung | Pydantic (declared models) | `validation.py` (Lambda-seitig) |
| Dependency Injection | nativ (Depends) | keine (Lambda-Ereignis direkt) |
| OpenAPI / Swagger UI | automatisch generiert | nicht im Projekt vorgesehen |
| Error Handling | Exception-Handler | `errors.py` + `index.fail` |
| Betrieb | eigener Server (z. B. Uvicorn) | AWS verwaltet Ausführung/Skalierung |

Im Projekt wurde der serverless Weg umgesetzt (ADR-001): **API Gateway (HTTP
API V2)** nimmt HTTP-Requests entgegen, validiert das JWT (Cognito) und reicht
das Ereignis an **Lambda (Python 3.14)** weiter; Lambda führt Validierung,
Service-Logik und DynamoDB-Zugriffe aus.

## HTTP / JSON API

**HTTP Request ≠ HTML.** Die API ist eine reine **HTTP+JSON**-Schnittstelle —
kein Browser-HTML, keine Seitenauslieferung.

Tatsächliche Endpunkte (aus `terraform/main.tf` + `lambda/src/index.py`):

| Methode | Pfad | Zweck | Handler-Route |
|---------|------|-------|---------------|
| POST | `/orders` | Order anlegen (Status `PENDING`) | `service.create_order` |
| GET | `/orders` | Order-Listing (paginiert, GSI1-Query) | `service.list_orders` |
| GET | `/orders/{orderId}` | Einzelne Order (AP2) | `service.get_order` |
| PATCH | `/orders/{orderId}/status` | Status-Update (AP4, Conditional Write) | `service.update_order_status` |

Konzeptioneller Request:

```http
POST /orders
Content-Type: application/json
Authorization: Bearer <JWT>

{ "customer": { "name": "Max", "email": "max@example.com" },
  "items": [ { "sku": "SKU-1", "quantity": 2, "unitPrice": 500 } ],
  "currency": "EUR" }
```

Ablauf im Projekt:

```text
API Gateway (HTTP API V2)
   ↓  Event (Payload Format 2.0)
JWT-Prüfung (Authorizer: Cognito-Issuer + Audience, Token aus Authorization-Header)
   ↓
Lambda Event (routeKey, pathParameters, queryStringParameters, body, isBase64Encoded)
   ↓
lambda/src/index.py (Routing + Fehler-Mapping)
   ↓  service
OrderService (boto3) → DynamoDB
```

Beispiel-Event-Struktur (tatsächlich verarbeitet in `index.py`):

```json
{
  "routeKey": "POST /orders",
  "rawPath": "/orders",
  "body": "{...}",
  "isBase64Encoded": false,
  "pathParameters": null,
  "queryStringParameters": null
}
```

Antwortformat (v2-Proxy): `{ "statusCode": <code>, "headers": {...},
"body": "<json>" }` (`index.py:ok`/`fail`).

## Cognito and JWT

- **Cognito** beantwortet: *Wer ist der Benutzer?* Der User Pool
  (`mays-orders-users`) verwaltet Identitäten; der App Client
  (`mays-orders-client`, `USER_PASSWORD_AUTH` + Refresh, Public Client) stellt
  den Login-Flow bereit; die Gruppe `staff` liefert den Claim `cognito:groups`.
  Benutzer werden administrativ angelegt (`allow_admin_create_user_only = true`);
  keine offene Registrierung.
- **JWT** beantwortet: *Welche authentifizierte Identität wird übertragen?*
  Nach Login liefert Cognito Token (ID/Access/Refresh). Das Access-Token trägt
  Issuer, Audience und Claims.
- **API Gateway JWT-Authorizer** beantwortet: *Ist das Token für diese API
  gültig?* Er prüft Signatur/Issuer (Cognito-Endpoint) und Audience
  (Client-ID) aus `Authorization: Bearer <JWT>`.
- **Lambda** verarbeitet die **autorisierte** Anfrage — es prüft das Token
  selbst nicht erneut (JWT-Prüfung liegt beim API Gateway).

Keine zusätzliche Authentifizierungsarchitektur im Projekt.

## Lambda

- Ressource: `aws_lambda_function.handler` (`mays-orders-handler`).
- Runtime **`python3.14`**, Handler **`index.handler`** (Python: `index.py` am
  ZIP-Root), Timeout 10 s, Memory 128 MB (Default), Env `ORDERS_TABLE`.
- Rolle: `aws_iam_role.handler` (T011-03, Least Privilege — DynamoDB auf
  Tabelle+GSI1, Logs).
- Boto3 wird von der Lambda-Runtime bereitgestellt → kein Bundling, kein
  `requirements.txt`.
- ZIP: `lambda/dist/lambda.zip` (6 Python-Module, `python3 build_zip.py`).
- Lambda verarbeitet das **HTTP-API-v2-Event** (`routeKey`, `pathParameters`,
  `queryStringParameters`, `body`, `isBase64Encoded`) und gibt v2-Proxy-
  Responses zurück. Läuft lokal (Tests) unter Python 3.12.3; Ziel-Runtime 3.14.

## Error Handling

Fehlerklassen und Codes (nur tatsächlich im Code vorhanden, `lambda/src/errors.py`):

| Klasse / Factory | Code | HTTP | Anlass |
|------------------|------|------|--------|
| `validation_error(...)` | `VALIDATION_ERROR` | **400** | ungültige Eingabe (Body/Pfad/Query/JSON) |
| `order_not_found(...)` | `ORDER_NOT_FOUND` | **404** | `GetItem` liefert kein Item |
| `invalid_transition(...)` | `INVALID_TRANSITION` | **409** | Status-Übergang verboten (State Machine) |
| `conflicted_update()` | `CONFLICTED_UPDATE` | **409** | Conditional Write schlägt fehl (Race) |
| `internal_error(...)` | `INTERNAL_ERROR` | **500** | unerwartete Fehler |

Fehlerformat (einheitlich, `errors.error_body`):

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": { "path": "..." } } }
```

Ablauf (`index.py`): alle Exceptions landen in `fail(err)`. `OrderError` →
kontrollierte HTTP/JSON-Antwort; unbekannte Fehler → `INTERNAL_ERROR` (500) +
Log auf stderr — **interne technische Fehler werden nicht ungefiltert an den
Benutzer weitergegeben**. Der Benutzer erhält kontrollierte HTTP-/JSON-Antworten.

Eine konkrete Benutzeroberfläche (UI/HTML-Client) ist **nicht** Bestandteil des
aktuellen AWS-Backend-Stands (kein UI-Code im Repo).

### Module im Überblick

- **`validation.py`** — Eingabevalidierung (Body/Customer/Items/Currency,
  `orderId`-Format `ord_<alphanumeric>`, `status` aus erlaubter Menge,
  `limit`/`nextToken`). → 400.
- **`errors.py`** — `OrderError` + Factorys + `error_body`.
- **`state_machine.py`** — Transition-Matrix `TRANSITIONS` + `can_transition`
  (pure Funktion): `PENDING→CONFIRMED|CANCELLED`, `CONFIRMED→PROCESSING|CANCELLED`,
  `PROCESSING→SHIPPED`, `SHIPPED→DELIVERED`, Endzustände `DELIVERED`/`CANCELLED`;
  gleicher Status → False. → 409.
- **`order_service.py`** — `OrderService` mit AP1..AP4 (boto3): Create (PutItem,
  `totalAmount` server-seitig, GSI1-Eintrag), Get (GetItem → 404), List (GSI1-
  Query, paginiert, `nextToken` Base64), Status-Update (GetItem → Transition →
  `UpdateItem` mit `ConditionExpression`; `ConditionalCheckFailedException` →
  409). Interne Felder (`pk/sk/gsi1pk/gsi1sk/version`) werden aus der öffentlichen
  Antwort entfernt.
- **`index.py`** — Handler, Routing, Body-Parsing (inkl. Base64), Fehler→HTTP.

## DynamoDB

- Tabelle `mays-orders`, **Single-Table-Design** (ADR-002), **On-Demand**
  (`PAY_PER_REQUEST`, ADR-007), PK `pk` / SK `sk` (S).
- Zugriffsstruktur: Order-Item mit `pk = ORDER#<id>`, `sk = #ORDER`, Felder
  `status`, `customer`, `items`, `currency`, `totalAmount`, `createdAt`,
  `updatedAt`, `version`, `gsi1pk/gsi1sk`.
- **GSI1** (`gsi1pk` HASH / `gsi1sk` RANGE, Projection INCLUDE: `orderId`,
  `status`, `customer`, `totalAmount`, `createdAt`, `updatedAt`) → **Access
  Pattern AP3** (GET /orders): `Query` statt `Scan`, `ScanIndexForward=false`
  (neueste zuerst), `Limit` + `ExclusiveStartKey` → `nextToken`.
- Operationen (nur): `PutItem`, `GetItem`, `Query` (GSI1), `UpdateItem`
  (conditional) — kein `Scan`, kein `DeleteItem` (konsistent mit IAM Least
  Privilege).
- **Warum DynamoDB:** serverless, key-value/Query über Access Patterns,
  On-Demand-Skalierung ohne Kapazitätsverwaltung, passt zu Lambda/API-GW
  (ADR-001/ADR-002/ADR-007).
- **Warum GSI1:** sonst wäre `GET /orders` ein `Scan` der gesamten Tabelle
  (linear wachsend); der Index erlaubt einen partitionierten, sortierten
  `Query` (kosten-/latenzstabil).

## IAM

- **IAM ≠ Benutzer-Authentifizierung.** Benutzer-Login läuft über Cognito/JWT
  (kein IAM-User, keine Access Keys — TR-15).
- IAM vergibt **Service-Berechtigungen** (Least Privilege, `security/iam-design.md`).
- `aws_iam_role.handler` (Trust: `lambda.amazonaws.com`) + `aws_iam_role_policy.handler`:
  - `DynamoDBOrders`: `dynamodb:PutItem/GetItem/UpdateItem/Query` auf Tabelle
    `mays-orders` **und** `/index/gsi1`.
  - `Logs`: `logs:CreateLogGroup/CreateLogStream/PutLogEvents` (Log-Ressourcen
    entstehen zur Laufzeit).
- **Kein** `Scan`/`DeleteItem`/`BatchWriteItem`, keine `s3`/`sqs`/`iam`-Rechte.
- API-GW → Lambda-Invoke-Permission (`aws_lambda_permission.api_gateway`):
  nur Principal `apigateway.amazonaws.com`, `source_arn` eng auf die HTTP API
  begrenzt (`${execution_arn}/*/*`).

## Terraform

- IaC für **alle** Infrastruktur-Ressourcen: DynamoDB, IAM, Lambda, Cognito,
  HTTP API (T011-01…T011-06). `terraform/` = `main.tf`, `variables.tf`,
  `outputs.tf`, `README.md`, Lockfile.
- AWS-Provider `~> 6.0` (6.60.0), `required_version >= 1.5.0`.
- Keine manuell erzeugte Infrastruktur; Reproduzierbarkeit und Versionierung im
  Repo.
- Stand: **16 Ressourcen** konfiguriert und geplant, **0 erzeugt** (kein apply).
- **Warum Terraform:** deklarative, versionierbare, wiederholbare Infrastruktur;
  ein Code-Stand definiert den Zielzustand („Infrastructure as Code").

## Terraform State

**Wichtige Abgrenzung — Terraform State ≠ Order State:**

| Begriff | Bedeutung | Beispiel |
|---------|-----------|----------|
| **Order State** | fachlicher Status einer Bestellung (Lifecycle) | `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` |
| **Terraform State** | Zustand der **von Terraform verwalteten Infrastruktur** | Lambda, DynamoDB, IAM, Cognito, API Gateway |

- Terraform State speichert, welche Ressourcen Terraform erzeugt hat, mit ihren
  Attributen/IDs — die Grundlage, um `plan` (Diff Ist↔Soll) und `apply`
  (Soll-Zustand herstellen) zu berechnen.
- Aktuell: **lokaler State** (kein Backend), da noch nie `apply` lief und keine
  Ressourcen existieren.

## S3 Backend

**T011-09 ist OPTIONAL / Architekturentscheidung — nicht implementiert.**

Würde T011-09 später umgesetzt, geschähe Folgendes:

```text
Terraform State
   ↓
S3 Backend (bucket)
   ↓
terraform.tfstate  (Zustandsdatei der Infrastruktur)
```

- Der S3-Bucket wäre **ausschließlich für Terraform State** (Zustandsdatei +
  ggf. Locking über DynamoDB).
- **Nicht** für Orders, **nicht** für Benutzerdateien, **nicht** pro Cognito-
  Benutzer.
- Sollte später ein Application-S3-Bucket (z. B. Dokumente/Dateien) vorgesehen
  werden, wäre das eine **separate Architekturentscheidung** (neue Ressource +
  IAM + ADR) — heute nicht Teil des Projekts.

## Validate vs Plan vs Apply

| Befehl | Frage | Aktion | Ergebnis im Projekt |
|--------|-------|--------|---------------------|
| `terraform validate` | Ist die Konfiguration syntaktisch/typ-korrekt? | prüft die Konfiguration (keine Cloud-Aktion) | PASS (ohne Warnungen) |
| `terraform plan` | Was würde Terraform ändern? | berechnet Diff Ist↔Soll (read-only) | RUN: 16 add, 0 change, 0 destroy — A) EXPECTED/CLEAN |
| `terraform apply` | Führe die Änderungen aus | erzeugt/ändert Ressourcen in AWS | **NOT RUN** (Freigabe erforderlich, T011-08) |

**„16 to add, 0 to change, 0 to destroy"** heißt: Terraform würde bei `apply`
16 neue Ressourcen erzeugen (DynamoDB, IAM-Rolle+Policy, Lambda, Cognito
Pool/Client/Gruppe, HTTP API, Stage, Authorizer, Integration, 4 Routen,
Invoke-Permission), nichts ändern und nichts löschen — konsistent mit
„bisher keine AWS-Ressourcen, kein State".

## Questions for Friday

1. **Warum Python statt Node.js?** (Node-Baseline vs. Migration auf Python 3.14)
2. **Warum kein FastAPI?**
3. **Was macht API Gateway?**
4. **Was macht Cognito?**
5. **Was ist ein JWT?**
6. **Was bekommt Lambda von API Gateway?** (Event / Payload 2.0)
7. **Was ist der Unterschied zwischen HTTP und HTML?**
8. **Wie funktioniert Error Handling?**
9. **Warum 400 statt 500?**
10. **Warum 409 bei einem State Conflict?**
11. **Warum DynamoDB?**
12. **Warum eine GSI?**
13. **Was macht IAM?**
14. **Warum Terraform?**
15. **Was ist Terraform State?** (Abgrenzung zu Order State)
16. **Warum könnte man S3 als Remote Backend verwenden?**
17. **Was ist der Unterschied zwischen validate, plan und apply?**
18. **Was bedeutet „16 to add, 0 to change, 0 to destroy"?**

## Short Answers

### Warum Python statt Node.js?
Die ursprüngliche Lambda-Implementierung (T011-04) war TypeScript/`nodejs22.x`.
Im Projekt wurde sie funktional identisch auf **Python 3.14** portiert
(boto3 von der Runtime, reproduzierbarer ZIP-Build, unittest 49/49); einzig
die Terraform-`runtime` änderte sich. Die Node-Baseline bleibt via Git
(`449cdd7`) nachvollziehbar. Laufzeit-Performance war **nicht** Messgrund und
wurde nicht gemessen.

### Warum kein FastAPI?
FastAPI ist eine **technische Alternative** (Python-Web-Framework mit eigenem
Server), **kein** Bestandteil des Projekts. Die Projektarchitektur ist
serverless (ADR-001): API Gateway (HTTP API V2) + Lambda. FastAPI wurde **nicht**
implementiert und ist im Repo nicht vorhanden.

### Was macht API Gateway?
API Gateway (HTTP API V2) ist der öffentliche Einstiegspunkt: es definiert die
4 Routen (`POST/GET /orders`, `GET /orders/{orderId}`, `PATCH
/orders/{orderId}/status`), prüft das Cognito-JWT (JWT-Authorizer) und reicht
das autorisierte Ereignis als v2-Payload an die Lambda weiter.

### Was macht Cognito?
Cognito verwaltet Benutzeridentitäten (User Pool), den Login-Flow (App Client,
`USER_PASSWORD_AUTH` + Refresh) und die Gruppe `staff` → liefert nach Login
JWTs. Es beantwortet: *Wer ist der Benutzer?*

### Was ist ein JWT?
Ein JSON Web Token — eine signierte Token-Datei mit Issuer, Audience und
Claims. Im Projekt: das Access-Token aus Cognito, das der Client als
`Authorization: Bearer <JWT>` mitsendet und das der JWT-Authorizer auf
Gültigkeit für die API prüft.

### Was bekommt Lambda von API Gateway?
Das HTTP-API-v2-**Event** (Payload Format 2.0): `routeKey`, `rawPath`,
`pathParameters`, `queryStringParameters`, `body`, `isBase64Encoded`. Lambda
antwortet mit einer v2-Proxy-Response (`statusCode`/`headers`/`body`).

### Was ist der Unterschied zwischen HTTP und HTML?
HTTP ist ein Übertragungsprotokoll für Requests/Responses; HTML ist ein
Auszeichnungsformat für Webseiten. Diese API nutzt **HTTP + JSON** (kein HTML):
strukturierte Daten für Maschinen/Clients, keine Seitenauslieferung.

### Wie funktioniert Error Handling?
Jede Exception landet in `index.fail`. `OrderError` → kontrollierte
HTTP/JSON-Antwort (400/404/409); unbekannte Fehler → 500 `INTERNAL_ERROR`
+ Log. Format einheitlich: `{ "error": { "code", "message", "details?" } }`.

### Warum 400 statt 500?
400 = der **Client** hat fehlerhaft eingegeben (ungültiges JSON, Feld, `orderId`
oder Status). Das ist ein erwartbarer Eingabefehler, keine Serverstörung.

### Warum 409 bei einem State Conflict?
409 Conflict = der **aktuelle Zustand der Ressource** passt nicht zur Anfrage:
entweder ist der Status-Übergang laut State Machine verboten
(`INVALID_TRANSITION`) oder ein gleichzeitiger Update hat den Zustand bereits
geändert (`CONFLICTED_UPDATE`, Conditional Write). 409 ist die korrekte
HTTP-Semantik für beides.

### Warum DynamoDB?
Serverless, passend zu Lambda/API-GW; Zugriff über definierte Access Patterns
(`PutItem`/`GetItem`/`Query`/`UpdateItem`); On-Demand ohne
Kapazitätsverwaltung (ADR-001/002/007).

### Warum eine GSI?
Ohne GSI wäre `GET /orders` ein `Scan` (linear wachsend). GSI1 ermöglicht einen
partitionierten, sortierten `Query` über alle Orders (AP3) mit nativer
Pagination — kosten-/latenzstabil.

### Was macht IAM?
IAM vergibt **Service-Berechtigungen** (Least Privilege): die Lambda-Rolle darf
genau die 4 DynamoDB-Aktionen auf Tabelle+GSI1 und Logs schreiben. Benutzer-
Login läuft **nicht** über IAM, sondern Cognito/JWT (keine Access Keys).

### Warum Terraform?
Infrastructure as Code: deklarativ, versioniert im Repo, reproduzierbar;
ein Konfigurationsstand definiert den Zielzustand und kann vor Änderungen
geprüft werden (`validate`/`plan`).

### Was ist Terraform State?
Die Zustandsdatei der von Terraform verwalteten Infrastruktur (welche
Ressourcen existieren mit welchen Attributen). **Nicht** zu verwechseln mit dem
fachlichen Order State (`PENDING → … → DELIVERED`).

### Warum könnte man S3 als Remote Backend verwenden?
Für **Team-/kollaboratives Arbeiten**: Der Terraform State wird zentral in S3
gehalten (statt lokal), damit alle an derselben Infrastruktur-Zustandsbasis
arbeiten (optional + Locking via DynamoDB). T011-09 ist OPTIONAL, nicht
implementiert; der Bucket wäre ausschließlich für Terraform State.

### Was ist der Unterschied zwischen validate, plan und apply?
`validate` prüft die Konfiguration; `plan` zeigt read-only, was geändert würde;
`apply` führt die Änderungen tatsächlich in AWS aus. Im Projekt: validate PASS,
plan 16/0/0 — apply **nicht** ausgeführt (Freigabe erforderlich).

### Was bedeutet „16 to add, 0 to change, 0 to destroy"?
Terraform würde 16 neue Ressourcen erzeugen, keine ändern und keine löschen —
konsistent damit, dass noch nie `apply` lief und keine AWS-Ressourcen existieren.

## Deeper Follow-up Answers

### Warum Python statt Node.js?
Der ursprüngliche Handler (T011-04) war TypeScript mit esbuild-Bundle
(`dist/lambda.zip` ~156 KB, Vitest 45/45). Im Migrationsschritt
(`feature/lambda-python-314`) wurde er funktional identisch auf **Python 3.14**
portiert: dieselben AP1..AP4, dieselben Transition-Regeln, dieselben
Validierungs- und Fehlerformate; boto3 kommt von der Lambda-Runtime (kein
Bundling, kein `requirements.txt`); der ZIP schrumpfte auf ~6,6 KB (6 Module,
`build_zip.py`); die Tests liefen als unittest 49/49. Terraform änderte sich nur
in `runtime`. Anschließend wurde die Node-Baseline im Cleanup
(T011-04-CLEANUP) aus dem aktiven Projekt entfernt, bleibt aber via Git
(`449cdd7`) und Reports nachvollziehbar. **Cold-Start/Duration/Memory wurden
nicht gemessen** (kein apply) — die Migration war eine Code-/Runtime-Umstellung,
kein gemessener Performance-Vergleich.

### Warum kein FastAPI?
Die Architektur ist serverless (ADR-001): ein permanenter Python-Server
(Uvicorn) wäre ein zusätzlicher, ständig laufender Dienst und passt nicht zum
Zielbild „API Gateway + Lambda" (kein Server-Management, Skalierung über AWS).
FastAPI würde Routing, Validierung (Pydantic), Dependency Injection und
OpenAPI/Swagger mitbringen — im Projekt übernehmen das API-Gateway-Routen,
`validation.py`, `errors.py` und das Lambda-Event-Modell. FastAPI wurde bewusst
**nicht** eingebaut (kein Repo-Code, keine Architekturänderung).

### Was macht API Gateway im Detail?
`aws_apigatewayv2_api.orders` (HTTP, `mays-orders-api`) + `$default`-Stage
(`auto_deploy = true`) + `aws_apigatewayv2_authorizer.jwt` (JWT, Identity Source
`$request.header.Authorization`, Issuer = `https://<cognito-endpoint>`, Audience =
Client-ID — beides aus Terraform-Ressourcen abgeleitet, nicht hardcodiert) +
eine Lambda-Integration (AWS_PROXY, Payload 2.0, `invoke_arn`) + 4 Routen, alle
mit `authorization_type = JWT` + `authorizer_id`. Die Invoke-Permission erlaubt
nur `apigateway.amazonaws.com` auf `execution_arn/*/*`.

### Was macht Cognito im Detail?
User Pool `mays-orders-users`: `allow_admin_create_user_only = true` (keine
offene Registrierung; Staff wird administrativ angelegt), Passwortrichtlinie
(min. 8, Upper/Lower/Number/Symbol), MFA OFF (Standard). App Client
`mays-orders-client`: `explicit_auth_flows = [ALLOW_USER_PASSWORD_AUTH,
ALLOW_REFRESH_TOKEN_AUTH]`, `generate_secret = false` (Public Client — für
`USER_PASSWORD_AUTH` nötig; kein App-Client-Secret). Gruppe `staff` →
Claim `cognito:groups` im Access-Token (Basis späterer Authorization).
Bewusst **kein** `user_pool_domain` (kein Hosted-UI nötig). Die Gruppenscope-
Auswertung im Lambda bleibt Woche 3 (Security) vorbehalten.

### Was ist ein JWT im Projekt?
Nach Login liefert Cognito Token. Der Client sendet das Access-Token im
`Authorization`-Header. Der JWT-Authorizer validiert Signatur, Issuer (Cognito)
und Audience (Client-ID) und lässt bei Erfolg die Anfrage an die Lambda durch.
Lambda selbst prüft das Token nicht erneut.

### Was bekommt Lambda von API Gateway (Event) — konkret?
Beim POST: `routeKey = "POST /orders"`, `body` (JSON, ggf. `isBase64Encoded`),
`pathParameters = null`. Bei `GET /orders/{orderId}`: `routeKey =
"GET /orders/{orderId}"`, `pathParameters = { "orderId": "ord_…" }`. Bei
`GET /orders`: `queryStringParameters = { "limit": "10",
"nextToken": "…" }`. Antwort: `{statusCode, headers, body}` (v2-Proxy).

### HTTP vs HTML — Abgrenzung?
HTTP ist das Protokoll (Anfrage/Antwort). HTML ist ein Dokumentformat. Diese
API ist eine **JSON-API** über HTTP: Clients senden JSON, Lambda antwortet mit
JSON. Kein HTML, keine UI-Seiten; die UI/der Client ist nicht Bestandteil des
AWS-Backend-Stands.

### Error Handling im Detail?
Schichtung: `validation.py` (Eingabe) → `state_machine.py` (Übergang) →
`order_service.py` (DynamoDB, Conditional Write) → `index.py` (Routing +
Fehler-Mapping). Alle Fehler sind `OrderError` mit `code`/`message`/`details`
und HTTP-Status. `fail()` wandelt sie in `{ "error": {…} }` um; unbekannte
Exceptions → 500 + stderr-Log (keine internen Details nach außen).

### Warum 409 bei einem State Conflict?
Der Status-Update (AP4) läuft in 2 Schritten: 1) `get_order` (aktueller Status),
2) `can_transition(current, requested)` → bei verbotenem Übergang
`INVALID_TRANSITION` (409, mit `currentStatus`/`requestedStatus`). Danach
`UpdateItem` mit `ConditionExpression: attribute_exists(pk) AND #status =
:currentStatus`; schlägt die Bedingung fehl (jemand hat parallel geändert),
folgt `CONFLICTED_UPDATE` (409). Beides ist HTTP-409-Semantik (Zustandskonflikt),
kein Serverfehler.

### Warum DynamoDB / eine GSI?
Single-Table + On-Demand (ADR-002/007) minimieren Komplexität und Kosten.
Alle 4 Access Patterns sind als gezielte Operationen abgebildet. GSI1 löst
AP3 (`GET /orders`): `Query` auf `gsi1pk=LIST` mit `ScanIndexForward=false`
(neueste zuerst), `Limit` + `ExclusiveStartKey` → `nextToken` (Base64). Ohne
GSI müsste der Handler scannen.

### IAM — Rollen im Projekt?
`aws_iam_role.handler` (Trust `lambda.amazonaws.com`) + Inline-Policy
(`DynamoDBOrders`: 4 Aktionen auf Tabelle+GSI1; `Logs`: CloudWatch-Schreib-
aktionen) + `aws_lambda_permission.api_gateway` (API-GW → Lambda, source_arn
begrenzt). Least Privilege: keine s3/sqs/iam-Rechte, kein Scan/DeleteItem.

### Terraform State / S3 Backend — vertieft?
Bisher lief nie `apply` → es gibt keinen State mit realen Ressourcen; die
Infrastruktur existiert nur als Konfiguration (Plan 16/0/0). Für Team-Arbeit
könnte der State in S3 liegen (T011-09, optional; + Locking via DynamoDB). Der
Bucket wäre ausschließlich für die Terraform-Zustandsdatei — nicht für
Anwendungsdaten. Ein App-Bucket wäre eine separate ADR-Entscheidung.

## Open Questions

- **T011-08 (`terraform apply`):** wann/wie erfolgt die menschliche Freigabe?
  Nach dem Apply ändern sich Outputs (Endpoint, Pool-ID, Client-ID) — diese
  müssen dann in der Doku nachgezogen werden.
- **T011-09 (S3 Backend):** Entscheidung offen, ob ein Remote-State gewünscht
  ist (Team-/Präsentationskontext).
- **Woche 3 (Security, F009):** Auswertung des Claims `cognito:groups`
  (`staff`) im Lambda — geplant, nicht umgesetzt.
- **Live-Verifizierung:** 401 ohne Token / 200 mit Token erst nach `apply`
  möglich (bisher keine AWS-Ressourcen).
- **Laufzeit-Performance (Python 3.14):** nicht gemessen — ggf. nach `apply`
  kontrolliert messen (Cold Start, Duration, Memory), wenn gewünscht.
- **UI/Client:** kein Frontend im Repo — falls in der Präsentation gewünscht,
  wäre das ein eigener (neuer) Umfang.
