# F010 — CloudWatch Monitoring

| Feld | Wert |
|------|------|
| **ID** | F010 |
| **Name** | CloudWatch Monitoring |
| **Status** | ⏳ PLANNED |
| **Week** | 3–4 |
| **Abhängigkeiten** | F003, F011 |
| **Fachquelle** | `monitoring/monitoring-design.md` |

## Beschreibung

Metriken (API 4xx/5xx, Lambda Errors/Duration, DynamoDB Throttling), strukturiertes JSON-Logging
mit Retention, minimale Alarme (kostenbewusst) und ggf. Dashboard.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T010-01 | JSON-Logging in Lambda | ⏳ PLANNED |
| T010-02 | Log-Retention setzen (7 Tage) | ⏳ PLANNED |
| T010-03 | Metriken definieren + Alarme (falls angemessen) | ⏳ PLANNED |
| T010-04 | Fehler-Szenarien auslösen und in Logs nachweisen | ⏳ PLANNED |
| T010-05 | Skalierungs-/Kosten-Messung (Woche 4) | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Logging verifiziert | NOT RUN |
| Alarme konfiguriert | NOT RUN |
| Messung (Duration/Cost) | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T010-01 (JSON-Logging) — nach Freigabe (Woche 3).