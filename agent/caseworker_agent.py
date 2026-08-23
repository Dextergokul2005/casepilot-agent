"""
agent/caseworker_agent.py

CaseworkerAgent — Workflow Orchestrator for CasePilot.

Responsibilities
----------------
- Coordinates the complete morning casework pipeline:
    ReferralLoader -> ContextBuilder -> PolicyEvaluator -> CaseRouter -> TriageGenerator -> AuditTracer
- Processes individual referrals (process_referral).
- Processes the full morning queue (run_morning_queue).
- Maintains strict authority boundaries:
    ALLOW    -> CaseRouter + TriageGenerator
    HANDOFF  -> CaseRouter (output/handoffs/) [TriageGenerator forbidden]
    ESCALATE -> CaseRouter (output/escalations/) [TriageGenerator forbidden]
- Persists unbroken execution traces via AuditTracer.

Architecture constraints
------------------------
- Dependency injection for all collaborators.
- Deterministic orchestration, standard-library only.
- No LLM calls.
- No network requests.
"""

from typing import Any, Dict, List

from models.policy_decision import ALLOW, ESCALATE, HANDOFF
from models.referral import Referral


class CaseworkerAgent:
    """
    Orchestrates the routine caseworker morning automation workflow.

    Parameters
    ----------
    referral_loader : ReferralLoader
        Loader service for reading incoming referral queue.
    context_builder : ContextBuilder
        Service for fetching resident history/household and building ResidentContext.
    policy_evaluator : PolicyEvaluator
        Deterministic authority policy evaluator.
    case_router : CaseRouter
        Router responsible for writing handoffs/escalations or returning ALLOW payload.
    triage_generator : TriageGenerator
        Service generating draft triage notes for ALLOW cases only.
    audit_tracer : AuditTracer
        Audit logger recording lifecycle execution traces.
    """

    def __init__(
        self,
        referral_loader,
        context_builder,
        policy_evaluator,
        case_router,
        triage_generator,
        audit_tracer,
    ):
        self.referral_loader = referral_loader
        self.context_builder = context_builder
        self.policy_evaluator = policy_evaluator
        self.case_router = case_router
        self.triage_generator = triage_generator
        self.audit_tracer = audit_tracer

    def process_referral(self, referral: Referral) -> Dict[str, Any]:
        """
        Process a single referral through the complete pipeline.

        Parameters
        ----------
        referral : Referral
            Incoming referral object.

        Returns
        -------
        dict
            Structured result of processing the referral.
        """
        referral_id = referral.referral_id
        resident_ref = referral.resident_ref

        # 1. Audit referral ingestion
        self.audit_tracer.log_referral_loaded(referral)

        try:
            # 2. Build ResidentContext
            context = self.context_builder.build(referral)
            self.audit_tracer.log_context_retrieved(context)

            # 3. Deterministic Policy Evaluation
            decision = self.policy_evaluator.evaluate(context)
            self.audit_tracer.log_policy_decision(
                referral_id=referral_id,
                resident_ref=resident_ref,
                decision=decision,
                requested_action=referral.requested_action,
            )

            # 4. Route Case (ALLOW, HANDOFF, ESCALATE)
            routing_result = self.case_router.route(context, decision)
            self.audit_tracer.log_routing(
                referral_id=referral_id,
                resident_ref=resident_ref,
                outcome=decision.outcome,
                destination=routing_result.get("destination"),
            )

            # 5. Triage Generation (Strictly ALLOW only)
            triage_note = None
            if decision.outcome == ALLOW:
                triage_note = self.triage_generator.generate(context, decision)

            return {
                "status": "SUCCESS",
                "referral_id": referral_id,
                "resident_ref": resident_ref,
                "outcome": decision.outcome,
                "policy_decision": decision.to_dict(),
                "routing": routing_result,
                "triage_note": triage_note,
                "error": None,
            }

        except Exception as exc:
            # Record failed processing without crashing the queue
            self.audit_tracer.log_event(
                event_type="PROCESSING_ERROR",
                referral_id=referral_id,
                resident_ref=resident_ref,
                details={"error": str(exc)},
            )
            return {
                "status": "FAILED",
                "referral_id": referral_id,
                "resident_ref": resident_ref,
                "outcome": None,
                "policy_decision": None,
                "routing": None,
                "triage_note": None,
                "error": str(exc),
            }

    def run_morning_queue(self) -> Dict[str, Any]:
        """
        Ingests the referral queue and processes all cases in batch.

        Returns
        -------
        dict
            Summary of morning run with counts and per-referral results.
        """
        referrals = self.referral_loader.load_referrals()
        results: List[Dict[str, Any]] = []

        allowed_count = 0
        handoff_count = 0
        escalated_count = 0
        failed_count = 0

        for referral in referrals:
            res = self.process_referral(referral)
            results.append(res)

            outcome = res.get("outcome")
            if res.get("status") == "FAILED":
                failed_count += 1
            elif outcome == ALLOW:
                allowed_count += 1
            elif outcome == HANDOFF:
                handoff_count += 1
            elif outcome == ESCALATE:
                escalated_count += 1

        # Persist execution trace
        self.audit_tracer.save()

        return {
            "total_processed": len(results),
            "allowed_count": allowed_count,
            "handoff_count": handoff_count,
            "escalated_count": escalated_count,
            "failed_count": failed_count,
            "results": results,
        }
