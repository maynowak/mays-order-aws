"""P3D-01: lokale Pruefungen fuer das PartiQL-Diagnosepaket.

Rein statisch: kein AWS, kein Terraform-Lauf, keine echten Daten.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIAG_DIR = REPO_ROOT / "docs" / "diagnostics" / "dynamodb"
DYNAMODB_TF = REPO_ROOT / "terraform" / "modules" / "dynamodb" / "main.tf"

EXPECTED_FILES = {
    "README.md",
    "schema-reference.md",
    "order-lookup.partiql",
    "order-status.partiql",
    "gsi-diagnostics.partiql",
    "subject-diagnostics.partiql",
    "restore-comparison.partiql",
    "security-and-iam.md",
}

# Nur diese Platzhalter sind dokumentiert; alles andere waere unstimmig.
DOCUMENTED_PLACEHOLDERS = {
    "TABLE_NAME",
    "RESTORE_TABLE_NAME",
    "ORDER_PK",
    "ORDER_ID",
    "SUBJECT_ID",
    "FROM_ISO",
    "TO_ISO",
    "REGION",
    "ACCOUNT_ID",
}

FORBIDDEN_STATEMENTS = re.compile(
    r"\b(insert|update|delete|replace|create|drop|alter)\b", re.IGNORECASE
)


def _read(name: str) -> str:
    return (DIAG_DIR / name).read_text(encoding="utf-8")


def _partiql_files() -> list[Path]:
    return sorted(DIAG_DIR.glob("*.partiql"))


def _strip_comments(sql: str) -> str:
    """Entfernt -- und /* */ Kommentare, ohne Strings anzutasten."""
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", sql)


def _strip_string_literals(sql: str) -> str:
    """Entfernt '...'-Literale (inkl. ''-Escape), damit Keyword-Pruefung
    nicht auf Beispielwerten wie 'updated' anspringt."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _statements(sql: str) -> list[str]:
    executable = _strip_string_literals(_strip_comments(sql))
    return [part.strip() for part in executable.split(";") if part.strip()]


def _gsi_blocks() -> dict[str, dict[str, object]]:
    text = DYNAMODB_TF.read_text(encoding="utf-8")
    result: dict[str, dict[str, object]] = {}
    for chunk in text.split("global_secondary_index {")[1:]:
        block = chunk.split("\n  }", 1)[0]
        name_match = re.search(r'name\s*=\s*"([^"]+)"', block)
        projection_match = re.search(r'projection_type\s*=\s*"([^"]+)"', block)
        attrs_match = re.search(r"non_key_attributes\s*=\s*\[(.*?)\]", block, re.DOTALL)
        if not name_match or not projection_match:
            continue
        attrs: list[str] = []
        if attrs_match:
            attrs = re.findall(r'"([^"]+)"', attrs_match.group(1))
        result[name_match.group(1)] = {
            "projection": projection_match.group(1),
            "non_key_attributes": attrs,
        }
    return result


class TestDiagnosticsFiles(unittest.TestCase):
    def test_keyword_scanner_is_not_naive(self) -> None:
        # Kommentare und Strings duerfen die Pruefung nicht ausloesen ...
        benign = "-- DELETE ist hier nur Prosa\nSELECT 'UPDATE' FROM \"<TABLE_NAME>\";"
        executable = _strip_string_literals(_strip_comments(benign))
        self.assertEqual(FORBIDDEN_STATEMENTS.findall(executable), [])
        # ... ein echtes schreibendes Statement aber schon.
        malicious = "SELECT \"pk\" FROM \"<TABLE_NAME>\";\nDELETE FROM \"<TABLE_NAME>\";"
        self.assertTrue(FORBIDDEN_STATEMENTS.findall(_strip_comments(malicious)))

    def test_expected_files_exist(self) -> None:
        present = {path.name for path in DIAG_DIR.iterdir() if path.is_file()}
        self.assertEqual(EXPECTED_FILES - present, set(), f"fehlend: {EXPECTED_FILES - present}")

    def test_only_readonly_statements(self) -> None:
        for path in _partiql_files():
            statements = _statements(path.read_text(encoding="utf-8"))
            self.assertTrue(statements, f"{path.name}: keine Statements gefunden")
            for statement in statements:
                self.assertTrue(
                    statement.upper().startswith("SELECT"),
                    f"{path.name}: nicht-lesendes Statement: {statement[:60]!r}",
                )

    def test_no_write_keywords_outside_strings_and_comments(self) -> None:
        for path in _partiql_files():
            executable = _strip_string_literals(_strip_comments(path.read_text(encoding="utf-8")))
            matches = FORBIDDEN_STATEMENTS.findall(executable)
            self.assertEqual(matches, [], f"{path.name}: schreibende Keywords {matches}")

    def test_no_select_star(self) -> None:
        for path in _partiql_files():
            text = _strip_comments(path.read_text(encoding="utf-8"))
            self.assertNotRegex(text, r"(?i)select\s+\*", f"{path.name}: SELECT * vermeiden")

    def test_placeholders_are_documented_and_consistent(self) -> None:
        used: set[str] = set()
        for path in DIAG_DIR.iterdir():
            if path.is_file():
                used |= set(re.findall(r"<([A-Z][A-Z0-9_]*)>", path.read_text(encoding="utf-8")))
        undocumented = used - DOCUMENTED_PLACEHOLDERS
        self.assertEqual(undocumented, set(), f"undokumentierte Platzhalter: {undocumented}")
        readme = _read("README.md")
        for placeholder in DOCUMENTED_PLACEHOLDERS:
            self.assertIn(f"`<{placeholder}>`", readme, f"{placeholder} fehlt im README")


