"""
services/triage_generator.py

Generates structured, deterministic draft triage notes for ALLOW cases.

Responsibilities
----------------
- Only operates when PolicyDecision.outcome == ALLOW.
- Raises ValueError if invoked on HANDOFF or ESCALATE.
- Synthesizes referral data, resident history, household composition,
  and prior events into a structured draft note for human caseworker review.
- Frames recommendations strictly as proposals for human review.
- Avoids asserting or executing restricted authority actions.

Architecture constraints
------------------------
- Deterministic, standard-library only.
- No LLM calls.
- No network requests.
- Does not modify policy or case data.
"""

from typing import Any, Dict, List

from models.policy_decision import ALLOW, ESCALATE, HANDOFF, PolicyDecision
from models.resident_context import ResidentContext


class TriageGenerator:
    """
    Produces structured draft triage notes for cases permitted by policy.
    """

    def generate(
        self,
        context: ResidentContext,
        decision: PolicyDecision,
    ) -> Dict[str, Any]:
        """
        Generate a structured draft triage note for an ALLOW case.

        Parameters
        ----------
        context : ResidentContext
            Authoritative context for the resident and referral.
        decision : PolicyDecision
            Evaluated policy decision. Must have outcome == ALLOW.

        Returns
        -------
        dict
            Structured draft triage note dictionary.

        Raises
        ------
        ValueError
            If decision.outcome is not ALLOW (e.g. HANDOFF or ESCALATE).
        """
        if decision.outcome != ALLOW:
            raise ValueError(
                f"TriageGenerator cannot generate notes for {decision.outcome!r} cases. "
                "Triage note drafting is strictly reserved for ALLOW outcomes under policy."
            )

        referral = context.referral
        background = self._build_background(context)
        assessment = self._build_assessment(referral, decision)
        recommended_actions = self._build_recommended_actions(referral)

        return {
            "referral_id": referral.referral_id,
            "resident_ref": referral.resident_ref,
            "summary": referral.summary,
            "urgency": referral.urgency,
            "requested_action": referral.requested_action,
            "background": background,
            "assessment": assessment,
            "recommended_actions": recommended_actions,
            "policy_reference": decision.policy_reference,
            "policy_outcome": ALLOW,
            "draft_status": "PROPOSED_FOR_CASEWORKER_REVIEW",
        }

    # ------------------------------------------------------------------
    # Internal Synthesis Helpers
    # ------------------------------------------------------------------

    def _build_background(self, context: ResidentContext) -> Dict[str, Any]:
        """Synthesize authoritative background facts without fabrication."""
        history = context.resident_history if isinstance(context.resident_history, dict) else {}
        household_data = context.household if isinstance(context.household, dict) else {}
        events_data = context.events if isinstance(context.events, dict) else {}

        # History summary
        status = history.get("status", "Unknown")
        benefit_code = history.get("benefit_code", "None recorded")
        district = history.get("district", "Unspecified")
        award_monthly = history.get("award_monthly")
        award_str = f"£{award_monthly:.2f}/month" if isinstance(award_monthly, (int, float)) else "No active award recorded"

        # Household summary
        members = household_data.get("household", [])
        household_summary: List[Dict[str, Any]] = []
        if isinstance(members, list) and members:
            for m in members:
                if isinstance(m, dict):
                    household_summary.append({
                        "name": m.get("name", "Unknown"),
                        "relationship": m.get("relationship", "Unknown"),
                        "date_of_birth": m.get("date_of_birth", m.get("age", "Not specified")),
                    })

        # Recent events
        raw_events = events_data.get("events", [])
        recent_events: List[str] = []
        if isinstance(raw_events, list) and raw_events:
            for ev in raw_events[-3:]:  # Last 3 events
                if isinstance(ev, dict):
                    ev_date = ev.get("date", "Unknown date")
                    ev_type = ev.get("type", "Event")
                    ev_detail = ev.get("detail", "")
                    recent_events.append(f"{ev_date}: {ev_type} ({ev_detail})".strip())

        return {
            "resident_status": status,
            "benefit_code": benefit_code,
            "district": district,
            "current_award": award_str,
            "household_members_count": len(household_summary),
            "household_members": household_summary if household_summary else "No household members recorded",
            "recent_events": recent_events if recent_events else ["No prior case events recorded."],
        }

    def _build_assessment(self, referral: Any, decision: PolicyDecision) -> str:
        """Construct transparent, non-executory casework assessment text."""
        return (
            f"Referral {referral.referral_id} concerning requested action '{referral.requested_action}' "
            f"was evaluated under authority policy {decision.policy_reference}. "
            "No authority restrictions were triggered. The requested task falls within routine casework "
            "scope and is eligible for automated triage drafting. This draft note is a proposal and has "
            "no operational effect until adopted by a human caseworker."
        )

    def _build_recommended_actions(self, referral: Any) -> List[str]:
        """Propose safe, review-oriented next steps for the caseworker."""
        action_lower = (referral.requested_action or "").lower()

        suggestions: List[str] = [
            f"Caseworker to review the referral request: '{referral.requested_action}'.",
        ]

        if "address" in action_lower:
            suggestions.append("Verify new address proof in attached documentation and update residential record if verified.")
        elif "income" in action_lower or "training" in action_lower or "employment" in action_lower:
            suggestions.append("Examine income verification evidence and determine if reassessment should be scheduled.")
        elif "household" in action_lower:
            suggestions.append("Verify reported household composition change against registry records.")
        elif "note" in action_lower or "explanatory" in action_lower:
            suggestions.append("Review payment and award history to prepare resident response.")
        elif "contact" in action_lower:
            suggestions.append("Attempt standard contact protocol via verified resident channels.")
        else:
            suggestions.append("Review case file history and proceed with standard verification procedure.")

        suggestions.append("Caseworker to adopt, modify, or decline this proposed triage note.")
        return suggestions
