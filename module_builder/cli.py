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

    subparsers.add_parser("presets", help="Verfügbare Presets auflisten")

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Bestehendes Builder-Projekt sicher aktualisieren (dry-run/apply)",
    )
    upgrade_parser.add_argument("--project", required=True,
                                help="Pfad zum bestehenden Builder-Projekt")
    upgrade_parser.add_argument("--source", default=None,
                                help="Quell-Repo-Root (Default: Auto-Erkennung)")
    upgrade_parser.add_argument("--project-name", default=None,
                                help="Erwarteter Projektname (fail-closed bei Abweichung)")
    upgrade_parser.add_argument("--dry-run", action="store_true", default=False,
                                help="Nur diffen, nichts schreiben")
    upgrade_parser.add_argument("--apply", action="store_true", default=False,
                                help="Sichere Aenderungen (ADD/UPDATE_SAFE) anwenden")
    upgrade_parser.add_argument("--adopt-legacy", action="store_true", default=False,
                                help="v1-Manifest adoption: nur bei nachgewiesener "
                                     "Quell-Commit-Gleichheit; keine ungeprueften Dateien")
    return parser


def _git_head(source: Path) -> str:
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _reference_tree(manifest: dict, source: Path, tmp: Path):
    """Generate the reference tree for this manifest (orders-service or preset)."""
    from module_builder.builder import build, build_module

    tree = tmp / "tree"
    preset = manifest.get("preset")
    project_name = manifest["project_name"]
    if preset == "orders-service":
        build_module(target_dir=tree, project_name=project_name,
                     source_root=source, force=True)
    else:
        modules = manifest.get("modules") if preset == "custom" else None
        build(target_dir=tree, project_name=project_name,
              preset_name="complete", source_root=source, force=True,
              modules=modules)
    return tree


def _adopt_legacy(project_dir: Path, manifest: dict, source: Path, tmp: Path,
                  apply: bool) -> int:
    """Legacy (v1) adoption: only files proven identical to the pinned source."""
    import json

    from module_builder.upgrade import _iter_files, sha256_file

    pinned = (manifest.get("source") or {}).get("commit") or ""
    head = _git_head(source)
    if not pinned or pinned != head:
        print("Status: BLOCKED (BUILDER_LEGACY_PIN_MISMATCH)")
        print(f"  Manifest-Quelle: {pinned or '(fehlt)'}")
        print(f"  Ausgecheckter HEAD: {head or '(unbekannt)'}")
        print("  Adoption nur bei identischer Quellversion zulaessig.")
        return 1

    tree = _reference_tree(manifest, source, tmp)
    reference = {rel: sha256_file(tree / rel) for rel in _iter_files(tree)}

    listed = [str(p).replace("\\", "/") for p in manifest.get("files_written", [])]
    adopted, deviations = {}, []
    for rel in listed:
        current = project_dir / rel
        if not current.is_file() or rel not in reference:
            deviations.append((rel, "missing"))
            continue
        if sha256_file(current) == reference[rel]:
            adopted[rel] = reference[rel]
        else:
            deviations.append((rel, "modified"))

    print(f"Status: {'ADOPTED' if not deviations else 'REVIEW_REQUIRED'} "
          f"(BUILDER_LEGACY_ADOPTION)")
    print(f"  Uebernommen: {len(adopted)} Datei(en)")
    for rel, why in deviations:
        print(f"  Abweichung ({why}): {rel} — NICHT uebernommen")

    if not apply:
        print("  Dry-Run: Manifest unveraendert.")
        return 0 if not deviations else 1

    data = dict(manifest)
    data["manifest_version"] = 2
    data["files"] = dict(sorted(adopted.items()))
    data["legacy_adoption"] = {
        "source_commit": pinned,
        "adopted": len(adopted),
        "deviations": [{"path": rel, "reason": why} for rel, why in deviations],
    }
    (project_dir / "module-builder.manifest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("  Manifest v2 geschrieben (nur belegte Dateien).")
    return 0 if not deviations else 1


def _run_upgrade(parsed) -> int:
    """Thin wiring around the existing module_builder.upgrade gates."""
    import tempfile

    from module_builder.upgrade import (
        BLOCKED, CODE_CONFLICT, CODE_LEGACY, CODE_UNVERIFIED, LEGACY_PROJECT,
        MANAGED_PROJECT, READY, apply_upgrade, build_report, decide_status,
        detect_project_status, diff_project, write_report,
    )

    if parsed.dry_run == parsed.apply:
        print("Bitte genau eine der Optionen --dry-run oder --apply angeben.")
        return 2

    project_dir = Path(parsed.project)
    source = Path(parsed.source) if parsed.source else _default_source_root()
    status, manifest, reasons = detect_project_status(
        project_dir, expected_project_name=parsed.project_name)

    if status == LEGACY_PROJECT:
        if not parsed.adopt_legacy:
            print(f"Status: BLOCKED ({CODE_LEGACY})")
            for reason in reasons:
                print(f"  - {reason}")
            return 1
        with tempfile.TemporaryDirectory(prefix="mo-upgrade-legacy-") as tmp:
            return _adopt_legacy(project_dir, manifest, source, Path(tmp),
                                 parsed.apply)

    if status != MANAGED_PROJECT:
        print(f"Status: BLOCKED ({CODE_UNVERIFIED})")
        for reason in reasons:
            print(f"  - {reason}")
        return 1

    if parsed.project_name and parsed.project_name != manifest.get("project_name"):
        print("BUILDER_UPGRADE_CONFIG_CONFLICT: project_name weicht ab.")
        return 1

    with tempfile.TemporaryDirectory(prefix="mo-upgrade-") as tmp:
        tree = _reference_tree(manifest, source, Path(tmp))
        diff = diff_project(project_dir, tree, manifest)
        import json
        new_manifest = json.loads((tree / "module-builder.manifest.json")
                                  .read_text(encoding="utf-8"))
        final_status, code = decide_status(MANAGED_PROJECT, diff)
        print(f"Status: {final_status} ({code})")
        print(f"  Aenderungen: {len(diff.writes)} | Konflikte: {len(diff.conflicts)}")
        for entry in diff.entries:
            if entry.category != "UNCHANGED":
                print(f"  - {entry.category}: {entry.path} — {entry.reason}")

        report = build_report(project_dir=project_dir, manifest=manifest,
                              new_manifest=new_manifest, diff=diff,
                              project_status=MANAGED_PROJECT,
                              status=final_status, code=code,
                              target_version=None)
        json_path, _md = write_report(project_dir, report)
        print(f"Bericht: {json_path}")
        if parsed.apply:
            if final_status != READY:
                print("Kein Apply: Status nicht READY.")
                return 1
            apply_upgrade(project_dir, tree, diff,
                          new_manifest=new_manifest,
                          previous_manifest=manifest)
            print("Upgrade angewendet (nur ADD/UPDATE_SAFE).")
        return 0 if final_status != BLOCKED else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = _create_parser()
    parsed = parser.parse_args(argv)

    if parsed.command == "presets":
        for name, spec in sorted(PRESETS.items()):
            print(f"{name}: {spec['description']}")
        return 0

    if parsed.command == "upgrade":
        return _run_upgrade(parsed)

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
