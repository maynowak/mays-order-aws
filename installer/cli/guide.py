"""``--guide`` support: point users straight at the Installer Guide.

There is no single CLI standard for documentation pointers (``--help`` is
usage only). This project uses an explicit ``--guide`` flag that prints the
guide's location and table of contents, then exits — so the documented
workflow (Abschnitt 5/9a/10 des Guides) is always one flag away.

Read-only: this module never touches AWS, Terraform, or the filesystem in
a mutating way.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

GUIDE_RELATIVE_PATH = "docs/INSTALLER_GUIDE.md"

# installer/cli/guide.py -> parents[2] = repository root
_REPO_ROOT = Path(__file__).resolve().parents[2]


def find_guide_path(start: Optional[Path] = None) -> Path:
    """Resolve the guide path relative to the repo root (CWD fallback)."""
    candidates = [
        _REPO_ROOT / GUIDE_RELATIVE_PATH,
    ]
    if start is not None:
        candidates.insert(0, Path(start) / GUIDE_RELATIVE_PATH)
    else:
        candidates.insert(0, Path.cwd() / GUIDE_RELATIVE_PATH)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def extract_sections(guide_path: Path) -> List[str]:
    """Extract ``## `` section headings from the guide (table of contents)."""
    sections: List[str] = []
    if not guide_path.is_file():
        return sections
    for line in guide_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            sections.append(stripped[3:].strip())
    return sections


def render_guide_info(start: Optional[Path] = None) -> str:
    """Render the human-readable ``--guide`` output."""
    guide_path = find_guide_path(start)
    lines = [
        "Mays-Orders-AWS — Installer-Handbuch",
        "",
        f"  Pfad: {guide_path}",
    ]
    if guide_path.is_file():
        lines.append("  Status: gefunden ✓")
        sections = extract_sections(guide_path)
        if sections:
            lines.append("")
            lines.append("  Inhaltsverzeichnis:")
            for section in sections:
                lines.append(f"    - {section}")
    else:
        lines.append("  Status: NICHT gefunden — Datei fehlt oder Repo unvollständig")
    lines.append("")
    lines.append("  Öffnen:  less docs/INSTALLER_GUIDE.md   (Repo-Root)")
    lines.append("  Workflow: validate → plan → Policy Gate → Freigabe → deploy/destroy")
    lines.append("  Vor jeder Mutation: Konto/Region/Workspace/State/Kollisionen prüfen (Abschnitt 5 + 9a).")
    lines.append("")
    return "\n".join(lines)
