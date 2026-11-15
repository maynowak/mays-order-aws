# MO-RC4-RELEASE-PACKAGE-FINAL-01 — GitHub Release Package

**Status:** `RESULT A — RELEASE PACKAGE PUBLISHED`
**Datum:** 2026-11-15
**Release:** `v0.6.0-rc.1`
**Repository:** `maynowak/mays-order-aws`
**Branch:** `release/rc4-integration`

## 1. Release-Paket

| Element | Wert |
|---|---|
| README | `README.md` |
| Release Notes | `docs/RELEASE_NOTES.md` |
| Changelog | `docs/CHANGELOG.md` |
| Release Candidate Dossier | `docs/release/RC4-MODULE-RELEASE-CANDIDATE.md` |
| Integration Manifest | `docs/release/RC4-INTEGRATION-MANIFEST.md` |
| Hero-Bild | `docs/assets/mays-orders-aws-rc4-hero.png` |
| PDF | `docs/release/MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` |
| GitHub Release | `https://github.com/maynowak/mays-order-aws/releases/tag/v0.6.0-rc.1` |

## 2. PDF

Das PDF wurde aus dem konsolidierten Release-Notes-Inhalt erstellt und mit dem
Hero-Bild gestaltet.

- Format: A4, 7 Seiten
- Größe: 3.668.656 Bytes
- SHA-256:
  `968a9276617f681e1534f60855de19c6a51889a3346c02907392df2a945438da`
- GitHub-Release-Asset: `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf`
- Download-Hash mit dem lokalen PDF verifiziert

## 3. GitHub Release

- Tag: `v0.6.0-rc.1` (bereits vorhanden, **nicht verschoben**)
- Tag-Objekt: `79628819717e4609d828581dff53055f2b32f8ec`
- Tag-Ziel: `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`
- Release-Name: `Mays-Orders-AWS v0.6.0-rc.1`
- Status: Pre-Release, veröffentlicht
- Beschreibung: `docs/RELEASE_NOTES.md`
- PDF als Asset angehängt
- Release-Beschreibung enthält die ausdrückliche Tag-Abgrenzung:
  README, PDF und spätere Dokumentationscommits sind Post-Tag-Dokumentation
  und nicht Bestandteil des getaggten Quellstands.

## 4. Versionen

| Komponente | Version |
|---|---|
| RC4 Release Label | `v0.6.0-rc.1` |
| Module Builder | `0.1.0` |
| Installer | `0.1.0` |
| Deployment-/Teststack | `0.2.0` |

## 5. Hausaufgabenprüfung

- README auf GitHub: **HTTP 200**, sichtbar
- Hero-Bild raw: **HTTP 200**, `image/png`, 2.233.800 Bytes
- Release Notes im Release-Body: **vorhanden**
- Tag-Abgrenzung im Release-Body: **vorhanden**
- PDF-Asset: **vorhanden und hashgleich**
- Tag unverändert: **ja**
- `main`: unverändert `f597d14`
- Working Tree nach Commit: **clean**
- Keine AWS-Aufrufe, kein Terraform Apply, kein Deployment, kein Main-Merge

## 6. Commits

- Paket-Commit: `a007c2047142a9d44d9c8faa689df133a2804e87`
- Audit-/Abschluss-Commit: dieser Commit
- Remote-Branch wird nach diesem Commit synchronisiert.

## 7. Offene Punkte

- Main-Merge bleibt separat freizugeben.
- Produktive Aktivierung, Retention und P00-F-Betriebsaktivität bleiben
  separat gesperrt.
- Der GitHub-Release beschreibt den getaggten Stand korrekt; die späteren
  README-/PDF-Dokumente sind ausdrücklich als Post-Tag-Paket gekennzeichnet.

**Ergebnis A:** README, Release Notes, Hero-Bild, PDF und GitHub-Release sind
veröffentlicht.
