"""
tests/test_triage_generator.py

Unit tests for services/triage_generator.py.

All tests are deterministic and do not require external services or networks.

Run with:
    python -m pytest tests/test_triage_generator.py -v
  or:
    python tests/test_triage_generator.py
"""

import os
import sys
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
from services.triage_generator import TriageGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_referral(
    referral_id="RF-2026-0413",
    received_at="2026-03-17T04:25:00",
    resident_ref="R-20507",
    source="Self-referral (online)",
    summary="New address notified. Resident has moved within the county.",
    requested_action="Record change of address",
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


def _make_context(
    referral: Referral = None,
    history: dict = None,
    household: dict = None,
    events: dict = None,
) -> ResidentContext:
    ref = referral or _make_referral()
    hist = history or {
        "resident_ref": ref.resident_ref,
        "status": "Active",
        "benefit_code": "HSP-C",
        "district": "Calder Central",
        "award_monthly": 707.9,
    }
    hh = household or {
        "resident_ref": ref.resident_ref,
        "household": [
            {"name": "Susan Marsh", "relationship": "Applicant", "date_of_birth": "1971-03-15"},
            {"name": "Sarah Hollis", "relationship": "Son/daughter", "date_of_birth": "2002-11-12"},
        ],
    }
    ev = events or {
        "resident_ref": ref.resident_ref,
        "events": [
            {"date": "2025-01-25", "type": "Evidence requested", "detail": "Left voicemail."},
            {"date": "2025-03-20", "type": "Address change recorded", "detail": "Attended office."},
        ],
    }
    return ResidentContext(
        referral=ref,
        resident_history=hist,
        household=hh,
        events=ev,
    )


def _make_decision(outcome=ALLOW, rule_id="", policy_reference="ACA-2026/1") -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        policy_reference=policy_reference,
        rule_id=rule_id,
        reason="Requested action is permitted under policy.",
        evidence=["Referral ID: RF-2026-0413", "Requested action: Record change of address"],
        required_action="Normal triage processing may continue.",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestTriageGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = TriageGenerator()

    # ------------------------------------------------------------------
    # 1. ALLOW produces structured triage result
    # ------------------------------------------------------------------
    def test_allow_produces_structured_result(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["policy_outcome"], ALLOW)
        self.assertEqual(result["draft_status"], "PROPOSED_FOR_CASEWORKER_REVIEW")

    # ------------------------------------------------------------------
    # 2 & 3. Result contains referral_id and resident_ref
    # ------------------------------------------------------------------
    def test_result_contains_identifiers(self):
        context = _make_context(_make_referral(referral_id="RF-ID-TEST", resident_ref="R-99999"))
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        self.assertEqual(result["referral_id"], "RF-ID-TEST")
        self.assertEqual(result["resident_ref"], "R-99999")

    # ------------------------------------------------------------------
    # 4. Result contains referral summary and urgency
    # ------------------------------------------------------------------
    def test_result_contains_summary_and_urgency(self):
        context = _make_context(_make_referral(summary="Custom referral text.", urgency="High"))
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        self.assertEqual(result["summary"], "Custom referral text.")
        self.assertEqual(result["urgency"], "High")

    # ------------------------------------------------------------------
    # 5. Result contains background information
    # ------------------------------------------------------------------
    def test_result_contains_background_info(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        bg = result["background"]
        self.assertIsInstance(bg, dict)
        self.assertEqual(bg["resident_status"], "Active")
        self.assertEqual(bg["benefit_code"], "HSP-C")
        self.assertEqual(bg["district"], "Calder Central")
        self.assertIn("707.90", bg["current_award"])
        self.assertEqual(bg["household_members_count"], 2)
        self.assertIsInstance(bg["recent_events"], list)

    # ------------------------------------------------------------------
    # 6. Result contains assessment
    # ------------------------------------------------------------------
    def test_result_contains_assessment(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        assessment = result["assessment"]
        self.assertIsInstance(assessment, str)
        self.assertIn("proposal", assessment.lower())
        self.assertIn("caseworker", assessment.lower())

    # ------------------------------------------------------------------
    # 7. Result contains recommended_actions
    # ------------------------------------------------------------------
    def test_result_contains_recommended_actions(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(context, decision)

        recs = result["recommended_actions"]
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)
        self.assertTrue(any("caseworker" in r.lower() for r in recs))

    # ------------------------------------------------------------------
    # 8. Result identifies policy reference and outcome
    # ------------------------------------------------------------------
    def test_result_identifies_policy_metadata(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW, policy_reference="ACA-2026/1")

        result = self.generator.generate(context, decision)

        self.assertEqual(result["policy_reference"], "ACA-2026/1")
        self.assertEqual(result["policy_outcome"], ALLOW)

    # ------------------------------------------------------------------
    # 9. HANDOFF raises ValueError
    # ------------------------------------------------------------------
    def test_handoff_raises_value_error(self):
        context = _make_context()
        decision = _make_decision(outcome=HANDOFF, rule_id="3.9")

        with self.assertRaises(ValueError) as ctx:
            self.generator.generate(context, decision)

        self.assertIn("HANDOFF", str(ctx.exception))

    # ------------------------------------------------------------------
    # 10. ESCALATE raises ValueError
    # ------------------------------------------------------------------
    def test_escalate_raises_value_error(self):
        context = _make_context()
        decision = _make_decision(outcome=ESCALATE, rule_id="3.1")

        with self.assertRaises(ValueError) as ctx:
            self.generator.generate(context, decision)

        self.assertIn("ESCALATE", str(ctx.exception))

    # ------------------------------------------------------------------
    # 11. Same input produces deterministic output
    # ------------------------------------------------------------------
    def test_deterministic_reproducible_output(self):
        context = _make_context()
        decision = _make_decision(outcome=ALLOW)

        result1 = self.generator.generate(context, decision)
        result2 = self.generator.generate(context, decision)

        self.assertEqual(result1, result2)

    # ------------------------------------------------------------------
    # 12 & 13. Empty history / events handled safely without fabrication
    # ------------------------------------------------------------------
    def test_empty_history_events_handled_safely(self):
        empty_context = ResidentContext(
            referral=_make_referral(),
            resident_history={},
            household={},
            events={},
        )
        decision = _make_decision(outcome=ALLOW)

        result = self.generator.generate(empty_context, decision)

        bg = result["background"]
        self.assertEqual(bg["resident_status"], "Unknown")
        self.assertEqual(bg["household_members_count"], 0)
        self.assertEqual(bg["household_members"], "No household members recorded")
        self.assertEqual(bg["recent_events"], ["No prior case events recorded."])


if __name__ == "__main__":
    unittest.main(verbosity=2)
