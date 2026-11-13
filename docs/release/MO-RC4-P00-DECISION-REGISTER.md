# MO-RC4-P00 Decision Register

**Status:** Q-02 + Q-08 + Q-10 DECIDED / OTHER QUESTIONS PENDING
**Reference:** `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`
**RC4 Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Integration Branch:** `release/rc4-integration`
**Prepared:** 2026-11-13

> **Owner update 2026-11-13:** Q-02 (Secrets Manager), Q-08 (ARN/name
> reference + runtime fetch, no plaintext secret in Env) and Q-10 (ADR-008,
> after C-01…C-07) are approved. ADR-008 is `ACCEPTED`. No product
> implementation is authorized by these decisions; P00-B is ready for a
> separate package authorization.

> Recommendations are not approvals. Only the Release Owner may change an
> `OPEN`/`PROPOSED` item to `DECIDED`.

---

## 1. Decision Status Summary

| ID | Frage | Status | Blockiert |
|---|---|---|---|
| Q-01 | RC3-Tag / RC4-Baseline | **ALREADY_DECIDED** (Baseline only) | nichts mehr |
| Q-02 | Secret-Backend | **DECIDED — Secrets Manager** | P00-C (Entscheidung geschlossen) |
| Q-03 | Modulplatzierung | **READY_FOR_OWNER** | P00-H |
| Q-04 | CMK erzeugen/extern | **READY_FOR_OWNER** | P00-E |
| Q-05 | `tenantId` | **READY_FOR_OWNER** | P00-G |
| Q-06 | Retention-Fristen | **BLOCKED_BY_EXTERNAL_DECISION** | P00-G |
| Q-07 | Cancel-Anonymisierung | **READY_FOR_OWNER** | P00-G |
| Q-08 | Secret-Referenz/Fetch | **DECIDED — ARN/Name + Runtime-Fetch** | P00-B/C (Entscheidung geschlossen) |
| Q-09 | Policy-Gate-Erweiterung | **READY_FOR_OWNER** | P00-C/E/H |
| Q-10 | ADR-008-Freigabe | **DECIDED — ADR-008 ACCEPTED** | P00-B/C/E (Entscheidung geschlossen) |
| Q-11 | Rotation in RC4 | **READY_FOR_OWNER** | P00-D/F |
| Q-12 | Release-Label | **READY_FOR_OWNER** | Release-Gate |
| Q-13 | AWS-Testkonto | **READY_FOR_OWNER** | P00-I |
| Q-14 | Bestand ohne Retention | **READY_FOR_OWNER** | P00-G |

`ALREADY_DECIDED` for Q-01 covers **only** the RC4 integration baseline. It is
not an RC3 release approval and does not create a tag.

---

## 2. Q-02 — Secret Backend

| Field | Content |
|---|---|
| Existing evidence | `MO-RC4-P00-MODULE-PLAN.md` P-02; `P01-SECRET-PROVIDER-DESIGN.md`; ADR-008 D-5 |
| Options | (a) Secrets Manager, (b) SSM SecureString, (c) ENV only |
| Security impact | Secrets Manager supports controlled versions/rotation; SSM needs separate policy; ENV is plaintext and not a production secret store |
| Compatibility | Additive; default `env` remains |
| Recommendation | **Secrets Manager** (`secretsmanager`) |
| Owner decision | **APPROVED 2026-11-13 — Secrets Manager** |
| Packages | P00-C, P00-F |
| Owner gate | Q-02 (closed) |
| Status | **DECIDED** |

The decision fixes the backend. It does not authorize P00-C implementation,
Terraform, AWS access or secret creation.

---

## 3. Q-03 — Module Placement

| Field | Content |
|---|---|
| Existing evidence | P00 P-11; Q-03; Module Contract |
| Options | (a) complete only, (b) separate `orders-service-hardened`, (c) extend `orders-service` |
| Security impact | Separate preset prevents P00 defaults leaking into existing consumers |
| Compatibility | `orders-service` contract must remain unchanged |
| Recommendation | **separate `orders-service-hardened`**; `orders-service` unchanged |
| Packages | P00-H |
| Owner gate | Q-03 |

---

## 4. Q-04 — CMK Ownership

