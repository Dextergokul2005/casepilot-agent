"""
tests/test_policy_evaluator.py

Unit tests for services/policy_evaluator.py.

All tests use mocks/fakes so that no live API server or network
connection is required.

Run with:
    python -m pytest tests/test_policy_evaluator.py -v
  or:
    python tests/test_policy_evaluator.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Project root on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.policy_decision import (
    ALLOW,
    ESCALATE,
    HANDOFF,
    PolicyDecision,
)
from models.referral import Referral
from models.resident_context import ResidentContext
from services.policy_evaluator import PolicyEvaluator


# ---------------------------------------------------------------------------
# Test Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_referral(
    referral_id="RF-2026-0001",
    received_at="2026-03-17T04:00:00",
    resident_ref="R-20001",
    source="Housing Options",
    summary="Standard referral summary.",
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


def _make_adult_household(resident_ref="R-20001") -> dict:
    return {
        "resident_ref": resident_ref,
        "household": [
            {
                "name": "Jane Adult",
                "date_of_birth": "1980-01-01",
                "relationship": "Applicant",
            },
            {
                "name": "John Adult",
                "date_of_birth": "1978-05-15",
                "relationship": "Partner",
            },
        ],
    }


def _make_minor_household(resident_ref="R-20001") -> dict:
    return {
        "resident_ref": resident_ref,
        "household": [
            {
                "name": "Jane Adult",
                "date_of_birth": "1985-01-01",
                "relationship": "Applicant",
            },
            {
                "name": "Billy Minor",
                "date_of_birth": "2020-06-01",
                "relationship": "Son/daughter",
            },
        ],
    }


def _make_context(referral: Referral, household: dict = None) -> ResidentContext:
    if household is None:
        household = _make_adult_household(referral.resident_ref)
    return ResidentContext(
        referral=referral,
        resident_history={"resident_ref": referral.resident_ref},
        household=household,
        events={"resident_ref": referral.resident_ref, "events": []},
    )


def _make_mock_policy_loader():
    mock = MagicMock()
    mock.load.return_value = {
        "policy_reference": "ACA-2026/1",
        "effective_from": "2026-03-01",
        "rules": [
            {"rule_id": "3.1", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.2", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.3", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.4", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.5", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.6", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.7", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.8", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
            {"rule_id": "3.9", "policy_reference": "ACA-2026/2", "outcome": "HANDOFF"},
            {"rule_id": "6.1", "policy_reference": "ACA-2026/1", "outcome": "ESCALATE"},
        ],
    }
    return mock


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestPolicyEvaluator(unittest.TestCase):

    def setUp(self):
        self.mock_loader = _make_mock_policy_loader()
        self.evaluator = PolicyEvaluator(self.mock_loader)

    # ------------------------------------------------------------------
    # 1. Clearly permitted action -> ALLOW
    # ------------------------------------------------------------------
    def test_clearly_permitted_action_returns_allow(self):
        referral = _make_referral(requested_action="Record change of address")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ALLOW)
        self.assertEqual(decision.policy_reference, "ACA-2026/1")
        self.assertEqual(decision.rule_id, "")
        self.assertIn("Normal triage processing", decision.required_action)
        self.assertTrue(any("RF-2026-0001" in item for item in decision.evidence))

    # ------------------------------------------------------------------
    # 2. Award / eligibility change -> ESCALATE 3.1
    # ------------------------------------------------------------------
    def test_award_change_returns_escalate_3_1(self):
        referral = _make_referral(requested_action="Change award amount")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.policy_reference, "ACA-2026/1")
        self.assertEqual(decision.rule_id, "3.1")
        self.assertIn("supervisor", decision.required_action.lower())

    # ------------------------------------------------------------------
    # 3. Suspension / termination / reinstatement -> ESCALATE 3.2
    # ------------------------------------------------------------------
    def test_suspension_reinstatement_returns_escalate_3_2(self):
        actions = [
            "Suspend assistance pending investigation",
            "Terminate award immediately",
            "Reinstate award from date of termination",
        ]
        for act in actions:
            with self.subTest(action=act):
                referral = _make_referral(requested_action=act)
                context = _make_context(referral, _make_adult_household())
                decision = self.evaluator.evaluate(context)

                self.assertEqual(decision.outcome, ESCALATE)
                self.assertEqual(decision.rule_id, "3.2")

    # ------------------------------------------------------------------
    # 4. Payment initiation / alteration / cancellation -> ESCALATE 3.3
    # ------------------------------------------------------------------
    def test_payment_initiation_returns_escalate_3_3(self):
        referral = _make_referral(requested_action="Issue payment for rent balance")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.3")

    # ------------------------------------------------------------------
    # 5. Payment detail change -> ESCALATE 3.4
    # ------------------------------------------------------------------
    def test_payment_detail_change_returns_escalate_3_4(self):
        referral = _make_referral(requested_action="Update payment details")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.4")

    # ------------------------------------------------------------------
    # 6. Communication to resident / third party -> ESCALATE 3.5
    # ------------------------------------------------------------------
    def test_communication_returns_escalate_3_5(self):
        referral = _make_referral(requested_action="Send letter to resident regarding claim")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.5")

    # ------------------------------------------------------------------
    # 7. External disclosure -> ESCALATE 3.6
    # ------------------------------------------------------------------
    def test_external_disclosure_returns_escalate_3_6(self):
        referral = _make_referral(requested_action="Disclose resident information to external agency")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.6")

    # ------------------------------------------------------------------
    # 8. Finding of fact about conduct / fraud -> ESCALATE 3.7
    # ------------------------------------------------------------------
    def test_finding_of_fact_returns_escalate_3_7(self):
        referral = _make_referral(requested_action="Record finding of fact regarding suspected fraud")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.7")

    # ------------------------------------------------------------------
    # 9. Irreversible action -> ESCALATE 3.8
    # ------------------------------------------------------------------
    def test_irreversible_action_returns_escalate_3_8(self):
        referral = _make_referral(requested_action="Action that cannot be reversed by department")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.8")

    # ------------------------------------------------------------------
    # 10. Under-18 household -> HANDOFF 3.9
    # ------------------------------------------------------------------
    def test_under_18_household_returns_handoff_3_9(self):
        referral = _make_referral(requested_action="Record change of address")
        context = _make_context(referral, _make_minor_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, HANDOFF)
        self.assertEqual(decision.policy_reference, "ACA-2026/2")
        self.assertEqual(decision.rule_id, "3.9")
        self.assertIn("caseworker", decision.required_action.lower())
        self.assertTrue(any("Billy Minor" in item or "Minor" in item for item in decision.evidence))

    # ------------------------------------------------------------------
    # 11. Household cannot be established -> HANDOFF 3.9
    # ------------------------------------------------------------------
    def test_household_cannot_be_established_returns_handoff_3_9(self):
        unestablished_cases = [
            None,
            {},
            {"resident_ref": "R-20001"},
            {"resident_ref": "R-20001", "household": "invalid_structure"},
            {"resident_ref": "R-20001", "household": [{"name": "NoAgeMember"}]},
        ]
        for hh in unestablished_cases:
            with self.subTest(household=hh):
                referral = _make_referral(requested_action="Record change of address")
                context = ResidentContext(
                    referral=referral,
                    resident_history={},
                    household=hh,
                    events={},
                )
                decision = self.evaluator.evaluate(context)

                self.assertEqual(decision.outcome, HANDOFF)
                self.assertEqual(decision.rule_id, "3.9")
                self.assertEqual(decision.policy_reference, "ACA-2026/2")

    # ------------------------------------------------------------------
    # 12. Ambiguous requested action -> ESCALATE 6.1
    # ------------------------------------------------------------------
    def test_ambiguous_requested_action_returns_escalate_6_1(self):
        referral = _make_referral(requested_action="Perform custom unspecified caseworker procedure")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.policy_reference, "ACA-2026/1")
        self.assertEqual(decision.rule_id, "6.1")
        self.assertIn("6.1", decision.reason)

    # ------------------------------------------------------------------
    # 13. Adult-only household with clearly permitted action -> ALLOW
    # ------------------------------------------------------------------
    def test_adult_only_household_permitted_action_returns_allow(self):
        referral = _make_referral(requested_action="Record income change")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ALLOW)
        self.assertEqual(decision.rule_id, "")

    # ------------------------------------------------------------------
    # 14. Under-18 household takes precedence over restricted action -> HANDOFF
    # ------------------------------------------------------------------
    def test_under_18_takes_precedence_over_restricted_action(self):
        # Action is "Change award amount" (normally ESCALATE 3.1), but household has a minor -> HANDOFF 3.9
        referral = _make_referral(requested_action="Change award amount")
        context = _make_context(referral, _make_minor_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, HANDOFF)
        self.assertEqual(decision.rule_id, "3.9")
        self.assertEqual(decision.policy_reference, "ACA-2026/2")

    # ------------------------------------------------------------------
    # 15. Evidence and required_action populated appropriately
    # ------------------------------------------------------------------
    def test_decision_evidence_and_required_action_populated(self):
        referral = _make_referral(requested_action="Change award amount")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertIsInstance(decision, PolicyDecision)
        self.assertIsInstance(decision.evidence, list)
        self.assertGreater(len(decision.evidence), 0)
        self.assertTrue(len(decision.required_action) > 0)
        self.assertTrue(len(decision.reason) > 0)

    # ------------------------------------------------------------------
    # 16. PolicyLoader used through dependency injection
    # ------------------------------------------------------------------
    def test_policy_loader_called_via_dependency_injection(self):
        referral = _make_referral(requested_action="Record change of address")
        context = _make_context(referral, _make_adult_household())

        self.evaluator.evaluate(context)

        self.mock_loader.load.assert_called_once()

    # ------------------------------------------------------------------
    # 17. Regression: "Review award" does NOT trigger 3.1
    # ------------------------------------------------------------------
    def test_review_award_does_not_trigger_3_1(self):
        referral = _make_referral(requested_action="Review award")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertNotEqual(decision.rule_id, "3.1")
        self.assertEqual(decision.outcome, ALLOW)

    # ------------------------------------------------------------------
    # 18. Regression: "Review eligibility" does NOT trigger 3.1
    # ------------------------------------------------------------------
    def test_review_eligibility_does_not_trigger_3_1(self):
        referral = _make_referral(requested_action="Review eligibility")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertNotEqual(decision.rule_id, "3.1")
        self.assertEqual(decision.outcome, ALLOW)

    # ------------------------------------------------------------------
    # 19. Regression: "Change award amount" triggers 3.1
    # ------------------------------------------------------------------
    def test_change_award_amount_triggers_3_1(self):
        referral = _make_referral(requested_action="Change award amount")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.1")

    # ------------------------------------------------------------------
    # 20. Regression: "Change eligibility status" triggers 3.1
    # ------------------------------------------------------------------
    def test_change_eligibility_status_triggers_3_1(self):
        referral = _make_referral(requested_action="Change eligibility status")
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, ESCALATE)
        self.assertEqual(decision.rule_id, "3.1")

    # ------------------------------------------------------------------
    # 21. Regression: Malformed received_at does NOT silently use 2026-03-01
    # ------------------------------------------------------------------
    def test_malformed_received_at_does_not_silently_invent_date(self):
        # DOB is provided, but received_at is invalid/missing -> age cannot be established -> HANDOFF 3.9
        referral = _make_referral(
            received_at="INVALID_TIMESTAMP",
            requested_action="Record change of address",
        )
        context = _make_context(referral, _make_adult_household())

        decision = self.evaluator.evaluate(context)

        self.assertEqual(decision.outcome, HANDOFF)
        self.assertEqual(decision.rule_id, "3.9")
        self.assertTrue(any("received_at is missing/invalid" in item for item in decision.evidence))

    # ------------------------------------------------------------------
    # 22. Regression: Explicit age or is_minor/under_18 evaluation
    # ------------------------------------------------------------------
    def test_explicit_age_and_minor_booleans_evaluated(self):
        # Test explicit age < 18
        hh_age_minor = {
            "resident_ref": "R-20001",
            "household": [{"name": "Child A", "age": 10}],
        }
        referral = _make_referral(requested_action="Record change of address")
        decision = self.evaluator.evaluate(_make_context(referral, hh_age_minor))
        self.assertEqual(decision.outcome, HANDOFF)
        self.assertEqual(decision.rule_id, "3.9")

        # Test explicit age >= 18
        hh_age_adult = {
            "resident_ref": "R-20001",
            "household": [{"name": "Adult A", "age": 30}],
        }
        decision = self.evaluator.evaluate(_make_context(referral, hh_age_adult))
        self.assertEqual(decision.outcome, ALLOW)

        # Test boolean is_minor=True
        hh_bool_minor = {
            "resident_ref": "R-20001",
            "household": [{"name": "Child B", "is_minor": True}],
        }
        decision = self.evaluator.evaluate(_make_context(referral, hh_bool_minor))
        self.assertEqual(decision.outcome, HANDOFF)
        self.assertEqual(decision.rule_id, "3.9")

        # Test boolean under_18=False
        hh_bool_adult = {
            "resident_ref": "R-20001",
            "household": [{"name": "Adult B", "under_18": False}],
        }
        decision = self.evaluator.evaluate(_make_context(referral, hh_bool_adult))
        self.assertEqual(decision.outcome, ALLOW)

    # ------------------------------------------------------------------
    # 23. Regression: False-positive prevention for broad standalone keywords
    # ------------------------------------------------------------------
    def test_broad_standalone_keywords_do_not_falsely_trigger_restrictions(self):
        # "Record change of address" contains "change", but is permitted (not 3.1 or 3.4)
        referral1 = _make_referral(requested_action="Record change of address")
        decision1 = self.evaluator.evaluate(_make_context(referral1, _make_adult_household()))
        self.assertEqual(decision1.outcome, ALLOW)

        # "Review payment details" contains "payment" and "details", but is a review (not 3.3 or 3.4) -> falls to ambiguous 6.1 or permitted
        # Since "review payment details" is not an explicit change/initiation, let's verify it is not 3.4
        referral2 = _make_referral(requested_action="Review payment procedure")
        decision2 = self.evaluator.evaluate(_make_context(referral2, _make_adult_household()))
        self.assertNotEqual(decision2.rule_id, "3.3")
        self.assertNotEqual(decision2.rule_id, "3.4")


if __name__ == "__main__":
    unittest.main(verbosity=2)
