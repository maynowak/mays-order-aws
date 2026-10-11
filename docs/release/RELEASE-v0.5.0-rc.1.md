# Release v0.5.0‑rc.1

**Date:** 2026‑10‑11

## Overview
Release Candidate v0.5.0‑rc.1 basierte auf Commit f6e737b und bleibt als Testversion solange das Secret‑Management nicht produktiv aktiviert ist.

## Highlights
- Interne Privacy‑Funktionen (`inspect_subject`, `export_subject`, `erase_subject`)
- Installer‑Härtung, Artifact Integrity Gate, Terraform Policy Gate
- Keine öffentliche Privacy‑API‑Route
- Produktionen‑Privacy‑Aktivierung **BLOCKED** (keine dauerhafte Secret‑Verwaltung vorhanden)

## Tests
- Lambda Unit Tests 76 PASS
- Installer Unit Tests 81 PASS
- Artifact Integrity 5 PASS
- Terraform fmt / validate PASS
- Historische Privacy‑E2E (P‑01 / P‑02 / P‑03) VERIFIED
- Destroy 37 Ressourcen entfernt, State leer

## Documentation
- [Release Notes](../RELEASE_NOTES.md)
- [Product Overview](../PRODUCT_OVERVIEW.md)
- [Installer Guide](../INSTALLER_GUIDE.md)
- [Release‑Candidate‑Report](../reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md)
- [Destroy‑Nachweis](../reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md)

---
**Bekannte Einschränkungen:**
- Dauerhafte Secret‑Verwaltung/Rotation nicht implementiert.
- Production‑Privacy‑Activation bleibt BLOCKED.
- Ein Release v0.5.0‑rc.2 ist nur bei Implementierung neuer Security‑Funktionen sinnvoll.
