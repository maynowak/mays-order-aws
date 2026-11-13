# MO-RC4-P00-A — SECURITY ARCHITECTURE DECISION

**P00-A: AWS_MANAGED / APP_MANAGED, SecretProvider, KMS, Rotation, Retention**

**Datum:** 2026-11-13
**Arbeitsverzeichnis:** `/home/dci-student/projects/Mays-Orders-AWS-rc4-integration`
**Branch:** `release/rc4-integration`
**HEAD:** `0e517c74b7ce2f8ae620e3b459428ac19a0ac5f0`
**RC3-Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Modus:** read-only Analyse und Dokumentation; keine Produkt-/Terraform-/AWS-Änderung,
kein Merge/Cherry-Pick, kein Push, kein Release-Tag.

```text
MO-RC4-P00-A — CONTRACT DRAFTED / Q-02 + Q-08 APPROVED / Q-10 PENDING
```

> **Owner update 2026-11-13:** Q-02 (Secrets Manager) und Q-08 (ARN/Name-
> Referenz + Laufzeit-Fetch, kein Klartext-Secret in Env) sind freigegeben.
> Q-10 bleibt nach dem ADR-008-Abgleich offen
> (`docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md`). Die Freigaben
> autorisieren keine Implementierung.

Der technische Vertrag ist konsistent ableitbar, aber mehrere
sicherheitsrelevante Entscheidungen sind weiterhin **PROPOSED** bzw. **OPEN**.
Sie werden nicht durch dieses Dokument freigegeben.

---

## 1. Ausgangslage und Geltung

Dieses Dokument präzisiert die bestehenden P00-/P01-Designs und ADR-008. Es
ersetzt **keine** ADR und erklärt **keine** offene Frage eigenmächtig für
entschieden.

| Quelle | Rolle |
|---|---|
| `docs/reports/MO-RC4-P00-MODULE-PLAN.md` | P-01…P-15 Plan |
| `docs/reports/MO-RC4-P00-OPEN-QUESTIONS.md` | Q-01…Q-14 |
| `docs/reports/MO-RC4-P01-SECRET-PROVIDER-DESIGN.md` | AWS_MANAGED/APP_MANAGED Design |
| `docs/reports/MO-RC4-P01-CONTRACT-INVENTORY.md` | Ist-Verträge |
| `architecture/architecture-decisions.md` ADR-008 | PROPOSED, nicht freigegeben |
| `docs/release/RC4-INTEGRATION-MANIFEST.md` | Integrationsbasis |
| `docs/reports/MO-RC4-RELEASE-CONSOLIDATION-02.md` | Integrationsnachweis |
| `docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` | Owner-Update 2026-11-13; Q-10-Abgleich |

### 1.1 Bestätigte Baseline

- RC3-Baseline `086a8be` ist vom Release-Owner autorisiert.
- RC3-Release-Tag bleibt nicht vorhanden und ist **keine** RC3-Releasefreigabe.
- P00 ist nicht implementiert.
- T011-14 KMS-Backup-Stash ist **nicht** P00 und wird nicht angewandt.

---

## 2. Entscheidungsmatrix (Q-01…Q-14)

