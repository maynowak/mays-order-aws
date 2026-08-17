# AI Tools & Learning Record — May's Orders

Dieses Dokument zeichnet auf, welche AI-Werkzeuge für **May's Orders** genutzt wurden und
was dabei gelernt wurde.

## 2026-08-17 — Woche 1 & Dokumentations-Transfer

**Tool:** DeepSeek V4 Flash Free (opencode)

**Work performed:**

- Woche-1-Analyse erstellt: Requirements, Order-Lifecycle mit Transition Matrix, API-Design,
  DynamoDB-Single-Table-Design mit GSI1, Auth-Entscheidung (Cognito, HTTP API, JWT-Flow),
  IAM-Least-Privilege-Design, ADR-001…007, Monitoring-/Reliability-/Cost-Konzept.
- Repo initialisiert, GitHub-Remote `maynowak/mays-order-aws` eingerichtet; Remote-„Initial
  commit" per `--allow-unrelated-histories` zusammengeführt.
- Dokumentations-Transfer nach Mays-Jobsearch-Muster: `docs/` mit Status, Portfolio,
  Changelog, AI-Kontextdokumenten, Feature-/Task-Dokumentation, Weekly-Reports.

**Lessons learned:**

- Unabhängige Git-Historien (lokal neu + Remote-Initial-Commit) erfordern
  `--allow-unrelated-histories`; Konflikte in README/.gitignore müssen bewusst zusammengeführt werden.
- Referenzdokumente dürfen als Muster dienen, Inhalte müssen aber fachlich zum Zielprojekt
  passen (kein 1:1-Kopieren von Job-Matcher-Inhalten).
- Status-Disziplin: Planungswerte (Kosten, Latenz) klar von Messungen trennen; zukünftige
  Phasen nie als abgeschlossen darstellen.
- Single Source of Truth: Fachentscheidungen nur in den Bereichsdokumenten pflegen;
  zentrale Statusdatei referenziert sie, statt zu duplizieren.

## Future record

Nach jeder relevanten AI-gestützten Session hier ergänzen.