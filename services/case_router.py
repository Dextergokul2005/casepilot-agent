"""
services/case_router.py

Routes a evaluated referral according to its PolicyDecision outcome.

Responsibilities
----------------
- Ingests ResidentContext and PolicyDecision.
- For ALLOW: Returns structured permitted-triage payload without writing
  to handoff or escalation sinks.
- For HANDOFF: Atomically writes full caseworker package to
  {output_root}/handoffs/{referral_id}.json.
- For ESCALATE: Atomically writes full supervisor package to
  {output_root}/escalations/{referral_id}.json.
- Validates that outcome is one of ALLOW, HANDOFF, ESCALATE.

Architecture constraints
------------------------
- Deterministic routing only.
- No policy evaluation (relies on PolicyDecision.outcome).
- No LLM calls.
- No HTTP/network requests.
- Standard library only.
"""

import json
import os
import tempfile
from typing import Any, Dict, Optional

from models.policy_decision import ALLOW, ESCALATE, HANDOFF, PERMITTED_OUTCOMES, PolicyDecision
from models.resident_context import ResidentContext


class CaseRouter:
    """
    Dispatches a ResidentContext and PolicyDecision to appropriate
    destinations or payloads.

    Parameters
    ----------
    output_root : str
        Base directory under which 'handoffs' and 'escalations' subdirectories
        will be located. Defaults to "output".
    """

    def __init__(self, output_root: str = "output"):
        self.output_root = output_root

    @property
    def handoffs_dir(self) -> str:
        return os.path.join(self.output_root, "handoffs")

    @property
    def escalations_dir(self) -> str:
        return os.path.join(self.output_root, "escalations")

    def route(self, context: ResidentContext, decision: PolicyDecision) -> Dict[str, Any]:
        """
        Route a case according to its PolicyDecision outcome.

        Parameters
        ----------
        context : ResidentContext
            Full context for the resident/referral.
        decision : PolicyDecision
            Authoritative decision produced by PolicyEvaluator.

        Returns
        -------
        dict
            Structured outcome payload, including destination path if an
            artifact was written.

        Raises
        ------
        ValueError
            If decision.outcome is not in PERMITTED_OUTCOMES (ALLOW, HANDOFF, ESCALATE).
        """
        outcome = decision.outcome
        if outcome not in PERMITTED_OUTCOMES:
            raise ValueError(
                f"Unknown or invalid policy decision outcome: {outcome!r}. "
                f"Expected one of: {sorted(PERMITTED_OUTCOMES)}"
            )

        referral_dict = context.referral.to_dict()
        referral_id = context.referral.referral_id
        resident_ref = context.referral.resident_ref

        if outcome == ALLOW:
            return {
                "status": ALLOW,
                "outcome": ALLOW,
                "referral": referral_dict,
                "resident_ref": resident_ref,
                "resident_context": context.to_dict(),
                "policy_decision": decision.to_dict(),
                "required_action": decision.required_action,
                "destination": None,
            }

        if outcome == HANDOFF:
            payload = {
                "status": HANDOFF,
                "outcome": HANDOFF,
                "referral": referral_dict,
                "resident_ref": resident_ref,
                "resident_history": context.resident_history,
                "household": context.household,
                "events": context.events,
                "policy_decision": decision.to_dict(),
                "policy_reference": decision.policy_reference,
                "rule_id": decision.rule_id,
                "reason": decision.reason,
                "evidence": decision.evidence,
                "required_action": decision.required_action,
            }
            target_path = os.path.join(self.handoffs_dir, f"{referral_id}.json")
            self._write_json_atomically(target_path, payload)
            payload["destination"] = target_path
            return payload

        # outcome == ESCALATE
        payload = {
            "status": ESCALATE,
            "outcome": ESCALATE,
            "referral": referral_dict,
            "resident_ref": resident_ref,
            "resident_history": context.resident_history,
            "household": context.household,
            "events": context.events,
            "policy_decision": decision.to_dict(),
            "policy_reference": decision.policy_reference,
            "rule_id": decision.rule_id,
            "reason": decision.reason,
            "evidence": decision.evidence,
            "required_action": decision.required_action,
        }
        target_path = os.path.join(self.escalations_dir, f"{referral_id}.json")
        self._write_json_atomically(target_path, payload)
        payload["destination"] = target_path
        return payload

    def _write_json_atomically(self, target_path: str, data: Dict[str, Any]) -> None:
        """
        Safely and atomically writes JSON data to the target path.
        Creates parent directories if they do not exist.
        """
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)

        # Write to a temporary file in the target directory, then atomic rename/replace
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_dir,
            prefix="tmp_case_",
            suffix=".json",
            text=True,
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, target_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
