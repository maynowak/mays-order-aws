# MO-RC4-P00-D-Q11-DECISION-02

**Status:** `A — READY`
`MO-RC4-P00-D — Q11 DECISION PACKAGE READY / OWNER APPROVAL PENDING`

**Projekt:** Mays-Orders-AWS · **Release:** RC4
**Datum:** 2026-11-14
**Branch:** `release/rc4-integration`
**HEAD:** `337aa4f1a58ce6765d58115d95c76f3fdb78322c`
**Modus:** Entscheidungsvorbereitung, keine Implementierung

**Freigabestatus der vorgeschlagenen Policy: PROPOSED — NICHT APPROVED.**

## 1. Git-/Governance-Basis

| Prüfung | Ergebnis |
|---|---|
| Git HEAD | `337aa4f1a58ce6765d58115d95c76f3fdb78322c` |
| Branch | `release/rc4-integration` |
| Working Tree | nur Dokumentation durch diese Aufgabe; Produktcode unverändert |
| ADR-008 | `ACCEPTED` (Q-10, 2026-11-13) |
| D-6/D-7/D-8 | gelesen; Q-11 bleibt separat offen |
| Contract §7 | gelesen |
| P00-D-Authorization-01 | gelesen |
| Decision Register Q-11 | `READY_FOR_OWNER`, nicht entschieden |

## 2. Vorgeschlagene Q-11-Policy

| Parameter | Vorschlag | Status |
|---|---|---|
| Aktive Schlüsselversion | genau eine | PROPOSED |
| Vorherige Version | höchstens eine | PROPOSED |
| Reguläres Übergangsfenster | maximal 24 Stunden | PROPOSED |
| Rotation | explizit durch Owner/Operator | PROPOSED |
| Automatische Rotation in P00-D | nicht erlaubt | PROPOSED |
| Kompromittierung | sofortiger Widerruf | PROPOSED |
| Unbekannte Key-Version | fail-closed | PROPOSED |
| Key-Löschung | Owner/Operator | PROPOSED |
| Key-Material | 32 Byte, Base64-kodiert | PROPOSED |
| Algorithmus | HMAC-SHA256 | PROPOSED |

Die Policy ist **kein** Ersatz für die separate P00-D-Implementierungsautorisierung.

## 3. Übereinstimmung mit bestehenden Verträgen

| Vertragspunkt | Befund |
|---|---|
| ADR-008 D-6: 32-Byte-Base64, HMAC-SHA256, keine Eigenbau-Chiffre | **KONSISTENT** |
| ADR-008 D-7: keine automatische Rotation in RC4, dokumentierte manuelle Rotation, Q-11 offen | **KONSISTENT** |
| ADR-008 D-8: additiv/default-off, RC3-Defaults plan-identisch, `orders-service` unverändert | **KONSISTENT** |
| Contract §7: `keyId` + `keyVersion`, fail-closed, keine Key-Werte in Logs | **KONSISTENT**, aber kanonische Payload nicht definiert |
| P00-D/P00-F-Abgrenzung | **KONSISTENT**: P00-F besitzt Rotation/Übergang/Widerruf/Cache-Recycle |
| Keine neue AWS-Abhängigkeit | **KONSISTENT** |
| Keine Cross-Provider-Fallbacks | **KONSISTENT** mit Contract §13 und vorhandener Provider-Isolation |

**Kein harter Vertragskonflikt festgestellt.** Es gibt jedoch offene Präzisierungen, die vor
einer Approval geschlossen werden müssen. Die Entscheidung ist daher nicht `APPROVED`.

## 4. Technischer Vertragscheck

