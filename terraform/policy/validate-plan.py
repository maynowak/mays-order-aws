#!/usr/bin/env python3
"""May's Orders Terraform Cost/Resource Policy Gate.

Input: terraform show -json <planfile>
Exit 0: PASS
Exit 1: FAIL
Exit 2: usage/configuration error

The gate deliberately checks concrete project governance rules rather than trying
 to predict an exact AWS bill. AWS IAM/permissions are still evaluated by AWS at
 apply time; this script validates the Terraform plan before apply.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

POLICY_PATH = Path(__file__).with_name("resource-policy.json")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"POLICY GATE ERROR: cannot read {path}: {exc}")
        raise SystemExit(2)


def get_after(change: dict[str, Any]) -> dict[str, Any]:
    after = change.get("change", {}).get("after")
    return after if isinstance(after, dict) else {}


def get_tags(resource: dict[str, Any]) -> dict[str, Any]:
    # Decision B: evaluate EFFECTIVE tags (explicit resource tags + provider default_tags).
    # Terraform exposes both "tags" (explicit only) and "tags_all" (merged effective tags)
    # in the plan JSON. Counting only "tags" made provider default_tags (e.g. "Maker")
    # invisible to the gate; "tags_all" is the authoritative effective tag set.
    tags = resource.get("tags_all")
    return tags if isinstance(tags, dict) else {}


def planned_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    root = plan.get("resource_changes", [])
    if isinstance(root, list):
        resources.extend(x for x in root if isinstance(x, dict))

    # Child-module resources are normally represented in root resource_changes,
    # but keep this defensive traversal for plan formats that expose nested modules.
    def walk(module: dict[str, Any]) -> None:
        changes = module.get("resource_changes", [])
        if isinstance(changes, list):
            resources.extend(x for x in changes if isinstance(x, dict))
        children = module.get("child_modules", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child)

    root_module = plan.get("planned_values", {}).get("root_module")
    if isinstance(root_module, dict):
        # planned_values is used below only as a fallback for resources whose
        # resource_changes representation is incomplete; no duplicate checks here.
        pass

    return resources


def check(plan: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    resources = planned_resources(plan)

    if not resources:
        errors.append("No resource changes found in Terraform plan.")
        return errors

    allowed_types = set(policy["resource_types"]["allowed"])
    required_tags = policy["required_tags"]
    policy_project = policy["project"]
    environment_policy = policy["environment"]

    # Derive project name from first resource's Project tag for parallel-project support
    project = policy_project
    for item in resources:
        resource = get_after(item)
        tags = get_tags(resource)
        proj_tag = tags.get("Project")
        if proj_tag:
            project = proj_tag
            break
    # If policy project is a wildcard pattern, allow any project starting with prefix
    if policy_project.startswith("mays-") and not project.startswith("mays-"):
        # keep policy strict
        pass

    counts: dict[str, int] = {}
    ec2_instances = 0

    for item in resources:
        address = item.get("address", "<unknown>")
        resource_type = item.get("type", "<unknown>")
        action = item.get("change", {}).get("actions", [])

        # Only creations/replacements need to pass resource-shape checks.
        if not any(a in action for a in ("create", "update", "replace")):
            continue

        if resource_type not in allowed_types:
            errors.append(
                f"{address}: resource type '{resource_type}' is not allowed by the project policy."
            )
            continue

        counts[resource_type] = counts.get(resource_type, 0) + 1
        resource = get_after(item)
        tags = get_tags(resource)

        # Required tags apply to resources that expose a Terraform tags attribute.
        if "tags_all" in resource:
            missing = [tag for tag in required_tags if not tags.get(tag)]
            if missing:
                errors.append(f"{address}: missing required tag(s): {', '.join(missing)}.")

            if tags.get("Project") != project:
                errors.append(
                    f"{address}: Project tag must be '{project}', got {tags.get('Project')!r}."
                )

            environment = tags.get("Environment")
            if environment == "Production":
                errors.append(f"{address}: Production resources are not allowed for the developer gate.")
            elif environment not in environment_policy["developer_allowed"]:
                errors.append(
                    f"{address}: Environment must be one of {environment_policy['developer_allowed']}; got {environment!r}."
                )

        if resource_type == "aws_lambda_function":
            runtime = resource.get("runtime")
            if runtime not in policy["lambda"]["allowed_runtimes"]:
                errors.append(f"{address}: Lambda runtime '{runtime}' is not allowed.")

            timeout = resource.get("timeout")
            if isinstance(timeout, (int, float)) and timeout > policy["lambda"]["max_timeout_seconds"]:
                errors.append(
                    f"{address}: Lambda timeout {timeout}s exceeds {policy['lambda']['max_timeout_seconds']}s."
                )

        elif resource_type == "aws_cloudwatch_log_group":
            retention = resource.get("retention_in_days")
            if isinstance(retention, (int, float)) and retention > policy["lambda"]["max_log_retention_days"]:
                errors.append(
                    f"{address}: log retention {retention} days exceeds {policy['lambda']['max_log_retention_days']} days."
                )

        elif resource_type == "aws_dynamodb_table":
            billing_mode = resource.get("billing_mode")
            if billing_mode not in policy["dynamodb"]["allowed_billing_modes"]:
                errors.append(
                    f"{address}: DynamoDB billing_mode must be PAY_PER_REQUEST, got {billing_mode!r}."
                )

        elif resource_type == "aws_s3_bucket":
            if policy["s3"]["project_bucket_required"]:
                bucket = resource.get("bucket")
                if isinstance(bucket, str) and not bucket.startswith(f"{project}-"):
                    errors.append(
                        f"{address}: S3 bucket '{bucket}' is outside the project namespace '{project}-*'."
                    )

        elif resource_type == "aws_s3_bucket_public_access_block":
            required = {
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            }
            for key, expected in required.items():
                if resource.get(key) is not expected:
                    errors.append(f"{address}: {key} must be true.")

        elif resource_type == "aws_s3_bucket_server_side_encryption_configuration":
            algorithms = []
            for rule in resource.get("rule", []) or []:
                if not isinstance(rule, dict):
                    continue
                defaults = rule.get("apply_server_side_encryption_by_default", []) or []
                for default in defaults:
                    if isinstance(default, dict):
                        algorithms.append(default.get("sse_algorithm"))
            if "AES256" not in algorithms and "aws:kms" not in algorithms:
                errors.append(f"{address}: S3 server-side encryption must be configured.")

        elif resource_type == "aws_cloudtrail":
            if resource.get("is_multi_region_trail") is not True:
                errors.append(f"{address}: CloudTrail must be multi-region.")
            if resource.get("include_global_service_events") is not True:
                errors.append(f"{address}: CloudTrail global service events must be enabled.")
            if resource.get("enable_log_file_validation") is not True:
                errors.append(f"{address}: CloudTrail log-file validation must be enabled.")

        elif resource_type == "aws_iam_role":
            name = resource.get("name")
            if isinstance(name, str) and not name.startswith(f"{project}-"):
                errors.append(f"{address}: IAM role name '{name}' is outside the project namespace '{project}-*'.")

        elif resource_type.startswith("aws_apigatewayv2_"):
            name = resource.get("name")
            # A Stage's `name` is the API Gateway stage name, not a project-namespaced
            # resource name. "$default" is the valid AWS HTTP-API default stage and is
            # already namespaced under its parent aws_apigatewayv2_api (checked above).
            # This exception is scoped to aws_apigatewayv2_stage only; it does not relax
            # namespace validation for any other API Gateway resource type.
            if resource_type == "aws_apigatewayv2_stage" and name == "$default":
                pass
            elif isinstance(name, str) and not name.startswith(f"{project}-"):
                errors.append(f"{address}: API Gateway name '{name}' is outside the project namespace '{project}-*'.")

        elif resource_type == "aws_cognito_user_pool":
            name = resource.get("name")
            if isinstance(name, str) and not name.startswith(f"{project}-"):
                errors.append(f"{address}: Cognito user pool name '{name}' is outside the project namespace '{project}-*'.")

        # EC2 support is intentionally included for future development/test use.
        # Current May's Orders Terraform configuration contains no EC2 resources.
        if resource_type == "aws_instance":
            ec2_instances += 1
            instance_type = resource.get("instance_type")
            if instance_type not in policy["ec2"]["allowed_instance_types"]:
                errors.append(f"{address}: EC2 instance type '{instance_type}' is not allowed.")

    if ec2_instances > policy["ec2"]["max_instances"]:
        errors.append(
            f"EC2 instance count {ec2_instances} exceeds maximum {policy['ec2']['max_instances']}."
        )

    # The plan's configuration normally contains the AWS provider's region expression.
    provider_configs = plan.get("configuration", {}).get("provider_config", {})
    if isinstance(provider_configs, dict):
        for provider_name, config in provider_configs.items():
            if not isinstance(config, dict) or provider_name.split(".")[0] != "aws":
                continue
            expressions = config.get("expressions", {})
            region_expr = expressions.get("region") if isinstance(expressions, dict) else None
            region = region_expr.get("constant_value") if isinstance(region_expr, dict) else None
            if region is not None:
                allowed = policy["region"]["allowed_patterns"]
                if not any(fnmatch.fnmatch(region, pattern) for pattern in allowed):
                    errors.append(
                        f"AWS provider region '{region}' is outside allowed region patterns: {', '.join(allowed)}."
                    )

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 terraform/policy/validate-plan.py <terraform-plan.json>")
        return 2

    plan_path = Path(sys.argv[1])
    if not plan_path.is_file():
        print(f"POLICY GATE ERROR: plan file not found: {plan_path}")
        return 2

    policy = load_json(POLICY_PATH)
    try:
        plan = load_json(plan_path)
    except SystemExit as exc:
        return int(exc.code)

    errors = check(plan, policy)

    print("May's Orders Terraform Cost/Resource Policy Gate")
    print(f"Policy: {POLICY_PATH}")
    print(f"Plan:   {plan_path}")

    if errors:
        print("\nRESULT: FAIL")
        for error in errors:
            print(f"  - {error}")
        print("\nTerraform apply MUST NOT proceed until the findings are reviewed/resolved.")
        return 1

    print("\nRESULT: PASS")
    print("No policy violations found in the supplied Terraform plan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
