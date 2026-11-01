# MO-RC4-P02F — PENDING-Recovery-Scheduler
#
# Ruft den BESTEHENDEN Order-Handler (keine zusaetzliche Lambda) alle 5 Minuten
# mit `internalAction: recovery/scan` auf. Der Handler sucht ueber GSI1
# liegengebliebene PENDING-Orders und stellt sie erneut in die bestehende
# SQS-Queue ein (gleicher Worker-/DLQ-Pfad, kein DLQ-Redrive).
#
# Sicherheit:
# - Keine oeffentliche API-Route; nur direkter Lambda-Invoke.
# - Scheduler-Rolle darf AUSSCHLIESSLICH diese eine Funktion aufrufen.
# - Kein Secret im Scheduler-Payload (maximale Reduktion von Leak-Flaechen).
#
# Aktivierung ist opt-in (default false), damit bestehende Deployments ohne
# explizite Zustimmung keine neuen Ressourcen erhalten.

variable "enabled" {
  description = "Aktiviert den Recovery-Scheduler (opt-in). Default false."
  type        = bool
  default     = false
}

variable "project_name" {
  description = "Name des Projekts (Namenskonvention der Ressourcen)"
  type        = string
}

variable "tags" {
  description = "Tags für Ressourcen"
  type        = map(string)
  default     = {}
}

variable "function_arn" {
  description = "ARN des bestehenden Order-Handlers (Recovery-Ziel)"
  type        = string
}

variable "schedule_expression" {
  description = "Schedule-Ausdruck (Default: alle 5 Minuten)"
  type        = string
  default     = "rate(5 minutes)"
}

variable "window_minutes" {
  description = "Recovery-Zeitfenster in Minuten (GSI1-Range-Query)"
  type        = number
  default     = 60
}

variable "min_age_seconds" {
  description = "Mindestalter einer PENDING-Order, bevor Recovery sie anfasst"
  type        = number
  default     = 60
}

variable "limit" {
  description = "Maximale Kandidaten pro Recovery-Lauf"
  type        = number
  default     = 50
}

variable "lease_seconds" {
  description = "Lease/Claim-Dauer gegen parallele Recovery-Laeufe"
  type        = number
  default     = 300
}

resource "aws_iam_role" "scheduler" {
  count = var.enabled ? 1 : 0
  name  = "${var.project_name}-orders-recovery-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "invoke_handler" {
  count = var.enabled ? 1 : 0
  name  = "${var.project_name}-orders-recovery-invoke"
  role  = aws_iam_role.scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [var.function_arn]
    }]
  })
}

resource "aws_scheduler_schedule" "recovery" {
  count = var.enabled ? 1 : 0
  name  = "${var.project_name}-orders-recovery"

  schedule_expression = var.schedule_expression
  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.function_arn
    role_arn = aws_iam_role.scheduler[0].arn

    input = jsonencode({
      internalAction = "recovery/scan"
      options = {
        windowMinutes = var.window_minutes
        minAgeSeconds = var.min_age_seconds
        limit         = var.limit
        leaseSeconds  = var.lease_seconds
      }
    })
  }
}

output "schedule_name" {
  description = "Name des Recovery-Schedulers (leer, wenn deaktiviert)"
  value       = var.enabled ? aws_scheduler_schedule.recovery[0].name : ""
}

output "scheduler_role_arn" {
  description = "ARN der Scheduler-Rolle (leer, wenn deaktiviert)"
  value       = var.enabled ? aws_iam_role.scheduler[0].arn : ""
}
