# MO-RC4-P00 — ADR-008 / Implementation Contract Comparison

**Status:** RESOLVED / Q-10 APPROVED 2026-11-13
**Datum:** 2026-11-13
**Branch:** `release/rc4-integration`
**ADR:** `architecture/architecture-decisions.md` → ADR-008 (**ACCEPTED**)
**Contract:** `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`
**Scope:** Read-only Abgleich der Architekturentscheidung mit dem
P00-Implementierungsvertrag; C-01…C-07 wurden anschließend in ADR-008
eingearbeitet. Keine Produktimplementierung.

---

## 1. Ergebnis

**Kein harter Architekturkonflikt.** Die Zielrichtung von ADR-008 und dem
Implementierungsvertrag ist konsistent. Der Abgleich war die Grundlage für die
Q-10-Freigabe; die sieben Klarstellungen wurden am 2026-11-13 in ADR-008
eingearbeitet und die Auflösung ist unten dokumentiert.

- `ENV` bleibt Default.
- `AWS_MANAGED` verwendet Secrets Manager.
- `APP_MANAGED` verwendet externes Key-Material und HMAC-SHA256.
- Kein stiller Provider-Fallback.
- Keine Eigenbau-Chiffre.
- KMS/Secrets/DynamoDB/SQS bleiben getrennte Encryption-Ebenen.
- Rotation ist nicht automatisch aktiv.
- Retention/TTL ist kein synchroner Löschbeweis.
- Erweiterungen sind additiv und default-off.

Der Abgleich zeigte **Klarstellungsbedarf** vor der Q-10-Freigabe. Dieser Bedarf
ist mit der Einarbeitung von C-01…C-07 in ADR-008 geschlossen; Q-10 ist
**APPROVED**.

---

## 2. Bereits entschiedene Grundlage

| ID | Owner-Entscheidung | Datum | Auswirkung |
|---|---|---|---|
| Q-02 | Secrets Manager als AWS-MANAGED-Backend | 2026-11-13 | P00-C-Backend festgelegt |
| Q-08 | ARN/Name-Referenz + Laufzeit-Fetch; kein Klartext-Secret in Env | 2026-11-13 | P00-B/C-Konfigurationsrichtung festgelegt |
| Q-10 | ADR-008 nach Einarbeitung C-01…C-07 | 2026-11-13 | ADR-008 `ACCEPTED`; P00-B ready for authorization |

Diese Freigaben autorisieren **keine Implementierung**. P00-B ist für eine
separate Paketfreigabe bereit; P00-C/D/E/G bleiben separat gated.

---

## 3. Entscheidungsabgleich

> Bewertung zum Zeitpunkt des Abgleichs. Die Auflösung der offenen Punkte ist
> in Abschnitt 5 dokumentiert.

