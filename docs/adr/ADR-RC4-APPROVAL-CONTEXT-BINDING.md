# ADR-RC4-APPROVAL-CONTEXT-BINDING

**Approval Context Binding für Installer-Mutationen**

**Status:** PROPOSED — NOT APPROVED

**Datum:** 2026-11-12

**Scope:** Deploy/Apply und Destroy des Mays-Orders-AWS-Installers

**Entscheidung:** ApprovalEvidence V2 als separates, plan- und
workspace-gebundenes Artefakt; keine Implementierung in 12A.

> Repository-Konvention: Die bestehenden ADRs liegen in
> `architecture/architecture-decisions.md` (ADR-001…008). Dieses Dokument ist
> ein separater, noch nicht freigegebener Vorschlag für die Approval-Bindung.

---

## Kontext

Die CLI prüft vor einer Mutation Plan-Manifest, Deployment-ID, Operation,
Workspace, Version, State-Baseline, Backup, Upgrade-Safety und Policy. Die
eigentliche Freigabe ist heute jedoch nur ein interaktiver Prompt oder
`--yes`; es gibt kein dauerhaftes, gebundenes Approval-Evidence-Objekt.
`ApprovalContext` wird von der CLI nicht verwendet. Eine Freigabe kann
daher nicht nachweisen, dass genau der ausgeführte Plan in genau dem
ausgewählten Workspace für genau diese Operation freigegeben wurde.

## Entscheidung

Ein separates **ApprovalEvidence V2**-Artefakt wird eingeführt. Es wird
unmittelbar vor `apply`/`destroy` gegen den tatsächlichen Ausführungskontext
geprüft. `--yes` bleibt ausschließlich eine Prompt-Unterdrückung und ist
keine eigenständige Evidence.

### Datenvertrag (Vorschlag)

```json
{
  "schemaVersion": 2,
  "approvalId": "apr_<opaque-unique-id>",
  "deploymentId": "<account>:<project>:<environment>",
  "operation": "APPLY",
  "workspace": "<canonical-workspace>",
  "planFingerprint": "sha256:<64-hex>",
  "planFormatVersion": "<optional>",
  "approvedAt": "<UTC timestamp>",
  "expiresAt": "<UTC timestamp>",
  "approvedBy": "<trusted-local-or-ci-identity>",
  "approvalMethod": "interactive|ci-approval|signed-evidence",
  "evidenceReference": "<immutable run reference>",
  "nonce": "<unique-nonce>",
  "signature": "<optional; requires a defined trust key>"
}
```

Pflichtfelder: `schemaVersion`, `approvalId`, `deploymentId`, `operation`,
`workspace`, `planFingerprint`, `approvedAt`, `expiresAt`, `approvedBy`,
`approvalMethod`, `evidenceReference`, `nonce`.

## Sicherheitsinvarianten

1. Deployment-ID muss exakt übereinstimmen.
2. Operation muss exakt übereinstimmen (APPLY ≠ DESTROY).
3. Workspace muss exakt übereinstimmen; leer/`default` ist unzulässig.
4. Plan-Fingerprint muss dem unmittelbar ausgeführten Plan entsprechen.
5. Fehlende, unbekannte oder unvollständige Bindungsdaten → DENY.
6. Abgelaufene/ungültige Evidence → DENY.
7. Planänderung nach Freigabe → DENY.
8. Evidence darf nicht unkontrolliert wiederverwendet werden
   (Approval-ID/Nonce/Verbrauch).
9. Verifikation erfolgt unmittelbar vor dem Runner-Aufruf.
10. Jeder Fehler in der Approval-Prüfung → DENY.

## Trust-Modell

- `--yes` = Prompt-Unterdrückung, keine Evidence.
- Operator-Prompt = lokale Zustimmung für die aktuelle Invocation.
- ApprovalEvidence = prüfbares Artefakt, abhängig von Herkunft und
  optionaler Signatur.
- Ohne definierten Trust-Key ist lokale Evidence integritäts-/zugriffsgeschützt,
  aber **nicht** kryptografisch nicht-abstreitbar.

