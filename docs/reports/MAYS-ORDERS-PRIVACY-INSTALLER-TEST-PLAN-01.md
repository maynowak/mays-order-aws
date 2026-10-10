# MAYS-ORDERS-PRIVACY-INSTALLER-TEST-PLAN-01

## Baseline
- HEAD: de96ffd
- Test Project: mays-orders-privacy-test
- Region: eu-central-1
- AWS Profile: mayaws (vorgesehen)
- Terraform Workspace: mays-orders-privacy-test

## Installer Vorbereitung
- Installer CLI `./Mays-Order-AWS-installer validate/plan` nutzbar
- Projektisolierung über `project_name` + Workspace + State S3 Bucket
- Keine Installer-Änderungen vorgenommen

## Geplanter Deployment-Plan
- `project_name = mays-orders-privacy-test`
- DynamoDB Tabelle `mays-orders-privacy-test` mit GSI1 + GSI2
- IAM Rolle mit Least Privilege: Table Put/Get/Update/Delete/Query, GSI Query
- Lambda Handler mit Privacy Funktionen
- Keine produktiven Ressourcen betroffen

## Prüfungen vor Plan
- AWS Profil/Account: nicht verifiziert im Read-Only Modus
- State-Zuordnung: nur nach erfolgreicher Isolation verifizierbar
- GSI2 + IAM Berechtigungen im Plan erwartbar

## Ergebnis
Plan-Ausführung wird NICHT gestartet
- Isolation des separaten Testprojekts nicht zweifelsfrei nachgewiesen
- Uncommitted Terraform Änderungen vorhanden
- Keine AWS Mutationen erlaubt

## Blockers
1. Isolation Nachweis fehlt
2. AWS Profil/Account Verifizierung offen
3. Uncommitted Änderungen in Terraform

## Empfehlung
Isolation verifizieren, uncommitted Änderungen bereinigen, dann Plan mit Installer ausführen.

Kosten: On-Demand DynamoDB, keine dauerhaften Kosten erwartet.
