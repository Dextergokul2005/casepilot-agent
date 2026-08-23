"""
tests/test_case_router.py

Unit tests for services/case_router.py.

All tests write to temporary directories to ensure test isolation
and avoid polluting repository output directories.

Run with:
    python -m pytest tests/test_case_router.py -v
  or:
    python tests/test_case_router.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Project root on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.policy_decision import ALLOW, ESCALATE, HANDOFF, PolicyDecision
from models.referral import Referral
from models.resident_context import ResidentContext
from services.case_router import CaseRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_referral(
    referral_id="RF-2026-0412",
    received_at="2026-03-17T04:42:00",
    resident_ref="R-20500",
    source="Housing Options",
    summary="Resident reports rent arrears.",
    requested_action="Review award",
    urgency="Standard",
) -> Referral:
    return Referral(
        referral_id=referral_id,
        received_at=received_at,
        resident_ref=resident_ref,
        source=source,
        summary=summary,
        requested_action=requested_action,
        urgency=urgency,
    )


def _make_context(referral: Referral = None) -> ResidentContext:
    ref = referral or _make_referral()
    return ResidentContext(
        referral=ref,
        resident_history={"resident_ref": ref.resident_ref, "status": "Active"},
        household={"resident_ref": ref.resident_ref, "household": [{"name": "Jane", "age": 30}]},
        events={"resident_ref": ref.resident_ref, "events": [{"type": "Review", "date": "2025-01-01"}]},
    )


def _make_decision(outcome=ALLOW, rule_id="", policy_reference="ACA-2026/1", reason="Reason", evidence=None, required_action="Action") -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        policy_reference=policy_reference,
        rule_id=rule_id,
        reason=reason,
        evidence=evidence or ["Evidence 1"],
        required_action=required_action,
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestCaseRouter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.router = CaseRouter(output_root=self.temp_dir)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # 1. HANDOFF writes JSON artifact to handoffs directory
    # ------------------------------------------------------------------
    def test_handoff_writes_artifact_to_handoffs(self):
        context = _make_context(_make_referral(referral_id="RF-HANDOFF-1"))
        decision = _make_decision(
            outcome=HANDOFF,
            rule_id="3.9",
            policy_reference="ACA-2026/2",
            reason="Child under 18 in household",
            evidence=["Minor: Billy (age 5)"],
            required_action="A caseworker must complete the triage note.",
        )

        result = self.router.route(context, decision)

        expected_file = os.path.join(self.temp_dir, "handoffs", "RF-HANDOFF-1.json")
        self.assertTrue(os.path.exists(expected_file))
        self.assertEqual(result["destination"], expected_file)
        self.assertEqual(result["outcome"], HANDOFF)

    # ------------------------------------------------------------------
    # 2. ESCALATE writes JSON artifact to escalations directory
    # ------------------------------------------------------------------
    def test_escalate_writes_artifact_to_escalations(self):
        context = _make_context(_make_referral(referral_id="RF-ESCALATE-1"))
        decision = _make_decision(
            outcome=ESCALATE,
            rule_id="3.1",
            policy_reference="ACA-2026/1",
            reason="Award modification requested",
            evidence=["Action: Change award amount"],
            required_action="Supervisor review is required.",
        )

        result = self.router.route(context, decision)

        expected_file = os.path.join(self.temp_dir, "escalations", "RF-ESCALATE-1.json")
        self.assertTrue(os.path.exists(expected_file))
        self.assertEqual(result["destination"], expected_file)
        self.assertEqual(result["outcome"], ESCALATE)

    # ------------------------------------------------------------------
    # 3. ALLOW returns structured permitted payload
    # ------------------------------------------------------------------
    def test_allow_returns_permitted_payload(self):
        referral = _make_referral(referral_id="RF-ALLOW-1")
        context = _make_context(referral)
        decision = _make_decision(
            outcome=ALLOW,
            rule_id="",
            policy_reference="ACA-2026/1",
            reason="No restrictions triggered",
            evidence=["Action: Record change of address"],
            required_action="Normal triage processing may continue.",
        )

        result = self.router.route(context, decision)

        self.assertEqual(result["outcome"], ALLOW)
        self.assertEqual(result["status"], ALLOW)
        self.assertEqual(result["referral"]["referral_id"], "RF-ALLOW-1")
        self.assertEqual(result["resident_ref"], "R-20500")
        self.assertIn("resident_context", result)
        self.assertIn("policy_decision", result)
        self.assertEqual(result["required_action"], "Normal triage processing may continue.")
        self.assertIsNone(result["destination"])

    # ------------------------------------------------------------------
    # 4 & 5. ALLOW does not create handoff or escalation artifact
    # ------------------------------------------------------------------
    def test_allow_does_not_create_file_artifacts(self):
        context = _make_context(_make_referral(referral_id="RF-ALLOW-NO-FILE"))
        decision = _make_decision(outcome=ALLOW)

        self.router.route(context, decision)

        handoffs_dir = os.path.join(self.temp_dir, "handoffs")
        escalations_dir = os.path.join(self.temp_dir, "escalations")

        if os.path.exists(handoffs_dir):
            self.assertEqual(os.listdir(handoffs_dir), [])
        if os.path.exists(escalations_dir):
            self.assertEqual(os.listdir(escalations_dir), [])

    # ------------------------------------------------------------------
    # 6. HANDOFF artifact contains complete expected context & decision
    # ------------------------------------------------------------------
    def test_handoff_artifact_content(self):
        referral = _make_referral(referral_id="RF-HANDOFF-DATA", resident_ref="R-20500")
        context = _make_context(referral)
        decision = _make_decision(
            outcome=HANDOFF,
            rule_id="3.9",
            policy_reference="ACA-2026/2",
            reason="Household under 18 condition",
            evidence=["Household evidence"],
            required_action="Caseworker review required",
        )

        self.router.route(context, decision)

        target_file = os.path.join(self.temp_dir, "handoffs", "RF-HANDOFF-DATA.json")
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["outcome"], HANDOFF)
        self.assertEqual(data["referral"]["referral_id"], "RF-HANDOFF-DATA")
        self.assertEqual(data["resident_ref"], "R-20500")
        self.assertIn("resident_history", data)
        self.assertIn("household", data)
        self.assertIn("events", data)
        self.assertIn("policy_decision", data)
        self.assertEqual(data["policy_reference"], "ACA-2026/2")
        self.assertEqual(data["rule_id"], "3.9")
        self.assertEqual(data["reason"], "Household under 18 condition")
        self.assertEqual(data["evidence"], ["Household evidence"])
        self.assertEqual(data["required_action"], "Caseworker review required")

    # ------------------------------------------------------------------
    # 7. ESCALATE artifact contains complete expected context & decision
    # ------------------------------------------------------------------
    def test_escalate_artifact_content(self):
        referral = _make_referral(referral_id="RF-ESCALATE-DATA", resident_ref="R-20500")
        context = _make_context(referral)
        decision = _make_decision(
            outcome=ESCALATE,
            rule_id="3.4",
            policy_reference="ACA-2026/1",
            reason="Payment details alteration",
            evidence=["Requested action: Update payment details"],
            required_action="Supervisor review is required.",
        )

        self.router.route(context, decision)

        target_file = os.path.join(self.temp_dir, "escalations", "RF-ESCALATE-DATA.json")
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["outcome"], ESCALATE)
        self.assertEqual(data["referral"]["referral_id"], "RF-ESCALATE-DATA")
        self.assertEqual(data["resident_ref"], "R-20500")
        self.assertIn("resident_history", data)
        self.assertIn("household", data)
        self.assertIn("events", data)
        self.assertIn("policy_decision", data)
        self.assertEqual(data["policy_reference"], "ACA-2026/1")
        self.assertEqual(data["rule_id"], "3.4")
        self.assertEqual(data["reason"], "Payment details alteration")
        self.assertEqual(data["evidence"], ["Requested action: Update payment details"])
        self.assertEqual(data["required_action"], "Supervisor review is required.")

    # ------------------------------------------------------------------
    # 8. Output root is configurable
    # ------------------------------------------------------------------
    def test_output_root_configurable(self):
        custom_root = os.path.join(self.temp_dir, "custom_root_dir")
        router = CaseRouter(output_root=custom_root)

        context = _make_context(_make_referral(referral_id="RF-CUSTOM-ROOT"))
        decision = _make_decision(outcome=ESCALATE, rule_id="3.2")
        result = router.route(context, decision)

        expected_file = os.path.join(custom_root, "escalations", "RF-CUSTOM-ROOT.json")
        self.assertTrue(os.path.exists(expected_file))
        self.assertEqual(result["destination"], expected_file)

    # ------------------------------------------------------------------
    # 9. Output directories created automatically
    # ------------------------------------------------------------------
    def test_output_directories_created_automatically(self):
        fresh_root = os.path.join(self.temp_dir, "fresh_nested", "sub_path")
        router = CaseRouter(output_root=fresh_root)

        # Neither handoffs nor escalations directories exist yet
        self.assertFalse(os.path.exists(fresh_root))

        context = _make_context(_make_referral(referral_id="RF-AUTO-CREATE"))
        decision = _make_decision(outcome=HANDOFF, rule_id="3.9")
        router.route(context, decision)

        self.assertTrue(os.path.exists(os.path.join(fresh_root, "handoffs")))
        self.assertTrue(os.path.exists(os.path.join(fresh_root, "handoffs", "RF-AUTO-CREATE.json")))

    # ------------------------------------------------------------------
    # 10. Re-processing same referral safely replaces previous artifact
    # ------------------------------------------------------------------
    def test_reprocessing_safely_replaces_artifact(self):
        referral = _make_referral(referral_id="RF-REPLACE-TEST")
        context = _make_context(referral)

        decision1 = _make_decision(outcome=HANDOFF, rule_id="3.9", reason="Initial reason")
        self.router.route(context, decision1)

        target_file = os.path.join(self.temp_dir, "handoffs", "RF-REPLACE-TEST.json")
        with open(target_file, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        self.assertEqual(data1["reason"], "Initial reason")

        # Process again with updated decision
        decision2 = _make_decision(outcome=HANDOFF, rule_id="3.9", reason="Updated replacement reason")
        self.router.route(context, decision2)

        with open(target_file, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        self.assertEqual(data2["reason"], "Updated replacement reason")

    # ------------------------------------------------------------------
    # 11. Unknown outcome raises ValueError
    # ------------------------------------------------------------------
    def test_unknown_outcome_raises_value_error(self):
        context = _make_context()
        invalid_decision = _make_decision(outcome="INVALID_OUTCOME")

        with self.assertRaises(ValueError) as ctx:
            self.router.route(context, invalid_decision)

        self.assertIn("INVALID_OUTCOME", str(ctx.exception))

    # ------------------------------------------------------------------
    # 12. Artifacts can be cleanly loaded back with json.load()
    # ------------------------------------------------------------------
    def test_artifacts_valid_json(self):
        context_h = _make_context(_make_referral(referral_id="RF-JSON-VALID-H"))
        decision_h = _make_decision(outcome=HANDOFF, rule_id="3.9")
        res_h = self.router.route(context_h, decision_h)

        context_e = _make_context(_make_referral(referral_id="RF-JSON-VALID-E"))
        decision_e = _make_decision(outcome=ESCALATE, rule_id="3.1")
        res_e = self.router.route(context_e, decision_e)

        with open(res_h["destination"], "r", encoding="utf-8") as f:
            loaded_h = json.load(f)
        with open(res_e["destination"], "r", encoding="utf-8") as f:
            loaded_e = json.load(f)

        self.assertEqual(loaded_h["outcome"], HANDOFF)
        self.assertEqual(loaded_e["outcome"], ESCALATE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
