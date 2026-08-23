"""
tests/test_caseworker_agent.py

Unit tests for agent/caseworker_agent.py.

All tests use mocks/fakes to ensure complete test isolation without
relying on real network services or disk artifacts.

Run with:
    python -m pytest tests/test_caseworker_agent.py -v
  or:
    python tests/test_caseworker_agent.py
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

from agent.caseworker_agent import CaseworkerAgent
from models.policy_decision import ALLOW, ESCALATE, HANDOFF, PolicyDecision
from models.referral import Referral
from models.resident_context import ResidentContext


# ---------------------------------------------------------------------------
# Fixtures & Mock Builders
# ---------------------------------------------------------------------------

def _make_referral(
    referral_id="RF-2026-0412",
    resident_ref="R-20500",
    requested_action="Record change of address",
) -> Referral:
    return Referral(
        referral_id=referral_id,
        received_at="2026-03-17T04:42:00",
        resident_ref=resident_ref,
        source="Housing Options",
        summary="Sample referral description.",
        requested_action=requested_action,
        urgency="Standard",
    )


def _make_context(referral: Referral) -> ResidentContext:
    return ResidentContext(
        referral=referral,
        resident_history={"resident_ref": referral.resident_ref, "status": "Active"},
        household={"resident_ref": referral.resident_ref, "household": []},
        events={"resident_ref": referral.resident_ref, "events": []},
    )


def _make_decision(outcome=ALLOW, rule_id="") -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        policy_reference="ACA-2026/1" if outcome != HANDOFF else "ACA-2026/2",
        rule_id=rule_id,
        reason="Decision reason",
        evidence=["Decision evidence"],
        required_action="Next action",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestCaseworkerAgent(unittest.TestCase):

    def setUp(self):
        self.mock_loader = MagicMock()
        self.mock_builder = MagicMock()
        self.mock_evaluator = MagicMock()
        self.mock_router = MagicMock()
        self.mock_generator = MagicMock()
        self.mock_tracer = MagicMock()

        self.agent = CaseworkerAgent(
            referral_loader=self.mock_loader,
            context_builder=self.mock_builder,
            policy_evaluator=self.mock_evaluator,
            case_router=self.mock_router,
            triage_generator=self.mock_generator,
            audit_tracer=self.mock_tracer,
        )

    # ------------------------------------------------------------------
    # 1 - 4. Pipeline Execution & Collaborator Invocations
    # ------------------------------------------------------------------
    def test_process_referral_executes_pipeline(self):
        referral = _make_referral(referral_id="RF-EXEC-1")
        context = _make_context(referral)
        decision = _make_decision(outcome=ALLOW)

        self.mock_builder.build.return_value = context
        self.mock_evaluator.evaluate.return_value = decision
        self.mock_router.route.return_value = {"status": ALLOW, "destination": None}
        self.mock_generator.generate.return_value = {"referral_id": "RF-EXEC-1", "draft_status": "PROPOSED"}

        result = self.agent.process_referral(referral)

        # Confirm collaborators called
        self.mock_builder.build.assert_called_once_with(referral)
        self.mock_evaluator.evaluate.assert_called_once_with(context)
        self.mock_router.route.assert_called_once_with(context, decision)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["outcome"], ALLOW)

    # ------------------------------------------------------------------
    # 5. ALLOW invokes TriageGenerator
    # ------------------------------------------------------------------
    def test_allow_invokes_triage_generator(self):
        referral = _make_referral()
        context = _make_context(referral)
        decision = _make_decision(outcome=ALLOW)

        self.mock_builder.build.return_value = context
        self.mock_evaluator.evaluate.return_value = decision
        self.mock_router.route.return_value = {"status": ALLOW}
        self.mock_generator.generate.return_value = {"draft": "Triage Note Content"}

        result = self.agent.process_referral(referral)

        self.mock_generator.generate.assert_called_once_with(context, decision)
        self.assertIsNotNone(result["triage_note"])
        self.assertEqual(result["triage_note"]["draft"], "Triage Note Content")

    # ------------------------------------------------------------------
    # 6. HANDOFF does NOT invoke TriageGenerator
    # ------------------------------------------------------------------
    def test_handoff_does_not_invoke_triage_generator(self):
        referral = _make_referral()
        context = _make_context(referral)
        decision = _make_decision(outcome=HANDOFF, rule_id="3.9")

        self.mock_builder.build.return_value = context
        self.mock_evaluator.evaluate.return_value = decision
        self.mock_router.route.return_value = {"status": HANDOFF, "destination": "/path/to/handoffs/RF.json"}

        result = self.agent.process_referral(referral)

        self.mock_generator.generate.assert_not_called()
        self.assertIsNone(result["triage_note"])
        self.assertEqual(result["outcome"], HANDOFF)

    # ------------------------------------------------------------------
    # 7. ESCALATE does NOT invoke TriageGenerator
    # ------------------------------------------------------------------
    def test_escalate_does_not_invoke_triage_generator(self):
        referral = _make_referral()
        context = _make_context(referral)
        decision = _make_decision(outcome=ESCALATE, rule_id="3.1")

        self.mock_builder.build.return_value = context
        self.mock_evaluator.evaluate.return_value = decision
        self.mock_router.route.return_value = {"status": ESCALATE, "destination": "/path/to/escalations/RF.json"}

        result = self.agent.process_referral(referral)

        self.mock_generator.generate.assert_not_called()
        self.assertIsNone(result["triage_note"])
        self.assertEqual(result["outcome"], ESCALATE)

    # ------------------------------------------------------------------
    # 8 - 10. Structured Result Returned Correctly for All Outcomes
    # ------------------------------------------------------------------
    def test_structured_results_returned(self):
        outcomes = [
            (ALLOW, ""),
            (HANDOFF, "3.9"),
            (ESCALATE, "3.2"),
        ]
        for out, rule in outcomes:
            with self.subTest(outcome=out):
                referral = _make_referral(referral_id=f"RF-{out}")
                context = _make_context(referral)
                decision = _make_decision(outcome=out, rule_id=rule)

                self.mock_builder.build.return_value = context
                self.mock_evaluator.evaluate.return_value = decision
                self.mock_router.route.return_value = {"status": out}
                self.mock_generator.generate.return_value = {"draft": "ok"} if out == ALLOW else None

                res = self.agent.process_referral(referral)

                self.assertEqual(res["status"], "SUCCESS")
                self.assertEqual(res["outcome"], out)
                self.assertEqual(res["referral_id"], f"RF-{out}")
                self.assertIn("policy_decision", res)

    # ------------------------------------------------------------------
    # 11 & 12. run_morning_queue processes multiple referrals with correct counts
    # ------------------------------------------------------------------
    def test_run_morning_queue_aggregates_counts(self):
        ref1 = _make_referral(referral_id="RF-1")
        ref2 = _make_referral(referral_id="RF-2")
        ref3 = _make_referral(referral_id="RF-3")
        self.mock_loader.load_referrals.return_value = [ref1, ref2, ref3]

        # Return ALLOW for ref1, HANDOFF for ref2, ESCALATE for ref3
        decisions = [
            _make_decision(outcome=ALLOW),
            _make_decision(outcome=HANDOFF, rule_id="3.9"),
            _make_decision(outcome=ESCALATE, rule_id="3.1"),
        ]
        self.mock_evaluator.evaluate.side_effect = decisions
        self.mock_router.route.side_effect = lambda ctx, dec: {"status": dec.outcome}

        summary = self.agent.run_morning_queue()

        self.assertEqual(summary["total_processed"], 3)
        self.assertEqual(summary["allowed_count"], 1)
        self.assertEqual(summary["handoff_count"], 1)
        self.assertEqual(summary["escalated_count"], 1)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(len(summary["results"]), 3)

    # ------------------------------------------------------------------
    # 13. Single referral failure does not crash the queue run
    # ------------------------------------------------------------------
    def test_single_failure_does_not_halt_queue(self):
        ref1 = _make_referral(referral_id="RF-FAIL-1")
        ref2 = _make_referral(referral_id="RF-SUCCESS-2")
        self.mock_loader.load_referrals.return_value = [ref1, ref2]

        # Context builder raises on ref1, succeeds on ref2
        self.mock_builder.build.side_effect = [
            RuntimeError("Simulated API failure on ref1"),
            _make_context(ref2),
        ]
        self.mock_evaluator.evaluate.return_value = _make_decision(outcome=ALLOW)
        self.mock_router.route.return_value = {"status": ALLOW}

        summary = self.agent.run_morning_queue()

        self.assertEqual(summary["total_processed"], 2)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["allowed_count"], 1)
        self.assertEqual(summary["results"][0]["status"], "FAILED")
        self.assertEqual(summary["results"][1]["status"], "SUCCESS")

    # ------------------------------------------------------------------
    # 14. AuditTracer receives lifecycle events
    # ------------------------------------------------------------------
    def test_audit_tracer_called_during_processing(self):
        referral = _make_referral()
        context = _make_context(referral)
        decision = _make_decision(outcome=ALLOW)

        self.mock_builder.build.return_value = context
        self.mock_evaluator.evaluate.return_value = decision
        self.mock_router.route.return_value = {"status": ALLOW, "destination": None}

        self.agent.process_referral(referral)

        self.mock_tracer.log_referral_loaded.assert_called_once_with(referral)
        self.mock_tracer.log_context_retrieved.assert_called_once_with(context)
        self.mock_tracer.log_policy_decision.assert_called_once()
        self.mock_tracer.log_routing.assert_called_once()

    # ------------------------------------------------------------------
    # 15. Audit trace is persisted after queue processing
    # ------------------------------------------------------------------
    def test_audit_tracer_saved_after_queue_run(self):
        self.mock_loader.load_referrals.return_value = [_make_referral()]
        self.mock_builder.build.return_value = _make_context(_make_referral())
        self.mock_evaluator.evaluate.return_value = _make_decision(outcome=ALLOW)
        self.mock_router.route.return_value = {"status": ALLOW}

        self.agent.run_morning_queue()

        self.mock_tracer.save.assert_called_once()

    # ------------------------------------------------------------------
    # 16. Dependencies are injected rather than instantiated internally
    # ------------------------------------------------------------------
    def test_dependency_injection_integrity(self):
        self.assertIs(self.agent.referral_loader, self.mock_loader)
        self.assertIs(self.agent.context_builder, self.mock_builder)
        self.assertIs(self.agent.policy_evaluator, self.mock_evaluator)
        self.assertIs(self.agent.case_router, self.mock_router)
        self.assertIs(self.agent.triage_generator, self.mock_generator)
        self.assertIs(self.agent.audit_tracer, self.mock_tracer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
