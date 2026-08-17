# Assumptions & Constraints — May's Orders

## 1. Assumptions (Annahmen)

| ID | Annahme | Risiko bei Verletzung |
|----|---------|----------------------|
| A-01 | Es existiert ein gültiges AWS-Konto mit Free-Tier-/Low-Cost-Nutzung | Kosten entstehen |
| A-02 | AWS CLI und Terraform sind lokal installiert und konfiguriert | Deployment nicht möglich |
| A-03 | Node.js-Laufzeit steht für lokale Entwicklung/Tests zur Verfügung | Build/Tests nicht möglich |
| A-04 | Eine Bestellung gehört genau einem Kunden (keine Teams/Sharing) | Datenmodell müsste erweitert werden |
| A-05 | Orders werden vom Backoffice bzw. einem autorisierten Client verwaltet; kein öffentlicher Self-Service-Shop gefordert | Berechtigungsmodell könnte erweitert werden |
| A-06 | Das System verarbeitet synchronen Request/Response-Verkehr (kein Eventing/Messaging gefordert) | Architektur müsste erweitert werden |
| A-07 | Einzelne Bestellung: unter 400 KB Payload (DynamoDB-Item-Grenze) | Item-Größe müsste optimiert/gesplittet werden |
| A-08 | Mengengerüst 100 → 100.000 Orders/Tag wird als Analyse-/Bewertungsziel betrachtet | Skalierungsprobleme (Hot Partitions) möglich |
| A-09 | Auth-Flow ist anfangs einfach: eine Benutzerrolle (Staff) mit Vollzugriff auf Orders | Rollen-/Feingranularitätsmodell müsste erweitert werden |

## 2. Constraints (Rahmenbedingungen)

| ID | Constraint | Implikation |
|----|------------|-------------|
| C-01 | Serverless-first: Lambda, API Gateway, DynamoDB | Kein EC2/RDS/Kubernetes |
| C-02 | Infrastructure as Code mit Terraform | Keine manuell erzeugte Infrastruktur als finales Ergebnis |
| C-03 | Fokussierte Architektur: keine unnötigen AWS-Services | Jede Erweiterung braucht eine begründete Architecture Decision |
| C-04 | Security: keine Secrets im Repo, Least Privilege | Secret-Audit in jedem Checkpoint |
| C-05 | Evidence-based: keine erfundenen Testergebnisse | Nur getestete Ergebnisse werden als PASS gemeldet |
| C-06 | Kostenbewusst, Free-Tier-beachtend | Keine dauerhaft laufenden teuren Ressourcen ohne Begründung |
| C-07 | Vier-Wochen-Zeitrahmen, Weekly Report bis Freitag 15:00 | Schrittweises Vorgehen mit Checkpoints |
| C-08 | Checkpoint-/Recovery-Strategie über Reports in `docs/reports/` | Reports sind die maßgebliche Recovery-Quelle |
| C-09 | API darf das Lebenszyklus-Modell nicht umgehen (Ungültige Übergänge → Fehler) | State Machine im Domain-Layer |

## 3. Offene Punkte (werden in Woche 1 entschieden)

| Offen | Entscheidung in |
|-------|-----------------|
| HTTP API vs. REST API | `architecture/architecture-decisions.md` |
| Cognito als Auth-Lösung ja/nein | `architecture/architecture-decisions.md` |
| Single-Table vs. Multi-Table DynamoDB | `database/dynamodb-design.md` |
| State Machine im Code vs. Step Functions | `architecture/architecture-decisions.md` |