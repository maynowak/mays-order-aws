# MO-RC4-P02A-INTEGRATION-GATES

**Gate-Matrix der Identitäts- und Consumer-Pfade**

**Datum:** 2026-11-01
**Basis:** P02A-Implementierung (`lambda/src/identity.py`)
**Lesart:** SUPPORTED = implementiert und getestet · DEGRADED = funktioniert, aber ohne
Owner-Zuordnung · BLOCKED = bewusst nicht implementiert (Vertrag fehlt) · UNCHANGED = nicht berührt.

---

## 1. Gate-Matrix

| # | Pfad / Consumer | Trust-Context | Owner | Actor | Status | Nachweis |
|---|---|---|---|---|---|---|
| G1 | **Benutzer über MO-API** (`POST /orders`, Cognito-JWT) | verifiziert (`sub`, `iss`, `client_id`/`aud`) | `user:<sub>` | `user:<sub>` | **SUPPORTED** | `TestOrderOwnership` (Handler), `TestIdentityPersistenceP02A` |
| G2 | MO-API ohne JWT-Claims (direkter Invoke, Fehlkonfiguration) | fehlt | — | — | **BLOCKED (401)** | `test_post_without_authorizer_is_rejected` |
| G3 | MO-API mit `sub`, aber ohne Consumer-Claims | unvollständig | — | — | **BLOCKED (401)** | `test_missing_consumer_identity_is_rejected` |
| G4 | MO-API mit Body-Identity (`subjectId`/`ownerId`) | unverifiziert | — | — | **BLOCKED (400)** | `test_body_cannot_smuggle_subject_id`, `test_body_subject_id_cannot_override_jwt` |
| G5 | **Agent handelt für Benutzer** (Delegation) | fehlt (kein signierter Kontext) | — | — | **BLOCKED (400)** | `test_delegated_resolution_is_blocked` |
| G6 | **Agent als Owner** | fehlt | — | — | **BLOCKED** | Modelltest `test_agent_can_act_for_user_without_becoming_owner` (nur Dataclass) |
| G7 | **Technischer Dienst als Owner** | fehlt | — | — | **BLOCKED** | Modelltest `test_service_owner_type_is_expressible_but_not_resolvable` |
| G8 | **RIS `orders_reader` Direktschreibung** | RIS-eigene Rolle, **keine** MO-API | — (kein `subjectId`) | — | **DEGRADED** | RIS-Code `orders_reader.py:244` + IAM (Get/Query/Update/Put) |
| G9 | RIS über RIS-eigene API (Endnutzer) | RIS-JWT, nicht MO | — | — | **UNCHANGED (außerhalb MO)** | P06/RIS-Research |
| G10 | Legacy-Bestellung mit `subjectId` | historisch verifiziert (P02-Vertrag) | `user:<subjectId>` | unbekannt | **DEGRADED (lesbar)** | `TestLegacyClassification::test_legacy_item_with_subject_only` |
| G11 | Legacy-Bestellung ohne `subjectId` | keine | — | — | **UNCHANGED (keine Zuordnung)** | `test_legacy_unowned_item_invents_nothing` |
| G12 | Privacy inspect/export/erase | interner Invoke + Secret | unverändert | — | **SUPPORTED** | `TestPrivacyConsistency` |
| G13 | Worker (`sqs_handler`) | SQS-Nachricht (keine Identität) | — | — | **UNCHANGED** | P01-Befund (Race offen, nicht P02A) |

## 2. Erforderliche Vertragsentscheidungen (nicht implementiert)

| ID | Entscheidung | Blockiert | Optionen |
|---|---|---|---|
| **V-1** | Delegationsvertrag für Agenten/Dienste: welches Format ist „verifiziert"? | G5, G6, G7 | (a) kurzlebiges, signiertes Owner-Assertion-Token (JWT mit `act`/`owner`), (b) MO-interne Service-Rolle mit expliziter Erlaubnisliste, (c) Umstellung auf Benutzer-JWT |
| **V-2** | Darf ein technischer Consumer `POST /orders` im Auftrag aufrufen? | G5 | (a) nein (nur Domänen-Benutzer), (b) ja mit V-1, (c) nur über separaten Endpunkt |
| **V-3** | Sollen RIS-Direktschreibungen einen Owner erhalten? | G8 | (a) nein (RIS bleibt eigentümerlos), (b) RIS setzt `subjectId` aus eigenem Tenant/Actor (Semantikfrage!), (c) RIS schreibt künftig über MO-API |
| **V-4** | Ist `consumerId` künftig Privacy-Filter? | G12 (nur künftig) | (a) nein (heute), (b) ja (dann GSI-Erweiterung nötig) |
| **V-5** | Sollen Legacy-Items mit `subjectId` ein `identityVersion=0`-Backfill erhalten? | G10 | (a) nein (nur Klassifikation), (b) Backfill (Migration, separat) |
| **V-6** | Bleibt `ownerType=user` die einzige zulässige Auflösung? | G1 | (a) ja bis V-1 entschieden, (b) Erweiterung |

**Regel:** Keine dieser Entscheidungen wurde vorweggenommen. Die Implementierung lehnt die
betroffenen Pfade **kontrolliert** ab (kein unsicherer Fallback).

## 3. Sicherheitsgates (geprüft)

| Gate | Ergebnis |
|---|---|
| Identität nur aus verifiziertem Kontext | ✅ |
| Keine implizite Berechtigung aus `consumerId`/`ownerId` | ✅ |
| Actor ≠ Owner ohne Vertrag | ✅ (blockiert) |
| Keine Ersatzidentität | ✅ |
| Kollisionsfreier Schlüssel | ✅ (Längenpräfixe, 4 Injektionsfälle getestet) |
| Bestehende Auth-Boundary der Privacy-Funktionen unverändert | ✅ |
| Keine Abschwächung bestehender Prüfungen | ✅ |
| Keine neuen AWS-Ressourcen / GSI-Änderungen | ✅ |

## 4. Regressionstests

| Suite | Ergebnis |
|---|---|
| Lambda (inkl. 27 neue P02A-Tests) | **120/120 PASS** |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `git diff --check` | clean |
| Secret-Audit | keine Treffer |

## 5. Konsequenz für die nächsten Phasen

1. **P-15 (Policy-Gate)** und **KMS/Secrets (P-02/P-04)** sind von P02A **nicht** blockiert.
2. **Retention/Orphan-Cleanup** muss die Klassifikation aus P02A verwenden
   (`legacy_unowned` niemals löschen) — das ist die Voraussetzung für P-08/P-09.
3. **RIS-Abstimmung** bleibt der kritische Pfad für jede Owner-Zuordnung
   außerhalb der MO-API (V-1/V-3).
