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
| RIS Builder contract | **57 passed** | RIS `tests/test_build_mays_orders_transport_outputs.py`, `test_orders_aws_name_limits.py` |
| Root Terraform | **fmt + validate PASS** | `terraform fmt -check -recursive`; isolated `terraform init -backend=false -input=false`; `terraform validate` |
| `orders-service` preset | **fmt/init/validate PASS** | Builder `--validate`; generated artifact in `%TEMP%\mo-rc4-orders-service-3cfdd654` |
| RIS generated-artifact contract | **BLOCKED: 7 passed, 2 failed** | RIS `tests/test_generated_module_artifact.py` against the generated preset |

The RIS contract and E2E profiles ran directly from the unchanged RIS worktree,
with `MO_ORDERS_SRC` pointing to this Mays candidate. AWS credential/profile
environment variables were removed and empty AWS config/credential files were
used. No AWS, LIVE, Terraform plan/apply, RIS installation/pin update, release,
redrive, or data repair was run.

## Blocked / not-yet-verified gates

- RIS Unified Runner provenance currently maps `upgrade_candidate` to the
  immutable RC4 peeled SHA, not this new candidate; it refuses a modified or
  different SHA. Direct XRepo tests above avoid changing RIS's version map.
- The generated-artifact contract ran against the clean-source build and failed
  two assertions: it expects an exactly 13-file ZIP (candidate contains five
  additional imported runtime modules: `hmac_contract.py`, `order_handlers.py`,
  `processing_result.py`, `recovery.py`, and `secret_provider.py`), and it checks
  the `gsi3` Terraform attribute spacing as a literal string although the
  formatted source contains the same index with different alignment. ZIP CRC,
  handler/import, and all other artifact assertions passed. No RIS test/source
  was edited to hide these failures.
- Ubuntu reference QA is **BLOCKED**: WSL is not installed in this environment.
- Feature-branch commits exist; final push and manifest-bound handoff are
  pending. Source identity fails closed on a dirty checkout.

## External QA contact

See `docs/reports/MO-RIS-AGENT-ORDER-BODY-01-A04.md`,
`MO-RIS-AGENT-DISPATCH-01-A05.md`, and
`MO-RIS-AGENT-RESULT-BOUNDARY-01-A06.md` for the component contracts. This QA
report is the status snapshot; update it with the final commit SHA and any
generated-module gate outcome before describing the candidate as ready for RIS
review.
