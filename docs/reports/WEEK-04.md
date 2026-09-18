# Weekly Report — Woche 4

**Datum:** September 14, 2026
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** ✅ COMPLETE (Phase-2 verifiziert)

## 1. Gesamtstatus

Phase 2 (SQS-Integration) wurde erfolgreich verifiziert.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| Phase-2 SQS Integration | Producer → SQS | ✅ VERIFIZIERT |
| Phase-2 Worker | DynamoDB Update | ✅ VERIFIZIERT |
| IAM-Berechtigungen | GetItem + UpdateItem | ✅ KORRIGIERT |
| Root-Cause-Analyse | Permissions Boundary | ✅ GEFUNDEN |

## 3. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| Python-Syntax | ✅ BESTANDEN |
| Terraform validate | ✅ BESTANDEN |
| E2E Integration (Producer → SQS → Worker → Dynamo | ✅ VERIFIZIERT |
| DynamoDB Status Transition (PENDING → CONFIRMED) | ✅ VERIFIZIERT |

## 4. AWS-Ressourcen

Phase 2 Deployment:

- Producer Lambda: Updated mit SQS-Integration
- IAM Policy: Erweitert um `dynamodb:UpdateItem`
- Permissions Boundary: Korrigiert (Account-ID)
- SQS Queue: Existiert bereits
- Worker Lambda: Existiert bereits, verwendet bereits korrigierte Policy

## 5. Probleme / Risiken / Blocker

### Root-Cause gefunden:

1. **Falsche Account-ID in Permissions-Boundary:**
   - Original: `20571105849`
   - Korrekt: `240571105849`

2. **Fehlende IAM-Berechtigung:**
   - Worker-Policy hatte nur `dynamodb:GetItem`
   - Ergänzt um `dynamodb:UpdateItem`

### Lösung:

- Boundary-Policy korrigiert und erweitert
- Worker-Policy erweitert

## 6. Kosten

Keine zusätzlichen Kosten (bestehende Ressourcen verwendet).

## 7. Nächste Schritte

- Phase 3: Idempotenz, DLQ, Status-Abfrage
- Woche 3 Grundlagen verifizieren

## 8. Zeitplan-Bewertung

✅ Phase 2 am Zeitplan

## 9. Git Checkpoint

- **Tag:** `week-4-final-20260914`
- **Commit:** `6a34a02`
- **Status:** Verified & Pushed to GitHub