| # | Prüfpunkt | Befund |
|---:|---|---|
| 1 | Eindeutige Nachrichtensemantik | **OFFEN** — die kanonische interne Payload ist nicht spezifiziert |
| 2 | Kanonische Darstellung der authentifizierten Daten | **OFFEN** — JSON-Reihenfolge, Encoding, Trennzeichen, Normalisierung nicht festgelegt |
| 3 | `keyId`/`keyVersion` kryptografisch gebunden | **OFFEN** — Contract nennt sie als Key-Identity, nicht als Bestandteil der HMAC-Payload |
| 4 | Exakte Base64-Dekodierung | **OFFEN** — Standard-/URL-safe-Alphabet, Padding, Whitespace nicht definiert |
| 5 | 32-Byte-Längenprüfung | im Vertrag gefordert; P00-D-Implementierung fehlt noch |
| 6 | Konstantzeitvergleich | im Vertrag gefordert; vorhandener Privacy-Pfad nutzt `compare_digest`-äquivalente Logik |
| 7 | Fail-closed | im Vertrag und im bestehenden APP_MANAGED-Boundary gefordert; `AppManagedProvider.resolve()` schließt aktuell absichtlich |
| 8 | Versionierte Verifikation | Vertraglich vorgesehen; P00-D-Implementierung fehlt |
| 9 | Keine Cross-Provider-Fallbacks | vorhandene Konfiguration lehnt gemischte Providerfelder ab |
| 10 | Keine Auswirkungen auf bestehende Orders | additiv/default-off gemäß D-8; keine Bestandsänderung vorgesehen |

Der aktuelle `AppManagedProvider` ist nur eine P00-B-Grenze: Er validiert Metadaten, löst aber
kein Key-Material auf und führt keine HMAC-Verifikation aus. Das ist kein Implementierungsnachweis
für P00-D.

## 5. Key-Kustodie

Der Vorschlag ist mit den Verträgen vereinbar:

- Erzeugung, Speicherung, Bereitstellung, Rotation, Widerruf und Löschung: Owner/Operator.
- Keine Key-Werte in Git, Terraform-State, Reports, Auditlogs oder Fehlermeldungen.
- Keine neue AWS-Abhängigkeit; APP_MANAGED ist kein KMS-Key.
- Runtime-Transport bleibt eine offene Owner-/Infrastrukturentscheidung.

**Offen:** konkreter externer Store/HSM, Loader-Vertrag, Injektionsweg, Berechtigungsmodell und
Nachweis, dass kein Key in Prozess-Env, Crash-Dumps oder Logs gelangt.

## 6. Konkrete Owner-Fragen

### Q11-O1 — Start des Übergangsfensters

Beginnt das 24-Stunden-Fenster bei Aktivierung der neuen Version, bei der ersten Verifikation
mit der neuen Version oder zu einem extern vorgegebenen Zeitpunkt? Der Start muss serverseitig,
explizit und nicht aus Request-Daten ableitbar sein. **Empfehlung:** separate
`transitionStart`/`transitionEnd`-Metadaten, keine Default-Dauer, fail-closed nach Ende.

### Q11-O2 — Sofortiger Widerruf und bestehende Signaturen

Was bedeutet „sofortiger Widerruf“ für bereits ausgestellte HMAC-Signaturen? Eine bereits
erzeugte Signatur kann nicht nachträglich ungültig werden, außer die Verifikation lehnt die
betroffene Version sofort ab oder die Daten werden neu signiert. **Owner-Entscheidung nötig:**
Version sofort sperren, Cache/Environment recyceln, bestehende Signaturen als kompromittiert
behandeln und einen Re-Signatur-/Migrationspfad festlegen.

### Q11-O3 — Kryptografische Bindung von `keyId` und `keyVersion`

Werden `keyId` und `keyVersion` in die kanonische HMAC-Payload aufgenommen? Ohne diese Bindung
ist ein Version-Downgrade nicht zuverlässig ausgeschlossen. **Empfehlung:** ja; kanonische
Payload mit explizitem Schema, Version und Key-ID; die serverseitige Auswahl darf nicht allein
aus einem nicht authentifizierten Header erfolgen.

