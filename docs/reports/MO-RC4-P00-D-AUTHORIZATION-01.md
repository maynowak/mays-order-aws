# MO-RC4-P00-D-AUTHORIZATION-01

**Status:** A — CONTRACT PREPARED / OWNER DECISIONS PENDING
**Datum:** 2026-11-14
**Branch:** `release/rc4-integration`
**HEAD:** `87762f67070c0bdfae97d7e8af875e1ef0676be0`
**Modus:** Dokumentation und Vertragsvorbereitung; keine P00-D-Implementierung.

```text
MO-RC4-P00-D — CONTRACT PREPARED / OWNER DECISIONS PENDING
```

Der APP_MANAGED-Vertrag ist für eine separate Owner-Freigabe vorbereitet.
Q-11, Key-Kustodie/-Transport und die Implementierungsautorisierung bleiben
**offen** und werden hier nicht eigenmächtig als APPROVED markiert.

---

## 1. Q-11 — Rotationsvertrag (Vorschlag)

**Status: PROPOSED / OWNER DECISION PENDING**

Verbindliche Leitplanken:

1. Jeder Schlüssel besitzt eine eindeutige `keyId`.
2. Jede Schlüsselversion besitzt eine eindeutige `keyVersion`.
3. Aktive und vorherige Versionen dürfen nicht unbegrenzt parallel gültig
   bleiben.
4. Keine automatische Rotation in P00-D.
5. Kein stillschweigender Wechsel der aktiven Version.
6. Kein Fallback auf unbekannte Versionen.
7. Keine Schlüsselwerte in Logs, Fehlern, Reports oder Auditlogs.
8. Rotation und Übergangsfenster werden in **P00-F** implementiert; P00-D
   liefert nur die versionierte Verifikationsgrundlage.

### Offene Owner-Parameter

| Parameter | Vorschlag | Owner-Entscheidung |
|---|---|---|
| Übergangsfenster für alte Version | Explizite Start-/Endzeit, **kein Default**, fail-closed nach Ablauf | **PENDING** |
| Anzahl parallel gültiger Versionen | Maximal aktive + eine vorherige, nie unbegrenzt | **PENDING** |
| Aktive Version | Explizite `PRIVACY_APP_KEY_VERSION`, keine automatische Auswahl | **PENDING** |
| Rotationstrigger | Manuell/geführt; kein Automatismus in RC4 | **PENDING** |
| Key-Löschung | Keine automatische Löschung; Owner-Freigabe | **PENDING** |

Die bestehende ADR-008 D-7 gibt bereits „keine automatische Rotation in RC4“ und
eine manuelle Rotation vor; konkrete Fristen und Verantwortlichkeiten sind dort
nicht festgelegt.

---

## 2. Key-Kustodie-Modell (Vorschlag)

**Status: PROPOSED / OWNER DECISION PENDING**

| Aufgabe | Vorgeschlagene Verantwortung | MO-Verhalten |
|---|---|---|
| Schlüsselerzeugung | Owner/Operator oder beauftragter Kustode | MO erzeugt keinen Key |
| Sichere Speicherung | Externer Secret Store/HSM oder gleichwertige Kustodie | Kein Key in Git/Reports/Auditlogs |
| Bereitstellung | Deploy-/Betriebsverantwortlicher injiziert Material zur Laufzeit | Nur In-Memory-Konsum |
| Rotation | Owner/Operator; P00-F-Mechanik | Keine automatische Rotation |
| Widerruf | Owner/Operator | Fail-closed, kein Fallback |
| Löschung | Owner/Operator | Keine automatische Löschung |
| Kompromittierung | Sofortiger Widerruf, aktive Version wechseln, Cache/Environment recyceln, Audit | Kein stiller Wechsel, keine unbekannte Version |

