# Kostenstrategie — May's Orders

> Detaillierte Zahlen: `cost/cost-analysis.md`.

## 1. Ziel

Das System bleibt für ein kleines Unternehmen kostenbewusst (< ~2 $/Monat im Zielbetrieb,
Test-/Entwicklungsphasen deutlich darunter).

## 2. Maßnahmen

| Maßnahme | Wirkung |
|----------|---------|
| Free-Tier zuerst prüfen | Lambda, DynamoDB, Cognito i. d. R. kostenlos für Zielvolumen |
| HTTP API (V2) | ~30 % günstiger als REST API |
| On-Demand DynamoDB | kein Provisioning-Overhead |
| Log-Retention 7 Tage | CloudWatch-Logkosten begrenzen |
| Keine dauerhaft laufenden Services | kein EC2/NAT/ALB/ECS |
| Kein Step Functions | keine State-Transition-Kosten (ADR-005) |
| Cognito Free-Tier | 0 $ bis 50.000 MAU |
| Minimaler Alarm-Umfang | 0,30 $/Monat, nur sinnvolle Alarme |

## 3. Kontrolle

- Vor jedem kostenrelevanten `terraform apply`: **Freigabe durch menschliche Prüfung**.
- Nach Deployments: CloudWatch Billing / AWS Cost Explorer checken.
- Optional: Billing-Alert (0 $ Schwellwert) — Entscheidung offen, bei Bedarf Woche 2.
- Terraform-Destroy nach abgeschlossenen Testphasen (nach Freigabe) für Cleanup.

## 4. Unerwartete Kosten vermeiden

- Keine Deployment-Loops (wiederholtes Apply nur nach Plan-Review).
- Keine Large-Payload-Logs (strukturiert, kurz).
- Keine teuren Indices „just in case" (nur GSI1).
- Keine VPC-Anhänge/NAT-Gateways.

## 5. Verantwortung

Jeder Checkpoint enthält einen **Secret-Audit** und einen **Kosten-Check**
(keine Ressourcen-Neuanlage ohne Begründung).