| ADR-008 | Vertrag | Bewertung | Klärungsbedarf |
|---|---|---|---|
| **D-1** Bestehende Nutzer-/Bestellverträge, keine neuen Pflichtfelder | §2 Invarianten; §10 Retention; Q-05 optional | **KONSISTENT** | Keine Pflichtfeld-Änderung; Q-05 bleibt separat offen |
| **D-2** Orphan Detection fail-closed, keine Löschung bei unprüfbarer Zuordnung | §10 Retention | **LÜCKE, KEIN KONFLIKT** | Vertrag enthält keine explizite Orphan-Detection-Spezifikation; P00-G/Q-14 müssen sie aufnehmen |
| **D-3** Cleanup dry-run/idempotent; TTL nur Beschleuniger | §10 Retention | **KONSISTENT** | Keine synchrone Löschzusage |
| **D-4** MO-Mechanik, Consumer entscheidet Fristen | §10; Q-06/Q-14 | **KONSISTENT** | Rechtliche Fristen bleiben offen |
| **D-5** Secrets Manager; Env nur `PRIVACY_SECRET_ID` und `PRIVACY_SECRET_PROVIDER`; IAM nur `GetSecretValue`; kein Fallback | §3.3, §6 | **TEILWEISE KONSISTENT** | Vertrag erlaubt zusätzlich optional `PRIVACY_KMS_KEY_ARN` und `kms:Decrypt` bei CMK; ADR-Wortlaut „nur“ muss präzisiert werden |
| **D-6** APP_MANAGED: 32-Byte-Base64, HMAC-SHA256, `compare_digest`, keine Eigenbau-Chiffre | §7 | **KONSISTENT** | Keine Kryptoänderung; APP_MANAGED bleibt Phase 2 |
| **D-7** Geführte Rotation später; keine Rotation in RC4 | §5 Rotation; Q-11 | **PRÄZISIERUNGSBEDARF** | „Keine Rotation in RC4“ kann als Verbot der dokumentierten manuellen Rotation gelesen werden; gemeint ist kein automatischer Rotator. Q-11 muss das bestätigen |
| **D-8** Additiv/default-off; RC3-Defaults plan-identisch; gleiche Modul-Inputs/Outputs | §2, §9 | **TEILWEISE KONSISTENT** | Neue optionale Modul-/Root-Variablen können plan-identisch sein, verändern aber die Input-Fläche; „gleiche Inputs/Outputs“ muss auf den bestehenden `orders-service`-Vertrag präzisiert werden |

---

## 4. Governance- und Traceability-Befunde

### G-01 — Legacy-Fragestellungen in ADR-008

ADR-008 verwendet im Abschnitt „Offen“ noch die alten P01-Frage-Nummern. Diese
sind nicht deckungsgleich mit dem P00-Decision-Register:

| ADR-008-Bezug | Bedeutung dort | P00-Register |
|---|---|---|
| Q-01 | subjectId aus JWT | Q-01 = RC3-Tag/Baseline |
| Q-13 | APP_MANAGED-Krypto | Q-13 = AWS-Testkonto |
| Q-19 | Freigabe der Dienste | Q-10 = ADR-008-Freigabe |
| Q-06 | RIS-Abstimmung | Q-06 = Retention-Fristen |

**Folge (historisch):** Q-10 sollte erst freigegeben werden, wenn die ADR-Nummern
auf das P00-Register abgebildet oder als historische P01-Nummern gekennzeichnet
sind. Sonst ist die Entscheidungsgrundlage nicht eindeutig auditierbar.

**Auflösung:** ADR-008 enthält jetzt die Tabelle „Historische P01-Fragen →
P00-Zuordnung“; die historischen Nummern werden nicht als offene P00-Fragen
verwendet.

### G-02 — ADR-006-Status

ADR-006 („keine zusätzlichen Services“) ist **ACCEPTED** und bleibt für alle
übrigen Services gültig. ADR-008 ist die neue Architecture Decision für Secrets
Manager und KMS; ADR-006 wird **nicht** als überholt markiert und es gibt keine
pauschale Freigabe weiterer Services.

**Auflösung:** Q-10 bestätigt diese explizite, eng begrenzte Behandlung. Der
ADR-006-Status wurde nicht eigenmächtig verändert.

### G-03 — ADR-Status

ADR-008 ist seit der Q-10-Freigabe **ACCEPTED**. Der Implementierungsvertrag
bleibt **DRAFTED**; Q-02/Q-08/Q-10 autorisieren keine Implementierung. Die
Freigaben legen Backend, Referenz-/Fetch-Richtung und die Architekturgrundlage
fest; die übrigen P00-Fragen bleiben offen.

---

## 5. Erforderliche Klarstellungen vor Q-10