| ID | Architekturfrage | Bisherige Entscheidung | Evidenz | Status | Handlungsbedarf |
|---|---|---|---|---|---|
| Q-01 | RC3-Tag nachziehen? | Kein Tag; `086a8be` nur als RC4-Baseline autorisiert | Release-Owner-Autorisierung; `PROJECT_STATUS` | **DECIDED (nur Baseline)** | Keine RC3-Releasefreigabe; kein Tag |
| Q-02 | Secret-Backend | Secrets Manager | P00 P-02; ADR-008 D-5; Owner-Freigabe 2026-11-13 | **DECIDED** | Backend festgelegt; P00-C bleibt durch Q-04/Q-09/Q-10 gated |
| Q-03 | Wo neue Module anbieten? | Eigenes `orders-service-hardened`-Preset empfohlen | P00 P-11; Q-03 | **OPEN** | Owner/Builder-Entscheidung |
| Q-04 | KMS-Key erzeugen oder extern? | Beides: Default erzeugen, externer ARN override | P00 P-04; Q-04 | **PROPOSED** | Owner-Freigabe |
| Q-05 | `tenantId`? | Optional, Default null | P00 P-08; Q-05 | **PROPOSED** | Owner/API-Entscheidung |
| Q-06 | Retention-Fristen | 365/30 Tage vorgeschlagen, rechtlich zu bestätigen | P00 P-08/P-09; Q-06 | **OPEN** | Rechtlich/fachlich |
| Q-07 | Cancel-Anonymisierung | Opt-in, Default Frist abwarten | P00 P-09; Q-07 | **PROPOSED** | Owner-Freigabe |
| Q-08 | Secret-Zustellung | ARN/Referenz in Env, Laufzeit-Fetch | P00 P-01/P-02; Q-08; Owner-Freigabe 2026-11-13 | **DECIDED** | Referenz/Fetch festgelegt; P00-B bleibt durch Q-10 gated |
| Q-09 | Policy-Gate-Allowlist | Erweitern mit Regeln | P00 P-15; Q-09 | **PROPOSED** | Governance-Freigabe |
| Q-10 | ADR/Services | ADR-008 für KMS/Secrets | ADR-008; ADR-008/Contract-Abgleich | **READY_FOR_OWNER** | ADR-008 bleibt PROPOSED; C-01…C-07 klären |
| Q-11 | Rotation in RC4? | Native Rotation später; manuelle Rotation dokumentieren | P00 P-03; Q-11 | **PROPOSED** | Owner-Freigabe |
| Q-12 | Release-Label | `v0.6.0-rc.1` bei P00-Feature-Generation, sonst `v0.5.0-rc.4` | Q-12; RC4-Dossier | **OPEN** | Release-Owner |
| Q-13 | AWS-Testkonto | RIS-Testkonto erneut vorgeschlagen | Q-13 | **OPEN** | Owner/Testfreigabe |
| Q-14 | Bestand ohne Retention | Separater Backfill, nicht RC4-Code | Q-14 | **OPEN** | Owner/Migration |

**Statuslegende:** `DECIDED` = ausdrücklich autorisierte Entscheidung
(Q-01 nur Baseline; Q-02/Q-08 am 2026-11-13 freigegeben); `PROPOSED` ist keine
Freigabe; `OPEN`/`READY_FOR_OWNER` blockiert die abhängigen Pakete.

---

## 3. Betriebsarten — verbindliche Semantik

### 3.1 ENV (bestehender Modus)

**Status:** implementiert, aber nicht produktionsfähig provisioniert.

| Aspekt | Ist-Zustand |
|---|---|
| Secret-Quelle | `PRIVACY_INTERNAL_SECRET` aus Lambda-Env |
| Verwendung | nur Order-Handler, interne Privacy-Actions |
| Vergleich | `secrets.compare_digest` mit `internal_token` |
| Fehler | fehlendes Secret/Token/Projekt/Berechtigung → 400, fail-closed |
| Worker | liest kein Secret |
| IaC | keine Secret-Provisionierung |
| Tests | `test_privacy_requires_internal_secret`, `test_privacy_requires_internal_token` |
| Risiko | Klartext in Env; kein Rotation-/Audit-Konzept |

**Kompatibilitätsregel:** ENV bleibt Default und darf durch P00 nicht
unbeabsichtigt verändert werden. Neue Provider dürfen nur bei explizit
gesetzter Provider-Konfiguration aktiv werden.

### 3.2 AWS_MANAGED

**Designstatus:** Q-02/Q-08 entschieden (2026-11-13); Q-10 offen; P00-C nicht
implementiert.

- **Secret-Herkunft:** AWS Secrets Manager; `PRIVACY_SECRET_ID` referenziert den
  exakten ARN/Name.
- **SecretProvider:** liefert `SecretMaterial` (Wert + Metadaten) aus dem
  Provider; der Order-Service nutzt weiterhin `compare_digest`.
- **Secrets-Manager-Verschlüsselung:** AWS-managed Key ist der Default;
  optionaler kundeneigener CMK ist eine separate Entscheidung.
