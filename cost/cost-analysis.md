# Cost Analysis — May's Orders

## 1. Grundprinzip

- Free-Tier zuerst prüfen.
- Nur die minimal nötigen Ressourcen erzeugen.
- Keine dauerhaft laufenden Ressourcen ohne Begründung.
- Logging-Retention begrenzen (CloudWatch-Kosten).

## 2. Kostenbestandteile (Stand Woche 1, Schätzung)

> Preise basieren auf AWS-Public-Pricing (Stand 2026, Region eu-central-1 angenommen).
> Es handelt sich um **Planungswerte** — tatsächliche Metered-Werte werden in Woche 4 gemessen.

### API Gateway (HTTP API)

- Kosten: ~1,00 $/Mio. Requests (HTTP API; günstiger als REST).
- Bei 100.000 Requests/Monat: **≈ 0,10 $/Monat.**

### Lambda

- Free-Tier: 1 Mio. Requests + 400.000 GB-s/Monat.
- 100.000 Requests × ~200 ms × 128 MB ≈ 25.600 GB-s → **innerhalb Free-Tier, ≈ 0 $.**

### DynamoDB (On-Demand)

- Free-Tier: 25 GB Speicher, 25 WCU/RCU On-Demand-Kapazität (~200 Mio. Read-/Write-Einheiten/Monat, je nach Quelle).
- 100.000 Orders mit je 1 Write + 1 Read + Listing: **≈ 0 $ (Free-Tier).**

### CloudWatch

- Logs: Log-Ingest/Storage; bei 7-Tage-Retention und strukturierten Kurzlogs gering.
- Schätzung bei 100k Requests: wenige $, meist < 1 $.
- Alarme: 3 Alarme à 0,10 $/Monat ≈ **0,30 $/Monat.**

### Cognito

- Kostenlos bis 50.000 MAU → **0 $** für dieses Projekt.

## 3. Zusammenfassung (Planung)

| Position | Monat (Planung) |
|----------|-----------------|
| API Gateway | ~0,10 $ |
| Lambda | 0 $ (Free-Tier) |
| DynamoDB | 0 $ (Free-Tier) |
| CloudWatch | ~0,30–1,00 $ |
| Cognito | 0 $ |
| **Gesamt (realistisch)** | **< 1,50 $/Monat** bei 100k Requests |

> **Wichtige Warnung:** Dies sind Planungswerte für das Zielmengengerüst. Für den
> Entwicklungs-/Testbetrieb wird mit deutlich weniger Requests gerechnet. Vor jedem
> Deployment wird der aktuelle Kostenstand mit `aws ce`/Billing-Dashboard geprüft.

## 4. Kosten-Bewusstseins-Maßnahmen

1. **On-Demand-DynamoDB** statt unnötig hohem Provisioning.
2. **Log-Retention 7 Tage**, strukturierte Logs, keine Token/PII.
3. **Keine dauerhaft laufenden Ressourcen** (kein EC2/NAT/ALB).
4. **Cognito im Free-Tier** (bis 50.000 MAU).
5. **HTTP API statt REST API** (~30 % geringere Kosten).
6. **Kein Step Functions** (ADR-005) → 0 State-Transition-Kosten.
7. **Cleanup-Plan:** Nach Testphasen Terraform-Destroy prüfen (nach Freigabe).

## 5. Offene Kostenentscheidungen

| Frage | Stand |
|-------|-------|
| DynamoDB Provisioned vs. On-Demand | Woche 4 quantifizieren (ADR-007) |
| PITR/Backups | Optional; kostenpflichtig. Abwägung Woche 3/4 |
| Terraform-State-Backend (S3) | S3 kostenminimal (~0,02 $), Entscheidung Woche 2 |
| SNS für Alarme | Nur falls Alarme benötigt; sehr gering |

## 6. Skalierungs-Kostenszenario (Woche 4-Input)

| Orders/Tag | Requests/Monat | Geschätzte Kosten/Monat |
|------------|----------------|-------------------------|
| 100 | ~12k | ≈ 0,10–0,30 $ |
| 1.000 | ~120k | ≈ 0,30–1,00 $ |
| 10.000 | ~1,2 Mio. | ≈ 2–4 $ |
| 100.000 | ~12 Mio. | ≈ 20–40 $ (API GW dominiert) |

Diese Werte werden in Woche 4 mit den tatsächlichen Metriken validiert und dokumentiert.