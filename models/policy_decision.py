"""
models/policy_decision.py

Represents the outcome of a single policy evaluation.

This module is a pure data container.
No evaluation logic, no HTTP calls, no LLM calls.

The three permitted outcomes are defined as module-level constants so
that the rest of the codebase always uses a canonical string rather
than a bare literal.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Permitted outcome constants
# ---------------------------------------------------------------------------

ALLOW = "ALLOW"
HANDOFF = "HANDOFF"
ESCALATE = "ESCALATE"

PERMITTED_OUTCOMES = {ALLOW, HANDOFF, ESCALATE}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """
    The result of evaluating one referral against the authority policy.

    Fields
    ------
    outcome : str
        One of ``ALLOW``, ``HANDOFF``, or ``ESCALATE``.
    policy_reference : str
        The policy document that produced this decision,
        e.g. ``"ACA-2026/1"``.
    rule_id : str
        The specific rule that was triggered, e.g. ``"3.2"``.
        Use ``""`` when the outcome is ALLOW (no restricting rule fired).
    reason : str
        A human-readable explanation of why this decision was reached.
    evidence : List[str]
        Supporting details drawn from the referral or resident context
        that justified this decision.  May be an empty list.
    required_action : str
        What must happen next, e.g. ``"Route to supervisor"`` or
        ``"Pass to caseworker queue"``.
    """

    outcome: str
    policy_reference: str
    rule_id: str
    reason: str
    evidence: List[str]
    required_action: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary representation of this decision."""
        return {
            "outcome": self.outcome,
            "policy_reference": self.policy_reference,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "required_action": self.required_action,
        }