| ID | Klarstellung | Betroffene Stelle | Owner-Aktion |
|---|---|---|---|
| C-01 | P01-Frage-Nummern in ADR-008 auf P00-Register abbilden oder historisch markieren | ADR-008 „Offen“, G-01 | Q-10 |
| C-02 | D-5-Wortlaut „Env enthält nur …“ um optionale `PRIVACY_KMS_KEY_ARN`-Referenz ergänzen; weiterhin kein Secretwert | ADR-008 D-5; Contract §3.3/§6 | Q-10 |
| C-03 | IAM-Aussage präzisieren: `GetSecretValue` immer; `kms:Decrypt` nur bei explizit aktivierter CMK auf exaktem ARN | ADR-008 D-5; Contract §6 | Q-10 |
| C-04 | D-7 präzisieren: kein automatischer Rotator in RC4; manuelle/dokumentierte Rotation bleibt gemäß Q-11 möglich | ADR-008 D-7; Contract §5 | Q-10 + Q-11 |
| C-05 | D-8 präzisieren: `orders-service`-Vertrag bleibt unverändert; gehärtete Module nur über separates Preset; neue optionale Variablen dürfen den Default-Plan nicht verändern | ADR-008 D-8; Contract §9 | Q-10 + Q-03 |
| C-06 | ADR-006-Status/„überholt“-Vermerk ausdrücklich beschließen | ADR-008 Konsequenzen; ADR-006 | Q-10 |
| C-07 | Orphan-Detection aus D-2 in P00-G aufnehmen oder ausdrücklich als separaten Auftrag abgrenzen | ADR-008 D-2; Contract §10 | Q-10/Q-14 |

`C-04` und `C-05` berühren auch Q-11 bzw. Q-03. Sie sind keine stillen
Vorentscheidungen; die jeweiligen Fragen bleiben separat. `C-04` bestätigt
ausdrücklich nur „kein automatischer Rotator“, nicht den Q-11-Umfang.

### Auflösung C-01…C-07

| ID | Status | Nachweis in ADR-008 |
|---|---|---|
| C-01 | **EINGEARBEITET** | Tabelle „Historische P01-Fragen → P00-Zuordnung“; keine alten IDs als offene P00-Fragen |
| C-02 | **EINGEARBEITET** | D-5: optionale `PRIVACY_KMS_KEY_ARN`-Referenz, kein Secret-Wert |
| C-03 | **EINGEARBEITET** | D-5: exakte ARNs, kein Wildcard, `kms:Decrypt` nur bei CMK |
| C-04 | **EINGEARBEITET** | D-7: kein Auto-Rotator, dokumentierte manuelle Rotation, Q-11 offen |
| C-05 | **EINGEARBEITET** | D-8: `orders-service` unverändert, gehärtete Module separat, Q-03 offen |
| C-06 | **EINGEARBEITET** | ADR-006 bleibt `ACCEPTED`; ADR-008 ist die neue ADR nur für Secrets Manager/KMS |
| C-07 | **EINGEARBEITET** | D-2: P00-G spezifiziert Detection/Fail-closed; keine automatische Löschung/Backfill/RIS |

---

## 6. Bewertung

```text
ADR-008 vs. P00 Implementation Contract
────────────────────────────────────────
Architekturrichtung:       KONSISTENT
Harte Konflikte:           KEINE
Klarstellungen:            7 (C-01…C-07) — EINGEARBEITET
Governance-Offenpunkte:    GESCHLOSSEN (G-01/G-02)
ADR-008-Status:            ACCEPTED
Q-10-Status:               APPROVED 2026-11-13
P00-B:                     READY FOR AUTHORIZATION
Implementierungsstart:     NICHT AUTORISIERT
```

Q-10 ist auf Basis der vollständigen Einarbeitung freigegeben. P00-B ist für
eine separate Paketfreigabe bereit; die Implementierung selbst ist nicht
autorisiert.

---

## 7. Nicht Teil dieses Abgleichs

- Keine Produkt-/Terraform-/AWS-Änderung.
- Keine Implementierung von P00-B bis P00-I.
- Keine Freigabe von Q-03/Q-04/Q-05/Q-06/Q-07/Q-09/Q-11/Q-12/Q-13/Q-14.
- Kein Push, Merge, Tag oder Deployment.
