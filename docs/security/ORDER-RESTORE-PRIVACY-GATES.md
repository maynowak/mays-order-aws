# Order-Restore-Privacy-Gates (P3E-01)

**Status:** Vertragsentwurf + lokaler Planner. **Keine P1-Gates verändert, keine
produktive Freigabe.** RC4-Entscheidung: `POST_RC4` — Restore/Cutover bleiben bis zu
einer separaten Freigabe gesperrt.

---

## 1. Vertrag `OrderRestorePrivacyReadinessV1`

```json
{
  "schemaVersion": 1,
  "status": "REVIEW_REQUIRED",
  "planStatus": "PLAN_VERIFIED",
  "executionStatus": "EXECUTION_NOT_VERIFIED",
  "cutoverStatus": "CUTOVER_BLOCKED",
  "cutoverApproved": false,
  "dataMigrationRequired": true,
  "backupEvidence": "NOT_PROVIDED",
  "restorePrivacyReadiness": "REVIEW_REQUIRED",
  "blockers": [],
  "conflicts": [],
  "actions": [
    { "orderRef": "ord_…", "action": "DELETE", "consumerId": "cognito:…", "eventIds": ["evt-…"] }
  ]
}
```

Dies ist ein **Vertragsbeispiel**, kein Nachweis einer Sicherung oder Ausführung.

### Statuswerte

| Wert | Bedeutung |
|---|---|
| `VERIFIED` | **in P3E-01 nie** für Restore/Cutover; erst nach nachgewiesener Ausführung + Freigabe denkbar |
| `REVIEW_REQUIRED` | Plan vollständig, aber Ausführung/Prüfung durch Menschen offen |
| `BLOCKED` | fehlende/invalide Historie, Konflikt oder Identitätsproblem |
| `UNKNOWN` | keine belastbare Grundlage |

### Getrennte Statusachsen

- `planStatus`: `PLAN_VERIFIED` / `REVIEW_REQUIRED` / `BLOCKED` / `UNKNOWN`
- `executionStatus`: `EXECUTION_NOT_VERIFIED` (P3E-01 immer)
- `cutoverStatus`: `CUTOVER_BLOCKED` (P3E-01 immer)
- `cutoverApproved`: `false` (P3E-01 immer)

**Ein erfolgreicher Plan ist kein Nachweis einer erfolgreich durchgeführten
Bereinigung.**

---

## 2. Mindestbedingungen für einen positiven Status

1. Restore-Tabellenidentität geprüft (Name, ARN, Account, Region, Namenskonvention).
2. Restore-Zeitpunkt (`restoreAt`) bekannt und valide.
3. Ledger-Quelle eindeutig (`ledgerId`, `source`).
4. Erforderliche Historie vollständig (`completeHistory=true`, Abdeckung umfasst
   `restoreAt`).
5. Alle relevanten ERASE/ANONYMIZE/RETAIN-Entscheidungen berücksichtigt.
6. Keine offenen Konflikte (Scope, Subject, Operation, Chronologie).
7. Tatsächliche Reconciliation-Ausführung separat nachgewiesen — **nicht** durch
   P3E-01.
8. Datenschutzstatus des Zielbestands geprüft (keine PII bei ERASE, Anonymisierung
   vollständig).

In P3E-01 ist maximal `REVIEW_REQUIRED` erreichbar.

---

## 3. Fail-closed-Regeln

| Bedingung | Ergebnis |
|---|---|
| Ledger fehlt/unlesbar | `BLOCKED` |
| Unbekannte Schema-Version | `BLOCKED` |
| `completeHistory=false` oder Abdeckung fehlt | `BLOCKED` |
| Restore-Zeitpunkt fehlt/ungültig | `BLOCKED` |
| Restore-Identität/ARN/Account/Region falsch | `BLOCKED` |
| Consumer-Scope fehlt/abweichend | `BLOCKED` |
| Widersprüchliche Ereignisse | `BLOCKED` |
| `PARTIALLY_COMPLETED`/`FAILED` | `BLOCKED` (keine automatische Fortsetzung) |
| Fehlende Integrität/Manipulation | `BLOCKED` |
| Leere Restore-Menge/keine Aktionen | `REVIEW_REQUIRED`, nie automatisch `VERIFIED` |
| Cutover-Freigabe ohne Ausführungsnachweis | verweigert (`ORDER_RESTORE_CUTOVER_BLOCKED`) |

---

## 4. RETAIN

`RETAIN` ist **keine Löschung**. Der Planner erzeugt höchstens eine
`RETAIN`-Aktion (Information), niemals `DELETE`. Ein RETAIN-Ereignis hebt eine
frühere Löschung nicht automatisch auf; widersprüchliche Operationen blockieren.

---

## 5. Integration in P1 (nur Spezifikation)

Der bestehende Upgrade-Readiness-Vertrag kann später additiv erweitert werden:

```json
{
  "dataMigrationRequired": true,
  "backupEvidence": "VERIFIED",
  "restorePrivacyReadiness": "BLOCKED",
  "cutoverApproved": false
}
```

Regeln für die spätere Umsetzung:

- `restorePrivacyReadiness` stammt aus diesem Vertrag, nicht aus dem Plan allein.
- `backupEvidence` stammt aus P3A (`order-backup-evidence.json`), nicht aus einer
  Annahme.
- `cutoverApproved` bleibt `false`, solange `executionStatus != VERIFIED`.
- `--accept-upgrade-review` darf **niemals** `BLOCKED`/`MIGRATION_REQUIRED` oder
  fehlende Backup-/Privacy-Nachweise übergehen.
- Kein zweiter Terraform-Apply-Pfad; der Planner ist ein separater Schritt.

**In P3E-01 werden keine P1-Gates verändert.**

---

## 6. Grenzen

- Kein Restore, keine Datenänderung, kein Cutover.
- Keine Ledger-Persistenz.
- Keine Aussage über DSGVO-Konformität.
- Keine produktive Freigabe durch lokale Tests.
