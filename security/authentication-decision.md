# Authentication Decision Analysis — May's Orders

## 1. Problem

Benutzer (Backoffice/Staff von OrderFlow) müssen sich gegenüber der API authentifizieren.
Fragen:

1. Wer ist der Benutzer? → **Authentication**
2. Was darf der Benutzer tun? → **Authorization**

Beides ist strikt getrennt von **IAM** (AWS-Service-Berechtigungen der Lambda-Funktionen).

## 2. Begriffsklärung

| Begriff | Bedeutung in diesem Projekt |
|---------|------------------------------|
| Authentication | Nachweis der Benutzeridentität („Wer bist du?“) |
| Authorization | Prüfung, ob der Benutzer eine Operation ausführen darf („Darfst du das?“) |
| IAM | AWS-internes Berechtigungssystem für AWS-Ressourcen („Darf die Lambda diese Tabelle lesen?“) |

**Kein IAM Access Key als Benutzer-Login.** Benutzer-Login läuft ausschließlich über
Cognito → JWT.

## 3. JWT-Flow

```text
Benutzer  →  login (USER_PASSWORD_AUTH / client auth)  →  Cognito User Pool
Benutzer  ←  Access Token (JWT, signiert, ~1 h gültig)  ←  Cognito
Benutzer  →  API-Request mit "Authorization: Bearer <JWT>"
API GW    →  validiert Signatur + Ablauf  →  reicht Claims an Lambda weiter
Lambda    →  nutzt Claims (sub, cognito:username, groups) für Authorization
```

- **Access Token** (JWT): Kurzlebig (~1 Std), wird an API gesendet.
- **Refresh Token**: Langlebig, nur zum Nachladen neuer Access Tokens (Client-seitig; nicht an API senden).
- **ID Token**: Enthält Benutzerprofil, für Client-Anzeige; nicht für API-Autorisierung gedacht.

## 4. Analyse: Cognito User Pool

| Kriterium | Bewertung |
|-----------|-----------|
| Benutzerverwaltung | Verwalteter Service: Signup/Signin, Passwortregeln, MFA (optional) |
| JWT-Ausstellung | Automatisch signierte Tokens |
| API-Gateway-Integration | Native Autorisierung (`COGNITO_USER_POOLS`), kein Custom Code |
| Kosten | Kostenlos bis 50.000 MAU (Free-Tier) |
| Gruppen/Claims | Gruppen → `cognito:groups` Claim → Basis für Authorization |
| Komplexität | Terraform-Ressource `aws_cognito_user_pool` + Client, gut dokumentiert |
| Nachteil | Eigene Benutzer-Store (kein SSO/SAML ohne Erweiterung) — für dieses Projekt irrelevant |

### Alternative 1: Lambda Authorizer (Custom JWT)

| Pro | Contra |
|-----|--------|
| Volle Kontrolle über Token-Prüfung | Eigenentwicklung, Security-Risiko bei Fehlern (Signatur-/Ablauf-Prüfung) |
| Flexibel für beliebige IdPs | Mehr Code, mehr Testfläche, kein verwalteter Benutzer-Store |

### Alternative 2: IAM + API Keys / IAM Auth

| Pro | Contra |
|-----|--------|
| Kein eigener User-Store nötig | IAM als Benutzer-Login missbraucht (Verstoß gegen Anforderung) |
| SigV4-Signierung | Keine Benutzerverwaltung, keine Passwort-Logins |

### Alternative 3: Kein Auth (offene API)

| Pro | Contra |
|-----|--------|
| Am einfachsten | Jeder kann Orders lesen/schreiben/stornieren — fachlich nicht akzeptabel |

### 3.6 Schlussfolgerung Auth

**Cognito User Pool + API Gateway `COGNITO_USER_POOLS`-Autorisator.**

Begründung:
- Verwalteter Benutzer-Store und JWT-Lebenszyklus (keine Eigenimplementierung von
  Signaturprüfung) → geringeres Security-Risiko.
- Native API-Gateway-Integration → kein Custom Authorizer-Code nötig.
- Free-Tier-kostenlos für die Zielgröße.
- Gruppen unterstützen spätere Rollentrennung (z. B. `staff`).

## 4. HTTP API vs. REST API

| Kriterium | HTTP API | REST API |
|-----------|----------|----------|
| Kosten | ~70 % günstiger als REST API (pro Mio. Requests) | teurer |
| Lambda-Integration | Nativ, JWT-Autorisator eingebaut | Custom Authorizer oder Cognito Auth |
| Features | JWT, CORS, Basic: ausreichend für dieses Projekt | Mehr: Request-Validierung, WAF, API-Keys, Usage-Plans, SDK-Erzeugung |
| Terraform-Ressource | `aws_apigatewayv2_api` | `aws_api_gateway_rest_api` |
| Geeignet | Leichtgewichtige Lambda-Proxies | Komplexe API-Verwaltung/Veröffentlichung |

**Entscheidung: HTTP API (API Gateway V2).**

Begründung:
- Volle JWT-Unterstützung (Cognito) direkt integriert.
- Deutlich geringere Kosten — passt zur Kostenstrategie.
- Request-Validierung per JWT-Autorisator + Lambda-Validierung deckt die Anforderungen ab.
- Kein Bedarf an API-Keys/Usage-Plans/WAF in diesem Projekt.

## 5. Authorization-Konzept (Woche 1-Vorab)

- Cognito-Gruppe `staff` wird über den Claim `cognito:groups` im Access Token ausgewertet.
- In Woche 1 ist die Semantik **„jeder authentifizierte Staff-Benutzer darf alle
  Order-Operationen"** (A-09).
- Detail-Entscheidungen (z. B. wer darf stornieren, wer nur lesen) werden als eigenes
  Feature in Woche 3 (Security) umgesetzt und getestet.

## 6. Offene Punkte

| Frage | Stand |
|-------|-------|
| Benutzer-Anlage (manuell via CLI vs. Terraform) | Woche 2 — Terraform-basiert bevorzugt, Live-Test mit CLI |
| MFA / Passwortrichtlinie | Standardwerte; Verfeinerung nur falls gefordert |
| Refresh-Token-Flow im Client | Client-seitig, nicht Teil des API-Backends |