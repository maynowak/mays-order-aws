"""MO-INSTALLER-UPGRADE-VERSIONING-P0B-01: Quellcode-Identitaet.

Ermittelt den Git-Commit des tatsaechlich verwendeten MO-Quellcodes sowie den
Dirty-Zustand des Working Trees. Es wird nie eine Commit-SHA erfunden:

- fehlende Git-Metadaten (kein .git, kein git-Binary) => ``available=False``
- detached HEAD wird unterstuetzt (``rev-parse HEAD``)
- Dirty-Erkennung bezieht sich auf **getrackte** Aenderungen
  (``--untracked-files=no``); neue, noch nicht getrackte Dateien aendern den
  ausgefuehrten Code nicht und werden daher nicht als dirty gewertet.

Kein AWS-, Terraform- oder Netzwerkzugriff.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class SourceIdentity:
    """Identitaet des ausgefuehrten Quellcodes."""

    available: bool
    commit: Optional[str] = None
    dirty: Optional[bool] = None
    detached: Optional[bool] = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "commit": self.commit,
            "dirty": self.dirty,
            "detached": self.detached,
            "reason": self.reason,
        }


def default_repo_root() -> Path:
    """Repository-Wurzel relativ zum Installer-Paket (nicht CWD)."""
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, args, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def resolve_source_identity(repo_root: Optional[Path] = None) -> SourceIdentity:
    """Lies Commit/Dirty-Status aus dem lokalen Repository (fail-closed)."""
    root = Path(repo_root) if repo_root is not None else default_repo_root()
    if not root.exists():
        return SourceIdentity(available=False, reason=f"Repository nicht gefunden: {root}")

    try:
        head = _git(root, ["rev-parse", "HEAD"])
    except (OSError, subprocess.SubprocessError) as exc:
        return SourceIdentity(available=False, reason=f"git nicht verfuegbar: {exc}")

    if head.returncode != 0:
        return SourceIdentity(
            available=False,
            reason=f"git rev-parse HEAD fehlgeschlagen: {head.stderr.strip()[:200]}",
        )

    commit = head.stdout.strip()
    if not _COMMIT_RE.match(commit):
        return SourceIdentity(
            available=False,
            reason=f"Unerwartete Commit-SHA: {commit!r}",
        )

    try:
        status = _git(root, ["status", "--porcelain", "--untracked-files=no"])
        symbolic = _git(root, ["symbolic-ref", "-q", "HEAD"])
    except (OSError, subprocess.SubprocessError) as exc:
        return SourceIdentity(available=False, reason=f"git status fehlgeschlagen: {exc}")

    if status.returncode != 0:
        return SourceIdentity(
            available=False,
            reason=f"git status fehlgeschlagen: {status.stderr.strip()[:200]}",
        )

    return SourceIdentity(
        available=True,
        commit=commit,
        dirty=bool(status.stdout.strip()),
        detached=symbolic.returncode != 0,
    )
