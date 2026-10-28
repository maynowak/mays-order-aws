# MO-MODULE-SQS-RESOURCE-POLICY-FIX-03

**SQS Resource Policy absichern**

## Ausgangspunkt

`terraform/modules/sqs/main.tf` enthielt:

```hcl
resource "aws_sqs_queue_policy" "orders" {
  ...
  Principal = "*"
}
```

## Analyse

- Policy erlaubte SendMessage/ReceiveMessage/DeleteMessage/GetQueueAttributes für jeden Principal
- Keine Condition, keine Konto-Beschränkung
- Zugriff bereits über IAM-Identitäts-Policies der Lambda-Rollen geregelt

## Maßnahme

Resource Policy entfernt und durch Kommentar ersetzt.

Begründung:
- Least Privilege: Zugriff nur via IAM-Rollen-Policies
- Kein Wildcard-Principal
- Kein festes AWS-Konto in der Policy
- Kontoportabel

## Tests

- Module Builder Tests: 90 OK
- Terraform validate: Success
- SQS-IAM-Gate weiterhin planstabil

## Ergebnis

**VERIFIED** — Keine ungeschützte SQS-Queue, F-03 behoben durch Entfernung der überflüssigen Resource Policy.