**Keine neue AWS-Abhängigkeit:** APP_MANAGED nutzt kein AWS KMS und keine neue
AWS-Ressource. Der konkrete Transport (injizierter Loader, externer Secret Store,
Laufzeitumgebung) ist eine **offene Owner-/Infrastruktur-Entscheidung**.

---

## 3. Key-Material-Vertrag

Verbindliche Grundlage:

- 32 Byte dekodiertes Schlüsselmaterial.
- Base64-kodierte Bereitstellung.
- HMAC-SHA256 über eine kanonische interne Payload.
- `keyId` und `keyVersion` sind explizit und nicht leer.
- Vergleich mit `hmac.compare_digest`-äquivalenter Konstante-Zeit-Logik.
- Keine Eigenbau-Verschlüsselung; HMAC ist Authentifizierung, keine
  Datenverschlüsselung.
- Unbekannte Version, ungültiges Base64, falsche Länge, leeres Material und
  Konfigurationsfehler → fail-closed.
- Keine Schlüsselwerte in Fehlern/Logs/Reports/Auditlogs.

**Nicht genehmigt:** genauer Transport, Key-Format-Constraints über 32 Byte
hinaus, Übergangsfenster und Rotationstrigger.

---

## 4. Provider-Kompatibilität

- `ENV` bleibt Default und unverändert.
- `AWS_MANAGED` bleibt unverändert.
- `APP_MANAGED` ist additiv und default-off.
- Provider-Auswahl ausschließlich aus serverseitiger Konfiguration.
- Kein Request-/Body-/Header-Feld kann Provider oder Key-Version wählen.
- Kein Cross-Provider-Fallback.
- Keine Änderung an bestehenden Orders, API-Verträgen oder
  DDB-/SQS-Verschlüsselung.

---

## 5. Sicherheits- und Testkonzept (P00-D, noch nicht implementiert)

Erforderliche lokale Tests:

- HMAC-SHA256 gegen bekannten Testvektor.
- Falscher Schlüssel / falsche `keyVersion` → fail-closed.
- Manipulierte Nachricht → Verifikation schlägt fehl.
- Ungültiges Base64 / falsche dekodierte Länge / leerer Wert → fail-closed.
- Unbekannte Version / fehlende Metadaten → fail-closed.
- Secret-Redaction in Fehlern und Logs.
- Provider-Isolation: ENV/AWS_MANAGED/APP_MANAGED mischen sich nicht.
- ENV-/AWS_MANAGED-Regression.
- Deterministisches Lambda-ZIP.
- Keine echten Schlüssel/Credentials in Tests.

---

## 6. Abgrenzung P00-D / P00-F

- **P00-D:** Key-Material-Vertrag, `keyId`/`keyVersion`, HMAC-Verifikation,
  fail-closed, keine Rotation.
- **P00-F:** Rotation, Übergangsfenster, Widerruf, Cache-/Environment-Recycle
  und operative Rotationsevidenz.
- Q-11 bleibt bis zur Owner-Entscheidung offen.

---

## 7. Offene Owner-Entscheidungen

1. **Q-11:** Übergangsfenster, Anzahl paralleler Versionen, Rotationstrigger und
   Löschverantwortung.
2. **Key-Transport/-Kustodie:** konkreter externer Store/Loader und
   Bereitstellungsweg ohne neue AWS-Abhängigkeit.
3. **P00-D-Implementierungsautorisierung:** separat, nicht durch diesen Report.
4. **Key-Format-Constraints:** nur die 32-Byte-Base64-Basis ist vertraglich
   festgelegt; weitere Formatregeln sind offen.

---

## 8. Git / Grenzen

```text
Branch:        release/rc4-integration
HEAD:          87762f67070c0bdfae97d7e8af875e1ef0676be0
Working Tree:  CLEAN
Product code:  NONE
AWS/Terraform: NONE
Merge/Push:    NONE
Deployment:    NONE
RIS/Jobsearch: NONE
```

**STOP vor P00-D-Implementierung.**
