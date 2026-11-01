# MO-RC4-P01-SECRET-PROVIDER-DESIGN

**SecretProvider: AWS_MANAGED → APP_MANAGED → geführte Rotation**

**Datum:** 2026-11-01
**Typ:** Design (keine Implementierung, kein Secret-Abruf)
**Grundlage:** `MO-RC4-P01-CONTRACT-INVENTORY.md`, RC3-Code

---

## 1. Ist-Zustand (belegt)

### 1.1 Wo das Secret gelesen wird

| Ort | Zeile | Verhalten |
|---|---|---|
| `lambda/src/order_service.py` | `101–124` (`_require_privacy_auth`) | `os.environ.get("PRIVACY_INTERNAL_SECRET")`; fehlt → `validation_error("Internal secret not configured")`; Token-Vergleich via `secrets.compare_digest` |
| `lambda/tests/test_order_service.py` | `8`, `486–493` | setzt/entfernt das Secret im Test-Env |
| `terraform/modules/lambda/main.tf` | `16–22` | Env: `ORDERS_TABLE`, `SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME` — **kein** Secret |
| `terraform/modules/sqs-worker/main.tf` | `10–14` | Env: nur `ORDERS_TABLE` |

**Befund:** Das Secret wird **nirgends provisioniert** (`grep PRIVACY_INTERNAL_SECRET terraform/ installer/ module_builder/` = 0 Treffer). Es wurde historisch **ephemer** gesetzt und nach dem Test wieder entfernt (`MAYS-ORDERS-PRIVACY-FINAL-EVIDENCE-AND-DESTROY-01.md` §45). **Status: PARTIAL.**

### 1.2 Welcher Handler es braucht

- **Nur der Order-Handler** (`index.handler`), genauer der interne Pfad
  `internalAction ∈ {privacy/inspect, privacy/export, privacy/erase}` (`index.py:105–125`).
- Der **Worker** (`sqs_handler.handler`) liest das Secret nicht.
- `cognito_backup_handler` und Rotations-/Seed-Tools: nicht relevant.

### 1.3 Fehlerbehandlung heute

Fail-closed und vollständig: fehlendes Secret, fehlendes Token, falsches Projekt,
fehlende Berechtigung, falsches Secret → jeweils `validation_error` (HTTP 400 im
internen Ergebnis). Kein Fallback, keine „Warnung“.

### 1.4 IAM heute

Keine `secretsmanager:*`- oder `kms:*`-Berechtigung in irgendeiner Rolle
(`grep kms:` in `terraform/modules/` = 0; `grep secretsmanager` = 0). Ein Provider-Wechsel
**ohne** IAM-Erweiterung schlägt zur Laufzeit mit `AccessDenied` fehl (fail-closed, korrekt,
aber funktionslos).

### 1.5 Auswirkung eines Provider-Wechsels

| Aspekt | Wirkung |
|---|---|
| Verhalten | unverändert (Vergleich bleibt `compare_digest`) |
| Kaltstart | +1 Netzwerkaufruf (Secrets Manager), ~10–40 ms, einmal pro Instanz |
| IAM | neue `secretsmanager:GetSecretValue`-Berechtigung nötig |
| Terraform | neue Ressource + Env-Variable (`PRIVACY_SECRET_ID`), kein Klartext |
| Rotation | Cache muss invalidiert werden (sonst läuft alte Kennung bis Kaltstart) |
| Tests | Fake-Client statt Env; Env-Pfad muss Default bleiben |

---

## 2. Zielarchitektur

### 2.1 Vertrag (vorgeschlagen)

```text
PRIVACY_SECRET_PROVIDER = "env" | "secretsmanager"   (Default: "env")
PRIVACY_SECRET_ID       = <ARN oder Name>            (nur bei secretsmanager)
PRIVACY_INTERNAL_SECRET = <Klartext>                 (nur bei env; Legacy)
```

```text
get_privacy_secret() -> str
  env              → os.environ["PRIVACY_INTERNAL_SECRET"] (fehlt ⇒ Fehler)
  secretsmanager   → boto3 secretsmanager.get_secret_value(SecretId=...)
                     (Fehler ⇒ Fehler, KEIN Env-Fallback)
```

- **Cache:** pro Prozess (Cold-Start-Cache), Invaliderung über Neustart/Env-Änderung.
- **Ausgabe:** nur der Secret-String; niemals loggen, niemals in Fehlertexten.
- **Kein Fallback** von `secretsmanager` auf `env` (sonst entstünde ein stiller Downgrade).

