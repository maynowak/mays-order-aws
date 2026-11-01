# MO-RC4-P02B-INTERNAL-IDENTITY-CONTRACT

**Interner Identitätsvertrag (Consumer / Owner / Actor / Verification Context)**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `a5cc3ec` (P02A)
**Typ:** additive interne Erweiterung, keine öffentliche API-Änderung

---

## 1. Umsetzung

| Datei | Erweiterung |
|---|---|
| `lambda/src/identity.py` | `verification_context` in `OrderIdentity`; `InternalOrderIdentity`; `resolve_internal_order_identity()`; Privacy-Scope-Helfer; Klassifikation erkennt inkonsistente Bindungen |
| `lambda/src/order_service.py` | optionaler Consumer-Scope in `inspect/export/erase`; `consumerId` in Erase-Kandidaten |
| `lambda/tests/test_identity.py` | +13 Tests (interne Auflösung, Scope, Verifikationskontext) |
| `lambda/tests/test_order_service.py` | +6 Tests (Scope in Privacy-Funktionen, Statusupdate berührt Identity nicht) |

## 2. Vertragsmodell

```text
InternalOrderIdentity (implementiert, intern)
├── consumerId            verifiziert (iss + client_id/aud)
├── ownerType             user  (agent/service: NICHT aktiviert)
├── ownerId               JWT sub
├── actorType             user
├── actorId               JWT sub
├── identityVersion       1
└── verificationContext   verified_jwt   (einziger zulässiger Wert)
```

Persistiert werden zusätzlich zu P02A: **`identityVerification`**.

### 2.1 Verbindliche Regeln (im Code erzwungen)

| Regel | Umsetzung | Test |
|---|---|---|
| Bindung nur mit verifiziertem Kontext | `OrderIdentity.__post_init__` lehnt `verificationContext ∉ {verified_jwt}` ab | `test_identity_rejects_unverified_verification_context` |
| Interne Auflösung ohne verifizierten Kontext → BLOCKED | `resolve_internal_order_identity` wirft `VALIDATION_ERROR` | `test_unverified_or_missing_context_is_blocked` |
| `order`-Daten sind keine Identitätsquelle | Parameter wird bewusst ignoriert | `test_order_data_is_never_an_identity_source` |
| Owner ≠ Actor nur mit signiertem Kontext | explizite Ablehnung | `test_owner_actor_separation_requires_signed_context` |
| Agent/Service als Owner nicht aktiviert | Ablehnung | `test_non_user_owner_types_are_not_enabled` |
| Manipulierte Komponenten | leer/zu lang/Steuerzeichen/Nicht-String → Fehler | `test_manipulated_components_are_rejected` |
| Wiederholte Auflösung stabil | identischer kanonischer Schlüssel | `test_repeated_resolution_is_stable` |

### 2.2 Nur entworfen, **nicht** implementiert

| Element | Status | Grund |
|---|---|---|
| `verificationContext = verified_internal_signed` | **BLOCKED** | kein signierter interner Vertrag (Format, Aussteller, Gültigkeit, Audience) definiert |
| Agent als Owner | **BLOCKED** | Owner-Typ nicht freigegeben (V-6) |
| Service als Owner | **BLOCKED** | dito |
| Owner ≠ Actor | **BLOCKED** | setzt signierten Delegationsnachweis voraus (V-1) |
| Interne HTTP-/Invoke-Route für Consumer-Bestellungen | **nicht vorhanden** | keine neue öffentliche API erlaubt; interner Pfad müsste erst definiert werden |

**Kernaussage:** Der Vertrag ist **definiert und strukturell durchgesetzt**, aber die
einzige heute nutzbare Verifikation ist `verified_jwt`. Alles darüber hinaus ist
**BLOCKED**, nicht „vorbereitet“.

## 3. Vertrauensgrenzen (unverändert gültig)

| Pfad | Wer prüft die Identität? | Wer kann sie durchsetzen? |
|---|---|---|
| MO-API (`POST /orders`) | MO (API Gateway JWT + `identity.py`) | **MO** — erzwungen |
| MO-API ohne Claims | — | MO lehnt ab (401) |
| Direkter DynamoDB-Schreibzugriff (RIS) | **RIS** (nichts) | **MO kann nichts erzwingen** |
| Interne Lambda-Invoke | IAM (`lambda:InvokeFunction`) | MO nur, wenn der Aufrufer einen verifizierten Kontext mitbringt (heute: keiner) |

**Wichtig:** Eine neue Python-Routine in MO schützt den RIS-Direktschreibpfad **nicht**.
Technische Schreibberechtigung (`dynamodb:PutItem`) ist **keine** Eigentümerbindung.

## 4. Kollisionsprävention

Unverändert aus P02A: kanonischer Schlüssel
`v1|<len>:<consumerId>|<ownerType>|<len>:<ownerId>` mit Längenpräfixen.

Ergänzung P02B: Der Verifikationskontext ist Teil der **Klassifikation**, nicht des
Schlüssels (ein Wechsel des Kontexts darf keine neue Identität erzeugen). Eine Bindung
ohne `identityVerification` wird als **`inconsistent_binding`** klassifiziert und **nicht**
als verifiziert behandelt (`test_binding_without_verification_context_is_inconsistent`).

## 5. Auswirkungen auf bestehende Verträge

| Vertrag | Auswirkung |
|---|---|
| `POST /orders` (Body/Response) | **keine** Änderung |
| Fehlercodes | unverändert (401/400 bereits dokumentiert) |
| `subjectId` / GSI2 | **unverändert** |
| Privacy-Funktionen | Erweiterung **nur** um optionalen Consumer-Scope (siehe Privacy-Isolation) |
| DynamoDB-Schema | nur additive Attribute (`identityVerification`) |
| Modul-Inputs/-Outputs (6/20) | **unverändert** |

## 6. Tests

| Suite | Ergebnis |
|---|---|
| Identity-Unit | 31/31 PASS |
| Lambda gesamt | **139/139 PASS** |
| Builder | 90/90 PASS |
| Installer | 81/81 PASS |

## 7. Risiken

| Risiko | Bewertung |
|---|---|
| Vertrag wirkt „fertig“, obwohl nur JWT nutzbar ist | dokumentiert; BLOCKED-Zustände sind getestet |
| Persistiertes `identityVerification` könnte künftig erweitert werden | Klassifikation prüft gegen `VERIFIED_CONTEXTS` |
| RIS-Direktschreiben umgeht alles | **offen** (siehe RIS-Compatibility) |
| Legacy-Items ohne Verifikation | werden nie als verifiziert gemeldet |

## 8. Akzeptanzkriterien

- [x] Owner/Actor/Consumer getrennt und im Code erzwungen.
- [x] Keine Bindung ohne verifizierten Kontext.
- [x] Keine Ersatzidentität, keine Übernahme aus Bestelldaten.
- [x] Keine öffentliche API-Änderung, keine neue Tabelle/GSI, keine AWS-Operation.
- [x] BLOCKED-Bereiche ausdrücklich benannt (nicht als implementiert dargestellt).
