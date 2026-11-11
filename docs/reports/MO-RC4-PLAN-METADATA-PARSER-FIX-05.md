# MO-RC4-PLAN-METADATA-PARSER-FIX-05

**Hyphenierte Projekt-/Environment-Namen im Plan-Metadata-Parser**

**Datum:** 2026-11-11
**Branch:** `fix/mo-rc4-plan-metadata-parser-fix-05` (ab `c38d191`)
**Modus:** lokale Implementierung/Tests; **keine AWS-Operation, kein Terraform
Plan/Apply/Destroy, kein State-Write, kein Backup, kein Push/Merge.**

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-aws-test-upgrade-apply-04` |
| Ausgangs-HEAD | `c38d191` |
| Arbeitsbranch | `fix/mo-rc4-plan-metadata-parser-fix-05` |
| Plan-Code-Pin | `ffbebe9` |
| Working Tree | CLEAN |

---

## 2. Root Cause

`PlanMetadata.parse_filename` zerlegte den Dateinamen ausschließlich an `-` und
nahm das Segment vor der Version als Environment. Bei `rc4-test` wurde daraus:

```text
Projekt:    mays-orders-rc4-test-rc4
Environment: test
```

Die erwartete Deployment-ID `240571105849:mays-orders-rc4-test:rc4-test` wurde
dadurch nicht erkannt. Der Fehler lag im Parser, nicht im Plan oder State.

---

## 3. Tatsächlicher Dateinamenvertrag

```text
<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan
```

Beispiel:

```text
mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0001.tfplan
```

Projekt und Environment dürfen Bindestriche enthalten. Ohne eine unabhängig
bekannte Projekt-/Environment-Identität ist der Name **nicht eindeutig**
zerlegbar.

---

## 4. Vertrauenswürdige Identitätsquellen

- **CLI-Deployment-Kontext**: Projekt, Environment und Account aus validierter
  AWS-/Installer-Konfiguration.
- **Plan-Manifest**: Deployment-ID wird gegen denselben Kontext geprüft.
- Der Dateiname liefert nur die festen Suffixfelder (Version, Phase, Account,
  Operation, Sequenz).
- Der Parser ohne erwartete Identität bleibt nur Legacy-/Anzeigefunktion und
  ist **keine** Sicherheitsautorität.

Damit entsteht keine Selbstbestätigung: Erwartete Identität und Dateiname sind
getrennte Quellen; der Dateiname wird gegen die erwartete Identität geprüft.

---

## 5. Implementierte Korrektur

`PlanMetadata.parse_filename(filename, *, expected_deployment_id=None)`:

- Mit erwarteter Deployment-ID wird zuerst der exakte Präfix
  `<project>-<environment>-` entfernt.
- Danach werden ausschließlich die fünf festen Suffixfelder geparst.
- Projekt und Environment mit Bindestrichen bleiben vollständig erhalten.
- Zusätzliche oder fehlende Segmente, ungültige Phase/Version/Operation/Account
  führen zu `None`.
- `PlanDiscovery.validate_plan_context` übergibt die erwartete Deployment-ID.
- `PlanDiscovery.find_plans` und `PlanSequenceManager` tun dasselbe.
- Die Deploy-/Destroy-Metadata-Prüfung in `installer/cli/main.py` übergibt die
  erwartete ID ebenfalls.
- Auch `plan_integrity.py` und die `--out`-Namensprüfung in `plan_contract.py`
  übergeben die erwartete ID.

Der alte Fallback ohne erwartete ID bleibt für bestehende nicht-ambige
Dateinamen erhalten; er wird nicht für Identitätsfreigaben verwendet.

---

## 6. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `installer/core/deployment_identity.py` | strikter Parser mit erwarteter ID; Discovery/Sequenz angepasst |
| `installer/cli/main.py` | Deploy/Destroy-Metadata-Prüfung mit erwarteter ID |
| `installer/core/plan_integrity.py` | Plan-Integritätsprüfung mit erwarteter ID |
| `installer/core/plan_contract.py` | `--out`-Namensprüfung mit erwarteter ID |
| `installer/tests/test_plan_metadata_parser.py` | 11 neue Parser-/Identitätstests |

Keine Terraform-Datei geändert.

---

## 7. Positive Tests

- `mays-orders-rc4-test` + `rc4-test` → korrekte Deployment-ID.
- Bekannter RC4-Plan-Dateiname validiert gegen den erwarteten Kontext.
- Weitere hyphenierte Projekt-/Environment-Kombinationen.
- Legacy-Dateiname mit `development` bleibt kompatibel.
- `PlanDiscovery.find_latest_plan` findet den hyphenierten Plan.
- Der historische RC4-Plan wird lokal gegen `240571105849:mays-orders-rc4-test:rc4-test` validiert: **PASS**.

---

## 8. Negative Tests

- Falscher AWS-Account → **BLOCKED**.
- Falscher Projektname → **BLOCKED**.
- Falsches Environment → **BLOCKED**.
- Ungültige Phase/Version/Operation → **BLOCKED**.
- Zusätzliches Dateinamen-Segment → **BLOCKED**.
- Ambiger Legacy-Parse ohne erwartete ID → weicht von der erwarteten ID ab;
  sicherheitsrelevante Aufrufer verwenden ausschließlich die erwartete ID.

---

## 9. Lokale Testergebnisse

| Lauf | Ergebnis |
|---|---|
| Installer gesamt | **621 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| Neue Parser-Tests | **11 PASS** |
| `python3 -m compileall installer` | PASS |
| `terraform fmt -check` | PASS |
| `terraform validate` | PASS |

Keine AWS-Mutation, kein Terraform-Plan/Apply.

---

## 10. Rückwärtskompatibilität

- Bestehende Dateinamen ohne hypheniertes Environment bleiben parsebar.
- `PlanMetadata.to_filename` bleibt unverändert.
- Die sichere Auflösung erfordert nun explizit die erwartete Deployment-ID;
  bestehende Aufrufer in Discovery/Sequenz/CLI wurden angepasst.
- Der alte Plan selbst wurde **nicht** verändert; seine Hashes bleiben
  historisch.

---

## 11. Sicherheitsgrenzen

- Der Dateiname allein ist keine Identitätsautorität.
- Manifest und CLI-Kontext werden weiterhin gegen die erwartete Identität
  geprüft; das Gate wurde nicht deaktiviert.
- Manifest/Evidence bleiben unsigniert (bestehende Vertrauensgrenze).
- Kein neuer Plan und keine Apply-Freigabe durch diesen Fix.

---

## 12. Offene Punkte

1. Der historische Plan `8fe8facf…` ist **nicht** automatisch wieder
   apply-fähig; er benötigt einen neuen Pre-Op/Apply-Freigabe-Lauf.
2. Ein neuer RC4-Testplan sollte mit dem korrigierten Parser erstellt werden,
   damit Dateiname, Manifest und Deployment-ID konsistent sind.
3. `REVIEW_REQUIRED` und die zwei post-apply Nachkontrollen bleiben bestehen.

---

## 13. Voraussetzungen für den neuen RC4-Testplan

1. Neuen Plan mit derselben RC3-Baseline und Evidence erstellen.
2. Neuen Plan-/Manifest-Hash dokumentieren.
3. P0A/P0C/P1/P3A erneut prüfen.
4. Präoperative Visite wiederholen.
5. Separate Apply-Freigabe für den neuen Hash.

## 14. Git-Commits

| Commit | Inhalt |
|---|---|
| `204a001` | Parser, Discovery/Sequenz, Deploy/Destroy-Metadaten |
| `f1f047f` | Plan-Integrität und `--out`-Namensprüfung |
| *(dieser Commit)* | Bericht, Auditlog |

**Status:**

```text
RC4 PLAN METADATA PARSER FIX VERIFIED — NEW TEST PLAN REQUIRED
```

Keine AWS-Operation, kein Terraform-Plan/Apply/Destroy, kein State-Write,
kein Backup, kein Push/Merge. **STOP.**
