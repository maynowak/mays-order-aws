# Mays-Orders-AWS — Release v0.5.0-rc.1

**Release-Typ:** Release Candidate / Pre-release  
**Datum:** 11. Oktober 2026  
**Git-Tag:** `v0.5.0-rc.1`  
**Codebasis:** `f6e737b`  
**Status:** Technischer Release Candidate; produktive Privacy-Aktivierung **BLOCKED**

> **Dokumentationsgrundlage:** [`docs/release/RELEASE-v0.5.0-rc.1.md`](https://github.com/maynowak/mays-order-aws/blob/main/docs/release/RELEASE-v0.5.0-rc.1.md) im Repository, abgerufen am 11.10.2026. Diese Fassung entspricht inhaltlich dem begleitenden PDF und ergänzt einen ausdrücklichen Evidenzhinweis.

## Release-Überblick

Der Release Candidate `v0.5.0-rc.1` basiert auf Commit `f6e737b`. Er bleibt eine Testversion, solange das Secret-Management nicht produktiv aktiviert ist.

## Funktionsumfang und Highlights

- Interne Privacy-Funktionen: `inspect_subject`, `export_subject` und `erase_subject`.
- Installer-Härtung, Artifact Integrity Gate und Terraform Policy Gate.
- Keine öffentliche Privacy-API-Route.
- Produktive Privacy-Aktivierung: **BLOCKED** (dauerhafte Secret-Verwaltung fehlt).

## Verifikationsstand

| Prüfung | Dokumentierter Status |
|---|---|
| Lambda Unit Tests | **76 PASS** |
| Installer Unit Tests | **81 PASS** |
| Artifact Integrity | **5 PASS** |
| Terraform `fmt` / `validate` | **PASS** |
| Historische Privacy-E2E-Tests `P-01` / `P-02` / `P-03` | **VERIFIED** |
| Isolierter Destroy | **37 Ressourcen entfernt; Terraform-State leer** |

## Dokumentation und Nachweise

- [Release Notes](https://github.com/maynowak/mays-order-aws/blob/main/docs/RELEASE_NOTES.md) — `docs/RELEASE_NOTES.md`
- [Product Overview](https://github.com/maynowak/mays-order-aws/blob/main/docs/PRODUCT_OVERVIEW.md) — `docs/PRODUCT_OVERVIEW.md`
- [Installer Guide](https://github.com/maynowak/mays-order-aws/blob/main/docs/INSTALLER_GUIDE.md) — `docs/INSTALLER_GUIDE.md`
- [Release-Candidate-Hardening-Report](https://github.com/maynowak/mays-order-aws/blob/main/docs/reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md) — `docs/reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md`
- [Privacy-Destroy- und Release-Nachweis](https://github.com/maynowak/mays-order-aws/blob/main/docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md) — `docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md`

## Bekannte Einschränkungen

- Dauerhafte Secret-Verwaltung und Secret-Rotation sind nicht implementiert.
- **Production Privacy Activation bleibt BLOCKED.**
- Ein `v0.5.0-rc.2` ist laut Quelldokument nur bei neuen Security-Funktionen sinnvoll.

## Hinweis zur Evidenz

Die genannten Tests und AWS-E2E-Nachweise sind dokumentierte Ergebnisse früherer Prüfungen. Die Erstellung dieses Dokuments führt **keine neuen Tests oder AWS-Deployments** aus. Markdown und PDF sind lesbare Ausgaben des vorhandenen Release-Standes, **keine neue Freigabe für den Produktivbetrieb**.

---

*Mays-Orders-AWS · v0.5.0-rc.1 · PRE-RELEASE*