class TestDiagnosticsSafety(unittest.TestCase):
    def _all_text(self) -> dict[str, str]:
        return {
            path.name: path.read_text(encoding="utf-8")
            for path in DIAG_DIR.iterdir()
            if path.is_file()
        }

    def test_no_aws_account_numbers(self) -> None:
        for name, text in self._all_text().items():
            self.assertNotRegex(text, r"(?<!\d)\d{12}(?!\d)", f"{name}: echte Kontonummer?")

    def test_no_credentials_or_pii_samples(self) -> None:
        patterns = [
            r"AKIA[0-9A-Z]{16}",
            r"(?i)aws_secret_access_key",
            r"(?i)password\s*[:=]",
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            r"(?i)max mustermann",
        ]
        for name, text in self._all_text().items():
            for pattern in patterns:
                self.assertNotRegex(text, pattern, f"{name}: verdaechtiger Inhalt {pattern}")

    def test_readme_covers_required_topics(self) -> None:
        readme = _read("README.md").lower()
        for topic in ("partiql", "scan", "kosten", "limit", "pii", "restore"):
            self.assertIn(topic, readme, f"README: {topic} fehlt")
        self.assertIn("keine vollständige", readme, "README muss Validierungsgrenze nennen")

    def test_security_doc_covers_iam_and_isolation(self) -> None:
        doc = _read("security-and-iam.md")
        for needle in ("PartiQLSelect", "PartiQLInsert", "GetItem", "Query", "Scan", "Isolation"):
            self.assertIn(needle, doc, f"security-and-iam.md: {needle} fehlt")
        self.assertIn("keine", doc.lower())


class TestSchemaConsistency(unittest.TestCase):
    def test_gsi_definition_matches_terraform(self) -> None:
        gsis = _gsi_blocks()
        self.assertEqual(set(gsis), {"gsi1", "gsi2", "gsi3"}, "GSI-Parsing unvollstaendig")
        doc = _read("schema-reference.md")
        for name, meta in gsis.items():
            self.assertIn(f"`{name}`", doc)
            self.assertIn(str(meta["projection"]), doc)
            for attribute in meta["non_key_attributes"]:
                self.assertIn(attribute, doc, f"{name}: {attribute} fehlt in schema-reference")
        self.assertIn("KEYS_ONLY", doc)

    def test_gsi3_keys_only_is_documented_as_two_step(self) -> None:
        lines = [line for line in _read("schema-reference.md").splitlines() if "| `gsi3` |" in line]
        self.assertEqual(len(lines), 1, "gsi3-Zeile fehlt")
        self.assertIn("KEYS_ONLY", lines[0])
        self.assertIn("GetItem", _read("gsi-diagnostics.partiql"))

    def test_gsi2_does_not_claim_consumer_projection(self) -> None:
        meta = _gsi_blocks()["gsi2"]
        self.assertNotIn("consumerId", meta["non_key_attributes"])
        self.assertIn("consumerId", _read("schema-reference.md"))

    def test_key_patterns_documented(self) -> None:
        doc = _read("schema-reference.md")
        for pattern in ("ord_ord_<24hex>", "#ORDER", "SUBJECT#", "PROCESSING#RUNNING", "LIST"):
            self.assertIn(pattern, doc, f"Schluesselmuster fehlt: {pattern}")

    def test_known_documentation_conflict_is_flagged(self) -> None:
        doc = _read("schema-reference.md")
        self.assertIn("CONFLICT", doc)
        self.assertIn("ORDER#", doc)


if __name__ == "__main__":
    unittest.main()
