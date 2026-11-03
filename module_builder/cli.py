"""CLI entry point: python -m module_builder <command> [options].

Commands:
    build     Generate a standalone Terraform deployment into a target folder.
    presets   List available presets.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
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
        help="B1/B2: kommagetrennte Modulauswahl (stabile Modulnamen), z. B. "
             "--modules dynamodb,sqs,iam. Pflichtabhängigkeiten müssen explizit "
             "angegeben werden — außer --with-deps ist gesetzt. Unbekannte/doppelte "
             "Module werden immer abgelehnt. Schließt --preset aus.",
    )
    build_parser.add_argument(
        "--with-deps", action="store_true",
        help="B2: fehlende Pflichtabhängigkeiten automatisch und transitiv "
             "ergänzen (optionale Abhängigkeiten wie sqs für iam/lambda werden "
             "NIEMALS ergänzt). Nur wirksam mit --modules.",
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

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Bestehendes Builder-Projekt kontrolliert aktualisieren (dry-run/apply)",
    )
    upgrade_parser.add_argument("--project", required=True,
                                help="Pfad zum bestehenden Builder-Projekt")
    upgrade_parser.add_argument("--source", default=None,
                                help="Quell-Repo-Root (Default: Auto-Erkennung)")
    upgrade_parser.add_argument("--project-name", default=None,
                                help="Erwarteter Projektname (muss zum Manifest passen)")
    upgrade_parser.add_argument("--target-version", default=None,
                                help="Erwartete Builder-Zielversion (muss der laufenden Version entsprechen)")
    upgrade_parser.add_argument("--dry-run", action="store_true", default=False,
                                help="Nur analysieren und Bericht schreiben (keine Projektdateien aendern)")
    upgrade_parser.add_argument("--apply", action="store_true", default=False,
                                help="Sichere Aenderungen (ADD/UPDATE_SAFE) anwenden und Manifest aktualisieren")
    upgrade_parser.add_argument("--preset", default=None, choices=sorted(PRESETS),
                                help="Nur zur Bestaetigung: muss dem Manifest-Preset entsprechen")
    upgrade_parser.add_argument("--modules", default=None,
                                help="Nur zur Bestaetigung: muss den Manifest-Modulen entsprechen")
    upgrade_parser.add_argument("--with-deps", action="store_true",
                                help="Bei --modules: Pflichtabhaengigkeiten ergaenzen (nur Bestaetigung)")

    subparsers.add_parser("presets", help="Verfügbare Presets auflisten")
    return parser


def _run_upgrade(parsed) -> int:
    """Builder-Upgrade: Dry-Run/Apply mit Manifest-, Diff- und Konfliktpruefung."""
    from module_builder.builder import build
    from module_builder.upgrade import (
        BLOCKED,
        CODE_CONFLICT,
        CODE_LEGACY,
        CODE_UNVERIFIED,
        CONFLICTED_PROJECT,
        LEGACY_PROJECT,
        MANAGED_PROJECT,
        NEW_PROJECT,
        NO_CHANGES,
        READY,
        REVIEW_REQUIRED,
        UNVERIFIED_PROJECT,
        BuilderUpgradeError,
        DiffResult,
        apply_upgrade,
        build_report,
        decide_status,
        detect_project_status,
        diff_project,
        read_manifest,
        write_report,
        MANIFEST_NAME,
    )

    if parsed.dry_run == parsed.apply:
        print("Bitte genau eine der Optionen --dry-run oder --apply angeben.")
        return 2

    project_dir = Path(parsed.project)
    source = Path(parsed.source) if parsed.source else _default_source_root()
    status, manifest, reasons = detect_project_status(
        project_dir, expected_project_name=parsed.project_name
    )

    if parsed.target_version and parsed.target_version != __version__:
        print(
            "BUILDER_TARGET_VERSION_MISMATCH: angefragte Zielversion "
            f"{parsed.target_version} entspricht nicht der laufenden Builder-Version "
            f"{__version__}; es wird keine andere Version generiert."
        )
        return 1

    if status != MANAGED_PROJECT:
        code = {
            LEGACY_PROJECT: CODE_LEGACY,
            NEW_PROJECT: CODE_UNVERIFIED,
            UNVERIFIED_PROJECT: CODE_UNVERIFIED,
            CONFLICTED_PROJECT: CODE_UNVERIFIED,
        }.get(status, CODE_UNVERIFIED)
        if project_dir.exists():
            report = build_report(
                project_dir=project_dir, manifest=manifest or {},
                new_manifest={}, diff=DiffResult(), project_status=status,
                status=BLOCKED, code=code, target_version=parsed.target_version,
            )
            json_path, md_path = write_report(project_dir, report)
            print(f"Status: BLOCKED ({code})")
            print(f"Bericht: {json_path}")
        for reason in reasons:
            print(f"  - {reason}")
        return 1

    # Zielgeneration muss dem Manifest entsprechen (kein stilles Umkonfigurieren).
    manifest_preset = manifest.get("preset")
    manifest_modules = manifest.get("modules") or []
    if parsed.preset and manifest_preset in ("complete", "custom") and parsed.preset != manifest_preset:
        print(
            "BUILDER_UPGRADE_CONFIG_CONFLICT: --preset weicht vom Manifest ab "
            f"({parsed.preset} != {manifest_preset})."
        )
        return 1
    if parsed.modules:
        requested = sorted({m.strip() for m in parsed.modules.split(",") if m.strip()})
        if requested != sorted(manifest_modules):
            print(
                "BUILDER_UPGRADE_CONFIG_CONFLICT: --modules weicht vom Manifest ab."
            )
            return 1

    project_name = manifest["project_name"]
    with tempfile.TemporaryDirectory(prefix="mo-builder-upgrade-") as tmp:
        tree = Path(tmp) / "tree"
        try:
            if manifest_preset == "custom" or manifest_modules:
                build(
                    target_dir=tree,
                    project_name=project_name,
                    preset_name="complete",
                    source_root=source,
                    force=False,
                    modules=manifest_modules,
                )
            else:
                build(
                    target_dir=tree,
                    project_name=project_name,
                    preset_name=manifest_preset or "complete",
                    source_root=source,
                    force=False,
                )
        except SystemExit as exc:
            print(f"Builder-Generierung fehlgeschlagen: {exc}")
            return 1

        new_manifest, state = read_manifest(tree)
        if state != "ok" or not new_manifest:
            print("BUILDER_UPGRADE_CONFLICT: Zielgeneration ohne gueltiges Manifest.")
            return 1

        diff = diff_project(project_dir, tree, manifest)
        status, code = decide_status(MANAGED_PROJECT, diff)
        report = build_report(
            project_dir=project_dir,
            manifest=manifest,
            new_manifest=new_manifest,
            diff=diff,
            project_status=MANAGED_PROJECT,
            status=status,
            code=code,
            target_version=parsed.target_version,
        )
        json_path, md_path = write_report(project_dir, report)

        print(f"Status: {status} ({code})")
        print(f"  Aenderungen: {len(diff.writes)} | Konflikte: {len(diff.conflicts)}")
        print(f"Bericht: {json_path}")

        if status == BLOCKED:
            for conflict in diff.conflicts:
                print(f"  - Konflikt: {conflict.path}: {conflict.reason}")
            return 1

        if parsed.dry_run or status == NO_CHANGES:
            return 0

        try:
            result = apply_upgrade(
                project_dir,
                tree,
                diff,
                new_manifest=new_manifest,
                previous_manifest=manifest,
            )
        except BuilderUpgradeError as exc:
            print(f"{exc.code}: {exc}")
            return 1
        print(f"Angewendet: {len(result['written'])} Datei(en); Manifest aktualisiert.")
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _create_parser()
    parsed = parser.parse_args(argv)

    if parsed.command == "upgrade":
        return _run_upgrade(parsed)

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
        final_modules: List[str] = []
        added_modules: List[str] = []
        requested_modules: List[str] = []

        if preset_name == "orders-service":
            # Orders-Service-Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01):
            # festes 7-Modul-Terraform-MODUL, keine Auswahl, keine Deps-Auflösung.
            from module_builder.builder import build_module
            from module_builder.validation import validate_generated_project

            target = Path(parsed.target)
            source = Path(parsed.source) if parsed.source else _default_source_root()
            result = build_module(
                target_dir=target,
                project_name=parsed.project_name,
                source_root=source,
                force=parsed.force,
            )
            print(f"Build OK: {result.target}")
            print(f"  Preset:      orders-service (Terraform-Modul)")
            print("  Vertrag:     Orders-Service = API+Handler, Worker, SQS, "
                  "DynamoDB, IAM, Cognito (fest, nicht abwählbar)")
            print(f"  Projekt:     {parsed.project_name}")
            if parsed.validate:
                validate_generated_project(result.target)
                print("Validierung:  terraform fmt -check / init -backend=false / "
                      "validate PASS")
            print("\nNutzung als lokales Modul:")
            print(f'  module "orders" {{ source = "{result.target}" project_name = "{parsed.project_name}" }}')
            print("Apply/Destroy ausschließlich nach menschlicher Freigabe.")
            return 0

        if parsed.modules:
            from module_builder.catalog import parse_and_resolve
            requested_modules = [n.strip() for n in parsed.modules.split(",") if n.strip()]
            final_modules, added_modules = parse_and_resolve(parsed.modules, parsed.with_deps)
            modules = final_modules

        target = Path(parsed.target)
        source = Path(parsed.source) if parsed.source else _default_source_root()
        result = build(
            target_dir=target,
            project_name=parsed.project_name,
            preset_name=preset_name,
            source_root=source,
            force=parsed.force,
            modules=modules,
            with_deps=parsed.with_deps,
        )
        print(f"Build OK: {result.target}")
        print(f"  Preset:      {preset_name if modules is None else 'custom (--modules)'}")
        if modules is None:
            pass  # Preset-Build: keine Modul-Blöcke
        elif parsed.with_deps:
            # WP5 — Transparenz: angefragt vs. ergänzt vs. final
            print("Requested modules:")
            for name in requested_modules:
                print(f"  {name}")
            print("Automatically added dependencies:")
            if added_modules:
                for name in added_modules:
                    print(f"  {name}")
            else:
                print("  (keine — Auswahl war bereits abhängigkeitsvollständig)")
            print("Final module selection:")
            print(f"  {', '.join(final_modules)}")
        else:
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
