# MAYS-ORDERS-MODULARIZATION-01-B-RIS-CONTRACTS-RESEARCH — EXECUTION LOG

- **Current Status:** COMPLETED (read-only Research abgeschlossen)
- **Date/Time:** 2026-10-18 (UTC-Kontext; Research im Rahmen der Worker-/IAM-Modularisierung)
- **Git Branch + HEAD:** Mays-Recruiting-Intelligent-System, main `1ed5a0b` (laut RIS-Report MAYS-RIS-CLEANUP-AND-VERIFY-mitluftposter-01; Orchard-Read-only-Kontext)
- **Scope:** Work-System, Worker und OrdersPort in Mays-RIS untersuchen; bestehende MO-Integrationsverträge dokumentieren; Wiederverwendbarkeit bewerten. KEINE Änderungen an RIS.
- **Mode:** READ-ONLY — keine Schreibzugriffe, keine AWS-Calls.

## Completed Sections

1. OrdersPort-Vertrag (Signaturen, OrderResult) erfasst
2. RealMaysOrdersAdapter-Zugriffsweg (HTTP vs. DynamoDB) nachgewiesen
3. RIS-Worker-Pfad-Ressourcen (Queues, Lambdas, Mappings) inventarisiert
4. RIS-IAM für den MO-Zugriff geprüft + Abhängigkeitsfrage zur MO-Handler-Policy
5. Verbindliche MO-erwartete Vertragspunkte zusammengestellt
6. Dokumentierte Wiederverwendungs-Kandidaten (MO-Bausteine) gesammelt

## Actual Findings

