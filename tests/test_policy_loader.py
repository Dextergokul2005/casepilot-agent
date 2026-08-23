"""
tests/test_policy_loader.py

Unit tests for services/policy_loader.py.

These tests work against the real policy/policy_rules.json file and
also use temporary in-memory JSON to verify error handling.

Run with:
    python -m pytest tests/test_policy_loader.py -v
  or:
    python tests/test_policy_loader.py
"""

import json
import os
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Project root on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.policy_loader import PolicyLoader


# ---------------------------------------------------------------------------
# Helper: write a temporary JSON file and return a PolicyLoader for it.
# ---------------------------------------------------------------------------

def _loader_for(content: str) -> PolicyLoader:
    """Write *content* to a temp file and return a PolicyLoader for it."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return PolicyLoader(policy_path=tmp.name)


# Expected rule IDs in the policy file.
ESCALATE_RULE_IDS = {"3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8"}
HANDOFF_RULE_IDS  = {"3.9"}
ALL_RULE_IDS      = ESCALATE_RULE_IDS | HANDOFF_RULE_IDS | {"6.1"}


# ---------------------------------------------------------------------------
# Tests against the real policy file
# ---------------------------------------------------------------------------

class TestPolicyLoaderRealFile(unittest.TestCase):
    """Tests that read the actual policy/policy_rules.json."""

    @classmethod
    def setUpClass(cls):
        """Load the policy once for all tests in this class."""
        cls.loader = PolicyLoader()
        cls.policy = cls.loader.load()
        cls.rules_by_id = {r["rule_id"]: r for r in cls.policy["rules"]}

    # ------------------------------------------------------------------
    # Test 1 — file loads successfully
    # ------------------------------------------------------------------
    def test_load_succeeds(self):
        """Policy file loads without raising an exception."""
        self.assertIsInstance(self.policy, dict)

    # ------------------------------------------------------------------
    # Test 2 — policy_reference is ACA-2026/1
    # ------------------------------------------------------------------
    def test_policy_reference_is_aca_2026_1(self):
        """Top-level policy_reference must be 'ACA-2026/1'."""
        self.assertEqual(
            self.policy["policy_reference"],
            "ACA-2026/1",
            f"Expected 'ACA-2026/1', got {self.policy['policy_reference']!r}.",
        )

    # ------------------------------------------------------------------
    # Test 3 — all expected rule IDs 3.1–3.9 are present
    # ------------------------------------------------------------------
    def test_all_expected_rules_present(self):
        """Rules 3.1 through 3.9 must all be present."""
        for rule_id in ESCALATE_RULE_IDS | HANDOFF_RULE_IDS:
            with self.subTest(rule_id=rule_id):
                self.assertIn(
                    rule_id,
                    self.rules_by_id,
                    f"Rule {rule_id!r} is missing from the policy file.",
                )

    # ------------------------------------------------------------------
    # Test 4 — rules 3.1–3.8 have outcome ESCALATE
    # ------------------------------------------------------------------
    def test_rules_3_1_to_3_8_outcome_is_escalate(self):
        """Rules 3.1 through 3.8 must each have outcome 'ESCALATE'."""
        for rule_id in ESCALATE_RULE_IDS:
            with self.subTest(rule_id=rule_id):
                outcome = self.rules_by_id[rule_id]["outcome"]
                self.assertEqual(
                    outcome,
                    "ESCALATE",
                    f"Rule {rule_id!r} has outcome {outcome!r}, expected 'ESCALATE'.",
                )

    # ------------------------------------------------------------------
    # Test 5 — rule 3.9 has outcome HANDOFF
    # ------------------------------------------------------------------
    def test_rule_3_9_outcome_is_handoff(self):
        """Rule 3.9 must have outcome 'HANDOFF'."""
        outcome = self.rules_by_id["3.9"]["outcome"]
        self.assertEqual(
            outcome,
            "HANDOFF",
            f"Rule 3.9 has outcome {outcome!r}, expected 'HANDOFF'.",
        )

    # ------------------------------------------------------------------
    # Test 6 — rule 6.1 is represented
    # ------------------------------------------------------------------
    def test_rule_6_1_is_present(self):
        """Interpretation rule 6.1 must be present in the policy file."""
        self.assertIn(
            "6.1",
            self.rules_by_id,
            "Interpretation rule 6.1 is missing from the policy file.",
        )

    def test_rule_6_1_outcome_is_escalate(self):
        """Interpretation rule 6.1 must have outcome 'ESCALATE'."""
        outcome = self.rules_by_id["6.1"]["outcome"]
        self.assertEqual(outcome, "ESCALATE")

    # ------------------------------------------------------------------
    # Test 7 — every rule has the required metadata fields
    # ------------------------------------------------------------------
    def test_every_rule_has_required_metadata(self):
        """Every rule must contain all required metadata fields."""
        required = {"rule_id", "policy_reference", "description",
                    "outcome", "stop_current_action", "source"}
        for rule in self.policy["rules"]:
            with self.subTest(rule_id=rule.get("rule_id", "<unknown>")):
                missing = required - rule.keys()
                self.assertFalse(
                    missing,
                    f"Rule {rule.get('rule_id')!r} is missing fields: {sorted(missing)}",
                )

    def test_get_rules_returns_list(self):
        """get_rules() returns a non-empty list."""
        rules = self.loader.get_rules()
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

    def test_get_rule_by_id_returns_correct_rule(self):
        """get_rule_by_id('3.1') returns the rule with rule_id '3.1'."""
        rule = self.loader.get_rule_by_id("3.1")
        self.assertEqual(rule["rule_id"], "3.1")

    def test_get_rule_by_id_unknown_raises_key_error(self):
        """get_rule_by_id() raises KeyError for a non-existent rule_id."""
        with self.assertRaises(KeyError):
            self.loader.get_rule_by_id("DOES_NOT_EXIST")


# ---------------------------------------------------------------------------
# Tests for error handling (malformed / missing policy data)
# ---------------------------------------------------------------------------

class TestPolicyLoaderErrorHandling(unittest.TestCase):
    """Test 8 — malformed or missing policy data raises a clear error."""

    def test_missing_file_raises_file_not_found(self):
        """A path that does not exist raises FileNotFoundError."""
        loader = PolicyLoader(policy_path="/nonexistent/path/policy.json")
        with self.assertRaises(FileNotFoundError):
            loader.load()

    def test_invalid_json_raises_value_error(self):
        """A file containing invalid JSON raises ValueError."""
        loader = _loader_for("{ this is not valid json }")
        with self.assertRaises(ValueError):
            loader.load()

    def test_missing_top_level_field_raises_value_error(self):
        """A document missing 'effective_from' raises ValueError."""
        content = json.dumps({"policy_reference": "ACA-2026/1", "rules": []})
        loader = _loader_for(content)
        with self.assertRaises(ValueError):
            loader.load()

    def test_empty_rules_list_raises_value_error(self):
        """An empty 'rules' array raises ValueError."""
        content = json.dumps({
            "policy_reference": "ACA-2026/1",
            "effective_from": "2026-01-01",
            "rules": [],
        })
        loader = _loader_for(content)
        with self.assertRaises(ValueError):
            loader.load()

    def test_rule_missing_field_raises_value_error(self):
        """A rule missing 'outcome' raises ValueError with a clear message."""
        content = json.dumps({
            "policy_reference": "ACA-2026/1",
            "effective_from": "2026-01-01",
            "rules": [
                {
                    "rule_id": "3.1",
                    "policy_reference": "ACA-2026/1",
                    "description": "Missing outcome field.",
                    "stop_current_action": True,
                    "source": "ACA-2026/1 section 3.1"
                    # 'outcome' deliberately omitted
                }
            ],
        })
        loader = _loader_for(content)
        with self.assertRaises(ValueError) as ctx:
            loader.load()
        self.assertIn("outcome", str(ctx.exception))

    def test_top_level_is_list_not_dict_raises_value_error(self):
        """A top-level JSON array (instead of object) raises ValueError."""
        loader = _loader_for("[]")
        with self.assertRaises(ValueError):
            loader.load()


# ---------------------------------------------------------------------------
# Allow running directly: python tests/test_policy_loader.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
