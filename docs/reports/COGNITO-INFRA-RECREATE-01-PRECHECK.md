# COGNITO-INFRA-RECREATE-01 PRECHECK

**Datum:** 2026-09-27

## 1. Terraform Configuration

module.cognito source: ./modules/cognito
project_name: var.project_name
tags: var.tags

Cognito Module definiert:
- aws_cognito_user_pool.users name = "${var.project_name}-users"
- aws_cognito_user_pool_client.app name = "${var.project_name}-client"
- aws_cognito_user_group.staff name = "staff"

Configuration PRESENT

## 2. AWS Identity
Profile: mayaws
Account: 240571105849
Region: eu-central-1

## 3. Workspace
mays-orders

## 4. Terraform Plan

terraform plan -target module.cognito

Ergebnis:
- aws_cognito_user_pool.users wird erstellt, name = mays-orders-users
- aws_cognito_user_pool_client.app wird erstellt, name = mays-orders-client
- aws_cognito_user_group.staff wird erstellt, name = staff

Plan: 3 to add, 0 to change, 0 to destroy

## 5. Erwarteter Poolname
mays-orders-users

Bestätigt durch Terraform Module:
name = "${var.project_name}-users"

## 6. Aktueller AWS Pool
AWS API list-user-pools → []
Kein Cognito User Pool existiert in Account 240571105849 eu-central-1

## 7. State Referenz
Terraform State für Workspace mays-orders enthält keine Cognito Ressourcen.
Nur module.cognito_backup vorhanden.

## Fazit
Configuration ist vorhanden und würde Cognito Infrastruktur erstellen.
Aktuell existiert kein Pool in AWS.
Kein Apply durchgeführt.
