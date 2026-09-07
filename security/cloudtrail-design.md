# CloudTrail Design — May's Orders

> **Source of Truth** für den AWS-API-Audit-Trail (Account-Level Security/Audit).
> Stand T011: CloudTrail wird vollständig per **Terraform** (`module.cloudtrail`)
> beschrieben. **Kein `terraform apply`/Live-Test in T011.**

## 1. Was (What)

CloudTrail liefert einen **Account-weiten AWS-API-Audit-Trail**: er protokolliert
Management-/API-Ereignisse der AWS-Konten-Ressourcen und beantwortet damit

- **WHO** — welche Identität (User/Rolle/Service) hat gehandelt,
- **WHAT** — welche API-Aktion wurde aufgerufen,
- **WHEN** — wann (Zeitstempel),
- **WHERE** — aus welcher Region/Quell-IP.

## 2. Warum (Why)

Sicherheit & Nachvollziehbarkeit (`security/iam-design.md` Grundprinzip „Least Privilege"
erweitert um Auditing). Ohne CloudTrail ist AWS-API-Aktivität nicht auditierbar — wer
z. B. eine IAM-Richtlinie, eine DynamoDB-Tabelle oder eine Lambda-Änderung vorgenommen
hat, wäre nicht belegbar.

## 3. Was wird aufgezeichnet (What is recorded)

- **Management Events** (Read **und** Write) auf Account-Ebene.
- **Alle Regionen** (`is_multi_region_trail = true`) + **globale Service-Events**
  (z. B. IAM, `include_global_service_events = true`).
- **Keine Data Events** (z. B. Objekt-Level DynamoDB) — bewusst außerhalb des
  Prototyp-Scopes (siehe §7).

## 4. Wo (Where)

- **Trail:** `mays-orders-trail` (`aws_cloudtrail.trail`).
- **Destination:** dedizierter S3-Bucket `mays-orders-cloudtrail-<account-id>`
  unter `AWSLogs/<account-id>/CloudTrail/`.

## 5. Wie (How — Terraform)

| Ressource | Terraform-Typ | Zweck |
|-----------|---------------|-------|
| Trail | `aws_cloudtrail.trail` | Trail, multi-region, Management Events Read+Write, Log-File-Validierung |
| Bucket | `aws_s3_bucket.trail` | Zweckgebundener Log-Bucket (global eindeutig via Account-ID) |
| Bucket-Eigentum | `aws_s3_bucket_ownership_controls.trail` | `BucketOwnerEnforced` (ACLs deaktiviert) |
| Public-Access-Block | `aws_s3_bucket_public_access_block.trail` | Jeglicher öffentlicher Zugriff gesperrt |
| Verschlüsselung | `aws_s3_bucket_server_side_encryption_configuration.trail` | At-rest **SSE-S3 (AES256)** explizit |
| Bucket-Policy | `aws_s3_bucket_policy.trail` | Nur `cloudtrail.amazonaws.com` darf `PutObject` auf das CloudTrail-Prefix (SourceArn-Condition) |

## 6. CloudWatch vs. CloudTrail

| | CloudWatch | CloudTrail |
|---|---|---|
| Zweck | Operational-/Application-Monitoring | AWS-API-Activity / Audit-Trail |
| Inhalt | Logs, Metriken, Alarme, Dashboard | Management-/API-Ereignisse |
| Fragestellung | „Läuft die App gesund?" | „Wer hat was wann wo getan?" |
| Modul | `module.monitoring` (+ Lambda-Log-Group) | `module.cloudtrail` |

Die beiden bleiben **strikt getrennt**; CloudTrail übernimmt keine CloudWatch-Funktion
und umgekehrt.

## 7. Current Prototype Scope

**Tatsächlich konfiguriert (Terraform, kein apply):**

