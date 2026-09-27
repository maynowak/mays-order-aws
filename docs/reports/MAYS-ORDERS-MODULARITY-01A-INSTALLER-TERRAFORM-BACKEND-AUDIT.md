# MAYS-ORDERS-MODULARITY-01A INSTALLER/TERRAFORM BACKEND RESOLUTION AUDIT

## STATUS
GREEN

## 1. aws_region
SOURCE OF TRUTH: Installer CLI --aws-region / --region, env AWS_REGION
RESOLUTION ORDER: CLI > env > default eu-central-1
DEFAULT: eu-central-1
EVIDENCE: installer/cli/main.py:55,65

## 2. environment
SOURCE OF TRUTH: Installer CLI --environment, env ENVIRONMENT
RESOLUTION ORDER: CLI > env > default Development
DEFAULT: Development
EVIDENCE: installer/cli/main.py:69
STATE ROLE: Tag only, not part of backend key

## 3. project_name
SOURCE OF TRUTH: Installer CLI --project-name, env PROJECT_NAME
RESOLUTION ORDER: CLI > env > default mays-orders
DEFAULT: mays-orders
WORKSPACE RELATION: project_name drives Terraform workspace via Installer context
STATE RELATION: Workspace isolation via workspace_key_prefix
EVIDENCE: installer/cli/main.py:60

## 4. terraform_workspace
SOURCE OF TRUTH: project_name derived
RESOLUTION ORDER: Installer creates workspace per project_name
EVIDENCE: installer/core/context.py
NOT DIRECTLY CLI SET

## 5. backend bucket
SOURCE OF TRUTH: terraform/backend.tf
ACTUAL VALUE: mays-orders-tfstate-central-240571105849
RESOLUTION PATH: Static in backend.tf

## 6. backend key
SOURCE OF TRUTH: terraform/backend.tf
KEY CONSTRUCTION: workspace_key_prefix "env:" + terraform workspace name
EXAMPLE: env:mays-orders/terraform.tfstate
EVIDENCE: terraform/backend.tf:8

## 7. terraform init caller
FILE: installer/cli/main.py
FUNCTION: _cmd_plan
CALLER: InstallerCLI.run
COMMAND: terraform init with backend flag

## 8. actual terraform init argv
FILE: installer/terraform/runner.py:235
ARGV: ["init", "-backend=false"] if backend=False else ["init"]
EVIDENCE: runner.py:221-242

## 9. backend-config
FOUND: NO
NO BACKEND-CONFIG MECHANISM FOUND

## 10. tfvars
FOUND: Manual --var / --var-file support
EVIDENCE: installer/cli/main.py:493-500

## 11. environment variables
AWS_REGION, AWS_PROFILE, PROJECT_NAME, ENVIRONMENT used

## 12. configuration files
No dynamic backend config files found

## 13. state isolation
PROJECT INPUT -> WORKSPACE -> BACKEND -> STATE KEY
project_name -> terraform workspace -> env: prefix -> state file

## 14. environment role
ENVIRONMENT is tag/governance only, not part of state isolation

## 15. implemented vs documented
No major deviations found

## AWS MUTATION
NONE

## TERRAFORM MUTATION
NONE
