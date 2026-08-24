"""
tests/test_end_to_end.py

End-to-End Integration Tests for CasePilot.

Validates the complete casework pipeline across all integrated components:
ReferralLoader -> ContextBuilder -> PolicyEvaluator -> CaseRouter -> TriageGenerator -> AuditTracer

All tests use temporary output/audit directories and mock History API data
to guarantee complete isolation and reproducibility without live network calls.

Run with:
    python -m pytest tests/test_end_to_end.py -v
  or:
    python tests/test_end_to_end.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Project root on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.caseworker_agent import CaseworkerAgent
from audit.audit_tracer import AuditTracer
from models.policy_decision import ALLOW, ESCALATE, HANDOFF
from models.referral import Referral
from services.case_router import CaseRouter
from services.context_builder import ContextBuilder
from services.policy_evaluator import PolicyEvaluator
from services.policy_loader import PolicyLoader
from services.referral_loader import ReferralLoader
from services.triage_generator import TriageGenerator


# ---------------------------------------------------------------------------
# Test Fixture & Mock History Client
# ---------------------------------------------------------------------------

class FakeHistoryClient:
    """
    In-memory fake HistoryClient providing deterministic resident histories
    without network socket calls.
    """

    def __init__(self, data=None):
        self.data = data or {}

    def health(self):
        return {"status": "ok", "service": "fake-history", "records": len(self.data)}

    def get_resident(self, resident_ref: str):
        if resident_ref in self.data:
            rec = self.data[resident_ref]
            return {
                "resident_ref": rec["resident_ref"],
                "status": rec.get("status", "Active"),
                "benefit_code": rec.get("benefit_code", "HSP-A"),
                "district": rec.get("district", "Calder Central"),
                "award_monthly": rec.get("award_monthly", 500.0),
                "household": rec.get("household", []),
                "events": rec.get("events", []),
            }
        return {"resident_ref": resident_ref, "status": "Active", "household": [], "events": []}

    def get_household(self, resident_ref: str):
        if resident_ref in self.data:
            return {"resident_ref": resident_ref, "household": self.data[resident_ref].get("household", [])}
        return {"resident_ref": resident_ref, "household": []}

    def get_events(self, resident_ref: str):
        if resident_ref in self.data:
            return {"resident_ref": resident_ref, "events": self.data[resident_ref].get("events", [])}
        return {"resident_ref": resident_ref, "events": []}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestEndToEndCasePilot(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_root = os.path.join(self.temp_dir, "output")
        self.triage_dir = os.path.join(self.output_root, "triage")
        self.audit_log_path = os.path.join(self.temp_dir, "audit", "trace.json")

        # Create temporary referral queue file
        self.queue_path = os.path.join(self.temp_dir, "test-queue.json")
        self._write_test_queue()

        # Build fake history database
        self.fake_history_data = {
            # Resident 1: Adult only (ALLOW case)
            "R-ALLOW-1": {
                "resident_ref": "R-ALLOW-1",
                "status": "Active",
                "benefit_code": "HSP-A",
                "district": "Calder Central",
                "award_monthly": 800.0,
                "household": [
                    {"name": "Alice Adult", "relationship": "Applicant", "date_of_birth": "1980-01-01"},
                ],
                "events": [{"date": "2025-01-01", "type": "Contact logged", "detail": "Routine check."}],
            },
            # Resident 2: Under-18 child in household (HANDOFF case under Rule 3.9)
            "R-HANDOFF-1": {
                "resident_ref": "R-HANDOFF-1",
                "status": "Active",
                "benefit_code": "HSP-B",
                "district": "Ash Hill",
                "award_monthly": 950.0,
                "household": [
                    {"name": "Bob Adult", "relationship": "Applicant", "date_of_birth": "1982-05-10"},
                    {"name": "Charlie Minor", "relationship": "Son/daughter", "date_of_birth": "2020-04-15"},
                ],
                "events": [],
            },
            # Resident 3: Adult only with restricted action (ESCALATE case under Rule 3.1)
            "R-ESCALATE-1": {
                "resident_ref": "R-ESCALATE-1",
                "status": "Active",
                "benefit_code": "HSP-C",
                "district": "Weybridge",
                "award_monthly": 600.0,
                "household": [
                    {"name": "David Adult", "relationship": "Applicant", "date_of_birth": "1975-08-20"},
                ],
                "events": [],
            },
        }

        # Compose dependencies
        self.history_client = FakeHistoryClient(self.fake_history_data)
        self.referral_loader = ReferralLoader(data_path=self.queue_path)
        self.context_builder = ContextBuilder(history_client=self.history_client)
        self.policy_loader = PolicyLoader()
        self.policy_evaluator = PolicyEvaluator(policy_loader=self.policy_loader)
        self.case_router = CaseRouter(output_root=self.output_root)
        self.triage_generator = TriageGenerator()
        self.audit_tracer = AuditTracer(log_path=self.audit_log_path)

        self.agent = CaseworkerAgent(
            referral_loader=self.referral_loader,
            context_builder=self.context_builder,
            policy_evaluator=self.policy_evaluator,
            case_router=self.case_router,
            triage_generator=self.triage_generator,
            audit_tracer=self.audit_tracer,
            triage_output_dir=self.triage_dir,
        )

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _write_test_queue(self):
        queue = [
            {
                "referral_id": "RF-TEST-001",
                "received_at": "2026-03-17T04:00:00",
                "resident_ref": "R-ALLOW-1",
                "source": "Housing Options",
                "summary": "Resident moved within district.",
                "requested_action": "Record change of address",
                "urgency": "Standard",
            },
            {
                "referral_id": "RF-TEST-002",
                "received_at": "2026-03-17T04:15:00",
                "resident_ref": "R-HANDOFF-1",
                "source": "Health Visitor",
                "summary": "Household support inquiry.",
                "requested_action": "Record change of address",
                "urgency": "Standard",
            },
            {
                "referral_id": "RF-TEST-003",
                "received_at": "2026-03-17T04:30:00",
                "resident_ref": "R-ESCALATE-1",
                "source": "District Office",
                "summary": "Requesting increase in monthly award.",
                "requested_action": "Change award amount",
                "urgency": "High",
            },
        ]
        with open(self.queue_path, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)

    # ------------------------------------------------------------------
    # 1 - 7. End-to-End Pipeline & Outcome Isolation
    # ------------------------------------------------------------------
    def test_complete_pipeline_flow(self):
        summary = self.agent.run_morning_queue()

        self.assertEqual(summary["total_processed"], 3)
        self.assertEqual(summary["allowed_count"], 1)
        self.assertEqual(summary["handoff_count"], 1)
        self.assertEqual(summary["escalated_count"], 1)
        self.assertEqual(summary["failed_count"], 0)

        # 1 & 2. Check ALLOW case (RF-TEST-001)
        allow_res = summary["results"][0]
        self.assertEqual(allow_res["outcome"], ALLOW)
        self.assertIsNotNone(allow_res["triage_note"])
        self.assertEqual(allow_res["triage_note"]["draft_status"], "PROPOSED_FOR_CASEWORKER_REVIEW")
        self.assertEqual(allow_res["triage_note"]["referral_id"], "RF-TEST-001")
        self.assertEqual(allow_res["triage_note"]["resident_ref"], "R-ALLOW-1")
        self.assertEqual(allow_res["triage_note"]["policy_outcome"], ALLOW)

        # 2 & 4 & 5. ALLOW artifact persisted under output/triage/
        triage_file = os.path.join(self.triage_dir, "RF-TEST-001.json")
        self.assertTrue(os.path.exists(triage_file))
        with open(triage_file, "r", encoding="utf-8") as f:
            t_data = json.load(f)
        self.assertEqual(t_data["referral_id"], "RF-TEST-001")
        self.assertEqual(t_data["resident_ref"], "R-ALLOW-1")
        self.assertEqual(t_data["policy_outcome"], ALLOW)

        # 7. ALLOW does not create file artifacts in handoffs or escalations
        self.assertFalse(os.path.exists(os.path.join(self.output_root, "handoffs", "RF-TEST-001.json")))
        self.assertFalse(os.path.exists(os.path.join(self.output_root, "escalations", "RF-TEST-001.json")))

        # 3 & 5 & 7. Check HANDOFF case (RF-TEST-002: under-18 child)
        handoff_res = summary["results"][1]
        self.assertEqual(handoff_res["outcome"], HANDOFF)
        self.assertIsNone(handoff_res["triage_note"])  # Must NOT draft note
        self.assertFalse(os.path.exists(os.path.join(self.triage_dir, "RF-TEST-002.json")))
        handoff_file = os.path.join(self.output_root, "handoffs", "RF-TEST-002.json")
        self.assertTrue(os.path.exists(handoff_file))
        with open(handoff_file, "r", encoding="utf-8") as f:
            h_data = json.load(f)
        self.assertEqual(h_data["rule_id"], "3.9")
        self.assertEqual(h_data["policy_reference"], "ACA-2026/2")

        # 4 & 6 & 8. Check ESCALATE case (RF-TEST-003: change award amount)
        escalate_res = summary["results"][2]
        self.assertEqual(escalate_res["outcome"], ESCALATE)
        self.assertIsNone(escalate_res["triage_note"])  # Must NOT draft note
        self.assertFalse(os.path.exists(os.path.join(self.triage_dir, "RF-TEST-003.json")))
        escalate_file = os.path.join(self.output_root, "escalations", "RF-TEST-003.json")
        self.assertTrue(os.path.exists(escalate_file))
        with open(escalate_file, "r", encoding="utf-8") as f:
            e_data = json.load(f)
        self.assertEqual(e_data["rule_id"], "3.1")
        self.assertEqual(e_data["policy_reference"], "ACA-2026/1")

    # ------------------------------------------------------------------
    # 8 & 9. AuditTracer records workflow & persists valid JSON
    # ------------------------------------------------------------------
    def test_audit_tracer_persistence_and_events(self):
        self.agent.run_morning_queue()

        self.assertTrue(os.path.exists(self.audit_log_path))
        with open(self.audit_log_path, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

        self.assertIn("events", audit_data)
        events = audit_data["events"]
        self.assertGreater(len(events), 0)

        # Confirm event types exist in correct sequence per referral
        event_types = [e["event_type"] for e in events if e.get("referral_id") == "RF-TEST-001"]
        self.assertIn("REFERRAL_INGESTED", event_types)
        self.assertIn("CONTEXT_RETRIEVED", event_types)
        self.assertIn("POLICY_EVALUATED", event_types)
        self.assertIn("CASE_ROUTED", event_types)
        self.assertIn("TRIAGE_GENERATED", event_types)

        # Verify details of TRIAGE_GENERATED event
        triage_event = [e for e in events if e.get("event_type") == "TRIAGE_GENERATED"][0]
        self.assertEqual(triage_event["referral_id"], "RF-TEST-001")
        self.assertEqual(triage_event["resident_ref"], "R-ALLOW-1")
        self.assertEqual(triage_event["outcome"], ALLOW)
        self.assertTrue(triage_event["destination"].endswith("RF-TEST-001.json"))

    # ------------------------------------------------------------------
    # 10. Multiple referrals processed independently
    # ------------------------------------------------------------------
    def test_referrals_processed_independently(self):
        summary = self.agent.run_morning_queue()
        self.assertEqual(len(summary["results"]), 3)
        self.assertEqual(summary["results"][0]["referral_id"], "RF-TEST-001")
        self.assertEqual(summary["results"][1]["referral_id"], "RF-TEST-002")
        self.assertEqual(summary["results"][2]["referral_id"], "RF-TEST-003")

    # ------------------------------------------------------------------
    # 11. One failed referral does not halt remaining referrals
    # ------------------------------------------------------------------
    def test_failed_referral_isolation(self):
        # Create a builder that fails specifically on the second referral
        failing_builder = MagicMock()
        context1 = self.context_builder.build(Referral(
            referral_id="RF-TEST-001",
            received_at="2026-03-17T04:00:00",
            resident_ref="R-ALLOW-1",
            source="Housing",
            summary="S1",
            requested_action="Record change of address",
            urgency="Standard",
        ))
        context3 = self.context_builder.build(Referral(
            referral_id="RF-TEST-003",
            received_at="2026-03-17T04:30:00",
            resident_ref="R-ESCALATE-1",
            source="District",
            summary="S3",
            requested_action="Change award amount",
            urgency="High",
        ))
        failing_builder.build.side_effect = [
            context1,
            RuntimeError("Simulated corruption in referral 2"),
            context3,
        ]

        agent = CaseworkerAgent(
            referral_loader=self.referral_loader,
            context_builder=failing_builder,
            policy_evaluator=self.policy_evaluator,
            case_router=self.case_router,
            triage_generator=self.triage_generator,
            audit_tracer=self.audit_tracer,
            triage_output_dir=self.triage_dir,
        )

        summary = agent.run_morning_queue()

        self.assertEqual(summary["total_processed"], 3)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["allowed_count"], 1)
        self.assertEqual(summary["escalated_count"], 1)
        self.assertEqual(summary["results"][0]["status"], "SUCCESS")
        self.assertEqual(summary["results"][1]["status"], "FAILED")
        self.assertEqual(summary["results"][2]["status"], "SUCCESS")

    # ------------------------------------------------------------------
    # 12. Final result outcome counts match reality
    # ------------------------------------------------------------------
    def test_outcome_counts_accuracy(self):
        summary = self.agent.run_morning_queue()
        total = summary["total_processed"]
        allowed = summary["allowed_count"]
        handoff = summary["handoff_count"]
        escalated = summary["escalated_count"]
        failed = summary["failed_count"]

        self.assertEqual(total, allowed + handoff + escalated + failed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