### 2.2 Phase 1 — AWS_MANAGED (Empfehlung für RC4)

| Anforderung | Umsetzung |
|---|---|
| Referenz statt Klartext in der Lambda-Konfiguration | Env enthält nur `PRIVACY_SECRET_ID` (ARN) + Provider-Name |
| Least-Privilege | `secretsmanager:GetSecretValue` auf **exakten** Secret-ARN (kein `*`) |
| Sichere Fehlerbehandlung | Exception → fail-closed; keine Teil-Erfolge |
| Keine Secret-Werte in Logs | Provider loggt nur den Secret-**Namen**/ARN-Suffix und den Fehlercode |
| Keine Werte in Terraform-Outputs | Outputs geben nur `privacy_secret_arn`/`-name` aus |
| Kein Wert im Terraform-State | `ephemeral`-Wert (TF ≥ 1.10; lokal 1.17) für die Erzeugung, `lifecycle.ignore_changes` auf der Version; alternativ Secret außerhalb von TF setzen (Q-03) |
| Rotation nicht erforderlich | `aws_secretsmanager_secret_rotation` bleibt in Phase 1 **aus** |

**Secret-Erzeugung:** `random_password` (ephemer) → `aws_secretsmanager_secret_version`;
`recovery_window_in_days = 7`; Name `${project_name}/privacy-internal-secret`.

### 2.3 Phase 2 — APP_MANAGED (Analyse, **nicht** RC4-Pflicht)

**Wichtige Klarstellung des Auftrags:** APP_MANAGED ≠ eigener AWS-KMS-Key. Die Anwendung
erhält einen **extern bereitgestellten Schlüssel** und nutzt ihn selbst.

#### Technische Realität im Lambda-Runtime

| Bedarf | Verfügbar? | Konsequenz |
|---|---|---|
| Keyed Hash / Authentifizierung (HMAC-SHA256) | **ja** (`hmac`, `hashlib`, stdlib) | sofort umsetzbar; deckt den heutigen Bedarf (Token-Vergleich) ab |
| Schlüsselableitung (KDF) | **ja** (`hashlib.pbkdf2_hmac`, `hashlib.scrypt`) | Passphrase → Schlüssel möglich |
| Symmetrische Verschlüsselung (AES-GCM) | **nein** in der stdlib | **nicht selbst implementieren** |
| Envelope-Verschlüsselung | ja, über **KMS** (`kms:Encrypt/Decrypt/GenerateDataKey`) | wäre dann AWS_MANAGED-Krypto, nicht APP_MANAGED |

**Empfehlung:** APP_MANAGED Phase 2a = **keyed authentication** (HMAC) mit
extern bereitgestelltem Schlüssel; Phase 2b (falls echte Datenverschlüsselung gefordert)
nur mit geprüfter Krypto-Bibliothek oder KMS-Envelope — **keine Eigenbau-Chiffre**.

#### Gefordertes Design

| Anforderung | Vorschlag |
|---|---|
| Sichere Schlüsselübergabe | Schlüssel als Secret-Wert (Secrets Manager) **oder** als Env-Referenz auf ein extern verwaltetes Secret; nie im Repo/in Doku |
| Schlüsselformat | 32 Byte, Base64 (256 Bit); Validierung auf Länge/Alphabet, fail-closed |
| Schlüsselableitung | `HKDF`-artig über `hmac`/`hashlib` oder `pbkdf2_hmac` mit dokumentierten Parametern (Salt + Iterationen) |
| Authentifizierte Verschlüsselung | nur mit geprüfter Bibliothek; HMAC-Authentifizierung mit `compare_digest` |
| Schlüsselidentifikation/Versionierung | `keyId` (z. B. `k1`) + `keyVersion`; bei mehreren Schlüsseln aktive Kennung im Secret-Metadatum |
| Trennung Schlüssel ↔ Daten | Schlüssel ausschließlich im Secret/Env, Daten in DynamoDB; kein Schlüssel im Item |
| Wiederherstellung nach Neustart | deterministisch aus Provider beziehen; kein In-Memory-Zustand nötig |
| Unbeaufsichtigte Worker | Worker benötigt **kein** Secret (nur der Handler) — bewusst beibehalten |

### 2.4 Phase 3 — Geführte Rotation (später)

