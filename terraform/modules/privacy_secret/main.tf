# P00-E — optional Secrets Manager secret container (no secret value)
#
# The secret VALUE is provisioned out-of-band by the operator. Terraform only
# owns the secret container/ARN; no aws_secretsmanager_secret_version is
# created here, so no plaintext value can enter plan/state/output.

resource "aws_secretsmanager_secret" "privacy" {
  name        = "${var.project_name}-privacy-internal"
  description = "May's Orders internal privacy secret; value provisioned out-of-band"
  kms_key_id  = var.kms_key_arn == "" ? null : var.kms_key_arn

  tags = merge({ "Project" = var.project_name }, var.tags)
}