- **KMS/CMK:** nicht automatisch erforderlich. Eine CMK kann für Secrets
  Manager, DynamoDB oder SQS separat aktiviert werden; sie ist keine
  Voraussetzung für den SecretProvider.
- **IAM:** `secretsmanager:GetSecretValue` auf exakten Secret-ARN; optional
  `kms:Decrypt` auf exakten CMK-ARN, falls CMK aktiviert.
- **Caching:** pro Lambda-Prozess; Cache-Key enthält Provider + Secret-ID +
  Version/Fingerprint; kein Cross-Provider-Fallback.
- **Rotation:** native Secrets-Manager-Rotation ist in RC4 **nicht automatisch**
  aktiviert (Q-11); manuelle Rotation/Neustart-Invalidierung wird dokumentiert.
- **Fehler:** fehlende Referenz, `ResourceNotFound`, `AccessDenied`, Timeout,
  ungültige Secret-Struktur → fail-closed; kein Fallback auf ENV.
- **Logging:** nur Provider, Secret-ID-Suffix, Fehlercode; niemals Wert,
  Token oder Klartext.

### 3.3 APP_MANAGED

**Designstatus:** PROPOSED; Phase 2, **nicht RC4-Pflicht** gemäß
`MO-RC4-P01-SECRET-PROVIDER-DESIGN.md`.

- **Secret-/Key-Herkunft:** extern bereitgestelltes Key-Material; nicht aus
  Request-Daten, nicht aus ungeprüften Headern.
- **Key-ID/Version:** `keyId` und `keyVersion` als Metadaten; aktive Version
  explizit referenziert.
- **Authentifizierung:** HMAC-SHA256 über kanonische interne Payload;
  `compare_digest`; keine selbst entwickelte Verschlüsselung.
- **Schlüsselformat:** 32 Byte/256 Bit, Base64; Länge/Alphabet fail-closed.
- **Rotation:** manuelle/geführte Rotation; alte Version nur im definierten
  Übergangsfenster gültig; keine automatische Löschung.
- **Neustart:** Key-Material wird deterministisch aus dem externen Provider
  geladen; kein In-Memory-only-Zustand.
- **Audit:** Key-ID/Version und Ergebnis, keine Key-Werte.
- **Abgrenzung:** APP_MANAGED ist **kein** AWS-KMS-Schlüssel und keine
  AWS_MANAGED-Variante.

### 3.4 Betriebsartenmatrix

| Eigenschaft | ENV | AWS_MANAGED | APP_MANAGED |
|---|---|---|---|
| Secret-Herkunft | Lambda-Env | Secrets Manager | externer Secret-/Key-Provider |
| Schlüsselverwaltung | Betreiber/Env | AWS Secrets Manager + optional CMK | Betreiber/extern |
| Secret-Rotation | manuell/Deploy | optional/manuell; native später | manuell/geführt |
| IAM-Abhängigkeit | keine zusätzliche | GetSecretValue, optional KMS | Provider-spezifisch |
| AWS-Abhängigkeit | AWS Lambda | Secrets Manager, optional KMS | keine zwingende AWS-Krypto |
| Key-Versionierung | keine | Secret-Version | keyId/keyVersion |
| Fail-closed | ja | ja | ja |
| Rückwärtskompatibilität | Default | additiv, default aus | additiv, default aus |

---

## 4. SecretProvider-Vertrag

Dies ist ein Implementierungsvertrag, **kein Produktcode**.

### 4.1 Schnittstelle

```text
Provider:
  name: "env" | "secretsmanager" | "app_managed"
  load(reference: SecretReference) -> SecretMaterial

SecretMaterial:
  value: str                  # nur im Prozessspeicher
  key_id: str | None
  version: str | None
  provider: str
```

Der bestehende Privacy-Code erhält weiterhin einen Token-String und verwendet
`secrets.compare_digest`. APP_MANAGED erhält zusätzlich `key_id`/`version` für
HMAC-Kontexte. Die Provider-Auswahl darf die bestehende Auth-Semantik nicht
verändern.

