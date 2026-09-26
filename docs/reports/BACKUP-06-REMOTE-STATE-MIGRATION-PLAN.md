# BACKUP-06 — Remote State Migration Plan

**Datum:** 2026-09-26  
**Scope:** Migrationsplanung von lokalem zu Remote Terraform State im Multi-Project Kontext  
**Keine Implementierung, nur Planung**

---

## 1. Scope

Definition einer sicheren Migrationsstrategie für Terraform State von lokalem Filesystem zu Remote S3 Backend mit DynamoDB Locking.

Erhaltung Multi-Project Isolation.

---

## 2. Git Basis

- Top-level: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `99e80b1ce712ac83c5f52bd832c3d5b65cdb02cf`
- Working Tree: CLEAN
- Vorgänger: BACKUP-05

---

## 3. Aktueller State Inventar

**Backend:** Keiner, lokaler State

**State Dateien:**
- `terraform/terraform.tfstate` — default workspace, leer, serial 3072
- `terraform/terraform.tfstate.backup` — Backup des default
- `terraform/terraform.tfstate.d/mays-order-par/terraform.tfstate` — Workspace mays-order-par, leer
- `terraform/terraform.tfstate.d/mays-order-par/terraform.tfstate.backup`

**Workspaces vorhanden:**
- default
- mays-order-par

**Projekt-Kontexte:**
- mays-orders
- mays-order-par

**Kein Remote Backend definiert**
**Kein Locking**
**Keine Versionierung**

---

## 4. Target State Design

### 4.1 S3 Backend

**Bucket Name Vorschlag:**
`<project-root>-terraform-state-<account-id>`
Beispiel: `mays-orders-terraform-state-240571105849`

Alternative zentrales Bucket:
`mays-orders-tfstate-central-240571105849`

**Vorteil zentral:** Ein Bucket für alle Projekte, Isolation via Key Prefix

Empfehlung: Zentrales Bucket mit Project Isolation via Key.

**Bucket Konfiguration:**
- Versionierung: Aktiv
- Server-Side Encryption: AES256
- Public Access Block: Aktiv
- Lifecycle: Optional, nicht für State nötig

### 4.2 State Key Convention

**Option A — Project-basiert:**
```
<project_name>/terraform.tfstate
```
Beispiel:
```
mays-orders/terraform.tfstate
mays-order-par/terraform.tfstate
```

Terraform Workspace wird automatisch in Key integriert via `workspace_key_prefix`.

**Option B — Environment + Project:**
```
<environment>/<project_name>/terraform.tfstate
```
Beispiel:
```
development/mays-orders/terraform.tfstate
development/mays-order-par/terraform.tfstate
```

Empfehlung: Option B für zukünftige Multi-Environment Nutzung.

### 4.3 DynamoDB Lock Table

**Tabelle Name:**
`mays-orders-terraform-locks`

**Schema:**
- Partition Key: `LockID` String
- TTL optional

**Vorteil:** Locking pro Workspace/State Key

---

## 5. Multi-Project Isolation

Remote State muss Isolation erhalten:

```
Bucket
    ↓
Prefix /environment/<project_name>/
    ↓
State File pro Workspace
    ↓
Lock Table schützt pro Key
```

Workspace Name = project_name → State Key enthält project_name → Isolation gewahrt.

---

## 6. Migrationsschritte Planung

**Phase 0 — Vorbereitung**
1. S3 Bucket + DynamoDB Lock Table erstellen
2. IAM Policies definieren
3. Bucket Versionierung aktivieren
4. Encryption konfigurieren

**Phase 1 — Backup**
1. Alle lokalen State Dateien sichern
2. Kopie nach sicherem Ort
3. Checksummen prüfen

**Phase 2 — Backend Konfiguration**
1. `terraform/backend.tf` erstellen mit S3 Backend Config
2. Backend Config enthält:
   - bucket
   - key
   - region
   - dynamodb_table
   - encrypt = true
   - workspace_key_prefix

**Phase 3 — Migration pro Workspace**
1. Für jeden Workspace:
   a. `terraform init -migrate-state` ausführen
   b. State wird nach S3 kopiert
   c. Lokaler State bleibt als Fallback

**Phase 4 — Verifikation**
1. `terraform plan` zeigt kein Diff
2. State in S3 prüfen
3. Locking testen

**Phase 5 — Cleanup**
1. Lokale State Dateien archivieren
2. `.gitignore` anpassen falls nötig

---

## 7. Risiken und Mitigation

**Risiko:** State Korruption bei Migration
**Mitigation:** Vollständiges Backup vor Migration, Versionierung aktiv

**Risiko:** Falscher Workspace migriert
**Mitigation:** Pre-Check project_name == workspace name

**Risiko:** Concurrent Änderungen während Migration
**Mitigation:** Migration im Wartungsfenster, Locking aktivieren

**Risiko:** IAM Berechtigungen fehlen
**Mitigation:** IAM Test vorher

**Risiko:** Bucket Name Kollision
**Mitigation:** Account-ID im Namen

---

## 8. Rollback Plan

**Rollback Trigger:**
- Migration fehlgeschlagen
- State unvollständig
- Plan zeigt unerwartete Änderungen

**Rollback Schritte:**
1. `terraform init` mit lokalem Backend wiederherstellen
2. Lokale State Dateien aus Backup zurückspielen
3. `terraform plan` verifizieren
4. Keine Apply

Rollback muss innerhalb von < 30 Minuten möglich sein.

---

## 9. Pre-Checks vor Migration

- Alle Workspaces dokumentiert
- State Dateien gesichert
- S3 Bucket existiert und erreichbar
- DynamoDB Lock Table existiert
- IAM Rolle hat Zugriff
- Terraform Version >= 1.5.0
- Kein laufender Apply

---

## 10. Post-Migration Validierung

- `terraform plan` zeigt kein Change
- State in S3 vorhanden und lesbar
- Locking funktioniert
- Workspace Switch funktioniert
- Multi-Project Isolation erhalten

---

## 11. Offene Entscheidungen

- Zentrales Bucket vs pro Projekt Bucket
- State Key Convention Option A vs B
- Bucket Name final
- Lock Table Name final
- Migration Zeitpunkt
- Verantwortlicher für Ausführung

---

## 12. Next Step

B7: Implementierung Remote State Backend Konfiguration nach Freigabe.

---

**Ende BACKUP-06**
