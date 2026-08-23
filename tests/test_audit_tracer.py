"""
tests/test_audit_tracer.py

Unit tests for audit/audit_tracer.py.

All tests write to temporary files/directories.

Run with:
    python -m pytest tests/test_audit_tracer.py -v
  or:
    python tests/test_audit_tracer.py
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

from audit.audit_tracer import (
    AuditTracer,
    EVENT_CASE_ROUTED,
    EVENT_CONTEXT_RETRIEVED,
    EVENT_POLICY_EVALUATED,
    EVENT_REFERRAL_INGESTED,
)
from models.policy_decision import ALLOW, ESCALATE, HANDOFF, PolicyDecision
from models.referral import Referral
from models.resident_context import ResidentContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_referral(referral_id="RF-2026-0412", resident_ref="R-20500") -> Referral:
    return Referral(
        referral_id=referral_id,
        received_at="2026-03-17T04:42:00",
        resident_ref=resident_ref,
        source="Housing Options",
        summary="Rent review inquiry",
        requested_action="Review award",
        urgency="Standard",
    )


def _make_context(referral: Referral = None) -> ResidentContext:
    ref = referral or _make_referral()
    return ResidentContext(
        referral=ref,
        resident_history={"resident_ref": ref.resident_ref, "status": "Active"},
        household={"resident_ref": ref.resident_ref, "household": [{"name": "Jane", "age": 30}]},
        events={"resident_ref": ref.resident_ref, "events": []},
    )


def _make_decision(outcome=ESCALATE, rule_id="3.1") -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        policy_reference="ACA-2026/1",
        rule_id=rule_id,
        reason="Award change restriction",
        evidence=["Requested action: Change award amount"],
        required_action="Supervisor review is required.",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestAuditTracer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_trace.json")
        self.tracer = AuditTracer(log_path=self.log_path)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # 1. Referral ingestion event is recorded
    # ------------------------------------------------------------------
    def test_log_referral_loaded_records_event(self):
        referral = _make_referral(referral_id="RF-INGEST-1", resident_ref="R-10001")
        event = self.tracer.log_referral_loaded(referral)

        self.assertEqual(event["event_type"], EVENT_REFERRAL_INGESTED)
        self.assertEqual(event["referral_id"], "RF-INGEST-1")
        self.assertEqual(event["resident_ref"], "R-10001")
        self.assertEqual(event["requested_action"], "Review award")
        self.assertIn("source", event["details"])
        self.assertEqual(self.tracer.count(), 1)

    # ------------------------------------------------------------------
    # 2. Context retrieval event is recorded
    # ------------------------------------------------------------------
    def test_log_context_retrieved_records_event(self):
        context = _make_context(_make_referral(referral_id="RF-CTX-1"))
        event = self.tracer.log_context_retrieved(context)

        self.assertEqual(event["event_type"], EVENT_CONTEXT_RETRIEVED)
        self.assertEqual(event["referral_id"], "RF-CTX-1")
        self.assertEqual(event["resident_ref"], "R-20500")
        self.assertIn("household_member_count", event["details"])
        self.assertEqual(self.tracer.count(), 1)

    # ------------------------------------------------------------------
    # 3. Policy evaluation event records outcome, rule_id, policy_reference
    # ------------------------------------------------------------------
    def test_log_policy_decision_records_metadata(self):
        decision = _make_decision(outcome=ESCALATE, rule_id="3.1")
        event = self.tracer.log_policy_decision(
            referral_id="RF-POLICY-1",
            resident_ref="R-20500",
            decision=decision,
            requested_action="Change award amount",
        )

        self.assertEqual(event["event_type"], EVENT_POLICY_EVALUATED)
        self.assertEqual(event["outcome"], ESCALATE)
        self.assertEqual(event["rule_id"], "3.1")
        self.assertEqual(event["policy_reference"], "ACA-2026/1")
        self.assertEqual(event["requested_action"], "Change award amount")
        self.assertIn("reason", event["details"])
        self.assertIn("evidence", event["details"])

    # ------------------------------------------------------------------
    # 4. Routing event records destination
    # ------------------------------------------------------------------
    def test_log_routing_records_destination(self):
        dest = "/path/to/output/escalations/RF-ROUTED-1.json"
        event = self.tracer.log_routing(
            referral_id="RF-ROUTED-1",
            resident_ref="R-20500",
            outcome=ESCALATE,
            destination=dest,
        )

        self.assertEqual(event["event_type"], EVENT_CASE_ROUTED)
        self.assertEqual(event["destination"], dest)
        self.assertEqual(event["outcome"], ESCALATE)

    # ------------------------------------------------------------------
    # 5. Events contain required canonical keys
    # ------------------------------------------------------------------
    def test_events_contain_canonical_keys(self):
        self.tracer.log_event(
            event_type="CUSTOM_EVENT",
            referral_id="RF-CANON-1",
            resident_ref="R-99999",
            details={"key": "val"},
        )
        events = self.tracer.get_events()
        self.assertEqual(len(events), 1)
        event = events[0]

        self.assertIn("timestamp", event)
        self.assertIn("referral_id", event)
        self.assertIn("resident_ref", event)
        self.assertIn("event_type", event)
        self.assertIn("details", event)

    # ------------------------------------------------------------------
    # 6. Events preserve insertion order
    # ------------------------------------------------------------------
    def test_events_preserve_insertion_order(self):
        referral = _make_referral(referral_id="RF-ORDER-1")
        context = _make_context(referral)
        decision = _make_decision(outcome=ALLOW, rule_id="")

        self.tracer.log_referral_loaded(referral)
        self.tracer.log_context_retrieved(context)
        self.tracer.log_policy_decision(referral.referral_id, referral.resident_ref, decision)
        self.tracer.log_routing(referral.referral_id, referral.resident_ref, outcome=ALLOW, destination=None)

        events = self.tracer.get_events()
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0]["event_type"], EVENT_REFERRAL_INGESTED)
        self.assertEqual(events[1]["event_type"], EVENT_CONTEXT_RETRIEVED)
        self.assertEqual(events[2]["event_type"], EVENT_POLICY_EVALUATED)
        self.assertEqual(events[3]["event_type"], EVENT_CASE_ROUTED)

    # ------------------------------------------------------------------
    # 7. Multiple referrals can be recorded
    # ------------------------------------------------------------------
    def test_multiple_referrals_recorded(self):
        ref1 = _make_referral(referral_id="RF-MULTI-1")
        ref2 = _make_referral(referral_id="RF-MULTI-2")

        self.tracer.log_referral_loaded(ref1)
        self.tracer.log_referral_loaded(ref2)

        self.assertEqual(self.tracer.count(), 2)

    # ------------------------------------------------------------------
    # 8. Filtering / querying events works
    # ------------------------------------------------------------------
    def test_filtering_events(self):
        ref1 = _make_referral(referral_id="RF-FILTER-1")
        ref2 = _make_referral(referral_id="RF-FILTER-2")

        self.tracer.log_referral_loaded(ref1)
        self.tracer.log_policy_decision("RF-FILTER-1", "R-1", _make_decision(outcome=ALLOW))
        self.tracer.log_referral_loaded(ref2)
        self.tracer.log_policy_decision("RF-FILTER-2", "R-2", _make_decision(outcome=ESCALATE))

        ref1_events = self.tracer.get_events_for_referral("RF-FILTER-1")
        self.assertEqual(len(ref1_events), 2)
        self.assertTrue(all(e["referral_id"] == "RF-FILTER-1" for e in ref1_events))

        allow_events = self.tracer.get_events_by_outcome(ALLOW)
        self.assertEqual(len(allow_events), 1)
        self.assertEqual(allow_events[0]["referral_id"], "RF-FILTER-1")

        escalate_events = self.tracer.get_events_by_outcome(ESCALATE)
        self.assertEqual(len(escalate_events), 1)
        self.assertEqual(escalate_events[0]["referral_id"], "RF-FILTER-2")

    # ------------------------------------------------------------------
    # 9, 10, 11. Execution trace persistence to valid JSON containing all events
    # ------------------------------------------------------------------
    def test_save_execution_trace(self):
        ref = _make_referral(referral_id="RF-PERSIST-1")
        self.tracer.log_referral_loaded(ref)
        self.tracer.log_policy_decision("RF-PERSIST-1", "R-1", _make_decision(outcome=HANDOFF, rule_id="3.9"))

        saved_path = self.tracer.save()
        self.assertEqual(saved_path, self.log_path)
        self.assertTrue(os.path.exists(self.log_path))

        with open(self.log_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("events", data)
        self.assertEqual(len(data["events"]), 2)
        self.assertEqual(data["events"][0]["referral_id"], "RF-PERSIST-1")
        self.assertEqual(data["events"][1]["outcome"], HANDOFF)

    # ------------------------------------------------------------------
    # 12. Immutability: tracer internal state cannot be mutated by caller
    # ------------------------------------------------------------------
    def test_returned_events_are_copies(self):
        ref = _make_referral(referral_id="RF-IMMUTABLE-1")
        self.tracer.log_referral_loaded(ref)

        events = self.tracer.get_events()
        events[0]["referral_id"] = "MUTATED_ID"

        # Internal state must not be modified
        internal_events = self.tracer.get_events()
        self.assertEqual(internal_events[0]["referral_id"], "RF-IMMUTABLE-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