### 4.2 Konfigurationsschema (Vorschlag)

| Feld | ENV | AWS_MANAGED | APP_MANAGED |
|---|---|---|---|
| `PRIVACY_SECRET_PROVIDER` | `env` (Default) | `secretsmanager` | `app_managed` |
| `PRIVACY_INTERNAL_SECRET` | erforderlich | **darf nicht gesetzt sein** | nicht verwenden |
| `PRIVACY_SECRET_ID` | nicht verwenden | exakter ARN/Name | externe Referenz |
| `PRIVACY_APP_KEY_ID` | — | — | optional |
| `PRIVACY_APP_KEY_VERSION` | — | — | optional |
| `PRIVACY_KMS_KEY_ARN` | — | optional | — |

### 4.3 Validierung und Fehlerklassen

| Bedingung | Ergebnis |
|---|---|
| unbekannter Provider | `ProviderConfigurationError`, fail-closed |
| ENV ohne `PRIVACY_INTERNAL_SECRET` | `SecretNotConfigured`, fail-closed |
| AWS_MANAGED ohne `PRIVACY_SECRET_ID` | `ProviderConfigurationError` |
| AWS_MANAGED mit `PRIVACY_INTERNAL_SECRET` gesetzt | `ProviderConfigurationError` (kein stiller Fallback) |
| Secrets Manager `ResourceNotFound` | `SecretNotFound` |
| `AccessDenied` | `SecretAccessDenied` |
| Timeout/Netzwerk | `SecretUnavailable` |
| leeres/ungültiges Material | `SecretInvalid` |
| APP_KEY Format/Version ungültig | `AppKeyInvalid` |
| fehlende Key-Version | `KeyVersionUnavailable` |

Alle Fehler werden vom Privacy-Handler als 400/fail-closed behandelt; keine
Teilfreigabe.

### 4.4 Caching / Nebenläufigkeit

- Prozesslokaler Cache, Cold-Start leer.
- Cache-Key: Provider + Referenz + Key-Version/Fingerprint.
- Kein Cache über Provider-Grenzen.
- Parallele Requests teilen einen unveränderlichen Snapshot; kein Lock um
  externe I/O.
- Rotation/Env-Wechsel invalidiert über Lambda-Neustart/Deployment; kein
  stiller Hot-Reload.
- Kein Loggen von Cache-Inhalten.

### 4.5 Akzeptanzkriterien

- ENV-Pfad bitgleich zum bestehenden Verhalten.
- AWS_MANAGED liefert ein Token, kein Secret im Log/Output/State.
- APP_MANAGED HMAC-Ergebnis ist mit dem bestehenden Vergleich kompatibel.
- Jeder Fehlerpfad ist fail-closed und getestet.
- Kein Provider-Fallback.
- Keine Secret-Werte in Fehlermeldungen.

### 4.6 Negative Tests

- fehlender/ungültiger Provider,
- fehlende/ungültige Referenz,
- ENV + AWS_MANAGED gleichzeitig,
- `AccessDenied`/`ResourceNotFound`/Timeout,
- falsche APP-Key-Version,
- Cache-Treffer ohne zweiten AWS-Aufruf,
- Log-/Exception-Redaction.

---

## 5. KMS- und Encryption-Vertrag

### 5.1 Getrennte Ebenen

| Ebene | Ist-Zustand | Zielentscheidung |
|---|---|---|
| Secrets-Manager-Verschlüsselung | AWS-managed Default | optional CMK, Q-02/Q-04 |
| Kunden-CMK | keine | optional, separate Q-04-Entscheidung |
| DynamoDB SSE | AWS-owned, kein CMK | optional CMK, P-05 |
| SQS SSE | SSE-SQS | optional SSE-KMS, P-06 |
| Anwendungs-Secretmaterial | ENV/Secret | Provider-Vertrag, P-01/P-02 |

AWS-owned-Verschlüsselung ist **keine** P00-CMK-Implementierung. T011-14
(DynamoDB-Backup-KMS) ist **nicht** P00.

### 5.2 CMK-Anforderungen

