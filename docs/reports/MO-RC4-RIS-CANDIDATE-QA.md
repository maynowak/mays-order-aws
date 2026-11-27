# MO-RC4-RIS-Compatibility candidate — QA evidence

**State:** IN PROGRESS — candidate is not released or deployed.  
**Scope:** Mays-Orders changes only; RIS checkout and configured pin are unchanged.  
**Environment:** Windows, Python 3.15, local/offline tests, Terraform backend disabled.

## Verified locally

| Gate | Result | Evidence / command |
|---|---:|---|
| Lambda originals + candidate tests | **576 passed** | From `lambda/`: `python -m compileall -q src tests`; `PYTHONPATH=src python -m unittest discover -s tests` |
| Lambda ZIP | **PASS** | `python build_zip.py`; committed artifact SHA-256 `4b50d510dff2694008efdd89f1d2a681a6759d14bf22bc08b31f513eaef72903` |
| Module Builder | **99 passed** | `python -m unittest module_builder.tests.test_module_builder` |
| Installer | **81 passed** | `python -m unittest installer.tests.test_installer` |
| Seed tools | **28 passed** | From `scripts/`: `python -m unittest discover -s tests` |
| RIS XRepo contract | **133 passed + 4 subtests** | RIS `tests/test_mo_contract_compat.py`, `test_cross_repo_mo_contract.py`, `test_order_transport_contract.py`, `test_agent_order_body.py`, `test_agent_order_order_description.py`, `test_dispatch_ingress_env.py` |
| RIS synthetic XRepo E2E | **39 passed** | RIS `tests/test_mo_dispatch_handoff.py`, `test_agent_order_dispatch_e2e.py`, `test_partner_e2e_real.py`, `test_lambda_bridge_e2e.py` |
| Root Terraform | **fmt + validate PASS** | `terraform fmt -check -recursive`; isolated `terraform init -backend=false -input=false`; `terraform validate` |
| `orders-service` preset | **fmt/init/validate PASS (pre-final edits)** | Builder `--validate`; rerun required from committed clean candidate |

The RIS contract and E2E profiles ran directly from the unchanged RIS worktree,
with `MO_ORDERS_SRC` pointing to this Mays candidate. AWS credential/profile
environment variables were removed and empty AWS config/credential files were
used. No AWS, LIVE, Terraform plan/apply, RIS installation/pin update, release,
redrive, or data repair was run.

## Gates not yet verified

- RIS Unified Runner provenance currently maps `upgrade_candidate` to the
  immutable RC4 peeled SHA, not this new candidate; it refuses a modified or
  different SHA. Direct XRepo tests above avoid changing RIS's version map.
- RIS `MODULE_BUILD` generated-artifact contract has not yet been run against a
  clean, manifest-bound artifact.
- Ubuntu reference QA is **BLOCKED**: WSL is not installed in this environment.
- Final candidate commit, push, immutable full-SHA manifest, and RIS handoff are
  pending. The source-identity gate now fails closed on a dirty checkout.

## External QA contact

See `docs/reports/MO-RIS-AGENT-ORDER-BODY-01-A04.md`,
`MO-RIS-AGENT-DISPATCH-01-A05.md`, and
`MO-RIS-AGENT-RESULT-BOUNDARY-01-A06.md` for the component contracts. This QA
report is the status snapshot; update it with the final commit SHA and any
generated-module gate outcome before describing the candidate as ready for RIS
review.
