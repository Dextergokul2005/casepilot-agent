"""
main.py — CasePilot Entry Point.

Composes the system components using dependency injection and executes
the routine caseworker morning automation workflow.

Run with:
    python main.py
"""

import os
import sys
from typing import Any, Dict

from agent.caseworker_agent import CaseworkerAgent
from audit.audit_tracer import AuditTracer
from services.case_router import CaseRouter
from services.context_builder import ContextBuilder
from services.history_client import HistoryClient
from services.policy_evaluator import PolicyEvaluator
from services.policy_loader import PolicyLoader
from services.referral_loader import ReferralLoader
from services.triage_generator import TriageGenerator


def build_agent(
    data_path: str = None,
    history_base_url: str = "http://127.0.0.1:8083",
    policy_path: str = None,
    output_root: str = "output",
    audit_log_path: str = "audit/execution_trace.json",
) -> CaseworkerAgent:
    """
    Constructs and wires all CasePilot dependencies cleanly.
    """
    referral_loader = ReferralLoader(data_path=data_path)
    history_client = HistoryClient(base_url=history_base_url)
    context_builder = ContextBuilder(history_client=history_client)
    policy_loader = PolicyLoader(policy_path=policy_path)
    policy_evaluator = PolicyEvaluator(policy_loader=policy_loader)
    case_router = CaseRouter(output_root=output_root)
    triage_generator = TriageGenerator()
    audit_tracer = AuditTracer(log_path=audit_log_path)

    return CaseworkerAgent(
        referral_loader=referral_loader,
        context_builder=context_builder,
        policy_evaluator=policy_evaluator,
        case_router=case_router,
        triage_generator=triage_generator,
        audit_tracer=audit_tracer,
        triage_output_dir=os.path.join(output_root, "triage"),
    )


def print_run_summary(summary: Dict[str, Any], audit_path: str = "audit/execution_trace.json") -> None:
    """
    Prints a concise, readable summary of the morning batch run.
    """
    print("\n" + "=" * 60)
    print("           CasePilot — Morning Casework Summary           ")
    print("=" * 60)
    print(f" Total Referrals Processed : {summary.get('total_processed', 0)}")
    print(f"   - ALLOW (Draft Triaged) : {summary.get('allowed_count', 0)}")
    print(f"   - HANDOFF (Caseworker)  : {summary.get('handoff_count', 0)}")
    print(f"   - ESCALATE (Supervisor) : {summary.get('escalated_count', 0)}")
    print(f"   - Failed / Errors       : {summary.get('failed_count', 0)}")
    print("-" * 60)
    print(f" Audit Trace Saved         : {audit_path}")
    print("=" * 60 + "\n")


def main() -> None:
    """
    Application entry point.
    """
    print("CasePilot — Caseworker Morning Automation")
    print("Initializing components and starting morning queue run...\n")

    agent = build_agent()
    summary = agent.run_morning_queue()
    print_run_summary(summary, audit_path=agent.audit_tracer.log_path)


if __name__ == "__main__":
    main()