- Key-Policy: Root-Admin, exakte Service-Principals, `kms:ViaService` für
  DynamoDB/SQS; kein `Principal: "*"`.
- IAM: `kms:Decrypt`, ggf. `GenerateDataKey`/`Encrypt` nur auf exakten Key-ARN.
- Rotation: `enable_key_rotation=true`; Löschschutz/Deletion Window ≥ 7 Tage.
- Keine automatische CMK-Erzeugung ohne explizite Aktivierung.
- DDB-/SQS-Migration nur als geplanter, separater Schritt; kein Apply in diesem
  Auftrag.

### 5.3 Terraform-State

- Kein Klartext-Secret in State/Plan/Output.
- Secret-Wert nur ephemer/out-of-band; Secret-ARN/Name als Output.
- Sensitive-Werte in Terraform sind **kein** Ersatz für State-Schutz; das
  Restrisiko muss dokumentiert bleiben.

---

## 6. Rotation-Vertrag

Die fünf Mechanismen sind nicht gleichwertig:

1. **AWS Secrets Manager Rotation** — Secret-Version `AWSPENDING` →
   `AWSCURRENT`; Provider-Cache muss invalidieren.
2. **KMS Key Rotation** — AWS-managed/CMK-Rotation; beeinflusst nicht
   automatisch Secret-Versionen.
3. **APP_MANAGED Key-Versionierung** — externer Key, explizite `keyVersion`;
   alte Version nur im Übergangsfenster.
4. **Manuelle Rotation** — dokumentierter Operator-Ablauf.
5. **Secret-Cache-Invalidierung** — Neustart/Deploy; kein stiller Fallback.

### Offene Owner-Entscheidungen

- Übergangsfenster für alte Secret-Versionen: **OWNER_DECISION_REQUIRED**
- Native Rotation in RC4 oder später: **OWNER_DECISION_REQUIRED**
- APP_MANAGED-Rotationsverantwortung: **OWNER_DECISION_REQUIRED**
- CMK-Rotation/Deletion Window: **OWNER_DECISION_REQUIRED**

Bis zur Entscheidung: keine automatische Rotation, keine Frist erfinden.

---

## 7. Retention- und Privacy-Lifecycle-Vertrag

### 7.1 Bestehende Privacy-Funktionen

`inspect`, `export` und `erase` bleiben unverändert in ihrer Auth- und
Scope-Semantik. P00 darf die bestehenden Fail-closed-Eigenschaften nicht
abschwächen.

### 7.2 Retention-Ebenen

| Ebene | Semantik |
|---|---|
| Fachliche Ablaufzeit | `retentionUntil` (Vorschlag, Q-06) |
| DynamoDB TTL | nur physischer Beschleuniger; **kein** synchrones Löschversprechen |
| Sichtbarkeit nach Ablauf | noch offen; Policy muss Lese-/Schreibverhalten definieren |
| ERASE | explizite Löschung, idempotent, kein TTL-Ersatz |
| ANONYMIZE | PII/Ergebnis entfernen; Owner-Link entfernen |
| RETAIN | keine Löschung; Frist/Pflicht dokumentieren |
| Backups/PITR | Restore kann gelöschte PII wiederherstellen; separater Nachweis |
| Audit | `operationId`/Ereignis, keine PII; dauerhaftes Ledger offen |

### 7.3 Nicht erfinden

Keine konkreten gesetzlichen Fristen, keine TTL-Dauer, keine automatische
Löschung. Q-06/Q-14 bleiben offen. TTL ist **kein** DSGVO-Löschnachweis.

---

## 8. Terraform / Installer / Builder

### Terraform

- Neue Module `privacy_secret` und `kms` nur optional/additiv.
- Defaults: `privacy_secret_enabled=false`, `kms_enabled=false`.
- Keine neuen Pflicht-Inputs; keine Outputs mit Secret-Werten.
- IAM und Key-Policy exakt, count-gated.
- Bestehende Ressourcen nicht ersetzen; DDB-/SQS-Änderungen in-place planen.
- Policy-Gate-Allowlist erst nach Owner-Freigabe erweitern.

