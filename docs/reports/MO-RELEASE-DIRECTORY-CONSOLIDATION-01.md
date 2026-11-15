# MO-RELEASE-DIRECTORY-CONSOLIDATION-01 — Release Directory Inventory

**Status:** `RESULT B — PARTIAL / SAFE PRESERVATION`
**Datum:** 2026-11-15
**Branch:** `docs/mo-release-directory-consolidation-01`
**Base main:** `c291d4a35130b6fdb1bf00f05ad6d67d44de2141`
**Release:** `v0.6.0-rc.1`

## 1. Git-Ausgangsstand

- `main` @ `c291d4a35130b6fdb1bf00f05ad6d67d44de2141`
- Remote `origin/main` @ identisch
- Working Tree: clean
- Worktrees: 2
- Release-Tag `v0.6.0-rc.1` unverändert auf
  `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`
- Neuer Arbeitsbranch von `main`: `docs/mo-release-directory-consolidation-01`
- Keine neuen Worktrees oder Klone

## 2. Inventar `docs/release/`

Legende: `Refs` = Treffer mit dem vollständigen Pfad inklusive der Datei selbst.
Entscheidung bezieht sich auf **diesen** Branch.

| Datei | Typ | Vorgeschlagener Zielpfad | Refs | Entscheidung | Begründung |
|---|---|---|---:|---|---|
| `RELEASE-v0.4.0.md` | offizielles Release-Dokument | bleiben | 2 | behalten | historische Release-Konvention; enthält relative Bildpfade |
| `RELEASE-v0.4.0.pdf` | offizielles Release-PDF | bleiben | 1 | behalten | veröffentlichtes Release-Artefakt |
| `RELEASE-v0.5.0-rc.1.md` | offizielles Release-Dokument | bleiben | 1 | behalten | historische Release-Konvention |
| `RELEASE-v0.5.0-rc.1.pdf` | offizielles Release-PDF | bleiben | 0 | behalten | veröffentlichtes Release-Artefakt |
| `RELEASE-v0.5.0-rc.2.md` | offizielles Release-Dokument | bleiben | 4 | behalten | historische Release-Konvention |
| `RELEASE-v0.5.0-rc.2.pdf` | offizielles Release-PDF | bleiben | 0 | behalten | veröffentlichtes Release-Artefakt |
| `RELEASE-v0.5.0-rc.2-COVER.png` | Release-Asset | `docs/release/img/` | 0 | behalten | wird relativ von `RELEASE-v0.5.0-rc.2.md` geladen; Verschieben würde historische Release-Doku brechen |
| `RELEASE-v0.5.0-rc.3.md` | offizielles Release-Dokument | bleiben | 6 | behalten | historische Release-Konvention |
| `RELEASE-v0.5.0-rc.3.pdf` | offizielles Release-PDF | bleiben | 2 | behalten | veröffentlichtes Release-Artefakt |
| `RELEASE-v0.6.0-rc.1.md` | offizielles Release-Dokument | bleiben | 5 | behalten | kanonische aktuelle Release-Datei mit Post-Merge-Addendum |
| `RELEASE-v0.6.0-rc.1.pdf` | offizielles Release-PDF | bleiben | 4 | behalten | kanonisches aktuelles Release-Artefakt |
| `RELEASE-GATES-v0.5.0-rc.3.md` | Release-Gate-Begleitdokument | `docs/reports/` | 7 | behalten | von CHANGELOG/RELEASE_NOTES und historischen Berichten referenziert; Teil der Release-Evidenz |
| `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` | technisches Detailpaket | bleiben | 5 | behalten | GitHub-Release-Asset; Entfernen/Ersetzen nur mit separater Freigabe |
| `RC4-MODULE-RELEASE-CANDIDATE.md` | technisches Release-Dossier | `docs/reports/` | 7 | behalten | aktuelle README-/Release-Notes-Referenz plus historische Berichte |
| `RC4-INTEGRATION-MANIFEST.md` | Integrations-/Release-Manifest | `docs/reports/` | 9 | behalten | historische Integrationsnachweise referenzieren den Pfad |
| `MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` | interne ADR-/Contract-Analyse | `docs/reports/` | 5 | behalten | ausschließlich historische Audit-/Report-Referenzen |
| `MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` | interne Entscheidungs-/Amendment-Vorlage | `docs/reports/` | 3 | behalten | historische Reports referenzieren den Pfad |
| `MO-RC4-P00-DECISION-REGISTER.md` | Decision Register | `docs/adr/` oder `docs/reports/` | 11 | behalten, gesondert prüfen | Zielkategorie nicht eindeutig; historische Architektur-/Report-Referenzen |
| `MO-RC4-P00-DEPENDENCY-GRAPH.md` | internes Planungsartefakt | `docs/roadmap/` | 4 | behalten | historische Reports referenzieren den Pfad |
| `MO-RC4-P00-EXECUTION-PLAN.md` | interner Execution Plan | `docs/roadmap/` | 7 | behalten | historische Reports referenzieren den Pfad |
| `MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` | interner Backlog | `docs/roadmap/` | 8 | behalten | historische Reports referenzieren den Pfad |
| `img/ChatGPT Image 14. Sept. 2026, 15_54_35.png` | Release-Asset | `docs/assets/` | 1 | behalten | bestehendes Release-Asset-Verzeichnis; keine aktuelle Release-Doku verweist darauf |
| `img/mays-orders-release-overview.png` | **fehlend** | — | — | offener Punkt | wird von `RELEASE-v0.4.0.md` referenziert, ist aber nicht im Checkout |
| `img/mays-orders-architecture.png` | **fehlend** | — | — | offener Punkt | dito |
| `img/mays-orders-e2e-flow.png` | **fehlend** | — | — | offener Punkt | dito |
| `img/mays-orders-project-journey.png` | **fehlend** | — | — | offener Punkt | dito |
| `img/mays-orders-ecosystem.png` | **fehlend** | — | — | offener Punkt | dito |

