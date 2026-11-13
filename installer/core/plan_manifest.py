"""MO-RC4-P02I-E2B: Plan-Manifest (Identitaetsbindung des Plan-Artefakts).

Ein kontrollierter Remote-Plan wird zusammen mit einem kleinen Manifest
gespeichert, das die Identitaet des Artefakts bindet:

    Plan-Datei  +  Manifest (Identitaet, Backend, Checksumme)

`apply`/`destroy` pruefen das Manifest gegen den aktuellen Kontext, bevor
ein Plan angewendet wird. So kann ein Plan nicht versehentlich gegen ein
anderes Projekt, einen anderen Account, eine andere Region oder ein anderes
Backend laufen.

Sicherheit:
- Das Manifest enthaelt KEINE Secrets und keine Variablenwerte ausser einer
  kleinen, festen Identitaets-Whitelist.
- Es werden keine Plan-Inhalte geloggt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from installer.core.deployment_identity import DeploymentId, PlanOperation

MANIFEST_VERSION = 2
MANIFEST_SUFFIX = ".manifest.json"

# Nur diese (nicht-geheimen) Variablen werden gebunden/gespeichert.
SAFE_VARIABLES = ("project_name", "recovery_enabled", "processing_recovery_enabled")


def manifest_path_for(plan_path: str | Path) -> Path:
    plan = Path(plan_path)
    return plan.with_name(plan.name + MANIFEST_SUFFIX)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class PlanManifest:
    """Lokales Manifest zur Identitaetsbindung eines Terraform-Plans."""

    deployment_id: DeploymentId
    operation: PlanOperation
    region: str
    workspace: str
    backend: Dict[str, Any]
    state_key: str
    plan_file: str
    plan_sha256: str
    plan_size: int
    variables: Dict[str, str] = field(default_factory=dict)
    git_commit: Optional[str] = None
    # MO-P0B: Versionsbindung (Manifest-Schema 2). Aeltere Manifeste (v1)
    # bleiben lesbar, gelten aber nicht als upgrade-fähig (siehe CLI-Gate).
    source_version: Optional[str] = None
    target_version: Optional[str] = None
    git_dirty: Optional[bool] = None
    version_status: Optional[str] = None
    version_source: Optional[str] = None
    # MO-P0C: State-Baseline und Drift-/No-op-Klassifikation (v2-kompatibel,
    # optionale Felder; Apply verlangt die Baseline explizit).
    state_baseline: Optional[Dict[str, Any]] = None
    drift_status: Optional[str] = None
    noop_status: Optional[str] = None
    compatibility_status: Optional[str] = None
    readiness_status: Optional[str] = None
    # MO-RC4-UPGRADE-RELEASE-GATES-01: P3A-Backup-Evidenz (optional; nur fuer
    # Upgrade-Plaene verbindlich). Enthaelt Metadaten, keine Evidenz-Inhalte.
    backup_required: Optional[bool] = None
    backup_evidence: Optional[Dict[str, Any]] = None
    backup_expected_arn: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    manifest_version: int = MANIFEST_VERSION

    # -- Erzeugung ---------------------------------------------------------
    @classmethod
    def create(
        cls,
        plan_path: str | Path,
        *,
        deployment_id: DeploymentId,
        operation: PlanOperation,
        region: str,
        workspace: str,
        backend: Any,
        variables: Optional[Dict[str, str]] = None,
        git_commit: Optional[str] = None,
        source_version: Optional[str] = None,
        target_version: Optional[str] = None,
        git_dirty: Optional[bool] = None,
        version_status: Optional[str] = None,
        version_source: Optional[str] = None,
        state_baseline: Optional[Dict[str, Any]] = None,
        drift_status: Optional[str] = None,
        noop_status: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        readiness_status: Optional[str] = None,
        backup_required: Optional[bool] = None,
        backup_evidence: Optional[Dict[str, Any]] = None,
        backup_expected_arn: Optional[str] = None,
    ) -> "PlanManifest":
        plan = Path(plan_path)
        safe_vars = {
            key: str(value)
            for key, value in (variables or {}).items()
            if key in SAFE_VARIABLES
        }
        backend_dict = backend.comparison_dict() if hasattr(backend, "comparison_dict") else dict(backend)
        return cls(
            deployment_id=deployment_id,
            operation=operation,
            region=region,
            workspace=workspace,
            backend=backend_dict,
            state_key=backend.state_key(workspace) if hasattr(backend, "state_key") else "",
            plan_file=plan.name,
            plan_sha256=sha256_file(plan),
            plan_size=plan.stat().st_size,
            variables=safe_vars,
            git_commit=git_commit,
            source_version=source_version,
            target_version=target_version,
            git_dirty=git_dirty,
            version_status=version_status,
            version_source=version_source,
            state_baseline=state_baseline,
            drift_status=drift_status,
            noop_status=noop_status,
            compatibility_status=compatibility_status,
            readiness_status=readiness_status,
            backup_required=backup_required,
            backup_evidence=backup_evidence,
            backup_expected_arn=backup_expected_arn,
        )

    # -- Persistenz --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["deployment_id"] = self.deployment_id.to_dict()
        data["operation"] = self.operation.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def write(self, plan_path: str | Path) -> Path:
        target = manifest_path_for(plan_path)
        target.write_text(self.to_json() + "\n", encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanManifest":
        return cls(
            deployment_id=DeploymentId(**data["deployment_id"]),
            operation=PlanOperation(data["operation"]),
            region=data["region"],
            workspace=data["workspace"],
            backend=dict(data.get("backend") or {}),
            state_key=data.get("state_key", ""),
            plan_file=data["plan_file"],
            plan_sha256=data["plan_sha256"],
            plan_size=int(data.get("plan_size", 0)),
            variables=dict(data.get("variables") or {}),
            git_commit=data.get("git_commit"),
            source_version=data.get("sourceVersion", data.get("source_version")),
            target_version=data.get("targetVersion", data.get("target_version")),
            git_dirty=data.get("gitDirty", data.get("git_dirty")),
            version_status=data.get("versionStatus", data.get("version_status")),
            version_source=data.get("versionSource", data.get("version_source")),
            state_baseline=data.get("stateBaseline", data.get("state_baseline")),
            drift_status=data.get("driftStatus", data.get("drift_status")),
            noop_status=data.get("noopStatus", data.get("noop_status")),
            compatibility_status=data.get("compatibilityStatus", data.get("compatibility_status")),
            readiness_status=data.get("readinessStatus", data.get("readiness_status")),
            backup_required=data.get("backupRequired", data.get("backup_required")),
            backup_evidence=data.get("backupEvidence", data.get("backup_evidence")),
            backup_expected_arn=data.get(
                "backupExpectedArn", data.get("backup_expected_arn")
            ),
            created_at=data.get("created_at", ""),
            manifest_version=int(data.get("manifest_version", MANIFEST_VERSION)),
        )

    @classmethod
    def load(cls, plan_path: str | Path) -> Optional["PlanManifest"]:
        path = manifest_path_for(plan_path)
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise ValueError(f"Plan-Manifest ist unlesbar oder ungueltig: {path}")

    # -- Pruefung ----------------------------------------------------------
    def verify(
        self,
        plan_path: str | Path,
        *,
        deployment_id: DeploymentId,
        region: str,
        workspace: str,
        backend: Any,
        operation: PlanOperation,
        allow_legacy_manifest: bool = False,
    ) -> Tuple[bool, str]:
        """Prueft Manifest gegen Plan-Datei und aktuellen Kontext.

        ``allow_legacy_manifest`` ist ausschliesslich fuer den Destroy-Pfad
        gedacht (kein Upgrade); Deploy verlangt Schema-Version 2.
        """
        plan = Path(plan_path)

        if self.manifest_version != MANIFEST_VERSION:
            if not (allow_legacy_manifest and self.manifest_version == 1):
                return False, (
                    f"Manifest-Version {self.manifest_version} wird nicht unterstuetzt "
                    f"(erwartet {MANIFEST_VERSION})."
                )
        if not plan.exists():
            return False, f"Plan-Datei fehlt: {plan}"
        if plan.name != self.plan_file:
            return False, (
                f"Plan-Dateiname '{plan.name}' passt nicht zum Manifest "
                f"('{self.plan_file}')."
            )
        if sha256_file(plan) != self.plan_sha256:
            return False, "Plan-Datei wurde nach der Manifest-Erstellung veraendert (Checksumme)."

        if self.deployment_id != deployment_id:
            return False, (
                f"Deployment-Identitaet weicht ab: Manifest {self.deployment_id}, "
                f"Kontext {deployment_id}."
            )
        if self.operation != operation:
            return False, (
                f"Plan-Operation '{self.operation.value}' passt nicht zur Aktion "
                f"'{operation.value}'."
            )
        if self.region != region:
            return False, f"Region weicht ab: Manifest {self.region}, Kontext {region}."
        if self.workspace != workspace:
            return False, (
                f"Workspace weicht ab: Manifest {self.workspace}, Kontext {workspace}."
            )

        backend_dict = backend.comparison_dict() if hasattr(backend, "comparison_dict") else dict(backend)
        if self.backend != backend_dict:
            return False, "Backend-Konfiguration weicht vom Manifest ab."
        expected_state_key = backend.state_key(workspace) if hasattr(backend, "state_key") else ""
        if expected_state_key and self.state_key != expected_state_key:
            return False, (
                f"State-Key weicht ab: Manifest {self.state_key}, erwartet {expected_state_key}."
            )

        return True, ""
