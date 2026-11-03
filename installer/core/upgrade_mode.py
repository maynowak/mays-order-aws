"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Upgrade-Modus.

Kleine, zentrale Vorpruefung fuer `plan --upgrade`:

- Upgrade erfordert einen Remote-Plan (State-Bezug).
- Upgrade erfordert eine vorhandene Installation (verifizierter oder als
  LEGACY_UNKNOWN erkannter State) — kein Upgrade aus dem Nichts.
- Ein unlesbarer State bleibt ein Fehler und wird nicht als Neuinstallation
  behandelt.

Keine AWS-Operation, keine Migration, kein Apply.
"""

from __future__ import annotations

CODE_OK = "OK"
CODE_REQUIRES_REMOTE = "UPGRADE_REQUIRES_REMOTE"
CODE_MISSING_INSTALLATION = "UPGRADE_SOURCE_INSTALLATION_MISSING"
CODE_STATE_UNREADABLE = "UPGRADE_STATE_UNREADABLE"

VERIFIED = "VERIFIED"
LEGACY_UNKNOWN = "LEGACY_UNKNOWN"
UNVERIFIED = "UNVERIFIED"
UNREADABLE = "UNREADABLE"


def check_upgrade_source(installed, *, remote: bool) -> tuple[bool, str, str]:
    """Prueft, ob ein Upgrade fuer die erkannte Installation zulaessig ist."""
    if not remote:
        return (
            False,
            CODE_REQUIRES_REMOTE,
            f"{CODE_REQUIRES_REMOTE}: Ein Upgrade benoetigt einen Remote-Plan "
            "(State-Bezug); bitte `plan --remote --upgrade` verwenden.",
        )
    if installed is None:
        return (
            False,
            CODE_MISSING_INSTALLATION,
            f"{CODE_MISSING_INSTALLATION}: Keine bestehende Installation erkannt.",
        )
    if installed.status == UNREADABLE:
        return (
            False,
            CODE_STATE_UNREADABLE,
            f"{CODE_STATE_UNREADABLE}: Der installierte State ist nicht lesbar; "
            "ein Upgrade ist blockiert (keine Neuinstallations-Annahme).",
        )
    if installed.status == UNVERIFIED:
        return (
            False,
            CODE_MISSING_INSTALLATION,
            f"{CODE_MISSING_INSTALLATION}: Kein bestehender State/Ressourcen "
            "gefunden — ein Upgrade ohne Installation ist nicht zulaessig.",
        )
    return (True, CODE_OK, "")
