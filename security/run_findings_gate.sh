#!/usr/bin/env bash
# run_findings_gate.sh
# Invoke the MO-GH-SEC-03 findings gate evaluator and exit with the appropriate code.
#
# Usage: ./security/run_findings_gate.sh <sarif_path> <selected_flag>
#
#   sarif_path   – path relative to the workflow working directory
#   selected_flag – "true" or "false" whether the scanner was selected for this run
#
# Exit codes (matching the gate policy):
#   0 → REPORT / PASS / NOT_EVALUATED
#   1 → FAIL / BLOCKED
set -euo pipefail

SARIF_PATH="${1:-}"
SELECTED="${2:-false}"

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
  echo "Security gate: no CRITICAL/HIGH findings; gate passes (NOT_EVALUATED)."
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
from findings_gate import evaluate_scan, write_report
result = evaluate_scan('${SARIF_PATH}', selected=True)
print(result.summary)
print('CLASSIFICATION:' + result.classification.name)
if result.classification.name in ('FAIL', 'REPORT'):
    report_path = '${SARIF_PATH}.gate-report.json'
    write_report(result, report_path)
    print('REPORT_PATH:' + report_path)
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
CLASSIFICATION=$(echo "$PYTHON_OUTPUT" | grep -oP 'CLASSIFICATION:\K\w+' || echo "UNKNOWN")
REPORT_PATH=$(echo "$PYTHON_OUTPUT" | grep -oP 'REPORT_PATH:\K\S+' || echo "")

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
    exit 1
    ;;
  NOT_EVALUATED)
    echo "Security gate: scanner not selected – NOT EVALUATED (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – NOT_EVALUATED

Scanner not selected for this run.

No security approval claimed.

EOF
    exit 0
    ;;
  PASS)
    echo "Security gate: no findings detected – gate passes (MO-GH-SEC-03)"
    _append_summary << EOF

### Security Gate (MO-GH-SEC-03) – PASS

No security findings detected.

No security approval claimed.

EOF
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
    exit 1
    ;;
esac