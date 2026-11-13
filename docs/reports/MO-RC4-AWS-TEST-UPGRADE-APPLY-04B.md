# MO-RC4-AWS-TEST-UPGRADE-APPLY-04B

**Kontrollierter RC4-Test-Apply — Pre-Op und Apply-Versuch**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-aws-test-upgrade-apply-04` @ `53bc5d9`
**Plan-Code:** `ffbebe9`
**Modus:** Pre-Op read-only + genau ein Apply-Versuch des freigegebenen Plans.
**Ergebnis:** **kein Apply ausgeführt** — Precondition Blocker.

```text
RC4 TEST APPLY BLOCKED — PRECONDITION FAILED
```

---

## 1. Operationsfreigabe

Der Operator erteilte `MO-RC4-AWS-TEST-UPGRADE-APPLY-04B` für genau den Plan
`8fe8facf39966afba26ff85f16e13631fa8295bf0cb7473f2b8d08e03883b49c`.
Kein anderer Plan, Workspace, Account oder Produktionssystem war freigegeben.

---

## 2. Git und AWS

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-aws-test-upgrade-apply-04` |
| HEAD | `53bc5d9` |
| Plan-Code-Pin | `ffbebe9` |
| AWS-Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| Workspace | `mays-orders-rc4-test` |

---

## 3. State-Baseline vor Apply

| Feld | Wert |
|---|---|
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Serial | `4` |
| Managed Resources | 37 |
| Fingerprint | `670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a` |
| Fingerprint-Version | `canonical-sha256-v1` |
| `mo_version` | `0.1.0` |

---

## 4. Plan / Manifest / Backup

| Feld | Wert |
|---|---|
| Plan-SHA-256 | `8fe8facf39966afba26ff85f16e13631fa8295bf0cb7473f2b8d08e03883b49c` |
| Manifest-SHA-256 | `64371e6d6a8307a84a4f91e4101567f95c2bc9c3587d645212608b37ce56ab32` |
| Planaktionen | 2 CREATE, 7 UPDATE, 0 DELETE, 0 REPLACE, 1 READ |
| Backup-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092` |
| Backup-Status | AVAILABLE |
| PITR | ENABLED |
| Evidence-SHA-256 | `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94` |
| P3A-Gate | VERIFIED |

P1 bleibt `REVIEW_REQUIRED`; die sieben Änderungen und zwei Nachkontrollen
wurden gemäß Pre-Op-Bericht akzeptiert.

---

## 5. Apply-Versuche

### Versuch 1 — aus Branch HEAD `53bc5d9`

```text
ALLOW_AWS_OPERATIONS=true Mays-Order-AWS-installer ... --accept-upgrade-review \
  deploy --plan <approved plan> --yes
```

Ergebnis vor jedem Apply:

```text
Upgrade version binding: BLOCKED (UPGRADE_VERSION_BINDING_MISMATCH)
Quellcode-Commit 53bc5d9... weicht vom Plan (ffbebe9...) ab
```

Grund: Der Plan wurde mit `ffbebe9` erstellt; `53bc5d9` ist der spätere
Dokumentations-Commit. **Kein Apply.**

### Versuch 2 — aus isoliertem Worktree bei `ffbebe9`

Der Plan-Code-Worktree wurde auf `ffbebe9` ausgecheckt, `terraform init` und
`terraform workspace select mays-orders-rc4-test` ausgeführt (read-only
Workspace-Auswahl), danach derselbe Plan erneut deployt.

Ergebnis vor jedem Apply:

```text
Version binding: OK (target=0.2.0, source=0.1.0, commit=ffbebe9...)
State baseline: OK (serial=4)
Upgrade backup gate: VERIFIED
Upgrade readiness: COMPATIBLE
Upgrade safety: PASS
Plan validation failed: Plan deployment ID mismatch:
expected 240571105849:mays-orders-rc4-test:rc4-test
got      240571105849:mays-orders-rc4-test-rc4:test
ERROR: --yes cannot bypass deployment identity mismatch.
```

**Kein Apply.**

---

## 6. Root Cause des Blockers

`PlanMetadata.parse_filename` (`installer/core/deployment_identity.py`)
zerlegt den Dateinamen ausschließlich an `-`:

```text
<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>
```

Das Environment `rc4-test` enthält selbst einen Bindestrich. Der Parser liest
dadurch `rc4` als Teil des Projekts und `test` als Environment; die erwartete
Deployment-ID `...:rc4-test` stimmt nicht mit der geparsten `...:rc4:test`
überein.

Der Plan selbst, das Manifest und die Terraform-Konfiguration sind korrekt; der
Blocker liegt im Dateinamen-/Deployment-ID-Parser.

**Keine Umgehung:** Es wurde kein direkter `terraform apply`, keine
Manifest-Manipulation, kein neuer Plan und keine Umbenennung des Planartefakts
verwendet.

---

## 7. Tatsächliche Änderungen

**Keine.** Es wurde kein Terraform Apply ausgeführt.

| Prüfung nach den Versuchen | Wert |
|---|---|
| State-Serial | `4` (unverändert) |
| State-Lineage | unverändert |
| Managed Resources | 37 |
| DynamoDB GSIs | GSI1, GSI2 — **kein GSI3** |
| Tabelle | ACTIVE, 0 Items |
| Backup | AVAILABLE |
| `mo_version` | `0.1.0` |

Keine AWS-Ressource geändert, kein Backup, kein Destroy, keine RIS-Änderung.

---

## 8. Postoperative Diagnose

**Nicht ausgeführt**, da kein Apply erfolgte.

---

## 9. Offene Punkte

1. `PlanMetadata` muss hyphenierte Environments korrekt parsen können
   (z. B. Environment aus dem Manifest/Deployment-Kontext statt aus dem
   Dateinamen ableiten).
2. Alternativ muss die Environment-Namenskonvention ohne Bindestrich
   entschieden und ein **neuer** Plan erstellt werden.
3. Danach neue Pre-Op-Prüfung und neue Apply-Freigabe für den neuen Plan-Hash.
4. Keine automatische Reparatur, kein direkter Terraform-Apply.

---

## 10. Nächster Schritt

**Contract-/Code-Entscheidung:** Hyphen-Environment-Parsing korrigieren oder
Environment-Namensschema ändern. Anschließend neuen Plan erstellen und separat
freigeben.

Bericht: `docs/reports/MO-RC4-AWS-TEST-UPGRADE-APPLY-04B.md`

**Kein Apply, keine AWS-Mutation, kein Backup, kein Push/Merge. STOP.**