- Multi-Region-Trail, Management Events (Read+Write), globale Service-Events.
- Log-Destination S3 mit expliziter At-rest-Verschlüsselung (SSE-S3), Public-Access-Block,
  BucketOwnerEnforced und CloudTrail-Bucket-Policy (Least Privilege).
- Log-File-Validierung aktiv (Integrität der Log-Dateien).

**Bewusst NICHT (Prototyp-Scope, siehe `terraform/README.md`):**

- **Kein Data-Events** (DynamoDB Object-Level).
- **Kein KMS** (SSE-S3 statt SSE-KMS — kostenbewusst; KMS wäre Best-Practice für
  strikte Zugriffshärtung).
- **Kein Lifecycle/Rretention-Regel** (keine automatische Löschung im Prototyp; S3-
  Lifecycle wäre sinnvoll für langfristige Retention).
- **Kein SNS-Alarm** auf CloudTrail-Ereignisse (Security-Eventing später möglich).

**AWS-managed Defaults vs. explizite Konfiguration:**

- Verschlüsselung at rest: **explizit** konfiguriert (SSE-S3), nicht nur Default.
- Öffentlicher Zugriff: **explizit** gesperrt (zusätzlich zum S3-Default „privat").
- Encryption in transit: AWS-intern TLS (AWS-managed, kein expliziter Config-Punkt).

## 8. Live-Verifikation (nach human-freigegebenem apply)

Noch **PENDING** (kein apply in T011). Zu verifizieren: Trail existiert, Logging aktiv,
Management-Events werden aufgezeichnet, S3-Destination erhält Logs, Bucket nicht öffentlich,
Verschlüsselung aktiv, API-Aktivität auditierbar.

## 9. Optional Production Hardening (Install-Mode / Future)

> **NICHT implementiert.** Zukünftige, optionale Security-/Compliance-Erweiterungen,
> klar getrennt vom implementierten Prototyp-Baseline (§7). Kein fehlender Kern-Scope —
> der Baseline erfüllt bereits den Audit-Grundbedarf (WHO/WHAT/WHEN/WHERE).

| # | Feature | Deferral-Reason | Abhängigkeit | Empf. Reihenfolge |
|---|---------|-----------------|--------------|-------------------|
| 1 | **SSE-KMS** (customer-managed key) | Kosten + Keys-Management (Key-Rotation, Key-Policy, Alias) | `aws_kms_key` + Key-Policy für CloudTrail-Service | 1 |
| 2 | **DynamoDB Data Events** | Event-Volumen/Kosten; erst bei konkreter Data-Plane-Audit-Anforderung | `event_selector` mit `data_resource` auf Table-ARN | 2 |
| 3 | **S3 Lifecycle / Retention** | Rein compliance-/betriebsgetrieben; keine willkürliche Frist hardcoden | `aws_s3_bucket_lifecycle_configuration` | 3 |
| 4 | **Security-Eventing (SNS/EventBridge)** | Trennung Audit-Speicherung vs. aktive Alarmierung; kostenbewusst | CloudTrail → EventBridge → SNS/Consumer | 4 |
| 5 | **MFA Delete / Log-Protection-Härtung** | Operative Einschränkungen (Root-Session nötig, Lifecycle-Konflikt) | S3 Versioning + `aws_s3_bucket_versioning`/MFA | 5 |

**Begründung der Deferral-Reasons:** jeweils Kosten, operative Komplexität oder fehlende
konkrete (Compliance-)Anforderung — nicht „fehlende Kernfunktion".

**Install-Mode-Hinweis:** Diese Features sind als **optionaler Install-Modus** vorgesehen,
d. h. sie würden über Terraform-Variablen (z. B. `cloudtrail_kms_enabled`, `cloudtrail_data_events`,
`cloudtrail_retention_days`) **bewusst aktiviert**, nicht per Default. Der aktuelle
`module.cloudtrail` bleibt für den Prototyp unverändert.

Siehe auch: `docs/roadmap/future-extensions.md` (CloudTrail Production Hardening).