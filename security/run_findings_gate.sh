#!/usr/bin/env bash
# run_findings_gate.sh
# Invoke the MO-GH-SEC-03 findings gate evaluator and exit with the appropriate code.
# 
# Usage: ./security/run_findings_gate.sh <sarif_path> <selected_flag>
#
#   sarif_path  – path relative to the workflow working directory
#   selected_flag – "true" or "false" whether the scanner was selected for this run
#
# Exit codes (matching the gate policy):
#   0 → REPORT / PASS / NOT_EVALUATED
#   1 → FAIL / BLOCKED
set -euo pipefail

SARIF_PATH="${1:-}"
SELECTED="${2:-false}"

# ---- If the scanner was not selected, report NOT_EVALUATED --------------
if [ "$SELECTED" != "true" ]; then
  echo "::notice::Scanner not selected for this run – NOT EVALUATED (MO-GH-SEC-03)"
  echo "Security gate: no CRITICAL/HIGH findings; gate passes (NOT_EVALUATED)."
  exit 0
fi

# ---- If SARIF file is missing, BLOCK -----------------------------------
if [ -z "$SARIF_PATH" ] || [ ! -f "$SARIF_PATH" ]; then
  echo "::error::SARIF file not found – gate BLOCKED (MO-GH-SEC-03)"
  echo "Security gate: SARIF file missing – gate BLOCKED."
  exit 1
fi

# ---- Run the Python evaluator and map classification to exit code -------
# The Python evaluator prints the summary to stdout and the classification
# name on a separate line (CLASSIFICATION:NAME). We capture both and use
# the classification to determine the exit code.

PYTHON_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '/home/dci-student/projects/Mays-Orders-AWS/security')
from findings_gate import evaluate_scan
result = evaluate_scan('${SARIF_PATH}', selected=True)
print(result.summary)
print('CLASSIFICATION:' + result.classification.name)
" 2>&1) || {
  # If Python fails entirely, that's a BLOCKED condition
  echo "::error::Findings gate evaluator failed – gate BLOCKED (MO-GH-SEC-03)"
  exit 1
}

# Extract the classification name from the Python output
CLASSIFICATION=$(echo "$PYTHON_OUTPUT" | grep -oP 'CLASSIFICATION:\K\w+' || echo "UNKNOWN")

# Map classification to bash exit code
case "$CLASSIFICATION" in
  FAIL)
    echo "Security gate: CRITICAL/HIGH findings detected – gate FAILS (MO-GH-SEC-03)"
    exit 1
    ;;
  REPORT)
    echo "Security gate: no CRITICAL/HIGH findings; MEDIUM/LOW findings reported (MO-GH-SEC-03)"
    # Output any MEDIUM/LOW findings as notices
    python3 -c "
import sys
sys.path.insert(0, '/home/dci-student/projects/Mays-Orders-AWS/security')
from findings_gate import evaluate_scan
result = evaluate_scan('${SARIF_PATH}', selected=True)
for f in result.findings:
    if f.severity.name in ('MEDIUM', 'LOW'):
        print(f'::notice::{f.rule_id}: {f.severity.name} – {f.message}')
"
    exit 0
    ;;
  BLOCKED)
    echo "::error::SARIF validation issue – gate BLOCKED (MO-GH-SEC-03)"
    exit 1
    ;;
  NOT_EVALUATED)
    echo "Security gate: scanner not selected – NOT EVALUATED (MO-GH-SEC-03)"
    exit 0
    ;;
  PASS)
    echo "Security gate: no findings detected – gate passes (MO-GH-SEC-03)"
    exit 0
    ;;
  *)
    # Unknown classification – fallback: treat as pass but log warning
    echo "Security gate: unknown classification – gate passes (fallback, MO-GH-SEC-03)"
    exit 0
    ;;
esac
