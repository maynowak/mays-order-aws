"""Terraform Module Builder for Mays-Orders-AWS.

Generates a standalone Terraform deployment from the existing
Mays-Orders-AWS components into a freely chosen target directory.

Design (MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01):
- NO meta-module to source from GitHub — the builder COPIES the existing
  terraform modules, root wiring and Lambda artifacts into the target.
- The generated project has NO dependency on the original repository
  (module sources stay relative "./modules/...", backend.tf is NOT copied).
- Fail-closed on missing artifacts — no dummy files are ever generated.
- No AWS mutations, no terraform apply/destroy, no state migration.
- Privacy production activation remains BLOCKED (documented in generated README).
"""

__version__ = "0.1.0"