## Migrationsentscheidung

- V2 ist für neue APPLY/DESTROY verpflichtend.
- V1/ungoverned/legacy Approval ohne Plan-/Workspace-Bindung → **DENY**;
  keine automatische Aufwertung.
- Bestehende Infrastruktur und lesende Operationen bleiben unverändert.
- `--yes` ohne V2-Evidence autorisiert keine Mutation.
- Rollback deaktiviert V2-Mutationen, fällt aber nicht auf ungebundene
  Freigaben zurück.

## Konsequenzen

Positiv: Plan-/Workspace-/Operationsbindung, Auditierbarkeit,
Replay-/TOCTOU-Schutz, klare Trennung von Consent und Evidence.

Negativ/Aufwand: neues Artefakt, CLI-Option/Kommando, Ablauf-/Replay-Speicher,
Trust-Key-Entscheidung, CI-Migration, zusätzliche Negativtests.

## Offene Entscheidungen

1. Signatur/Trust-Key oder nur lokale Integrität?
2. Darf `--yes` mit V2-Evidence den Prompt überspringen?
3. Ablaufdauer und Zeitquelle?
4. Wo wird Replay-Verbrauch atomar gespeichert?
5. Roher Plan vs. Plan-JSON als kanonischer Fingerprint?
6. Persistente vs. flüchtige interaktive Evidence?
7. CI-Migration von `--yes`?
8. Legacy-Destroy weiterhin zulässig, aber nur mit V2-Approval?
9. Evidence-Aufbewahrung und Zugriffsrechte?
10. Key-Owner/Rotation/Revocation, falls signiert?

## Nachtrag 12A-1 — Empfehlungen (weiterhin nicht genehmigt)

Die detaillierte Entscheidungsvorlage steht in
`docs/reports/MO-RC4-SECURITY-APPROVAL-DECISION-12A-1.md`.

Empfohlen, aber **nicht freigegeben**:

- **Trust:** lokal Modell A mit geschützter Evidence; CI Modell C; bei
  getrennten Hosts/externer Quelle Modell B (Signatur).
- **Vertrag:** separates `ApprovalEvidence`-V2-Artefakt, nicht in
  `ApprovalContext` integriert.
- **`--yes`:** ausschließlich Prompt-Unterdrückung; ohne gültige V2-Evidence
  für APPLY/DESTROY **DENY**.
- **Fingerprint:** SHA-256 über die rohen Bytes der ausgeführten binären
  Terraform-Plan-Datei; Plan-JSON nur ergänzend.
- **TOCTOU:** private, unveränderliche Ausführungskopie plus erneuter Hash
  unmittelbar vor Ausführung.
- **Ablauf:** 15 Minuten (konfigurierbar), UTC, ±60 s Clock-Skew.
- **Replay:** lokaler atomarer Verbrauch für lokale Läufe; zentraler Store
  für mehrere CI-Runner/externe Systeme. Lokaler Store ist kein globaler
  Schutz.
- **Legacy:** ungebundene Freigaben für Mutationen **DENY**, keine
  automatische Aufwertung.
- **Destroy:** eigene DESTROY-Evidence und eigener Plan-Fingerprint; keine
  APPLY-Übernahme.
- **Signatur:** für CI/multi-host/externe Approval-Quelle erforderlich oder
  durch gleichwertige authentifizierte Übertragung zu ersetzen; lokal nicht
  zwingend, dann keine Non-Repudiation-Behauptung.

Offene Entscheidungen: Trust-Key/Signatur, `--yes`-Semantik mit Evidence,
Ablaufdauer, Replay-Speicher, binärer vs. JSON-Fingerprint, persistente vs.
flüchtige interaktive Evidence, CI-Migration, Legacy-Destroy,
Evidence-Aufbewahrung und Key-Rotation.

## Status

**PROPOSED — NOT APPROVED.** Keine Implementierung, keine CLI-Änderung und
keine Freigabe von 12B ohne separate Entscheidung.
