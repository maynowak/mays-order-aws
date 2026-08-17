# IAM Design — May's Orders

## 1. Grundprinzip

IAM regelt ausschließlich **AWS-Service-Berechtigungen** („darf die Lambda-Funktion auf
diese DynamoDB-Tabelle zugreifen?“). Benutzer-Authentifizierung läuft **nicht** über IAM,
sondern über Cognito (siehe `authentication-decision.md`).

**Least Privilege ist verpflichtend:**

- Jede Rolle darf nur die minimal nötigen Aktionen auf genau die benötigten Ressourcen.
- Kein `*` auf Ressourcen, wo ein konkreter ARN möglich ist.
- Keine unnötigen AWS Services in der Policy.

## 2. Rollen & Policies

### 2.1 Lambda Execution Role (je Funktion, minimal)

| Komponente | Trust Policy | Attached Policy |
|------------|--------------|-----------------|
| `mays-orders-handler-role` | `lambda.amazonaws.com` | s. u. |

**Minimal-Policy (Konzept):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBOrders",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:REGION:ACCOUNT:table/mays-orders",
        "arn:aws:dynamodb:REGION:ACCOUNT:table/mays-orders/index/gsi1"
      ]
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Begründung der Aktionen:**

| Aktion | Wofür |
|--------|-------|
| `dynamodb:PutItem` | AP1 Create |
| `dynamodb:GetItem` | AP2 Get by ID |
| `dynamodb:UpdateItem` | AP4 Status-Update (Conditional) |
| `dynamodb:Query` | AP3 Listing (GSI1) |
| `logs:*` (eingeschränkt) | CloudWatch-Logging der Lambda |

**Bewusst NICHT erlaubt:** `dynamodb:Scan`, `dynamodb:DeleteItem`, `dynamodb:BatchWriteItem`,
`dynamodb:CreateTable`, `s3:*`, `sqs:*`, `iam:*`. Unnötige Rechte werden nicht vergeben.

> Hinweis: `logs:*` auf `Resource: "*"` ist üblich, weil Log-Gruppen/-Streams erst zur
> Laufzeit entstehen. Alternativ kann der Log-Group-ARN auf die Funktion beschränkt werden
> (Verfeinerung in Woche 2/3).

## 3. Service-to-Service-Berechtigungen

```text
Client
  │  (Cognito JWT — Authentication)
  ▼
API Gateway (HTTP API)
  │  (Integration: Lambda) — API-Gateway-Integration mit invoke-Permission
  ▼
Lambda Execution Role
  │  (IAM — Service-Berechtigung)
  ▼
DynamoDB (Tabelle + GSI)
```

### API Gateway → Lambda (Resource-Based Policy / Invoke Permission)

- Die Lambda `mays-orders-handler` erhält eine **Resource-Based-Policy**, die nur dem
  API-Gateway-ARN das `lambda:InvokeFunction` erlaubt.
- Kein öffentlicher Lambda-Aufruf.

## 4. Authentication vs. IAM (Trennung)

| Ebene | Zuständig für |
|-------|---------------|
| Cognito | Benutzeridentität, JWT, Login (Authentication) |
| API Gateway (JWT-Autorisator) | Token-Validierung am Gateway |
| Lambda + Claims | Authorization-Logik (was der Benutzer darf) |
| IAM | Rechte der AWS-Services untereinander |

## 5. Keine benutzerspezifischen IAM-Rollen

- Benutzer erhalten **keine** AWS-IAM-Rollen/Access-Keys.
- Benutzerzugriff läuft ausschließlich über Cognito-Token → API.

## 6. Secrets & Sensitive Data

- Keine Secrets in Terraform/Code. Passwörter/Keys nur über AWS Secrets Manager bzw.
  Cognito verwaltet (nicht im Repo).
- JWT / Tokens werden nicht geloggt.
- Kunden-Daten (Name, E-Mail) nicht ungefiltert in CloudWatch-Logs (Anonymisierung/Pruning
  in Woche 3).

## 7. Verifikation (geplant, Woche 2/3)

- Terraform `plan` zeigt die tatsächlich erzeugten Policies.
- Live-Test: Unauthentifizierter Request → 401; Lambda ohne Policy → Zugriffsfehler (als Negativ-Test).
- Secret-Audit: `grep` auf Access Keys/Passwörter im Repo vor jedem Checkpoint.