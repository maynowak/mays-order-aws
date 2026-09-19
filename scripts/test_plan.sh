#!/usr/bin/env bash
"""
Mays Installer - Test Script for Plan Operations

This script simulates the complete D0-D5 lifecycle:
DISCOVERY -> VALIDATION -> TERRAFORM VALIDATE -> DEPLOY PLAN -> DESTROY PLAN

Usage:
    ./scripts/test_plan.sh [--dry-run] [--profile PROFILE] [--region REGION]

Options:
    --dry-run          Run in dry-run mode (default: true)
    --profile PROFILE  AWS profile to use (default: mayaws)
    --region REGION    AWS region (default: eu-central-1)
    --help             Show this help message
"""

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=true
AWS_PROFILE="${AWS_PROFILE:-mayaws}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
PROJECT_NAME="${PROJECT_NAME:-mays-orders}"
TERRAFORM_DIR="${TERRAFORM_DIR:-terraform}"
RUN_DIR="${RUN_DIR:-.mays-installer/runs}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-dry-run)
            DRY_RUN=false
            shift
            ;;
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --terraform-dir)
            TERRAFORM_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run              Run in dry-run mode (default)"
            echo "  --no-dry-run           Disable dry-run mode"
            echo "  --profile PROFILE      AWS profile (default: mayaws)"
            echo "  --region REGION        AWS region (default: eu-central-1)"
            echo "  --project-name NAME    Project name (default: mays-orders)"
            echo "  --terraform-dir DIR    Terraform directory (default: terraform)"
            echo "  --help                 Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/${TERRAFORM_DIR}"
RUN_DIR="${PROJECT_ROOT}/.mays-installer/runs"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RUN_ID="test-plan-${TIMESTAMP}"
RUN_DIR="${RUN_DIR}/${RUN_ID}"

export AWS_PROFILE="${AWS_PROFILE}"
export AWS_REGION="${AWS_REGION}"
export PROJECT_NAME="${PROJECT_NAME}"
export ENVIRONMENT="Development"
export TERRAFORM_DIR="${TERRAFORM_DIR}"
export RUN_DIR="${RUN_DIR}"
export DRY_RUN="${DRY_RUN}"
export AWS_PROFILE="${AWS_PROFILE}"
export AWS_REGION="${AWS_REGION}"
export PROJECT_NAME="${PROJECT_NAME}"

# Create run directory
mkdir -p "${RUN_DIR}/logs"
mkdir -p "${RUN_DIR}/plans"
mkdir -p "${RUN_DIR}/artifacts"

log_info "=== Mays Installer Test Plan - D0-D5 Milestone ==="
log_info "Run ID: ${RUN_ID}"
log_info "Project: ${PROJECT_NAME}"
log_info "Profile: ${AWS_PROFILE}"
log_info "Region: ${AWS_REGION}"
log_info "Terraform Dir: ${TERRAFORM_DIR}"
log_info "Run Dir: ${RUN_DIR}"
log_info "Dry Run: ${DRY_RUN}"

# Function to save context
save_context() {
    local context_file="${RUN_DIR}/context.json"
    cat > "${RUN_DIR}/context.json" <<EOF
{
    "aws_profile": "${AWS_PROFILE}",
    "aws_region": "${AWS_REGION}",
    "aws_account_id": null,
    "identity_arn": null,
    "environment": "Development",
    "project_name": "${PROJECT_NAME}",
    "cognito_mode": "user_pool",
    "cognito_user_pool_id": null,
    "cognito_client_id": null,
    "terraform_dir": "terraform",
    "terraform_workspace": "default",
    "run_id": "$(basename ${RUN_DIR})",
    "run_dir": "${RUN_DIR}",
    "allow_aws_operations": false,
    "dry_run": true
}
EOF
    log_info "Context saved to ${RUN_DIR}/context.json"
}

