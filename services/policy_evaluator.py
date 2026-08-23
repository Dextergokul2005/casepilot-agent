"""
services/policy_evaluator.py

Applies authority policy rules deterministically to a ResidentContext.

Responsibilities
----------------
- Evaluate household composition from context.household for minors (under 18).
- If household cannot be reliably established -> HANDOFF under ACA-2026/2 section 3.9.
- If household contains any person under 18 -> HANDOFF under ACA-2026/2 section 3.9.
- Evaluate context.referral.requested_action against restricted categories (3.1 - 3.8).
  If matched -> ESCALATE under the matching rule.
- If requested action is clearly permitted -> ALLOW.
- If requested action is ambiguous or unknown -> ESCALATE under ACA-2026/1 section 6.1.
- Return a structured PolicyDecision with audit evidence.

Architecture constraints
------------------------
- Deterministic, conservative evaluation.
- No LLM calls.
- No network/HTTP requests.
- Does not generate triage notes.
- PolicyLoader is injected via constructor.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from models.policy_decision import (
    ALLOW,
    HANDOFF,
    ESCALATE,
    PolicyDecision,
)
from models.resident_context import ResidentContext


# ---------------------------------------------------------------------------
# Deterministic pattern sets for requested actions
# ---------------------------------------------------------------------------

RESTRICTED_ACTION_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "3.1": (
        "change award amount",
        "change entitlement",
        "alter entitlement",
        "increase entitlement",
        "decrease entitlement",
        "change award",
        "alter award",
        "recalculate award",
        "change eligibility status",
        "change eligibility",
        "alter eligibility status",
        "alter eligibility",
        "modify award",
        "modify entitlement",
        "entitlement change",
        "eligibility change",
    ),
    "3.2": (
        "suspend assistance",
        "suspend award",
        "suspension of award",
        "suspension of assistance",
        "terminate award",
        "terminate assistance",
        "termination of award",
        "termination of assistance",
        "reinstate award",
        "reinstate assistance",
        "reinstatement of award",
        "reinstatement of assistance",
        "reinstatement",
        "cancellation of award",
    ),
    "3.3": (
        "initiate payment",
        "alter payment",
        "cancel payment",
        "cancellation of payment",
        "issue payment",
        "stop payment",
        "authorize payment",
        "make payment",
        "withhold payment",
    ),
    "3.4": (
        "update payment details",
        "change payment details",
        "modify payment details",
        "change bank details",
        "update bank details",
        "change payment account",
        "update payment account",
        "change bank account",
        "update bank account",
    ),
    "3.5": (
        "send communication",
        "send letter",
        "send notice",
        "send notification",
        "notify resident",
        "notify third party",
        "contact third party",
        "issue notice",
        "issue letter",
        "dispatch correspondence",
    ),
    "3.6": (
        "disclose resident information",
        "disclosure of resident information",
        "disclose information",
        "share data with external",
        "share information outside",
        "release resident information",
        "release resident records",
        "external data disclosure",
    ),
    "3.7": (
        "record finding of fact",
        "assert finding of fact",
        "record fraud",
        "record suspected fraud",
        "record misrepresentation",
        "assert misconduct",
        "finding of fact regarding conduct",
        "record resident misconduct",
    ),
    "3.8": (
        "action that cannot be reversed",
        "action which cannot be reversed",
        "irreversible action",
        "irreversible referral",
        "court referral",
        "action requiring court order",
        "refer to external tribunal",
        "external legal action",
    ),
}

PERMITTED_ACTION_PATTERNS: Tuple[str, ...] = (
    "record change of address",
    "record income change",
    "review household composition",
    "review award",
    "review eligibility",
    "draft explanatory note",
    "flag for contact attempt",
    "flag for contact",
    "draft triage note for supervisor",
    "draft triage note",
    "log contact",
    "file document",
    "record document receipt",
    "schedule appointment",
    "log enquiry",
    "log inquiry",
    "flag for review",
)


class PolicyEvaluator:
    """
    Evaluates authority policy against a ResidentContext.

    Parameters
    ----------
    policy_loader : PolicyLoader
        Injected policy loader instance for retrieving authority rules.
    """

    def __init__(self, policy_loader):
        self.policy_loader = policy_loader

    def evaluate(self, context: ResidentContext) -> PolicyDecision:
        """
        Evaluate authority policy for the given resident context.

        Precedence
        ----------
        1. Household under-18 restriction / inability to establish household -> HANDOFF (3.9)
        2. Clearly restricted requested action -> ESCALATE (3.1 - 3.8)
        3. Clearly permitted requested action -> ALLOW
        4. Ambiguous requested action -> ESCALATE (6.1)
        """
        # Ensure policy rules are accessible
        rules = self.policy_loader.load()
        default_policy_ref = rules.get("policy_reference", "ACA-2026/1")

        # 1. Household check (Rule 3.9)
        household_decision = self._evaluate_household(context)
        if household_decision is not None:
            return household_decision

        # 2 & 3 & 4. Requested action check
        return self._evaluate_requested_action(context, default_policy_ref)

    # ------------------------------------------------------------------
    # Household evaluation
    # ------------------------------------------------------------------

    def _evaluate_household(self, context: ResidentContext) -> Optional[PolicyDecision]:
        """
        Check if household composition cannot be established or contains minors.
        Returns a HANDOFF PolicyDecision if rule 3.9 triggers, otherwise None.
        """
        raw_household = context.household

        # Check for unestablished / invalid household structure
        if not isinstance(raw_household, dict) or "household" not in raw_household:
            return self._build_handoff_decision(
                context,
                reason="Household composition cannot be established reliably from authoritative data.",
                evidence=[
                    f"Referral ID: {context.referral.referral_id}",
                    "Authoritative household data missing or malformed",
                ],
            )

        members = raw_household.get("household")
        if not isinstance(members, list):
            return self._build_handoff_decision(
                context,
                reason="Household member list is missing or invalid.",
                evidence=[
                    f"Referral ID: {context.referral.referral_id}",
                    "Household list structure is invalid",
                ],
            )

        # Parse reference date strictly without inventing silent defaults
        ref_date = self._parse_reference_date(context.referral.received_at)

        for member in members:
            if not isinstance(member, dict):
                return self._build_handoff_decision(
                    context,
                    reason="Household composition cannot be established reliably (invalid member record).",
                    evidence=[
                        f"Referral ID: {context.referral.referral_id}",
                        "Invalid member record encountered in household data",
                    ],
                )

            is_minor, member_evidence = self._is_member_under_18(member, ref_date)
            if is_minor is None:
                # Age cannot be reliably established
                return self._build_handoff_decision(
                    context,
                    reason=f"Age for household member '{member.get('name', 'Unknown')}' cannot be established reliably.",
                    evidence=[
                        f"Referral ID: {context.referral.referral_id}",
                        f"Unestablished age for member: {member_evidence}",
                    ],
                )

            if is_minor:
                return self._build_handoff_decision(
                    context,
                    reason=f"Household includes a person under 18 ({member.get('name', 'Unknown')}, {member_evidence}).",
                    evidence=[
                        f"Referral ID: {context.referral.referral_id}",
                        f"Minor in household: {member.get('name', 'Unknown')} ({member_evidence})",
                    ],
                )

        return None

    def _is_member_under_18(
        self, member: Dict[str, Any], ref_date: Optional[date]
    ) -> Tuple[Optional[bool], str]:
        """
        Determines whether a member is under 18.
        Returns (is_minor_bool_or_none, evidence_string).
        """
        # Explicit age provided
        if "age" in member and isinstance(member["age"], (int, float)):
            age = member["age"]
            return (age < 18, f"Age: {age}")

        # Boolean flags if provided
        if "is_minor" in member and isinstance(member["is_minor"], bool):
            return (member["is_minor"], f"is_minor: {member['is_minor']}")
        if "under_18" in member and isinstance(member["under_18"], bool):
            return (member["under_18"], f"under_18: {member['under_18']}")

        # Date of birth provided
        dob_str = member.get("date_of_birth")
        if dob_str and isinstance(dob_str, str):
            if ref_date is None:
                return (
                    None,
                    f"DOB: {dob_str}, but referral received_at is missing/invalid to calculate age",
                )
            try:
                dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
                age = (
                    ref_date.year
                    - dob.year
                    - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
                )
                return (age < 18, f"DOB: {dob_str}, Calculated age: {age}")
            except Exception:
                return (None, f"Malformed date_of_birth: {dob_str}")

        # No valid age indicators found
        return (None, "No valid age or date_of_birth field found")

    def _parse_reference_date(self, received_at: Optional[str]) -> Optional[date]:
        """
        Parse reference date from referral.received_at strictly.
        Returns None if received_at is missing or invalid (no silent date invention).
        """
        if received_at and isinstance(received_at, str):
            try:
                return datetime.fromisoformat(received_at[:10]).date()
            except Exception:
                return None
        return None

    def _build_handoff_decision(
        self, context: ResidentContext, reason: str, evidence: List[str]
    ) -> PolicyDecision:
        """Builds a HANDOFF PolicyDecision under ACA-2026/2 section 3.9."""
        return PolicyDecision(
            outcome=HANDOFF,
            policy_reference="ACA-2026/2",
            rule_id="3.9",
            reason=reason,
            evidence=evidence,
            required_action="A caseworker must complete the triage note.",
        )

    # ------------------------------------------------------------------
    # Requested action evaluation
    # ------------------------------------------------------------------

    def _evaluate_requested_action(
        self, context: ResidentContext, default_policy_ref: str
    ) -> PolicyDecision:
        """
        Evaluate context.referral.requested_action against restricted,
        permitted, or ambiguous rules.
        """
        raw_action = context.referral.requested_action or ""
        action = raw_action.strip().lower()
        referral_id = context.referral.referral_id

        # Check restricted actions (3.1 - 3.8) using exact action phrase matching
        for rule_id, patterns in RESTRICTED_ACTION_PATTERNS.items():
            for pattern in patterns:
                if pattern in action:
                    return PolicyDecision(
                        outcome=ESCALATE,
                        policy_reference="ACA-2026/1",
                        rule_id=rule_id,
                        reason=f"Requested action '{raw_action}' falls under restricted section {rule_id}.",
                        evidence=[
                            f"Referral ID: {referral_id}",
                            f"Requested action: {raw_action}",
                            f"Matched restricted rule: {rule_id}",
                        ],
                        required_action="Supervisor review is required.",
                    )

        # Check clearly permitted actions
        for pattern in PERMITTED_ACTION_PATTERNS:
            if pattern in action:
                return PolicyDecision(
                    outcome=ALLOW,
                    policy_reference=default_policy_ref,
                    rule_id="",
                    reason="No policy restrictions triggered. Requested action is permitted for automated processing.",
                    evidence=[
                        f"Referral ID: {referral_id}",
                        f"Requested action: {raw_action}",
                    ],
                    required_action="Normal triage processing may continue.",
                )

        # Ambiguous / unclassified action -> Rule 6.1 (ESCALATE)
        return PolicyDecision(
            outcome=ESCALATE,
            policy_reference="ACA-2026/1",
            rule_id="6.1",
            reason=(
                f"Requested action '{raw_action}' is ambiguous or unclassified. "
                "Under rule 6.1, unclear actions must be treated as restricted."
            ),
            evidence=[
                f"Referral ID: {referral_id}",
                f"Requested action: {raw_action}",
                "Ambiguous requested action triggered rule 6.1",
            ],
            required_action="Supervisor review is required.",
        )
