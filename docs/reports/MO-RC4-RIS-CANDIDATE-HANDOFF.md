# RIS handoff — Mays-Orders RC4 compatibility candidate

**Status:** Candidate for RIS engineering review; **not release-ready**.  
**Owner boundary:** Changes are in Mays-Orders only. RIS source, test-version
map, branch, and pins are unchanged.  
**Candidate identity:** Use the full SHA at the feature branch HEAD and the
`source.commit` in the generated `module-builder.manifest.json`. The builder
rejects a dirty checkout; the deployment ZIP hash is recorded in the manifest.

## Included

- Agent Order V1 validation in native-body and RIS OrderV1 serialized
  `orderDescription` forms.
- Owner/consumer-bound persistence and owner-only result projection.
- Server-generated Work-ID binding, dispatch, HMAC-verified result consumer,
  duplicate/stale-result handling, and opt-in Mays result transport.
- Builder wiring for the optional, default-off result transport, contract
  variable audit, and full-SHA source provenance.
- Privacy export projection and anonymization of Agent Order, result, dispatch,
  and identity attributes.

## Evidence

See [`MO-RC4-RIS-CANDIDATE-QA.md`](MO-RC4-RIS-CANDIDATE-QA.md) for commands,
counts, and limitations. Local gates:

- Lambda **576/576**, Module Builder **99/99**, Installer **81/81**, Seed
  **28/28**.
- RIS XRepo contract **133 + 4 subtests**, synthetic XRepo E2E **39/39**, RIS
  builder contracts **57/57**.
- Root Terraform and generated `orders-service` configuration pass
  backend-free format/validation.
- Lambda deployment ZIP SHA-256:
  `4b50d510dff2694008efdd89f1d2a681a6759d14bf22bc08b31f513eaef72903`.

## Acceptance blockers / limitations

RIS generated-artifact tests are **not green**: 7 passed and 2 failed. One
assertion requires an exact ZIP member list omitting five Python modules
imported by the candidate runtime. The other asserts literal whitespace for the
`gsi3` declaration rather than matching the equivalent formatted Terraform
structure. Neither was worked around by editing RIS. Please review these
expectations against the candidate manifest, ZIP/source imports, and formatted
Terraform before deciding whether the RIS profile needs adjustment.

The RIS unified runner's `upgrade_candidate` map points to RC4's immutable
peeled SHA, so it refuses this new SHA by design. XRepo tests were run directly
against the unchanged RIS test tree with the candidate source injected through
the documented `MO_ORDERS_SRC` boundary. Ubuntu reference QA remains blocked
because WSL is not installed. None of these results authorizes a pin update,
module installation, release, deployment, or live test.

## Safety statement

No AWS operation, LIVE test, Terraform plan/apply/state mutation, RIS module
installation or pin change, release, main merge, redrive, or data repair was
performed. RIS reference HEAD at test time:
`9e1cff4f392410de887ddef10e86edc9008d2bdb`.
