#!/usr/bin/env bash
# run_findings_gate.sh
# Invoke the MO-GH-SEC-03 findings gate evaluator and exit with the appropriate code.
#
# Usage: ./security/run_findings_gate.sh <sarif_path> <selected_flag> [scanner_id] [sha] [ref] [attempt]
#
#   sarif_path   – path relative to the workflow working directory
#   selected_flag – "true" or "false" whether the scanner was selected for this run
#   scanner_id   – optional scanner identity (e.g. "codeql", "dependency")
#   sha          – optional commit SHA
#   ref          – optional git ref
#   attempt      – optional workflow attempt number
#
# Exit codes (matching the gate policy):
#   0 → REPORT / PASS / NOT_EVALUATED
#   1 → FAIL / BLOCKED
set -euo pipefail

SARIF_PATH="${1:-}"
SELECTED="${2:-false}"
SCANNER_ID="${3:-}"
SHA="${4:-}"
REF="${5:-}"
ATTEMPT="${6:-}"

# ---- Determine the security directory relative to this script -------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# GitHub Actions step summary file (may be unset locally)
SUMMARY_FILE="${GITHUB_STEP_SUMMARY:-}"

_append_summary() {
  if [ -n "$SUMMARY_FILE" ]; then
    cat >> "$SUMMARY_FILE"
  fi
}

_write_summary_line() {
  if [ -n "$SUMMARY_FILE" ]; then
    echo "$1" >> "$SUMMARY_FILE"
  fi
}

# ---- If the scanner was not selected, report NOT_EVALUATED --------------
if [ "$SELECTED" != "true" ]; then
  echo "::notice::Scanner not selected for this run – NOT EVALUATED (MO-GH-SEC-03)"
  echo "Security gate: scanner not selected – NOT EVALUATED."
  _append_summary << 'EOF'

### Security Gate (MO-GH-SEC-03) – NOT_EVALUATED

Scanner was not selected for this run. No security approval claimed.

EOF
  exit 0
fi

# ---- If SARIF file is missing, BLOCK -----------------------------------
if [ -z "$SARIF_PATH" ] || [ ! -f "$SARIF_PATH" ]; then
  echo "::error::SARIF file not found – gate BLOCKED (MO-GH-SEC-03)"
  echo "Security gate: SARIF file missing – gate BLOCKED."
  _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – BLOCKED

SARIF file not found: \`$SARIF_PATH\`

No security approval claimed.

EOF
  exit 1
fi

# ---- Run the Python evaluator ------------------------------------------
# Use relative import from the script's own directory – no hardcoded paths.
PYTHON_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
from findings_gate import evaluate_scan, write_report, _validate_sarif_structure, _get_scanner_identity_from_run
import json
with open('${SARIF_PATH}', 'r') as f:
    data = json.load(f)
verr = _validate_sarif_structure(data)
print('DEBUG_VAL_ERROR:' + str(verr))
# Get scanner ID from SARIF if not provided
scanner_id = '${SCANNER_ID}' or _get_scanner_identity_from_run(data.get('runs', [{}])[0])
result = evaluate_scan('${SARIF_PATH}', selected=True, scanner_id=scanner_id, sha='${SHA}', ref='${REF}', attempt=int('${ATTEMPT:-1}') if '${ATTEMPT}' else 1)
print(result.summary)
print('CLASSIFICATION:' + result.classification.name)
print('DEBUG_NUM_FINDINGS:' + str(len(result.findings)))
if result.findings:
    f0 = result.findings[0]
    print('DEBUG_FIRST_SEVERITY:' + f0.severity.name)
    print('DEBUG_FIRST_SEVERITY_VAL:' + str(f0.security_severity))
    print('DEBUG_FIRST_IS_QUALITY:' + str(f0.is_quality_finding))
    print('DEBUG_FIRST_IS_DEP:' + str(f0.is_dependency_finding))
# GENERATE REPORT FOR ALL CLASSIFICATIONS
report_path = '${SARIF_PATH}.gate-report.json'
write_report(result, report_path)
print('REPORT_PATH:' + report_path)
print('REPORT_SCANNER_ID:' + str(result.scanner_id))
print('REPORT_SHA:' + str(result.sha))
print('REPORT_REF:' + str(result.ref))
print('REPORT_ATTEMPT:' + str(result.attempt))
" 2>&1) || {
  # If Python fails entirely (import error, crash, etc.), that's BLOCKED
  echo "::error::Findings gate evaluator failed – gate BLOCKED (MO-GH-SEC-03)"
  _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – BLOCKED

Findings gate evaluator failed with a Python error.

No security approval claimed.

EOF
  exit 1
}

# ---- Extract classification from Python output -------------------------
# Use sed for portability (grep -oP is not available on all systems)
CLASSIFICATION=$(echo "$PYTHON_OUTPUT" | sed -n 's/.*CLASSIFICATION:\([A-Za-z]*\).*/\1/p' | tail -n 1)
CLASSIFICATION="${CLASSIFICATION:-UNKNOWN}"
REPORT_PATH=$(echo "$PYTHON_OUTPUT" | sed -n 's/.*REPORT_PATH:\([^ ]*\).*/\1/p' | tail -n 1)

# Debug output (visible in job log)
echo "::debug::Findings gate Python output: ${PYTHON_OUTPUT}"
echo "::debug::Classification: ${CLASSIFICATION}"

# ---- Fail-closed: unknown classification blocks -----------------------
case "$CLASSIFICATION" in
  FAIL)
    echo "Security gate: CRITICAL/HIGH findings detected – gate FAILS (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – FAIL

CRITICAL/HIGH security findings detected. Gate exits with code 1.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    _write_summary_line "No security approval claimed."
    exit 1
    ;;
  REPORT)
    echo "Security gate: no CRITICAL/HIGH findings; MEDIUM/LOW findings reported (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – REPORT

No CRITICAL/HIGH findings. MEDIUM/LOW findings reported below.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    _write_summary_line "Findings are informational only — no security approval claimed."
    # Emit individual finding notices
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import json
with open('${REPORT_PATH}') as f:
    report = json.load(f)
for finding in report.get('findings', []):
    if finding.get('severity') in ('MEDIUM', 'LOW'):
        sev = finding.get('security_severity', 'n/a')
        print(f'::notice::{finding[\"rule_id\"]}: {finding[\"severity\"]} (security-severity={sev}) – {finding[\"message\"]}')
"
    fi
    exit 0
    ;;
  BLOCKED)
    echo "::error::SARIF validation issue – gate BLOCKED (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – BLOCKED

SARIF validation failed or security-severity is missing/invalid.

No security approval claimed.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    exit 1
    ;;
  NOT_EVALUATED)
    echo "Security gate: scanner not selected – NOT EVALUATED (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – NOT_EVALUATED

Scanner not selected for this run.

No security approval claimed.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    exit 0
    ;;
  PASS)
    echo "Security gate: no findings detected – gate passes (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – PASS

No security findings detected.

No security approval claimed.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    exit 0
    ;;
  *)
    # FAIL-CLOSED: unknown classification blocks – no successful fallback
    echo "::error::Unknown gate classification '$CLASSIFICATION' – gate BLOCKED (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – BLOCKED

Unknown gate classification: \`$CLASSIFICATION\`

No security approval claimed.

EOF
    if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
      _write_summary_line "Machine-readable report: \`$REPORT_PATH\`"
      _write_summary_line ""
    fi
    exit 1
    ;;
esac