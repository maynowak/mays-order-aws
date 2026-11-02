"""MO-RC4-P02I-E2B: Remote-Plan-Vertrag (Backend, Identity, Artefaktpfad).

Der kontrollierte Remote-Plan ist ein eigener, ausdruecklicher Modus:
er nutzt das konfigurierte S3-Backend, den Workspace = project_name und
erzeugt ein gespeichertes Plan-Artefakt. Er fuehrt niemals ein Apply aus.

Dieses Modul kapselt die *lokale* (nicht-AWS) Vertragspruefung:
- Backend-Konfiguration aus terraform/backend.tf lesen und validieren.
- State-Key deterministisch ableiten.
- Voraussetzungen fuer einen Remote-Plan fail-closed pruefen.
- Ausgabepfad des Plan-Artefakts aufloesen (Identitaetsbindung erhalten).

Kein Terraform-Aufruf, keine AWS-Operation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class BackendContractError(RuntimeError):
    """Backend-Konfiguration ist nicht eindeutig oder nicht lesbar."""


class PlanOutputError(RuntimeError):
    """Der angeforderte Plan-Ausgabepfad ist ungueltig."""


_BACKEND_BLOCK_RE = re.compile(r'backend\s+"([^"]+)"\s*\{', re.MULTILINE)
_STRING_ATTR_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*=\s*"([^"]*)"\s*$', re.MULTILINE)
_BOOL_ATTR_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*=\s*(true|false)\s*$', re.MULTILINE)
_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class BackendContract:
    """Effektiver Terraform-Backend-Vertrag aus dem Repository."""

    backend_type: str
    bucket: str
    key: str
    region: str
    workspace_key_prefix: str = ""
    dynamodb_table: Optional[str] = None
    use_lockfile: bool = False
    encrypt: bool = False

    def state_key(self, workspace: str) -> str:
        """Terraform-State-Key fuer einen Workspace.

        `workspace_key_prefix = "env:"` + Workspace `x` + key `terraform.tfstate`
        ergibt ``env:/x/terraform.tfstate`` (Terraform-Semantik).
        """
        if workspace == "default" or not self.workspace_key_prefix:
            return self.key
        return f"{self.workspace_key_prefix}/{workspace}/{self.key}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def comparison_dict(self) -> Dict[str, Any]:
        """Identitaetsfelder, die in einem Plan-Manifest gebunden werden."""
        return {
            "type": self.backend_type,
            "bucket": self.bucket,
            "key": self.key,
            "region": self.region,
            "workspace_key_prefix": self.workspace_key_prefix,
        }


def _extract_block(text: str, match: re.Match) -> str:
    """Return the braced body of a Terraform block starting at `match`."""
    start = match.end() - 1  # at "{"
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    raise BackendContractError("Backend-Block ist nicht geschlossen.")


def parse_backend_contract(backend_tf_text: str) -> BackendContract:
    """Parse `terraform/backend.tf` (nur S3-Backend wird unterstuetzt)."""
    match = _BACKEND_BLOCK_RE.search(backend_tf_text)
    if not match:
        raise BackendContractError(
            "Kein `backend`-Block in terraform/backend.tf gefunden. "
            "Ein Remote-Plan ohne explizites Backend ist nicht zulaessig."
        )
    backend_type = match.group(1)
    if backend_type != "s3":
        raise BackendContractError(
            f"Backend-Typ '{backend_type}' wird fuer den Remote-Plan nicht unterstuetzt "
            "(erwartet: s3)."
        )

    body = _extract_block(backend_tf_text, match)
    strings = {k: v for k, v in _STRING_ATTR_RE.findall(body)}
    booleans = {k: v == "true" for k, v in _BOOL_ATTR_RE.findall(body)}

    required = ("bucket", "key", "region")
    missing = [name for name in required if not strings.get(name)]
    if missing:
        raise BackendContractError(
            "S3-Backend unvollstaendig: fehlende Pflichtfelder " + ", ".join(missing)
        )

    return BackendContract(
        backend_type=backend_type,
        bucket=strings["bucket"],
        key=strings["key"],
        region=strings["region"],
        workspace_key_prefix=strings.get("workspace_key_prefix", ""),
        dynamodb_table=strings.get("dynamodb_table") or None,
        use_lockfile=booleans.get("use_lockfile", False),
        encrypt=booleans.get("encrypt", False),
    )


def load_backend_contract(terraform_dir: str | Path) -> BackendContract:
    """Lies den Backend-Vertrag aus `<terraform_dir>/backend.tf`."""
    path = Path(terraform_dir) / "backend.tf"
    if not path.exists():
        raise BackendContractError(f"terraform/backend.tf nicht gefunden: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive
        raise BackendContractError(f"terraform/backend.tf nicht lesbar: {exc}") from exc
    return parse_backend_contract(text)


def validate_remote_plan(
    contract: BackendContract,
    *,
    project_name: str,
    environment: str,
    region: str,
    workspace: str,
    project_name_explicit: bool,
    environment_explicit: bool,
    output_explicit: bool,
    operation: str = "deploy",
) -> List[str]:
    """Fail-closed Voraussetzungen fuer einen kontrollierten Remote-Plan.

    Gibt eine Liste von Fehlern zurueck (leer = zulaessig). Es wird nichts
    ausgefuehrt, keine AWS-Abfrage gemacht.
    """
    errors: List[str] = []

    if not project_name_explicit:
        errors.append(
            "--project-name muss fuer einen Remote-Plan ausdruecklich angegeben werden "
            "(kein Default, keine Environment-Ableitung)."
        )
    if not environment_explicit:
        errors.append(
            "--environment muss fuer einen Remote-Plan ausdruecklich angegeben werden."
        )
    if not output_explicit:
        errors.append(
            "--out muss fuer einen Remote-Plan ausdruecklich angegeben werden "
            "(Pfad oder Verzeichnis fuer das Plan-Artefakt)."
        )

    if not project_name or not _PROJECT_NAME_RE.match(project_name):
        errors.append(
            f"Ungueltiger project_name '{project_name}': erlaubt sind Kleinbuchstaben, "
            "Ziffern und Bindestriche (kein fuehrender/trailender Bindestrich)."
        )
    if not environment:
        errors.append("Environment darf nicht leer sein.")

    if workspace == "default":
        errors.append(
            "Workspace 'default' ist fuer einen projektisolierten Remote-Plan nicht zulaessig."
        )
    elif workspace != project_name:
        errors.append(
            f"Workspace '{workspace}' muss dem Projektnamen '{project_name}' entsprechen "
            "(project_name == terraform_workspace)."
        )

    if region != contract.region:
        errors.append(
            f"Region '{region}' weicht von der Backend-Region '{contract.region}' ab "
            "(ein Plan darf nicht gegen ein anderes Backend-Ziel laufen)."
        )

    if not contract.encrypt:
        errors.append(
            "S3-Backend ohne `encrypt = true` ist fuer den Remote-Plan nicht zulaessig."
        )

    if not contract.dynamodb_table and not contract.use_lockfile:
        errors.append(
            "Kein State-Locking konfiguriert: `dynamodb_table` oder `use_lockfile = true` "
            "ist fuer einen kontrollierten Remote-Plan erforderlich."
        )

    if operation not in ("deploy", "destroy"):
        errors.append(f"Unbekannte Plan-Operation '{operation}'.")

    return errors


def resolve_plan_output(
    terraform_dir: str | Path,
    out_value: Optional[str],
    canonical_filename: str,
    expected_metadata=None,
) -> Path:
    """Loest `--out` in einen konkreten Plan-Pfad auf.

    - fehlt/leer: kanonischer Name im Terraform-Verzeichnis
    - endet auf `.tfplan`: Dateiname muss die Deployment-Identitaet tragen
      (PlanMetadata-Format) und zur erwarteten Identitaet passen
    - sonst: als Verzeichnis behandelt, kanonischer Name darin

    Ein abweichender/unparsebarer Dateiname wird abgelehnt, damit die
    Identitaetsbindung ueber den Dateinamen nicht verloren geht.
    """
    from installer.core.deployment_identity import PlanMetadata

    base = Path(terraform_dir)
    if not out_value:
        return (base / canonical_filename).resolve()

    candidate = Path(out_value)
    if candidate.suffix == ".tfplan":
        parsed = PlanMetadata.parse_filename(candidate.name)
        if parsed is None:
            raise PlanOutputError(
                f"--out '{out_value}' ist kein gueltiger Plan-Dateiname. Erwartet wird das "
                "Identitaetsformat <project>-<environment>-<version>-<phase>-<account>-"
                "<operation>-<sequence>.tfplan (oder ein Verzeichnis)."
            )
        if expected_metadata is not None and not parsed.matches_deployment(
            expected_metadata.deployment_id
        ):
            raise PlanOutputError(
                f"--out '{out_value}' traegt eine fremde Deployment-Identitaet "
                f"({parsed.deployment_id})."
            )
        if expected_metadata is not None and parsed.operation != expected_metadata.operation:
            raise PlanOutputError(
                f"--out '{out_value}' traegt die Operation '{parsed.operation.value}', "
                f"erwartet '{expected_metadata.operation.value}'."
            )
        return (candidate if candidate.is_absolute() else (base / candidate)).resolve()

    directory = candidate if candidate.is_absolute() else (base / candidate)
    return (directory / canonical_filename).resolve()