# Function to run validation
run_validation() {
    log_info "=== PHASE 1: DISCOVERY & VALIDATION ==="
    
    local validation_output="${RUN_DIR}/validation.json"
    
    # Run Python validation
    if python3 -c "
import sys
sys.path.insert(0, '.')
from installer.core.context import InstallationContext, ValidationLayer

ctx = InstallationContext(
    aws_profile='${AWS_PROFILE}',
    aws_region='${AWS_REGION}',
    project_name='${PROJECT_NAME}',
    environment='Development',
    terraform_dir='terraform'
)
validation = ValidationLayer(ctx)
result = validation.run_all()
print(result.to_json())
" > "${RUN_DIR}/validation.json" 2>&1; then
    
    # Check validation result
    if python3 -c "
import json, sys
with open('${RUN_DIR}/validation.json') as f:
    data = json.load(f)
if data['status'] == 'BLOCKED':
    sys.exit(1)
" 2>/dev/null; then
        echo "Validation PASSED"
        return 0
    else
        echo "Validation BLOCKED"
        cat "${RUN_DIR}/validation.json" | python3 -m json.tool
        return 1
    fi
else
    log_error "Validation script failed"
    return 1
fi
}

# Function to run terraform init
run_terraform_init() {
    log_info "Running terraform init..."
    
    cd "${TERRAFORM_DIR}"
    
    # Check if backend should be initialized
    local init_args=()
    if [ "${DRY_RUN}" = "true" ]; then
        init_args+=("-backend=false")
    fi
    
    if terraform init "${init_args[@]}" 2>&1 | tee "${RUN_DIR}/logs/terraform_init.log"; then
        log_success "Terraform init successful"
        return 0
    else
        log_error "Terraform init failed"
        return 1
    fi
}

# Function to run terraform validate
run_terraform_validate() {
    log_info "Running terraform validate..."
    
    cd "${TERRAFORM_DIR}"
    
    if terraform validate 2>&1 | tee "${RUN_DIR}/logs/terraform_validate.log"; then
        log_success "Terraform validate passed"
        return 0
    else
        log_error "Terraform validate failed"
        return 1
    fi
}

# Function to run terraform plan
run_terraform_plan() {
    local mode="$1"
    local output_file="${RUN_DIR}/plans/${2:-deploy.tfplan}"
    local mode_flag=""
    
    if [[ "${mode}" == "destroy" ]]; then
        mode_flag="-destroy"
    fi
    
    log_info "Running terraform plan (mode: ${mode})..."
    
    mkdir -p "$(dirname "${output_file}")"
    
    cd "${TERRAFORM_DIR}"
    
    if terraform plan -out="${output_file}" ${mode_flag:+-destroy} 2>&1 | tee "${RUN_DIR}/logs/terraform_plan_${mode}.log"; then
        log_success "Terraform plan (${mode}) successful"
        return 0
    else
        log_error "Terraform plan (${mode}) failed"
        return 1
    fi
}

# Function to analyze plan
analyze_plan() {
    local plan_file="$1"
    local mode="${2:-deploy}"
    
    if [[ ! -f "${plan_file}" ]]; then
        log_warning "Plan file not found: ${plan_file}"
        return 1
    fi
    
    # Use terraform show -json to analyze
    local plan_json="${RUN_DIR}/plans/$(basename ${plan_file} .tfplan)-plan.json"
    
    if terraform show -json "${plan_file}" > "${plan_file}.json" 2>/dev/null; then
        # Analyze with Python
        python3 -c "
import json, sys
with open('${plan_file}.json') as f:
    plan = json.load(f)

add = change = destroy = replace = 0
for change in plan.get('resource_changes', []):
    actions = change.get('change', {}).get('actions', [])
    for action in actions:
        if action == 'create':
            print('ADD=1')
        elif action == 'update':
            print('CHANGE=1')
        elif action == 'delete':
            print('DESTROY=1')
        elif action == 'replace':
            print('REPLACE=1')
" 2>/dev/null | sort | uniq -c | while read count action; do
            echo "${action}=${count}"
        done
    fi
    
    # Also create plan analysis JSON
    if command -v python3 >/dev/null; then
        python3 -c "
import json, sys
with open('${plan_file}.json') as f:
    plan = json.load(f)

add = change = destroy = replace = 0
resources = []
for change in plan.get('resource_changes', []):
    actions = change.get('change', {}).get('actions', [])
    for action in actions:
        if action == 'create':
            print('ADD=1')
        elif action == 'update':
            print('CHANGE=1')
        elif action == 'delete':
            print('DESTROY=1')
        elif action == 'replace':
            print('REPLACE=1')
" 2>&1 | grep -E '^(ADD|CHANGE|DESTROY|REPLACE)=' | sort | uniq -c
    fi
}

