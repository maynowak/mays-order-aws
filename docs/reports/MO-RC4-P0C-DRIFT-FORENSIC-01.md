# MO-RC4-P0C-DRIFT-FORENSIC-01

**Forensische Analyse der P0C-Drift-Blockade aus `MO-RC4-AWS-UPGRADE-PLAN-02`**

**Datum:** 2026-11-04
**Branch:** `test/mo-rc4-p0c-drift-forensic-01` (ab `3432ca8`)
**Modus:** READ-ONLY. **Keine AWS-Mutation, kein Terraform-Plan, kein Apply,
kein State-Write, kein Backup, kein Push/Merge.**

---

## 1. Git- und AWS-Baseline

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-aws-upgrade-plan-02` |
| Ausgangs-HEAD | `3432ca8` |
| Arbeitsbranch | `test/mo-rc4-p0c-drift-forensic-01` |
| RC4-Code-Pin | `2e09e72` |
| RC3-Marker | `ff60a65` |
| Working Tree | CLEAN |
| AWS-Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| Workspace | `mays-orders-rc4-test` |
| State-Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| State-Serial | `4` |
| State-Objekte | 37 managed + 9 data |

Der State wurde ausschließlich lesend über `terraform state pull` inspiziert.

---

## 2. Verwendete Evidence

- Plan-Artefakt aus `MO-RC4-AWS-UPGRADE-PLAN-02`:
  `c266ed53f8f2753d076fd52725a8ab3f10fb15832e3cc8e74e08b97ae02aa43a`
- P3A-Backup-Evidence:
  `9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1`
- Plan-JSON (lokal, nicht im Repo) mit `resource_changes` und `resource_drift`
- 3 wiederholte `terraform state pull`-Läufe
- AWS Describe/Get: S3-Policy, Cognito-Pool
- Terraform-Konfiguration RC3 (`086a8be`) und RC4 (`2e09e72`)

---

## 3. S3-Drift: `module.cloudtrail.aws_s3_bucket.trail`

### Befund

| Quelle | Ergebnis |
|---|---|
| Terraform-Konfiguration | `aws_s3_bucket.trail` hat **kein** `policy`-Argument |
| Separate Ressource | `aws_s3_bucket_policy.trail_policy` verwaltet die Policy |
| Plan `resource_changes` | `aws_s3_bucket.trail` = **no-op**; `aws_s3_bucket_policy.trail_policy` = **no-op** |
| State `aws_s3_bucket.trail.policy` | leer (Länge 0) |
| Refresh/Drift `policy` | 842 Zeichen |
| AWS `GetBucketPolicy` | 842 Zeichen |
| State `aws_s3_bucket_policy.trail_policy.policy` | 842 Zeichen |
| Kanonischer Policy-Hash (State-Policy-Ressource vs. AWS) | **identisch** (`2a6c5525…`) |

### Klassifikation

**`STATE_REPRESENTATION_DIFFERENCE` / `PROVIDER_NORMALIZATION`**

Der `policy`-Wert am `aws_s3_bucket` ist ein berechnetes/abgeleitetes Attribut.
Die tatsächliche Policy wird durch die separate `aws_s3_bucket_policy`-Ressource
verwaltet und stimmt mit AWS überein. Es gibt **keine externe Policy-Änderung**
und **keine Konfigurationsänderung** am Bucket.

P0C wertet den Drift dennoch als Drift eines geschützten S3-Buckets.

---

## 4. Cognito-Drift: `module.cognito.aws_cognito_user_pool.users`

### Befund

| Quelle | `auto_verified_attributes` | `username_attributes` |
|---|---|---|
| RC3-Konfiguration | nicht gesetzt | nicht gesetzt |
| RC4-Konfiguration | nicht gesetzt | nicht gesetzt |
| Terraform-State | `null` | `null` |
| AWS `DescribeUserPool` | `null` | `null` |
| Refresh/Drift | `[]` (leere Liste) | `[]` (leere Liste) |
| Plan `resource_changes` | **no-op** | **no-op** |

Die RC3- und RC4-Cognito-Konfiguration ist in diesem Bereich **identisch**.
AWS liefert keine Attribute; Terraform normalisiert `null` beim Refresh zu einer
leeren Liste.

### Klassifikation

- `auto_verified_attributes`: **`PROVIDER_NORMALIZATION`**
- `username_attributes`: **`PROVIDER_NORMALIZATION`**

Kein REAL_DRIFT, keine externe Änderung, keine RC4-Konfigurationsänderung.

---

## 5. State-Fingerprint-Ursache

### Implementierungen

| Quelle | Berechnung |
|---|---|
| P3A-Baseline (durch uns beim Backup erzeugt) | SHA-256 über rohe `terraform state pull`-Bytes |
| P0C (`installer/core/state_baseline.py`) | SHA-256 über rohe `terraform state pull`-Bytes |

Beide verwenden **denselben Algorithmus** und dieselbe Datenquelle, aber
unterschiedliche Snapshots.

### Reproduzierter Befund

Drei unmittelbar aufeinanderfolgende `terraform state pull`-Läufe (gleicher
State, Serial 4, Lineage unverändert, S3-Objekt unverändert seit Apply):

| Pull | Raw-SHA-256 | Länge |
|---|---|---|
| 1 | `b6011034…` | 106057 |
| 2 | `684907f5…` | 106057 |
| 3 | `d44ccfa3…` | 106057 |

Die drei States sind inhaltlich identisch; der strukturierte Diff zeigt
**ausschließlich Änderungen an der Reihenfolge von `check_results`**
(`/check_results/*`). `resources`, `outputs`, `serial`, `lineage` sind
unverändert.

### Klassifikation

**`STATE_REPRESENTATION_DIFFERENCE` — nicht-deterministische
State-Serialisierung.**

Der Fingerprint ist kein stabiler Identitätsnachweis, solange er rohe
`state pull`-Bytes inklusive der ungeordneten `check_results`-Liste hashiert.
P3A (`684907f5…`) und P0C (`cbb81ab4…`) sind beide korrekte Hashes
unterschiedlicher Serialisierungen desselben Zustands.

Der State wurde durch den Plan **nicht inhaltlich verändert**; das
S3-State-Objekt trägt weiterhin `LastModified=2026-11-03T20:02:01Z`.

---

## 6. P0C-Klassifizierungsbewertung

| Ressource | Tatsächliche Drift | Konfigurationsänderung | Provider-Normalisierung | Sicherheitsrelevanz | P0C | Minimale Korrektur |
|---|---|---|---|---|---|---|
| `aws_s3_bucket.trail` (`policy`) | nein — Policy-Ressource unverändert, AWS = State | nein (no-op) | ja, computed `policy` | gering für diesen Drift, aber S3-Schutz bleibt wichtig | **zu streng** | computed `policy` bei separater Policy-Ressource von Drift-Blockade ausnehmen bzw. als REVIEW behandeln |
| `aws_cognito_user_pool.users` (`auto_verified_attributes`) | nein | nein | ja (`null` → `[]`) | gering | **zu streng** | `null`/leere Liste normalisieren |
| `aws_cognito_user_pool.users` (`username_attributes`) | nein | nein | ja (`null` → `[]`) | gering | **zu streng** | wie oben |

Die pauschale CRITICAL-Regel „jede Drift an einem geschützten Typ blockiert“
ist sicherheitskonservativ, erzeugt hier aber **False Positives**, weil die
betroffenen Ressourcen im Plan `no-op` sind und die Abweichung nur aus
Provider-/State-Normalisierung besteht.

**Wichtig:** Das bedeutet nicht, echte Drift an S3/Cognito freizugeben. Die
Korrektur muss computed/normalisierte Attribute gezielt behandeln und echte
Attribut-/Policy-Abweichungen weiterhin blockieren.

---

## 7. Backup-Gate-Bewertung

`installer/core/backup_gate.py` prüft:

- Schema/Pflichtfelder
- SHA-256 der Evidenz
- Projekt/Environment/Account/Region/Tabelle/ARN
- `backupStatus=AVAILABLE`
- `overallStatus=VERIFIED`
- PITR `ENABLED`
- State-Lineage und State-Serial

**Nicht geprüft:** `stateFingerprint`.

P3A selbst speichert den vom Aufrufer übergebenen Fingerprint; es berechnet ihn
nicht aus dem Live-State. P0C berechnet ihn roh. Eine gemeinsame normalisierte
Fingerprint-Semantik existiert derzeit nicht.

Eine Bindung ohne Änderung der Evidence ist möglich, sofern der Fingerprint
künftig kanonisch berechnet wird und die Evidence diesen kanonischen Wert
enthält; die bestehende Evidence müsste dann neu gebunden/erneuert werden.
Die aktuelle Gate-Implementierung ist davon nicht betroffen, weil sie den
Fingerprint ignoriert.

---

## 8. Trennung: echte Drift vs. Normalisierung

| Kandidat | Klassifikation |
|---|---|
| S3 `aws_s3_bucket.trail.policy` | State-Repräsentation/Provider-Normalisierung; tatsächliche Policy-Ressource unverändert |
| Cognito `auto_verified_attributes` | Provider-Normalisierung (`null` → `[]`) |
| Cognito `username_attributes` | Provider-Normalisierung (`null` → `[]`) |
| State-Fingerprint | Nicht-deterministische Serialisierung (`check_results`-Reihenfolge) |
| Übrige Drift-Punkte (API/Lambda/IAM/CloudWatch/SQS-ESM) | **nicht abschließend bewertet**; außerhalb der beiden blockierenden Protected-Typen, aber im Plan als REVIEW geführt |

Keine echte externe Drift wurde für S3-Policy oder Cognito nachgewiesen.

---

## 9. Sicherheitsrisiken

- P0C blockiert derzeit aus Konservativität; das ist kein Datenrisiko, sondern
  ein Release-/Verfügbarkeitsrisiko.
- Eine zu großzügige Lockerung könnte echte S3-/Cognito-Drift übersehen.
- Der rohe Fingerprint ist kein verlässlicher Nachweis; er kann bei
  unverändertem State zufällig wechseln.
- Der Plan enthält weiterhin keine DELETE/REPLACE-Aktion; das ersetzt keine
  Attributprüfung.

---

## 10. Minimale Korrekturempfehlung

**Keine AWS-Änderung, keine Terraform-Konfigurationsänderung.**

1. **P0C:** Drift-Findings mit `resource_changes=no-op` und ausschließlich
   computed/normalisierten Attributen gezielt behandeln:
   - S3 `aws_s3_bucket.policy` bei separat verwalteter
     `aws_s3_bucket_policy` nicht als kritische Bucket-Drift werten.
   - Cognito `null` ↔ `[]` für `auto_verified_attributes` /
     `username_attributes` normalisieren.
   - Echte Attribut-/Policy-Abweichungen weiterhin blockieren.
2. **Fingerprint:** Kanonische Berechnung einführen:
   - `check_results` ausschließen **oder** nach stabilem Schlüssel sortieren;
   - alternativ nur `serial` + `lineage` + normalisierte Ressourcenidentität
     verwenden.
3. **Backup-Gate:** Entscheiden, ob der (kanonische) Fingerprint Teil der
   Bindung wird; falls ja, P3A-Evidence mit derselben Semantik erzeugen.
4. **Keine** `ignore_changes`-Hacks, keine State-Manipulation, keine
   Cognito-/S3-Änderung.

---

## 11. Notwendige Regressionstests

- S3: separate `aws_s3_bucket_policy` + computed `policy`-Drift → kein
  kritischer Bucket-Drift.
- Cognito: `null` vs `[]` → keine CRITICAL-Blockade; echte
  Attributabweichung → weiterhin BLOCKED.
- Fingerprint: zwei `state pull`-Serialisierungen mit unterschiedlicher
  `check_results`-Reihenfolge → gleicher kanonischer Fingerprint.
- Echte State-Änderung (Serial/Lineage/Resource) → weiterhin Mismatch.
- P0A/P0C/P1/P3A unverändert grün.

---

## 12. Entscheidungsvorlage

**A. Muss AWS verändert werden?**  
**NEIN.** S3-Policy und Cognito-Attribute stimmen mit Konfiguration/State überein;
keine externe Änderung nachgewiesen.

**B. Muss Terraform-Konfiguration verändert werden?**  
**NEIN.** RC3/RC4-Cognito-Konfiguration identisch; S3-Policy separat verwaltet.

**C. Muss P0C korrigiert werden?**  
**JA.** Computed-/Normalisierungsdrift bei `no-op`-Ressourcen wird derzeit zu
streng als CRITICAL behandelt; echte Drift muss weiter blockieren.

**D. Muss die Fingerprint-Berechnung korrigiert werden?**  
**JA.** Roh-State-Hash inkl. ungeordneter `check_results` ist nicht stabil;
kanonische Berechnung erforderlich.

**E. Ist ein neues Backup erforderlich?**  
**NEIN** für die Datensicherheit. Falls der Fingerprint künftig verbindlich
geprüft wird, muss die Evidence mit der neuen kanonischen Semantik neu gebunden
werden; ein neues Backup allein löst die Serialisierungs-Nichtdeterminismus
nicht.

**F. Ist nach der Korrektur ein neuer Upgrade-Plan erforderlich?**  
**JA.** Der vorliegende Plan ist blockiert und nicht apply-fähig; nach
P0C-/Fingerprint-Korrektur muss ein neuer Plan erstellt und separat freigegeben
werden.

---

## Status

```text
RC4 P0C DRIFT ROOT CAUSE VERIFIED — FIX DECISION REQUIRED
```

Keine AWS-Mutation, kein Terraform-Plan, kein Apply, kein Backup, kein
State-Write, kein Push/Merge. **STOP.**
