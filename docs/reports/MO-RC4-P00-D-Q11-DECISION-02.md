# MO-RC4-P00-D — Q11 DECISION PACKAGE

**Status:** A — Q11 DECISION PACKAGE READY / OWNER APPROVAL PENDING
**Datum:** 2026-11-14
**Branch:** `release/rc4-integration`
**HEAD:** `337aa4f1a58ce6765d58115d95c76f3fdb78322c`
**Modus:** Entscheidungsvorbereitung; keine Produktimplementierung.

```text
MO-RC4-P00-D — Q11 DECISION PACKAGE READY / OWNER APPROVAL PENDING
```

Die vorgeschlagene APP_MANAGED-Policy ist mit ADR-008 D-6/D-7/D-8 und dem
P00-D-Vertrag grundsätzlich vereinbar. Die exakte kanonische HMAC-Payload und
die sofortige Widerrufswirkung in warmen Lambda-Umgebungen benötigen jedoch
ausdrückliche Owner-Entscheidungen. Es gibt **keinen harten Vertragskonflikt**,
aber mehrere offene Präzisierungen.

---

## 1. Vorgeschlagene Q-11-Policy

| Parameter | Vorgeschlagener Wert | Status |
|---|---|---|
| Aktive Schlüsselversion | Genau eine | PROPOSED |
| Vorherige Version | Höchstens eine | PROPOSED |
| Reguläres Übergangsfenster | Maximal 24 Stunden | PROPOSED |
| Rotation | Explizit durch Owner/Operator | PROPOSED |
| Automatische Rotation in P00-D | Nicht erlaubt | PROPOSED |
| Kompromittierung | Sofortiger Widerruf | PROPOSED |
| Unbekannte Key-Version | Fail-closed | PROPOSED |
| Key-Löschung | Owner/Operator | PROPOSED |
| Key-Material | 32 Byte, Base64-kodiert | CONTRACTED |
| Algorithmus | HMAC-SHA256 | CONTRACTED |

**Status: PROPOSED — NICHT APPROVED.** Q-11 bleibt `READY_FOR_OWNER`.

---

## 2. Vertragsabgleich

| Prüfung | Ergebnis |
|---|---|
| ADR-008 D-6: 32-Byte-Base64, HMAC, keine Eigenbau-Chiffre | **KONSISTENT** |
| ADR-008 D-7: kein Auto-Rotator in RC4, manuelle Rotation | **KONSISTENT** |
| ADR-008 D-8: additiv/default-off, keine Order-Änderung | **KONSISTENT** |
| Contract §7: `keyId`/`keyVersion`, Fail-closed, kein KMS | **KONSISTENT** |
| P00-D/P00-F-Abgrenzung | **KONSISTENT**; P00-F bleibt für Rotation/Übergang zuständig |
| 24h-Übergangsfenster | **NEU — Owner-Parameter, kein bestehender Widerspruch** |
| Sofortiger Widerruf | **PRÄZISIERUNGSBEDARF** in warmen Lambda-Umgebungen |
| Kanonische HMAC-Payload | **OFFEN — exact protocol not specified** |
| `keyId`/`keyVersion` kryptografisch gebunden | **OFFEN — abhängig von kanonischer Payload** |

### Kein harter Konflikt

Die 24-Stunden-Grenze widerspricht keiner bestehenden ADR. Sie ist eine neue,
owner-genehmigungspflichtige Policy. `P00-D` darf daraus keine automatische
Rotation oder einen Hot-Reload ableiten.

---

## 3. Technische Klärungsfragen

### Q11-T1 — Beginn des Übergangsfensters

**Vorschlag:** Das Fenster beginnt mit einem expliziten Aktivierungszeitpunkt
`activeVersion.activatedAt`; `retiredAt = activatedAt + window`. Kein
implizites „jetzt + 24h“ beim ersten Request.

**Owner-Frage:** Wird der Zeitpunkt durch Deployment-Konfiguration oder durch
einen P00-F-Aktivierungsschritt festgelegt?

### Q11-T2 — Sofortiger Widerruf

**Vorschlag:** Kompromittierte Version wird durch explizite Konfiguration
deaktiviert; P00-F erzwingt Environment-Recycle/Cache-Invalidierung.

**Befund:** P00-C cached das Secret modulweit ohne TTL. Ein Widerruf ist in einer
warmen Lambda-Umgebung nicht sofort wirksam, solange die Umgebung nicht
recycelt wird. P00-D darf keinen Hot-Reload vortäuschen.

**Owner-Frage:** Akzeptiert der Owner „Widerruf = neue Konfiguration +
Environment-Recycle“ als sofortige operative Semantik, oder muss P00-F einen
stärkeren Mechanismus liefern?

### Q11-T3 — Bestehende Signaturen