| Field | Content |
|---|---|
| Existing evidence | P00 P-04; Q-04; ADR-008 |
| Options | (a) create CMK, (b) external ARN only, (c) both (default create or external override) |
| Security impact | External ARN preserves BYOK/portability; creating a CMK increases control and lifecycle responsibility |
| Compatibility | Optional; default off; no automatic CMK |
| Recommendation | **both**: explicit external ARN supported; optional create only when enabled |
| Packages | P00-E |
| Owner gate | Q-04 |

---

## 5. Q-05 — `tenantId`

| Field | Content |
|---|---|
| Existing evidence | P00 P-08; Q-05; RC4 identity model |
| Options | (a) no tenantId, (b) optional null, (c) required |
| Security impact | A required field is a breaking contract; optional can support consumer isolation without changing existing items |
| Compatibility | Existing orders/API must remain valid |
| Recommendation | **optional, default null**; do not make required in RC4 |
| Packages | P00-G |
| Owner gate | Q-05 |

---

## 6. Q-06 — Retention Periods

| Field | Content |
|---|---|
| Existing evidence | P00 P-08/P-09; Q-06; `ORDER-ERASURE-RETENTION-DECISIONS.md` |
| Options | (a) 365/30 days, (b) configurable without default, (c) other legal values |
| Security impact | Wrong periods create compliance/data-loss risk; no period is legally approved |
| Compatibility | New fields must not alter existing data |
| Recommendation | Configurable mechanics first; **legal/owner must approve actual periods** |
| Packages | P00-G |
| Owner gate | Q-06 + legal/operational decision |
| Status | **BLOCKED_BY_EXTERNAL_DECISION** |

---

## 7. Q-07 — Cancel Semantics

| Field | Content |
|---|---|
| Existing evidence | P00 P-09; Q-07; state machine |
| Options | (a) always wait period, (b) immediate anonymize, (c) opt-in flag |
| Security impact | Immediate anonymization can destroy needed order evidence; waiting requires retention enforcement |
| Compatibility | Status transitions must not change |
| Recommendation | **opt-in flag**, default wait/no immediate anonymization |
| Packages | P00-G |
| Owner gate | Q-07 |

---

## 8. Q-08 — Secret Reference and Fetch

| Field | Content |
|---|---|
| Existing evidence | P00 P-01/P-02; Q-08; P01 design |
| Options | (a) ARN/reference in Env + runtime fetch, (b) plaintext Env, (c) both |
| Security impact | Runtime fetch avoids plaintext configuration; plaintext Env is not production-safe |
| Compatibility | Default ENV unchanged; new provider opt-in |
| Recommendation | **ARN/name reference + runtime fetch**, no plaintext Secret in Env |
| Owner decision | **APPROVED 2026-11-13 — Option (a)**, no plaintext secret in Env; contract configuration/validation surface applies |
| Packages | P00-B/C/H |
| Owner gate | Q-08 (closed) |
| Status | **DECIDED** |

The decision fixes reference/fetch semantics. It does not authorize P00-B
implementation; Q-10 was approved separately on 2026-11-13.

---

## 9. Q-09 — Policy-Gate Allowlist

| Field | Content |
|---|---|
| Existing evidence | P00 P-15; Q-09; `terraform/policy/` |
| Options | (a) extend with rules, (b) no KMS/Secrets, (c) project exceptions |
| Security impact | Gate extension can weaken controls if not exact; no extension blocks P00 IaC |
| Compatibility | Existing resource types/rules must remain |
| Recommendation | Extend with explicit KMS/Secrets types and rotation/least-privilege rules |
| Packages | P00-C/E/H |
| Owner gate | Q-09 |

---

## 10. Q-10 — ADR-008 Approval

| Field | Content |
|---|---|
| Existing evidence | ADR-008 (ACCEPTED), P00/P01 designs, `MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md`, `docs/reports/MO-RC4-P00-Q10-APPROVAL.md` |
| Options | (a) approve ADR-008 with documented clarifications, (b) revise ADR first, (c) reject |
| Security impact | KMS/Secrets service adoption needs a governance decision |
| Compatibility | No runtime change until implementation |
| Recommendation | **Approve ADR-008 with C-01…C-07**, then set ADR-008 to `ACCEPTED` |
| Packages | P00-B/C/E |
| Owner gate | Q-10 (closed) |
| Status | **DECIDED — ADR-008 ACCEPTED** |