### Q11-O4 — Base64- und Payload-Kanonisierung

Welches Base64-Alphabet, welche Padding-Regeln und welche JSON-Kanonisierung gelten? Der
Vertrag nennt 32 Byte und Base64, aber keine exakte Kodierung. **Empfehlung:** strikte
Standard-Base64-Dekodierung mit Validierung, exakt 32 Byte, keine Whitespaces, keine
URL-safe-Alternative ohne explizite Entscheidung; kanonische UTF-8-Payload mit definierter
Feldreihenfolge.

### Q11-O5 — Löschung alter Schlüssel

Dürfen Schlüssel gelöscht werden, solange noch gültige Signaturen oder Audit-Nachweise mit
dieser Version existieren? **Owner-Entscheidung nötig:** Mindestaufbewahrung, Verhältnis zu
Retention/Q-14 und Verhalten nach Löschung.

### Q11-O6 — P00-D/P00-F-Grenze

P00-D soll Key-Metadaten, HMAC und versionierte Verifikation liefern. Rotation, Übergangsfenster,
Widerruf, Cache-/Environment-Recycle und Löschung gehören zu P00-F. **Bestätigung nötig**, dass
P00-D keine versteckte Rotationslogik oder automatische Versionsauswahl enthält.

## 7. Entscheidungsblatt

| Feld | Inhalt |
|---|---|
| Vorgeschlagene Entscheidung | Q-11-Policy wie in Abschnitt 2, mit den Präzisierungen O1–O6 |
| Alternative 1 | Nur eine aktive Version, keine vorherige Version; Rotation erst nach separatem P00-F-Design |
| Alternative 2 | Zwei Versionen mit explizitem Start/Ende und versionierter Payload-Bindung; längere Übergangszeit nur per Owner-Freigabe |
| Alternative 3 | APP_MANAGED in RC4 zurückstellen und Q-11 erst mit P00-F entscheiden |
| Sicherheitsfolgen | Ohne Payload-Bindung und klaren Widerruf besteht Downgrade-/Replay-Risiko; ohne Key-Löschungsregel bleiben Alt-Signaturen prüfbar oder werden unerwartet unprüfbar |
| Auswirkungen P00-D | Implementiert Key-Metadaten, strikte Base64-/32-Byte-Prüfung, HMAC-SHA256, versionierte Verifikation, Fail-closed; keine Rotation |
| Auswirkungen P00-F | Implementiert Aktivierung, Übergangsfenster, Widerruf, Cache-/Environment-Recycle, Löschung und Betriebsnachweise |
| Offene Fragen | O1–O6 |
| Owner-Freigabe | **[ ] APPROVED — NAME/DATUM:** __________________ |
| Bedingungen | Nur nach Schließung von O1–O6 und separater P00-D-Implementierungsautorisierung |

**Die Entscheidung ist ausdrücklich nicht APPROVED. Das Freigabefeld bleibt leer.**

## 8. P00-D/P00-F-Abgrenzung

**P00-D (dieses Paket):**

- Key-Metadaten und exakte Materialvalidierung.
- HMAC-SHA256 über die vom Owner bestätigte kanonische Payload.
- Versionierte Verifikation und Fail-closed-Verhalten.
- Lokale Tests; keine AWS-Abhängigkeit.

**P00-F (später):**

- Rotation, Aktivierung, Übergangsfenster.
- Widerruf, Cache-/Environment-Recycle.
- Löschung und operative Nachweise.

Keine P00-F-Funktionalität wird in P00-D vorweggenommen.

## 9. Status

**A — READY**

`MO-RC4-P00-D — Q11 DECISION PACKAGE READY / OWNER APPROVAL PENDING`

Keine Produktimplementierung, kein AWS-Aufruf, keine Terraform-/AWS-Mutation, kein Push,
kein Main-Merge, kein Deployment, kein Release-Tag, keine RIS-/Jobsearch-Änderung.
