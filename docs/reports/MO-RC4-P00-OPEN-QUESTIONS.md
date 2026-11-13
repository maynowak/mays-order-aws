# MO-RC4-P00-OPEN-QUESTIONS

**Offene Entscheidungen vor RC4-Implementierung**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Regel:** Keine Implementierung von P0-Items (Q-Abhängigkeiten), bevor die jeweilige
Frage entschieden ist. Empfehlungen sind Vorschläge, keine Beschlüsse.

| ID | Frage | Optionen | Empfehlung | Betroffen | Blockiert |
|---|---|---|---|---|---|
| **Q-01** | Wird der RC3-Tag `v0.5.0-rc.3` nachgezogen (auf `086a8be`)? | (a) Tag jetzt nachziehen, (b) RC3 ohne Tag weiterentwickeln, (c) RC3 verwerfen | **(a)** — der Stand ist geprüft, dokumentiert und released-fähig; ein fehlender Tag erschwert Rückverfolgbarkeit | Release-Governance | Release-Nummerierung |
| **Q-02** | Secret-Backend: AWS Secrets Manager oder SSM Parameter Store (SecureString)? | (a) Secrets Manager (Rotation, 0,40 $/Secret/Monat), (b) SSM SecureString (günstiger, keine native Rotation), (c) nur Env (Status quo) | **(a)** — Rotation ist RC4-Ziel; Kosten sind bei ≤ 3 Secrets vernachlässigbar | P-02, P-03 | P-02-Implementierung |
| **Q-03** | Wo werden die neuen Module angeboten? | (a) nur `complete` (default aus), (b) neues Preset `orders-service-hardened`, (c) zusätzlich im `orders-service`-Vertrag | **(b)** — Vertrag von `orders-service` bleibt stabil (RIS), Härtung als eigenes Preset | P-11, P-12 | Builder-Implementierung |
| **Q-04** | KMS-Key: pro Projekt erzeugen oder externen ARN durchreichen? | (a) nur erzeugen, (b) nur durchreichen (BYOK), (c) beides (Default erzeugen, ARN override) | **(c)** — Muster wie `lambda_execution_boundary` (Portabilität + Kontrolle) | P-04, P-10 | P-04-Implementierung |
| **Q-05** | Bekommt MO ein `tenantId`-Feld? | (a) nein — Retention nur pro Subject/Order, (b) optional (`null` erlaubt), (c) Pflichtfeld | **(b)** optional, Default `null` — RIS führt Tenant selbst; Pflichtfeld wäre ein Breaking Change am Modul/API | P-08, P-12 | P-08-Implementierung |
| **Q-06** | Rechtliche Retention-Fristen (Basis-Frist + Cancel-Frist)? | (a) 365 Tage / 30 Tage, (b) konfigurierbar ohne Default, (c) andere Werte | **(a)** als Default, vollständig konfigurierbar; Fristen müssen fachlich/rechtlich bestätigt werden | P-08, P-09 | P-08, P-09 |
| **Q-07** | Semantik bei `CANCELLED`: sofort anonymisieren, Frist abwarten oder optional? | (a) immer Frist, (b) sofort anonymisieren, (c) Opt-in-Flag | **(c)** Default „Frist abwarten" (`false`), Opt-in für sofortige Anonymisierung | P-09 | P-09 |
| **Q-08** | Secret-Zustellung an die Lambda: Env-Variable (ARN) oder Laufzeit-Fetch? | (a) nur ARN in Env + Fetch im Code (empfohlen), (b) Klartext in Env (Status quo), (c) beides | **(a)** — Env enthält nur ARN; Klartext wird nie in der Konfiguration sichtbar | P-01, P-02 | P-01 |
| **Q-09** | Muss die Policy-Gate-Allowlist erweitert werden und wer gibt das frei? | (a) ja, mit Regeln (Rotation, kein `Principal:"*"`), (b) nein (RC4 ohne KMS/Secrets), (c) Ausnahmen pro Projekt | **(a)** — sonst ist kein `apply` mit KMS/Secrets möglich; Freigabe als Governance-Entscheid dokumentieren | P-15 | P-02/P-04 |
| **Q-10** | Gilt Secrets Manager/KMS als „neuer AWS-Service" mit ADR-Pflicht (ADR-006)? | (a) ja, ADR-007 anlegen, (b) nein (Sicherheits-Härtung, kein Produktfeature) | **(a)** — formale ADR vermeidet Präzedenzfall-Lücken | Governance | P-02, P-04 |
| **Q-11** | Rotationsumfang: native Rotation (Rotator-Lambda) in RC4? | (a) ja, sofort, (b) nur manuelle Rotation dokumentiert, Rotator in RC5, (c) verwerfen | **(b)** — Storage + Provider in RC4, Rotator optional als P1 (P-03) | P-03 | P-03 |
| **Q-12** | Release-Bezeichnung: `v0.5.0-rc.4` oder `v0.6.0-rc.1`? | (a) `v0.5.0-rc.4` (Fortsetzung der Serie), (b) `v0.6.0-rc.1` (neue Feature-Generation: KMS/Retention) | **(b)** wenn KMS/Retention als Feature-Generation gilt; sonst **(a)**. Entscheidung vor P-14 | P-14 | Tag/Dossier |
| **Q-13** | AWS-Testkonto für RC4-E2E (KMS/Secrets sind konto-/policy-abhängig) | (a) RIS-Testkonto `262370457690` erneut, (b) neues, isoliertes Testkonto, (c) kein AWS-Test in RC4 | **(a)** mit frischem Workspace; KMS/Secrets brauchen zusätzliche IAM-Rechte im Testkonto | P-13, E2E | E2E-Gate |
| **Q-14** | Umgang mit Bestandsdaten ohne `retentionUntil` | (a) unbefristet belassen + Doku, (b) Backfill-Skript (separat, nicht RC4-Code), (c) Frist beim ersten Zugriff setzen | **(b)** als separater Auftrag; RC4-Code ändert Bestandsdaten nicht | P-08 | Datenmigration |

## Entscheidungsbedarf vor Implementierungsstart

**Blockierend (P0):** Q-01, Q-02, Q-04, Q-08, Q-09, Q-10
**Wichtig, aber nicht blockierend für P-01/P-15:** Q-03, Q-05, Q-06, Q-07, Q-11, Q-13, Q-14
**Spätestens vor Release:** Q-12

## Sicherheitsrelevante Klarstellungen

1. **Kein Klartext-Secret im Terraform-State.** RC4 verwendet `ephemeral`-Werte
   (Terraform ≥ 1.10, lokal 1.17) und `lifecycle.ignore_changes`; andernfalls muss
   die Entscheidung dokumentiert und kompensiert werden (State-Zugriff = Secret-Zugriff).
2. **Kein `Resource: "*"` für KMS.** KMS-Aktionen ausschließlich auf den Key-ARN.
3. **Fail-closed bleibt fail-closed.** Ein nicht abrufbares Secret darf die
   Privacy-Operation blockieren, nie erlauben.
4. **Keine AWS-Mutation in P00.** Alle Aussagen sind aus Code/Config abgeleitet.