## 3. Tatsächlich verschobene Dateien

**Keine.** Es wurden keine Dateien verschoben, umbenannt oder gelöscht.

Grund: Jede interne Datei mit einer vorgeschlagenen neuen Kategorie wird von
mindestens einem historischen Report oder Auditlog über den bestehenden Pfad
referenziert. Nach der Vorgabe „historische Auditlogs und Reports nicht
umschreiben“ und „bei historischem Pfadbedarf am bisherigen Ort belassen“ wurde
keine Pfadänderung erzwungen.

## 4. Referenzprüfung

- README-Links: **gültig**
- Neue/aktuelle Release-Referenzen: **gültig**
- Release-Dateien unter `docs/release/`: keine durch diese Aufgabe neu
  gebrochenen Links
- **Vorbestehender Befund:** `RELEASE-v0.4.0.md` referenziert fünf nicht
  vorhandene Bilder unter `docs/release/img/`. Dieser Befund bestand vor dieser
  Aufgabe und wurde nicht verändert.
- `RELEASE-v0.6.0-rc.1.md` und `.pdf`: kanonische Dateien vorhanden
- `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf`: technisches Detailpaket vorhanden
- GitHub-Release-Asset und Release-Body: **unverändert**
- Release-Tag: **unverändert**

## 5. Offene Zuordnungsfragen

1. Soll das Decision Register nach `docs/adr/` oder `docs/reports/` wandern?
2. Sollen die P00-Planungsdokumente nach `docs/roadmap/` wandern, obwohl
   historische Reports dann alte Pfade nennen?
3. Sollen `RC4-MODULE-RELEASE-CANDIDATE.md` und
   `RC4-INTEGRATION-MANIFEST.md` als technische Release-Dossiers im
   Release-Verzeichnis bleiben?
4. Sollen die fehlenden v0.4.0-Bilder aus einem externen Archiv ergänzt werden?
5. Soll das GitHub-Release-Asset später gegen das kanonische Release-PDF
   ausgetauscht werden? Dafür ist eine separate Freigabe erforderlich.

## 6. Ergebnis

**B — PARTIAL:** Das Inventar, die Klassifizierung und die Referenzprüfung sind
vollständig. Sichere Dateiverschiebungen wurden nicht erzwungen, weil alle
Kandidaten historische Pfadreferenzen besitzen. Das Release-Verzeichnis bleibt
funktional und nachvollziehbar; keine Daten wurden verändert.

## 7. Git

- Arbeitsbranch: `docs/mo-release-directory-consolidation-01`
- Keine Produktcode-/Terraform-/AWS-/CI-Änderung
- Kein Tag, kein GitHub-Release, kein Main-Merge
- Branch wird regulär gepusht; Main-Merge separat freizugeben