The comparison found no hard architecture conflict. C-01…C-07 were fully
incorporated into ADR-008 on 2026-11-13; ADR-006 remains `ACCEPTED` without
implicit extension. Q-10 is approved, but P00-C/E and all other packages remain
separately gated.

---

## 11. Q-11 — Rotation Scope

| Field | Content |
|---|---|
| Existing evidence | P00 P-03; Q-11; P01 rotation phase |
| Options | (a) native rotation now, (b) manual rotation documented/native later, (c) discard |
| Security impact | Native rotation requires cache invalidation and failure handling; unsupported rotation risks auth outage |
| Compatibility | Rotation must be default-off; old/new version transition must be explicit |
| Recommendation | **manual rotation documented in RC4; native rotation later** |
| Packages | P00-D/F |
| Owner gate | Q-11 |

---

## 12. Q-12 — Release Label

| Field | Content |
|---|---|
| Existing evidence | Q-12; RC4 dossier; release history |
| Options | `v0.5.0-rc.4` vs. `v0.6.0-rc.1` |
| Security impact | None directly; release identity/communications |
| Compatibility | Release tag is separate from deployment version `0.2.0` |
| Recommendation | `v0.6.0-rc.1` only if P00 is a feature generation; `v0.5.0-rc.4` for limited order-core candidate |
| Packages | Release gate only |
| Owner gate | Q-12; can wait until release gate |

---

## 13. Q-13 — AWS Test Account

| Field | Content |
|---|---|
| Existing evidence | Q-13; P00-I |
| Options | (a) isolated test account/workspace, (b) existing RIS test account, (c) no AWS test |
| Security impact | Cross-project access and test identity risk; least privilege required |
| Compatibility | Only test infrastructure |
| Recommendation | isolated test account/workspace with explicit approval |
| Packages | P00-I |
| Owner gate | Q-13 |

---

## 14. Q-14 — Legacy Without Retention

| Field | Content |
|---|---|
| Existing evidence | Q-14; P02A Legacy; retention design |
| Options | (a) leave indefinitely + docs, (b) separate backfill, (c) set on first access |
| Security impact | Retroactive deletion without evidence is risky; unbounded retention is a privacy risk |
| Compatibility | Existing orders/API must remain valid |
| Recommendation | **separate, explicitly approved backfill**; no automatic mutation in RC4 |
| Packages | P00-G |
| Owner gate | Q-14 |

---

## 15. Joint vs. Individual Approval

### Can be approved together

- **Foundation bundle:** Q-02 + Q-08 + Q-10 (provider/backend/reference/ADR).
  All three are approved; P00-B is ready for separate authorization.
- **KMS bundle:** Q-04 + Q-09 (CMK ownership + gate rules).
- **Retention bundle:** Q-05 + Q-06 + Q-07 + Q-14 (data model, legal, semantics).
- **Later release bundle:** Q-03 + Q-11 + Q-13 (module, rotation scope, test account)
  may be approved later, before the corresponding packages.

### Must be individually explicit

- Q-06 requires legal/operational input separate from engineering.
- Q-10 is an ADR/governance decision.
- Q-12 is the release identity decision and may wait until release gate.
- Q-01 is already decided only for baseline; no tag is authorized.

---

## 16. Blocking and Non-Blocking

| Question | Blocks |
|---|---|
| Q-02 | P00-C (decision closed; remaining Q-04/Q-09/Q-10 still gate implementation) |
| Q-03 | P00-H |
| Q-04 | P00-E |
| Q-05 | P00-G |
| Q-06 | P00-G |
| Q-07 | P00-G |
| Q-08 | P00-B/C (decision closed; P00-B still gated by Q-10) |
| Q-09 | P00-C/E/H |
| Q-10 | P00-B/C/E (decision closed; P00-B ready for authorization, C/E still gated) |
| Q-11 | P00-D/F |
| Q-12 | Release-Gate only |
| Q-13 | P00-I only |
| Q-14 | P00-G |

No package may start until its listed decisions are closed.

---

## 17. Status

```text
Q-02 + Q-08 + Q-10 DECIDED / REMAINING QUESTIONS PENDING
```

Q-01 is baseline-decided. Q-02, Q-08 and Q-10 are owner-approved; ADR-008 is
`ACCEPTED`. Q-03…Q-07 and Q-09…Q-14 remain open/proposed. No product
implementation is authorized by this register; P00-B is ready for a separate
package authorization.
