"""Read-only AWS resource collision scan for the installer preflight.

Purpose (incident 2026-10, account 240571105849): two independent
deployments used the same project name ``mays-orders`` in the same AWS
account. The result was two Cognito user pools with the identical name
``mays-orders-users`` (one from this repo's S3-state workspace, one from a
parallel RIS-managed installation with local state). Nothing in the
toolchain surfaced that situation, which cost significant debugging time.

This module provides read-only AWS inventory helpers (``aws`` CLI via
subprocess, JSON output) plus pure classification functions:

* :func:`find_name_duplicates` — same-service resources with identical
  names (the strongest collision signal, e.g. duplicate Cognito pools).
* :func:`match_project_resources` — existing resources whose name contains
  the project name (may belong to this state OR to a parallel deployment;
  must be verified before plan/apply).

All AWS calls are list/read-only. The subprocess ``runner`` is injectable
so unit tests never touch real AWS.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Dict, List, Optional

Runner = Callable[[List[str], Dict[str, str]], Dict[str, Any]]

DEFAULT_TIMEOUT_SECONDS = 30


def _run_aws_json(args: List[str], env: Dict[str, str],
                  timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Run an ``aws`` CLI command and parse its JSON output.

    Raises RuntimeError on non-zero exit so callers can degrade gracefully.
    """
    result = subprocess.run(
        ["aws"] + args,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"aws {' '.join(args[:2])} failed: {result.stderr.strip()[-200:]}"
        )
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def scan_cognito_pools(env: Dict[str, str], runner: Runner = _run_aws_json) -> List[Dict[str, str]]:
    data = runner(["cognito-idp", "list-user-pools", "--max-results", "20"], env)
    return [
        {"id": str(p.get("Id", "")), "name": str(p.get("Name", ""))}
        for p in data.get("UserPools", [])
    ]


def scan_dynamodb_tables(env: Dict[str, str], runner: Runner = _run_aws_json) -> List[str]:
    data = runner(["dynamodb", "list-tables"], env)
    return [str(t) for t in data.get("TableNames", [])]


def scan_lambda_functions(env: Dict[str, str], runner: Runner = _run_aws_json) -> List[str]:
    data = runner(["lambda", "list-functions"], env)
    return [str(f.get("FunctionName", "")) for f in data.get("Functions", [])]


def scan_sqs_queues(env: Dict[str, str], runner: Runner = _run_aws_json) -> List[str]:
    data = runner(["sqs", "list-queues"], env)
    urls = data.get("QueueUrls") or []
    return [str(u).rstrip("/").rsplit("/", 1)[-1] for u in urls]


def scan_s3_buckets(env: Dict[str, str], runner: Runner = _run_aws_json) -> List[str]:
    data = runner(["s3api", "list-buckets"], env)
    return [str(b.get("Name", "")) for b in data.get("Buckets", [])]


def scan_project_inventory(env: Dict[str, str], project_name: str,
                           runner: Runner = _run_aws_json) -> Dict[str, Any]:
    """Collect a read-only, account-wide inventory relevant for collisions."""
    return {
        "project_name": project_name,
        "cognito_pools": scan_cognito_pools(env, runner),
        "dynamodb_tables": scan_dynamodb_tables(env, runner),
        "lambda_functions": scan_lambda_functions(env, runner),
        "sqs_queues": scan_sqs_queues(env, runner),
        "s3_buckets": scan_s3_buckets(env, runner),
    }


def find_name_duplicates(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect same-service AWS resources with IDENTICAL names.

    Cognito allows duplicate pool names, which is exactly how the 2026-10
    incident stayed invisible: two pools named ``mays-orders-users``.
    The other scanned services enforce unique names per account/region,
    so only Cognito pools are checked for duplicates here.
    """
    duplicates: List[Dict[str, Any]] = []
    names: Dict[str, List[str]] = {}
    for pool in inventory.get("cognito_pools", []):
        name = str(pool.get("name", ""))
        if name:
            names.setdefault(name, []).append(str(pool.get("id", "")))
    for name, ids in names.items():
        if len(ids) > 1:
            duplicates.append({
                "service": "cognito_user_pools",
                "name": name,
                "count": len(ids),
                "ids": ids,
            })
    return duplicates


def match_project_resources(inventory: Dict[str, Any], project_name: str) -> Dict[str, List[str]]:
    """Return resources whose name contains the project name (case-insensitive).

    Matches do not prove ownership: a resource may be managed by this
    project's Terraform state OR by a parallel deployment using the same
    project name. Callers must surface matches for human verification.
    """
    needle = str(project_name).lower()
    matches: Dict[str, List[str]] = {}

    def _matching(values: List[str]) -> List[str]:
        return [str(v) for v in values if needle in str(v).lower()]

    pool_names = _matching([p.get("name", "") for p in inventory.get("cognito_pools", [])])
    if pool_names:
        matches["cognito_user_pools"] = pool_names
    for key in ("dynamodb_tables", "lambda_functions", "sqs_queues", "s3_buckets"):
        found = _matching(inventory.get(key, []))
        if found:
            matches[key] = found
    return matches
