# MO-RC4-P01-OPEN-QUESTIONS

**Offene Entscheidungen aus der P01-Analyse**

**Datum:** 2026-11-01
**Basis:** `MO-RC4-P01-CONTRACT-INVENTORY.md`, `-ORPHAN-CLEANUP-DESIGN.md`, `-SECRET-PROVIDER-DESIGN.md`
**Regel:** Keine Implementierung eines blockierten Items vor Entscheidung.

---

## A. Blockierend für jede Retention-/Cleanup-Implementierung

| ID | Frage | Warum blockierend | Optionen | Empfehlung |
|---|---|---|---|---|
| **Q-01** | Wird `subjectId` beim Anlegen künftig aus dem JWT (`requestContext.authorizer.jwt.claims.sub`) gesetzt? | Ohne Nutzerbezug findet **kein** Cleanup und **kein** Erase die Bestellung (Beleg: `index.py:143` übergibt keinen `subject_id`) | (a) `sub` automatisch setzen, (b) Client darf `subjectId` übergeben (API-Erweiterung), (c) beides, (d) nichts ändern | **(a)** — sicher, kein Client-Vertrauen nötig; API-Body bleibt unverändert |
| **Q-02** | Gilt `subjectId` auch für Bestandsdaten? Backfill nötig? | Bestand hat kein Feld (Seed: 0 Treffer) | (a) kein Backfill (Bestand bleibt „unverknüpft"), (b) Backfill aus vorhandenen Daten (nicht möglich — keine Quelle), (c) Bestand bei erstem Zugriff verknüpfen | **(a)** + dokumentierte Einschränkung |
| **Q-03** | Wie wird das Secret ohne Klartext im Terraform-State erzeugt? | Sicherheitsanforderung; `random_password` im State wäre ein Leak | (a) `ephemeral` (TF ≥ 1.10) + `ignore_changes`, (b) Secret außerhalb TF (manuell/CLI), (c) Klartext akzeptieren + dokumentieren | **(a)**, Fallback (b) |
| **Q-04** | Kandidatenfindung für Fristen: neuer GSI3 (`retentionUntil`) oder gefilterter Scan? | Ohne Index ist jede Fristprüfung ein Full-Scan (Kosten/Zeit) | (a) GSI3, (b) Scan mit Filter + Limit, (c) Scan nur bei kleinem Datenbestand | **(a)** bei erwarteter Größe; (b) als Start, wenn RC4 klein bleibt |
| **Q-05** | Wird ein Provenienzfeld (`dataProvenance`) eingeführt, um RIS-Schreibpfade zu schützen? | Ohne Marker ist „verwaist" nicht von „fremd geschrieben" unterscheidbar (RIS repliziert MO-Verhalten) | (a) neues Feld, (b) Heuristik über `pk`-Muster `ord_ord_`, (c) RIS-Flag im Deployment, (d) kein Schutz | **(a)**; (b) nur als Übergangslösung, weil RIS das Doppelpräfix bewusst repliziert |
| **Q-06** | Wer koordiniert den RIS-Schreibpfad (Setzen von `subjectId`/Provenienz)? | RIS schreibt direkt in die MO-Tabelle; ohne Abstimmung bleiben die Daten unauffindbar | (a) RIS übernimmt die neuen Felder, (b) RIS schreibt künftig nur über MO-API, (c) MO duldet Fremdschreibungen ohne Cleanup | **(a)** kurzfristig, **(b)** strategisch |

## B. Retention-Semantik

| ID | Frage | Optionen | Empfehlung |
|---|---|---|---|
| **Q-07** | Basis-Frist und Cancel-Frist (Werte)? | (a) 365 / 30 Tage, (b) frei konfigurierbar ohne Default, (c) 180 / 14 | **(a)** als Default, vollständig konfigurierbar; rechtliche Bestätigung einholen |
| **Q-08** | Ist `RETAIN` pro Bestellung setzbar oder nur global? | (a) pro Bestellung (Feld), (b) global, (c) beides | **(a)** mit globalem Default |
| **Q-09** | Wird die Frist bei Statuswechsel neu berechnet? | (a) ja ab letztem Statuswechsel, (b) fix ab Erstellung, (c) nur bei `DELIVERED`/`CANCELLED` | **(c)** — sonst verlängert jede Statusänderung die Aufbewahrung unbegrenzt |

## C. Status / Lifecycle

| ID | Frage | Optionen | Empfehlung |
|---|---|---|---|
| **Q-10** | Sollen `COMPLETED`/`FAILED` als Bestell-Status eingeführt werden? | (a) nein (DELIVERED/CANCELLED genügen), (b) ja `COMPLETED` als Alias für DELIVERED, (c) ja `FAILED` für fehlgeschlagene Verarbeitung | **(a)** — `FAILED` gehört auf die Verarbeitungs-/DLQ-Ebene, nicht in den Bestellstatus |
| **Q-11** | Wird der Worker-Race (Read→Write ohne Condition) in RC4 behoben? | (a) ja, Condition + Version-Inkrement, (b) nein, nur dokumentieren | **(a)** — Datenintegrität, kleiner Aufwand, hoher Nutzen |
| **Q-12** | Wird eine DLQ eingeführt? | (a) ja (neue Queue + Alarm), (b) nein, Fehler nur loggen | **(a)** als eigenes Paket; neue AWS-Ressource → ADR-006-Thema |

## D. Secret-Management

| ID | Frage | Optionen | Empfehlung |
|---|---|---|---|
| **Q-13** | APP_MANAGED ohne stdlib-AES: welcher Weg? | (a) nur keyed authentication (HMAC), (b) geprüfte Krypto-Bibliothek bündeln, (c) KMS-Envelope als „APP_MANAGED"-Ersatz | **(a)** für RC4; (b)/(c) nur mit eigener ADR und Security-Review |
| **Q-14** | Wird die Rotation (Rotator-Lambda) in RC4 gebaut? | (a) ja, (b) nein (Phase 3), (c) manuelle Rotation dokumentieren | **(b)**, manuelle Rotation in der Doku |
| **Q-15** | Wird das Secret künftig auch vom Worker benötigt? | (a) nein (Status quo), (b) ja (falls Worker PII anfasst) | **(a)** — Worker bleibt secret-frei |

## E. ADR / Governance

| ID | Frage | Befund | Empfehlung |
|---|---|---|---|
| **Q-16** | **ADR-Nummerierung:** `ADR-007` ist bereits vergeben („On-Demand Capacity", PROPOSED in `architecture/architecture-decisions.md`) | Die angeforderte Datei `ADR-007-…` würde kollidieren | **ADR-008** in der bestehenden Datei anlegen; Auftragsnummer als „ADR-007 (Auftrag) → ADR-008 (vergeben)" dokumentieren |
| **Q-17** | ADR-Verzeichnisstruktur: `docs/adr/` existiert nicht; Konvention ist `architecture/architecture-decisions.md` | Bestätigt (`ls docs/adr` → kein Verzeichnis) | bestehende Konvention nutzen (kein Parallel-Ordner) |
| **Q-18** | ADR-006 („keine zusätzlichen Services") ist faktisch überholt (SQS existiert) | Widerspruch zwischen Doku und Code | ADR-008 erklärt KMS/Secrets Manager explizit als zulässige Sicherheitsdienste; ADR-006 als „historisch/überholt" markieren (separate Doku-Korrektur) |
| **Q-19** | Gilt Secrets Manager/KMS als „neuer AWS-Service" mit Freigabepflicht? | ADR-006 sagt „kein Service ohne neue ADR" | **ja** → ADR-008 (PROPOSED) muss freigegeben werden, bevor P-02/P-04 starten |

## F. Betrieb / Tests

| ID | Frage | Optionen | Empfehlung |
|---|---|---|---|
| **Q-20** | Cleanup-Trigger in RC4: Scheduler, Event oder nur manuell? | (a) Scheduler (neue EventBridge-Ressource), (b) rein manuell (interner Invoke), (c) Cognito-Event | **(b)** für RC4 (keine neue Ressource, testbar), Scheduler in RC5 |
| **Q-21** | Wo wird der Lösch-Audit gespeichert? | (a) CloudWatch-Log, (b) Audit-Item in derselben Tabelle (`#AUDIT`-SK), (c) eigene Tabelle | **(b)** — kein neues Modul, abfragbar; PII-frei |
| **Q-22** | Testkonto/Rechte für KMS/Secrets | Testkonto `262370457690` hat evtl. keine KMS/Secrets-Rechte | vor RC4-E2E prüfen (read-only `iam`-Abfrage durch Menschen) |
| **Q-23** | Wie wird „Nutzer existiert nicht" bei EXTERNAL-Cognito behandelt? | (a) unbestimmt → kein Löschen (fail-closed), (b) Consumer meldet Löschung als Ereignis, (c) Löschen nach Frist ohne Prüfung | **(a)+(b)** — nie (c) |

---

## Blockierend (P0) für RC4-Start

**Q-01, Q-03, Q-05, Q-13, Q-16, Q-19**

Alle übrigen Fragen sind für die ersten Implementierungsschritte (Policy-Gate, Secret-Provider
ohne Aktivierung) nicht blockierend, müssen aber vor dem jeweiligen Paket entschieden sein.
