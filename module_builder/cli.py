"""CLI entry point: python -m module_builder <command> [options].

Commands:
    build     Generate a standalone Terraform deployment into a target folder.
    presets   List available presets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from module_builder import __version__
from module_builder.spec import PRESETS


def _default_source_root() -> Path:
    """Repo root that contains this package (module_builder/ lives at top level)."""
    return Path(__file__).resolve().parents[1]


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m module_builder",
        description="Mays-Orders-AWS Terraform Module Builder — erzeugt eine "
                    "eigenständige Terraform-Bereitstellung aus den bestehenden "
                    "Komponenten (kein GitHub-Sourcing, keine Abhängigkeit zum "
                    "Quell-Repository).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser(
        "build", help="Standalone-Bereitstellung in Zielordner generieren"
    )
    build_parser.add_argument(
        "--target", required=True,
        help="Zielordner (z. B. ./generated/my-orders)",
    )
    build_parser.add_argument(
        "--project-name", required=True,
        help="Projektname (Kleinbuchstaben/Ziffern/Bindestrich, mind. 3 Zeichen)",
    )
    build_parser.add_argument(
        "--preset", default=None, choices=sorted(PRESETS),
        help="Preset (MVP: nur 'complete'); gegenseitig ausschließend zu --modules",
    )
    build_parser.add_argument(
        "--modules", default=None,
        help="B1: kommagetrennte Modulauswahl (stabile Modulnamen), z. B. "
             "--modules dynamodb,sqs,iam. Pflichtabhängigkeiten müssen explizit "
             "angegeben werden (keine automatische Ergänzung); unbekannte/doppelte "
             "Module werden abgelehnt. Schließt --preset aus.",
    )
    build_parser.add_argument(
        "--source", default=None,
        help="Quell-Repo-Root (Default: Auto-Erkennung relativ zum Builder-Paket)",
    )
    build_parser.add_argument(
        "--force", action="store_true",
        help="Bestehende Builder-eigene Dateien im Zielordner überschreiben "
             "(löscht niemals fremde Dateien; ohne --force wird ein "
             "nicht-leerer Zielordner abgelehnt)",
    )
    build_parser.add_argument(
        "--validate", action="store_true",
        help="Nach dem Build terraform fmt -check, init -backend=false und "
             "validate ausführen (read-only; kein AWS-Kontakt)",
    )

    subparsers.add_parser("presets", help="Verfügbare Presets auflisten")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _create_parser()
    parsed = parser.parse_args(argv)

    if parsed.command == "presets":
        for name, spec in sorted(PRESETS.items()):
            print(f"{name}: {spec['description']}")
        return 0

    if parsed.command == "build":
        from module_builder.builder import build
        from module_builder.validation import validate_generated_project

        if parsed.preset and parsed.modules:
            parser.error("--preset und --modules schließen sich gegenseitig aus.")
        preset_name = parsed.preset or "complete"
        modules = None
        if parsed.modules:
            from module_builder.catalog import parse_module_selection
            modules = parse_module_selection(parsed.modules)

        target = Path(parsed.target)
        source = Path(parsed.source) if parsed.source else _default_source_root()
        result = build(
            target_dir=target,
            project_name=parsed.project_name,
            preset_name=preset_name,
            source_root=source,
            force=parsed.force,
            modules=modules,
        )
        print(f"Build OK: {result.target}")
        print(f"  Preset:      {preset_name if modules is None else 'custom (--modules)'}")
        if modules is not None:
            print(f"  Module:      {', '.join(sorted(modules))}")
        print(f"  Projekt:     {parsed.project_name}")
        print(f"  Dateien:     {len(result.files)}")
        for artifact, digest in sorted(result.artifacts.items()):
            print(f"  Artefakt:    {artifact} (sha256 {digest[:16]}…)")
        if parsed.validate:
            validate_generated_project(result.target / "terraform")
            print("Validierung:  terraform fmt -check / init -backend=false / "
                  "validate PASS")
        print("\nNächste Schritte (read-only):")
        print(f"  cd {result.target / 'terraform'}")
        print("  terraform init -backend=false && terraform validate")
        print("Apply/Destroy ausschließlich nach menschlicher Freigabe.")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