Ablauf (interaktiv, mit Wiederanlauf):

```text
1. Aufforderung zur Schlüsselbereitstellung (neuer Schlüssel + keyId)
2. Prüfung des bisherigen Schlüssels (Ist-Zustand: welche Daten mit welcher keyId?)
3. Bereitstellung des neuen Schlüssels (Secret-Version, AWSPENDING)
4. Kontrollierte Neuverschlüsselung (batch, idempotent, mit Fortsetzungsmarke)
5. Wiederanlauf nach Unterbrechung (Fortsetzung ab Marke, keine Doppelarbeit)
6. Abschlussprüfung (Stichprobe: alt entschlüsselbar? neu lesbar?)
7. Erst danach Freigabe zur Entfernung des alten Schlüssels (AWSPREVIOUS → löschen)
```

**In P01 keine Rotation, keine Neuverschlüsselung, kein Automatismus.**

---

## 3. Architekturentscheidungen (Vorschlag, PROPOSED)

| # | Entscheidung | Status |
|---|---|---|
| S-1 | Provider-Vertrag mit `env` als Default (rückwärtskompatibel) | PROPOSED |
| S-2 | `secretsmanager` als erste produktive Implementierung | PROPOSED |
| S-3 | Nur ARN in der Lambda-Env, Klartext ausschließlich im Secret | PROPOSED |
| S-4 | Kein stiller Fallback; jeder Fehler ist fail-closed | **ACCEPTED (bestehendes Verhalten)** |
| S-5 | Kein Klartext-Secret im Terraform-State | PROPOSED (Umsetzungsweg offen, Q-03) |
| S-6 | APP_MANAGED als HMAC-basierte Authentifizierung, keine Eigenbau-Chiffre | PROPOSED |
| S-7 | Rotation erst nach RC4 (eigene Phase mit Wiederanlauf) | PROPOSED |

## 4. Risiken

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Klartext im State (naiver Ansatz) | Secret für jeden mit State-Zugriff lesbar | ephemer + `ignore_changes`; Q-03 |
| Cache hält altes Secret nach Rotation | Auth schlägt fehl, bis Cold Start | Cache-Invalidierung über Env-Änderung/Deploy; Rotation dokumentiert |
| IAM zu breit (`Resource: "*"`) | Secret-Zugriff für fremde Secrets | exakter ARN |
| Env-Fallback „aus Bequemlichkeit“ | stiller Downgrade auf unsicheren Pfad | Code-Regel + Negativtest |
| Netzwerkfehler zu Secrets Manager | Privacy blockiert | fail-closed (korrekt), Alarm/Metrik |
| Mehrere Secrets/Projekte | Verwechslung | projektgebundener Name + ARN-Prüfung |
| APP_MANAGED mit selbstgebauter Krypto | Sicherheitslücke | Verbot in ADR; nur HMAC/KDF oder KMS |

## 5. Teststrategie

| Test | Inhalt |
|---|---|
| Provider-Auswahl | `env` (Default) nutzt Env; `secretsmanager` ruft Client mit exaktem SecretId |
| Fehlerfälle | fehlendes Secret, `ResourceNotFound`, `AccessDenied`, Timeout → Exception, kein Fallback |
| Cache | zweiter Aufruf ohne Client-Aufruf; Neustart-Cache leer |
| Log-Hygiene | Secret-Wert taucht in keiner Log-Zeile/Fehlermeldung auf |
| Auth-Verhalten | gleiche Ergebnisse wie heute (richtig/falsch/fehlt) |
| State/Outputs | Terraform-Output enthält keinen Secret-Wert; Plan-Assertion |
| IAM | Dokument-Assertion: nur `GetSecretValue`, nur exakter ARN |
| Rotation (Phase 3) | 4-Schritt-Protokoll mit Fake-Client, Wiederanlauf, Abschlussprüfung |

## 6. Akzeptanzkriterien (Design)

- [x] Gelesen-Stellen, Handler-Bedarf, Env-Nutzung, Fehlerpfad, IAM belegt.
- [x] Phase 1 vollständig spezifiziert inkl. State-/Output-/Log-Anforderungen.
- [x] APP_MANAGED von KMS abgegrenzt und Krypto-Grenzen benannt.
- [x] Rotation als spätere Phase mit Wiederanlauf beschrieben.
- [x] Keine Implementierung, kein Secret-Abruf, keine AWS-Operation.
