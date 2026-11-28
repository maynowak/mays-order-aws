# RIS–Mays-Orders Integration Reference (2026-11-28)

**Status:** Documentation reference prepared; no Mays-Orders module/source change.

The completed synthetic RIS-DEV2 Addition roundtrip is documented centrally in
the [RIS integration dossier](https://github.com/maynowak/Mays-Recruiting-Intelligence-System/blob/main/docs/integration/RIS-MAYS-ORDERS-INTEGRATION-DOSSIER.md).
The RIS status report records final acceptance and preserves earlier STOP /
BLOCKED snapshots:
[integration status](https://github.com/maynowak/Mays-Recruiting-Intelligence-System/blob/main/docs/reports/RIS-MAYS-ORDERS-INTEGRATION-STATUS.md).

## Source/version distinction

RIS records `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` as the integrated,
reproducible Mays-Orders module/test source pin. This is not a claim that this
commit is the current Mays-Orders `main` head and is not the separate
`v0.6.0-rc.1` / `5bc154e` RC4 tag or the `80a84ca` OrderDescription upgrade
candidate. RIS's successful technical acceptance is limited to synthetic data;
it is not a privacy/product approval for real personal data.

## Boundary and scope

Mays-Orders remains a separately versioned system. This report is a pointer,
not a copy of the RIS dossier and not an upstream module release, installation,
or upgrade approval. The documentation change does not alter runtime, module,
Terraform, AWS state, or deployment artifacts. The companion documentation PR
in this repository is prepared separately; neither documentation PR is merged
as part of this change.