**Owner-Frage:** Dürfen Signaturen der bisherigen Version nach Ablauf des
24h-Fensters weiterhin verifiziert werden (nur Verifikation, keine neuen
Signaturen), oder müssen sie ab dem Stichtag fehlschlagen? Das beeinflusst
gespeicherte Nachweise und Retry-/Recovery-Pfade.

### Q11-T4 — Downgrade-Schutz

**Vorschlag:** Die erwartete aktive `keyVersion` ist explizit konfiguriert;
jede unbekannte oder nicht aktive Version wird abgelehnt. Kein Fallback auf
eine ältere Version außerhalb des genehmigten Fensters.

**Owner-Frage:** Wird die aktive Version ausschließlich über Deployment-
Konfiguration festgelegt, oder darf P00-F sie zur Laufzeit wechseln?

### Q11-T5 — Kanonische HMAC-Payload

**Befund:** Der Vertrag verlangt HMAC-SHA256 über eine „canonical internal
payload“, definiert aber nicht die exakten Bytes/Reihenfolge. Ohne diese
Definition sind `keyId`/`keyVersion` nicht kryptografisch an die Daten
gebunden.

**Vorschlag zur Owner-Freigabe:** Kanonische Payload enthält mindestens:

```text
keyId
keyVersion
algorithm = "HMAC-SHA256"
message (length-prefixed or canonical JSON with sorted keys)
```

Keine stillschweigende Festlegung: exakte Serialisierung, Encoding und
Feldreihenfolge bleiben Owner-/Contract-Entscheidung.

### Q11-T6 — Base64- und Längenprüfung

**Vorschlag:** strikte Base64-Dekodierung (`validate=True`), exakt 32 Byte,
keine Whitespace-/Padding-Toleranz, fail-closed. Keine Schlüsselwerte in
Fehlern.

**Owner-Frage:** Sind 32 Byte die einzige zulässige Länge, oder sollen längere
Schlüssel später unterstützt werden?

---

## 4. Key-Kustodie

| Aufgabe | Vorschlag | Status |
|---|---|---|
| Schlüsselerzeugung | Owner/Operator | PROPOSED |
| Speicherung | externer Secret Store oder HSM | PROPOSED |
| Bereitstellung | autorisierter Betriebsprozess | PROPOSED |
| Runtime-Transport | explizite, geschützte Konfigurationsinjektion | PROPOSED |
| Rotation | Owner/Operator, P00-F | PROPOSED |
| Widerruf | Owner/Operator | PROPOSED |
| Löschung | Owner/Operator, keine Automatik | PROPOSED |
| Kompromittierung | Widerruf + aktive Version wechseln + Recycle + Audit | PROPOSED |

Keine Schlüsselwerte in Git, Terraform-State, Reports, Auditlogs oder
Fehlermeldungen. Keine neue AWS-Abhängigkeit.

---

## 5. P00-D / P00-F

**P00-D:** Key-Material-Validierung, HMAC-SHA256, `keyId`/`keyVersion`,
versionierte Verifikation, sichere Provider-Integration, lokale Tests.

**P00-F:** Rotation, Übergangsfenster, Widerruf, Aktivierungswechsel,
Cache-/Environment-Recycle.

P00-D implementiert **keine** P00-F-Funktionalität und keine automatische
Rotation.

---

## 6. Owner-Entscheidungsblatt

| Feld | Inhalt |
|---|---|
| Vorgeschlagene Entscheidung | Q-11-Policy mit 24h-Fenster, einer aktiven + einer vorherigen Version, HMAC-SHA256, Fail-closed |
| Alternativen | (a) 0h / sofortiger Wechsel; (b) 24h; (c) anderes Fenster; (d) keine vorherige Version |
| Sicherheitsfolgen | Längeres Fenster erhöht Missbrauchsfenster bei Kompromittierung; kürzeres Fenster erhöht Ausfallrisiko bei laufenden Retries |
| P00-D-Auswirkung | Implementiert nur Verifikation und Metadatenbindung; keine Rotation |
| P00-F-Auswirkung | Implementiert Aktivierung, Window, Widerruf, Recycle und Rollback |
| Offene Fragen | Q11-T1…T6; Key-Transport; exakte kanonische Payload |
| Freigabe | **`[ ] APPROVED  [ ] REJECTED  [ ] REVISE`** |

**Keine Freigabe durch den Commander.**

---

## 7. Git / Grenzen

```text
Branch:        release/rc4-integration
HEAD:          337aa4f1a58ce6765d58115d95c76f3fdb78322c
Working Tree:  CLEAN
Product code:  NONE
AWS/Terraform: NONE
Merge/Push:    NONE
Deployment:    NONE
RIS/Jobsearch: NONE
```

Keine Tests ausgeführt, da ausschließlich Dokumentation geändert wird.

**STOP vor P00-D-Implementierung.**
