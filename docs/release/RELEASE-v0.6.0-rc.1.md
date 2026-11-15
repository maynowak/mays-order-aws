# Mays Orders AWS — RC4 Release Notes

**Release-Label:** `v0.6.0-rc.1` · **Entwicklungsstand:** RC4 · **Dokumentstand:** 14. November 2026

![Mays Orders AWS — freundliches RC4-Infografikmotiv](a_bright_modern_illustrated_infographic_hero_ban.png)

> **Build modular. Secure by design. Verify the full lifecycle.**

## 1. Auf einen Blick

RC4 bündelt den **Module Builder**, den **Installer**, den AWS-Order-Core und erweiterte **Security-/Privacy-Optionen** zu einer modularen Infrastruktur. Das System wurde im AWS-Development-Account mit echten Ressourcen erfolgreich bereitgestellt, getestet und vollständig zurückgebaut. **Kein Produktionsrollout** ist Teil dieser Verifikation.

| Kennzahl | Bestätigter Stand |
|---|---|
| RC4-Release-Label | `v0.6.0-rc.1` — Q-12 beschlossen |
| RC4-Branch | `release/rc4-integration` — veröffentlicht |
| Zuletzt bestätigter Branch-HEAD | `368ac590` (vor dem beauftragten Versions-Commit) |
| AWS Development Deploy | 58 Ressourcen erstellt |
| Live E2E | 4 von 4 bestanden |
| AWS Development Destroy | 58 Ressourcen entfernt; Terraform-State: 0 Ressourcen |
| Production | Keine Aktivierung / kein Rollout |

## 2. Module Builder — Infrastruktur aus Bausteinen

Der **Module Builder `0.1.0`** erzeugt reproduzierbare, modular zusammengestellte Artefakte. Er nutzt Presets und eine deterministische Generierung; der erzeugte Umfang kann lokal überprüft werden. Terraform-Ausgabe und Lambda-Artefakte sind Bestandteil des Workflows.

**Ablauf:** Preset/Modulauswahl → Modul generieren → generierten Inhalt und Konfiguration validieren → Installer verwenden → Terraform-Plan und Deployment im freigegebenen Umfeld prüfen.

**Wichtig für die Freigabe:** Das generierte Modul ist der Prüfgegenstand; Testergebnisse für einen anderen Quellstand ersetzen keine Validierung des tatsächlichen ZIP-Artefakts. Für RC4 wurde ein reproduzierbares Lambda-ZIP dokumentiert (46.929 Bytes; SHA-256 `20f4bab5766529e3340273cfde3b35c601a389122759051f2aef801337b76377`).

## 3. Installer — von der Konfiguration zur Installation

Der **Installer `0.1.0`** verbindet Modulkonfiguration, lokale Prüfungen und Terraform-Integration. Validierungen und Policy Gates sollen fehlerhafte oder unzulässige Kombinationen vor einem Cloud-Eingriff erkennen. Im dokumentierten Testlauf: **674 Installer-Tests PASS, 1 SKIP**.

Die Komponentenversion `0.1.0` ist **nicht** das RC4-Release-Label.

## 4. AWS-Order-Core und Infrastruktur

- **AWS Lambda:** Ausführung der Order-/Service-Logik.
- **DynamoDB:** Persistenz für den Order-Core.
- **Amazon SQS:** Entkopplung asynchroner Verarbeitung.
- **IAM:** Ressourcenbezogene Rollen und Berechtigungen; optionales Secret-Zugriffsrecht nur bei Aktivierung.
- **Terraform:** Definierter Infrastruktur-Lifecycle von Plan über Deploy bis Destroy.
- **AWS Secrets Manager:** Optionaler Baustein für APP_MANAGED; keine Secret-Werte im Terraform-Code.

Die RC4-Erweiterungen sollten keine bestehenden Cognito-/CloudFront-Ressourcen verändern. Die separate bestehende Testumgebung sowie die CI-/Pipeline-States blieben im dokumentierten Lifecycle unangetastet.

## 5. Security, Privacy und DSGVO-Annäherung

**Sicherheitskonzept:**

