# Consistency & Failure Handling — May's Orders

## 1. Konsistenz

### 1.1 Statusübergänge (atomar)

Statusänderungen laufen ausschließlich über **DynamoDB Conditional Writes**:

```text
ConditionExpression: attribute_exists(pk) AND status = :current
```

Damit gilt pro Item atomar:

- Nur ein konkurrierendes Update gewinnt (siehe `transition-rules.md` §4).
- Ein ungültiger Übergang wird bereits durch die State-Machine-Prüfung in der Lambda
  verhindert; der Conditional Check ist die zweite, atomare Verteidigungslinie.

### 1.2 Letztendliche Konsistenz vs. starke Konsistenz

| Pattern | Standard-Konsistenz | Erklärung |
|---------|---------------------|-----------|
| GetItem / Query | eventual (Standard) | Nach einem Write ist ein evtl. verzögerter Read möglich |
| GetItem stark | `ConsistentRead=true` | Immer neuester Stand, 2× RCU |

- **GET /orders/{id}:** starke Konsistenz ist NICHT zwingend (Bestellobjekte ändern sich
  selten und Kunden erwartet den neuesten Stand nach eigenem Write). Entscheidung Woche 2:
  `ConsistentRead=true` für `GET` nach eigener Schreibaktion prüfen — anfangs `eventual`.
- **PATCH:** nutzt `UpdateItem` → liest+schreibt atomar, kein Konsistenzproblem.

### 1.3 Konkurrierende Updates (Detail)

| Schritt | Aktion |
|---------|--------|
| 1 | Beide Clients lesen `status=CONFIRMED` |
| 2 | A: Update `status→PROCESSING` mit `WHERE status=CONFIRMED` → **gewinnt** |
| 3 | B: Update `status→CANCELLED` mit `WHERE status=CONFIRMED` → `ConditionalCheckFailedException` → 409 CONFLICTED_UPDATE |
| 4 | Endzustand: `PROCESSING` — konsistent, kein ungültiger Übergang |

Zusätzliche Reserve: `version`-Attribut (Optimistic Locking) ist vorgesehen,
aber Status-basierte Bedingung reicht für das reale Szenario (vgl. transition-rules §4).

## 2. Fehlerbehandlung

### 2.1 Lambda

- Try/Catch am Handler-Rand; alle Fehler in strukturierte Fehlerantworten mappen
  (siehe `api/endpoints.md` §3).
- Unerwartete Exceptions → 500 `INTERNAL_ERROR` (keine internen Details nach außen);
  vollständiger Stacktrace nur in CloudWatch.
- Retry-fähig: Handler sind idempotent (kein doppeltes Anlegen bei Retry durch API GW;
  Retries sind bei HTTP API standardmäßig deaktiviert — bewusst).

### 2.2 DynamoDB-Fehler

| Fehler | Handling |
|--------|----------|
| `ConditionalCheckFailedException` | 409 CONFLICTED_UPDATE |
| `ResourceNotFoundException` | 404 ORDER_NOT_FOUND |
| `ProvisionedThroughputExceeded`/Throttling | Bei On-Demand selten; Retry mit Backoff in der Lambda |
| Netzwerk-/Timeout | Retry mit exponentiellen Backoff (AWS SDK default), sonst 500 |

## 3. Skalierung

- Lambda skaliert automatisch (Stateless, 1.000 gleichzeitige Invocations pro Region Default).
- API Gateway skaliert automatisch; HTTP API ohne Abonnement.
- DynamoDB On-Demand skaliert adaptiv.
- **Hot-Partition-Notiz:** GSI1-Partition `LIST` konstant (siehe `dynamodb-design.md` §6);
  bei den Zielvolumina unkritisch, Sharding dokumentiert.

## 4. Disaster/Recovery

- DynamoDB On-Demand: automatisch repliziert (AZ-redundant) — keine manuelle Sicherung nötig.
- Terraform-State ist die Wiederherstellungsquelle der Infrastruktur (S3-Backend ab Woche 2,
  Entscheidung offen; anfangs lokal).
- **Backup-Entscheidung offen:** DynamoDB PITR (Point-in-Time Recovery) kostenpflichtig;
  für Demo-Zweck optional. Wird in `cost/cost-analysis.md` abgewogen.