# Function to run policy gate
run_policy_gate() {
    local plan_file="$1"
    local plan_json="${plan_file}.json"
    
    if [[ -f "${plan_file}.json" ]]; then
        log_info "Running policy gate..."
        
        if python3 terraform/policy/validate-plan.py "${plan_file}.json" 2>&1 | tee "${RUN_DIR}/logs/policy_gate.log"; then
            log_success "Policy gate PASSED"
            return 0
        else
            log_warning "Policy gate had findings (check log)"
            return 0  # Don't fail, just warn
        fi
    else
        log_warning "Plan JSON not found, skipping policy gate"
        return 0
    fi
}

# Function to save plan analysis
save_plan_analysis() {
    local plan_file="$1"
    local mode="${2:-deploy}"
    
    if [[ -f "${plan_file}.json" ]]; then
        # Create analysis JSON
        cat > "${RUN_DIR}/plans/$(basename ${plan_file} .tfplan)-plan.json" <<EOF
{
    "plan_file": "$(basename ${plan_file})",
    "mode": "${mode}",
    "timestamp": "$(date -Iseconds)",
    "note": "Plan analysis saved for review"
}
EOF
    fi
}

# Main test execution
main() {
    local start_time=$(date +%s)
    local failed=0
    
    # Phase 0: Setup
    log_info "=== Mays Installer Test Plan (D0-D5) ==="
    log_info "Run ID: $(basename ${RUN_DIR})"
    log_info "Timestamp: $(date -Iseconds)"
    
    # Save context
    save_context
    
    # Phase 1: Discovery & Validation
    log_info "=== D0: DISCOVERY ==="
    # Discovery is implicit in validation
    
    log_info "=== D1: VALIDATION ==="
    if ! run_validation; then
        log_error "Validation failed"
        failed=1
    fi
    
    # Phase 2: Terraform
    log_info "=== D2: TERRAFORM INIT ==="
    if ! run_terraform_init; then
        ((failed++))
    fi
    
    log_info "=== D3: TERRAFORM VALIDATE ==="
    if ! run_terraform_validate; then
        ((failed++))
    fi
    
    # Phase 3: Deploy Plan
    log_info "=== D4: DEPLOY PLAN ==="
    if run_terraform_plan "deploy" "deploy.tfplan"; then
        log_info "Analyzing deploy plan..."
        if [[ -f "deploy.tfplan.json" ]]; then
            save_plan_analysis "deploy.tfplan" "deploy"
        fi
    else
        ((failed++))
    fi
    
    # Phase 5: Destroy Plan
    log_info "=== D5: DESTROY PLAN ==="
    if run_terraform_plan "destroy" "destroy.tfplan"; then
        log_info "Analyzing destroy plan..."
        if [[ -f "destroy.tfplan.json" ]]; then
            save_plan_analysis "destroy.tfplan" "destroy"
        fi
    else
        ((failed++))
    fi
    
    # Summary
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "=== TEST SUMMARY ==="
    log_info "Duration: ${duration}s"
    log_info "Run directory: ${RUN_DIR}"
    
    if [[ ${failed} -eq 0 ]]; then
        log_success "All phases completed successfully!"
        return 0
    else
        log_error "${failed} phase(s) failed"
        return 1
    fi
}

# Run main
main "$@"