- **AWS_MANAGED:** Unterstützter Provider-Modus.
- **APP_MANAGED:** Optionaler, standardmäßig deaktivierter Provider mit **HMAC-SHA256**.
- **Schlüsselrotation und Widerruf:** Maximal ein vorheriger Schlüssel und höchstens **24 Stunden** explizit freigegebene Überlappung; sonst fail-closed.
- **Secrets:** AWS Secrets Manager optional; standardmäßig AWS-verwaltete Verschlüsselung, alternativ bestehender kundenseitiger KMS-Schlüssel bei geeigneter Freigabe. Kein neuer KMS-Schlüssel im RC4-Lifecycle erforderlich.
- **Least Privilege:** IAM-Zugriffe auf konkrete Secret-ARNs beschränkt, wenn der optionale Modus aktiviert ist.
- **Retention:** **Deaktiviert**; die Owner-Entscheidungen Q-05/Q-06/Q-07/Q-14 sind noch offen.

**Datenschutz-Einordnung:** Die Architektur unterstützt datensparsame und nachvollziehbare Verarbeitung durch optionale Schutzmechanismen, begrenzte Zugriffsrechte und bewusst deaktivierte automatische Aufbewahrungs-/Löschlogik. Das ist eine **DSGVO-orientierte technische Annäherung, keine bestätigte DSGVO-Konformität oder Rechtsprüfung**. Für produktive personenbezogene Daten sind u. a. Zweck/Rechtsgrundlage, Aufbewahrung, Löschung, Informationspflichten, Auftragsverarbeitung und operative Prozesse gesondert festzulegen und zu prüfen.

## 6. Qualität und nachgewiesener AWS-Lifecycle

| Testbereich | Ergebnis |
|---|---|
| Lambda | **440 PASS** |
| Installer | **674 PASS**, 1 SKIP |
| Module Builder | **129 PASS** |
| Policy Gates | **23 PASS** |
| Lokale E2E | **36 PASS**, 5 SKIP |
| Seed | **28 PASS** |
| AWS Live E2E | **4/4 PASS**, einschließlich Cleanup |

**Development-Lifecycle:** Validate (12 PASS, 1 WARN) → Terraform-Plan (58 add / 0 change / 0 destroy) → Deploy (58/58) → Post-Deploy PASS → Live-E2E (4/4 PASS) → Destroy-Plan (58 destroy) → Destroy (58/58) → Post-Destroy PASS; Terraform-State anschließend **0 Ressourcen**.

Der Lifecycle wurde mit dem AWS-Development-Profil `mayaws` in `eu-central-1` dokumentiert. Es gab **keine produktive Aktivierung**. Temporäre Testidentitäten wurden nach den Tests bereinigt.

## 7. Versionen und Release-Grenzen

| Ebene | Version / Status |
|---|---|
| **RC4-Release-Label (Q-12)** | **`v0.6.0-rc.1` — beschlossen** |
| Module Builder | `0.1.0` — unverändert |
| Installer | `0.1.0` — unverändert |
| Deployment-/Teststack | `0.2.0` — unverändert |
| Git-Tag `v0.6.0-rc.1` | Erstellung/Push beauftragt; Abschluss bislang nicht belegt |
| Main-Merge | Nicht ausgeführt; separate Freigabe nötig |
| Produktionsdeployment | Nicht durchgeführt |

**Freigabegrenze:** Ein beschlossenes Release-Label ist nicht dasselbe wie ein nachgewiesen gepushter Git-Tag oder ein produktiver Rollout. Optionales APP_MANAGED und Retention werden durch das Release-Label nicht automatisch aktiviert.

## 8. Was vor Production offen bleibt

- **Q-05/Q-06/Q-07/Q-14:** Retention und Aufbewahrungs-/Löschentscheidungen.
- **Q-11:** Operative Rotation/Revocation und Secret-Bereitstellung.
- **Release-Verifikation:** Tag- und Branch-Ziel nach dem finalen Release-Commit nachweisen; Main-Merge separat prüfen und freigeben.
- **Datenschutzbetrieb:** Rechtliche/organisatorische Datenschutzprüfung und produktive Betriebsprozesse ergänzen.

---

**Mays Orders AWS · RC4 · Modular Cloud Engineering**  
*Stand 14.11.2026. Die technischen Ergebnisse basieren auf den im Projektverlauf dokumentierten RC4-Test- und Lifecycle-Berichten; neuere Release-Aktionen wurden nicht als abgeschlossen vorausgesetzt.*