1. **OrdersPort-Vertrag** (agents/orders/adapter.py Z.45–96): `submit_order(work_item, capability, payload=None, tenant_id=None, actor_id=None, idempotency_key=None) -> OrderResult`; `get_order_status(order_id) -> Optional[OrderResult]`; `can_handle(capability) -> bool` (Default `True`); `OrderResult{success, order_id, result_type, reason, data}`; `OrdersResultType{APPROVED, REJECTED, PENDING, ERROR}`. GATE-6 bestätigt den Vertrag als unverändert.
2. **Zwei-Stufen-Integration — Real-Adapter nutzt HTTP auf die RIS-EIGENE API, NICHT die MO-API und NICHT direkt DynamoDB:** agents/orders/real.py (Docstring Z.8–11: „EIGENE Orders-Routen auf UNSERER API (fronten die live Mays-Orders-Tabelle; eigenes JWT)"), `DEFAULT_BASE_URL = https://aboqolpm0f…` = RIS-API `mays-ris-dev-api` (GATE-4 Z.61); HTTP via `urllib.request.urlopen` (real.py Z.57–72), Routen POST /orders, PATCH /orders/{id}/status, GET /orders/{id} (Z.169, 187–188, 194), JWT Bearer aus injiziertem token_provider.
3. **Direkter MO-Zugriff liegt ausschließlich im RIS-`orders_reader`-Lambda** (lambda/orders_reader.py): boto3 `Table(ORDERS_TABLE)` (Z.68–77), `put_item` mit `attribute_not_exists(pk)` (Z.244), `update_item` mit Status-Guard (Z.152–164), GSI-Query `gsi1pk = LIST` (Z.119–126); **MO-SQS-Kick nach Create** `{"orderId", "status":"CONFIRMED", "metadata.reason":"order_created"}` (Z.208–218, „beobachtete Nachrichtenform des Live-Systems"); Provenienz-Kommentar Z.2–14: „keine Aenderung am fremden Projekt", Verhalten „1:1 aus dokumentiertem Mays-Orders-Verhalten (Gate-2/3 verifiziert)".
4. **RIS-Worker-Pfad:** eigene Queues `mays-ris-dev-{work,cv,ats,match}-queue` + `-dlq` (modules/sqs/main.tf Z.3–60), Worker `mays-ris-dev-agent` (modules/lambda/main.tf Z.4, Event-Source-Mapping Z.429–433, batch 5), Orders-Function als Port-Delegation (agents/orders/function.py, keine Fachlogik), Bootstrap-Registrierung pipeline.py Z.92,126; kontrollierte Fehlercodes ohne SQS-Retry (pipeline.py Z.70–77).
5. **RIS-IAM für MO-Zugriff — ARN-präzise, EIGENE Rolle:** modules/orders_reader/main.tf Z.33–71: `reader_orders_table` = DDB GetItem/Query/UpdateItem/PutItem auf `var.orders_table_arn` + `/index/*` (Z.41–51); SQS NUR `SendMessage` auf `var.orders_queue_arn` (Z.53–59, „Queue gehört fremdem Projekt; nur SendMessage"). **KEINE Abhängigkeit von der MO-Handler-Policy** — RIS hängt ausschließlich an: (a) gleichem Konto, (b) dem MO-Naming-Contract (Tabelle == project_name; Queue == `{project}-orders-queue`, installer/ris.py Z.138–142, 448–461), (c) der MO-Queue-Policy, die SendMessage erlaubt (Principal `*`, live belegt GATE-3 Z.70,113).
6. **Verbindliche Vertragspunkte:** Statusmaschine PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED, CANCELLED aus PENDING/CONFIRMED (orders_reader.py Z.44–61); `orderId`-Format `ord_*` (Z.37, 174–177, 226; pk-Doppelpräfix `ord_ord_…` bewusst repliziert, GATE-3 Z.65); Schema `pk/sk=#ORDER/gsi1pk=LIST/gsi1sk=createdAt/version` (Z.37–40); Integer-Preise ≥1 (Z.180–205); 400/404/409/500-Fehlercodes; HTTP-Form POST 201+PENDING / GET 200/404 / PATCH 200/409; **GET-Polling ist der einzige Handoff** (GATE-3 Z.109); kein serverseitiger Idempotency-Key, kein Tenant-Feld (GATE-6 Z.46,48).
7. **Dokumentierte Wiederverwendungs-Kandidaten aus MO-Sicht:** MO-Installer-CLI + Lifecycle (validate→plan→policy→approval→deploy; GATE-3 Z.45–47), Policy-Gate (RIS bindet es als Composite-Step „POLICY CHECK" ein, RIS-ORDERS-INSTALLER-CONTRACT-ALIGNMENT-01 Z.18–34), Preflight-Muster (MAYS-RIS-PARALLEL-INSTALLATION-PREFLIGHT-01 Z.288–294), MO-Naming-Contract als Bindungs-Mechanismus (ris.py Z.138–142, Kollisions-Guard Z.440–444), Pin-/Versionsierung (installer/mays-orders-clone.pinned.json, GATE-3 Z.7).

## Evidence / File References

- RIS: `agents/orders/adapter.py` Z.27–99; `agents/orders/real.py` Z.8–11, 34, 57–72, 99–103, 169–194; `agents/orders/function.py` Z.2–10, 30–32, 52–69; `agents/runtime/pipeline.py` Z.70–77, 92, 126
- RIS: `lambda/orders_reader.py` Z.2–14, 37–61, 68–77, 119–126, 132–300
- RIS: `terraform/modules/sqs/main.tf` Z.3–60; `terraform/modules/lambda/main.tf` Z.4, 147–168, 376–377, 429–433; `terraform/modules/orders_reader/main.tf` Z.11–143 (IAM Z.14–71, Routen Z.113–143); `terraform/variables.tf` Z.4, 15, 126, 255–324; `installer/ris.py` Z.138–142, 402–405, 440–461, 691–818
- RIS-Reports: `GATE-2-MO-INSTALLATION-RIS-HANDOFF-01.md` Z.22, 38, 54, 58; `GATE-3-MO-LIVE-INSTALLATION-AND-VERIFICATION-01.md` Z.7, 21–47, 61–70, 83–113, 116; `GATE-4-MO-DECIMAL-RESPONSE-FIX-AND-READ-E2E-01.md` Z.61; `GATE-6-ORDERS-PORT-REAL-MAYS-ORDERS-ADAPTER-01.md` Z.10, 27–48, 89; `RIS-ORDERS-INSTALLER-CONTRACT-ALIGNMENT-01.md` Z.18–36; `RIS-ORDERS-INSTALLER-CONTEXT-HANDOFF-01.md` Z.28–36

## Classification

**GREEN** — Verträge vollständig dokumentiert; RIS hängt NICHT an der MO-Handler-Policy-Form, sondern an Naming-Contract, Queue-Nachrichtenform, Statusmaschine, Schema und offener Queue-Policy. MO-seitige Modularisierung SQS-optional ist RIS-neutral (MO-API/Tabelle/Queue/Worker unverändert).

## Checks Actually Executed

Nur Leseoperationen: file reads, grep über Py/Terraform/Reports. Keine AWS-Calls, keine Schreibzugriffe.

## Git Status

RIS-Repo unverändert (Agent schreibt nichts; read-only bestätigt).

## Files Changed

**Keine — read-only.** (Bestätigt.)

## Open Questions

1. MO-Queue-Policy Principal `*` ist Teil des RIS-Live-Pfads — jede Einengung ist EINE Vertragsänderung mit RIS-Ablastung → NIEMALS ohne Freigabe des RIS-Teams ändern.
2. RIS erhält MO-Bindung via Naming-Contract-Ableitung (keine SQS-Outputs genutzt) — bei MO-Renaming-Mechanismen (falls künftig) muss der Naming-Contract stabil bleiben.
3. Contract-Befund „kein serverseitiger Idempotency-Key / kein Tenant-Feld" bleibt RIS-offen (GATE-6 Z.46–48) — kein MO-Auftrag dieses Checkpoints.

## Risks

- MO-seitige SQS-Modularisierung berührt RIS NICHT, solange: Statusmaschine, `ord_`-Format, Schema, Queue-Nachrichtenform `{orderId, status, metadata}`, Naming `{project}-orders-queue` und Queue-Send-Policy unverändert bleiben. STOP-Regel: Jegliche Änderung an diesen Vertragspunkten vorher freigeben.

## Recommended Next Actions

1. MO-Modularisierung (SQS optional für iam/lambda) ohne Berührung der Vertragspunkte umsetzen.
2. Vertragsinventar (dieser Report §Findings 6) als Abnahme-Referenz in das zukünftige MO-Modularisierungs-Report übernehmen.
3. Queue-Policy-Einengung als SEPARATEN, gemeinsam mit RIS zu fassenden Beschluss behandeln (Security-Finding, nicht Teil dieses Checkpoints).

## Current Resume Point

Research B abgeschlossen und in diesem Log nachgetragen. Verträge sind die Abnahme-Basis für Phase 2 (Modularisierung) — Umsetzung siehe MAYS-ORDERS-MODULARIZATION-01.