### Module Builder

- `orders-service`-Vertrag bleibt unverändert.
- Neue Module nur in explizitem `orders-service-hardened` oder `complete`
  (Q-03), Default aus.
- Keine Secret-Werte im Manifest; Validierung fail-closed.

### Installer

- Neue Flags nur optional; Default-Aufruf unverändert.
- Keine Secrets über CLI/argv/History.
- Preflight verweigert inkonsistente Provider-/Key-Konfiguration.
- Upgrade/Rollback dokumentiert; keine Ressourcenersetzung.

---

## 9. Owner Decision Register

**Status: OWNER_DECISIONS_PENDING**

| ID | Entscheidung | Bestehende Evidenz | Empfehlung | Auswirkung | Status |
|---|---|---|---|---|---|
| Q-02 | Secrets Manager vs. SSM vs. ENV | P00/P01 | Secrets Manager | P00-C/P00-E | OPEN |
| Q-03 | Modulangebot | P00 Q-03 | separates hardened Preset | P00-H | OPEN |
| Q-04 | CMK erzeugen/extern | P00 Q-04 | beides, Default extern | P00-E | OPEN |
| Q-05 | `tenantId` | P00 Q-05 | optional/null | P00-G | OPEN |
| Q-06 | Retention-Fristen | P00 Q-06 | 365/30 nur Vorschlag, rechtlich bestätigen | P00-G | OPEN |
| Q-07 | Cancel-Anonymisierung | P00 Q-07 | Opt-in | P00-G | OPEN |
| Q-08 | Secret-Referenz/Fetch | P00 Q-08 | ARN + Laufzeit-Fetch | P00-B/C | OPEN |
| Q-09 | Policy-Gate-Erweiterung | P00 Q-09 | mit Regeln | P00-E | OPEN |
| Q-10 | ADR-008-Freigabe | ADR-008 | PROPOSED freigeben/ändern | P00-A | OPEN |
| Q-11 | Rotation in RC4? | P00 Q-11 | nur manuell, native später | P00-F | OPEN |
| Q-12 | Release-Label | Q-12 | abhängig vom P00-Scope | Release | OPEN |
| Q-13 | AWS-Testkonto | Q-13 | isoliertes Testkonto/Freigabe | P00-I | OPEN |
| Q-14 | Bestand ohne Retention | Q-14 | separater Backfill | P00-G | OPEN |

Q-01 ist für die RC4-Baseline entschieden (kein RC3-Tag; `086a8be` autorisiert);
das ist **keine** RC3-Releasefreigabe.

**Nicht entschieden:** Q-02, Q-03, Q-04, Q-05, Q-06, Q-07, Q-08, Q-09, Q-10,
Q-11, Q-12, Q-13, Q-14.

---

## 10. Fazit

Ein konsistenter technischer Vertrag ist aus den vorhandenen Designs ableitbar,
insbesondere:

- ENV bleibt rückwärtskompatibler Default.
- AWS_MANAGED = Secrets Manager + optionaler CMK + exakter IAM-Zugriff, kein
  stiller ENV-Fallback.
- APP_MANAGED = externes Key-Material + HMAC, keine Eigenbau-Chiffre, keine
  Gleichsetzung mit KMS.
- KMS/Secrets/DDB/SQS sind getrennte Encryption-Ebenen.
- Rotation, Retention und TTL sind getrennte Mechanismen.
- Retention-Fristen und TTL-Semantik bleiben offen.

**Nächster Schritt:** Owner-Entscheidungen gemäß Register; danach P00-B
(SecretProvider Foundation) als separates Implementierungspaket.

Verwandte Dokumente:

- `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`
- `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md`
- `architecture/architecture-decisions.md` (ADR-008, PROPOSED)

---

## 11. Commit / Working Tree

| Feld | Wert |
|---|---|
| Dokumentations-Commit | `cf8edc7a2778eb5cc3f9a1cb5a487def7fc16e8d` |
| Working Tree nach Commit | CLEAN |

Keine Produkt-, AWS-, Terraform-, RIS- oder Jobsearch-Änderung.
