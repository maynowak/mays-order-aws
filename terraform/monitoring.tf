# =============================================================================
# T011-11 — CloudWatch Monitoring as Code
# Fachquelle: monitoring/monitoring-design.md (Source of Truth für Anforderungen),
#             cost/cost-analysis.md §2 (kostenbewusst: 7-Tage-Retention, minimaler
#             Alarm-Umfang, kein SNS-Topic in dieser Aufgabe).
#
# Ziel: Dashboard + Alarme + Log-Retention vollständig per Terraform beschrieben,
# damit sie später reproduzierbar in AWS erzeugt werden können (kein apply in
# T011-11). Verwendete Metriken sind ausschließlich echte AWS-Namespaces:
#   AWS/ApiGateway (Count, 4XXError, 5XXError)        — HTTP API (ApiId, Stage)
#   AWS/Lambda     (Invocations, Errors, Duration,     — FunctionName
#                   Throttles, ConcurrentExecutions)
#   AWS/DynamoDB   (ThrottledRequests,                 — TableName
#                   ConditionalCheckFailedRequests)
#
# Business-Metriken (Orders Created / Orders by Status / Order Success Rate)
# sind BEWUSST NICHT als Custom Metrics implementiert (GAP, siehe
# docs/reports/T011-11-CLOUDWATCH-MONITORING.md): sie stünden als
# "FUTURE APPLICATION METRIC" auf Datenquelle DynamoDB/Order-Daten
# (createdAt, updatedAt, status). Keine erfundenen Metric Names.
# =============================================================================

# --- Monitoring wurde in das Modul terraform/modules/monitoring/ verschoben.
# Siehe module.monitoring.

# Die Log-Group für Lambda ist im Lambda-Modul (terraform/modules/lambda/).