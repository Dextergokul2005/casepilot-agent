"""
audit/audit_tracer.py

Records structured execution traces for referral processing in CasePilot.

Responsibilities
----------------
- Captures ordered lifecycle events:
    REFERRAL_INGESTED -> CONTEXT_RETRIEVED -> POLICY_EVALUATED -> CASE_ROUTED
- Retains events in memory for fast lookup and filtering.
- Persists audit logs to valid, formatted JSON (e.g. audit/execution_trace.json).
- Preserves audit data immutability and insertion order.

Architecture constraints
------------------------
- Logging/auditing only.
- No policy evaluation.
- No LLM calls.
- No HTTP/network requests.
- Standard library only.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional

from models.policy_decision import PolicyDecision
from models.referral import Referral
from models.resident_context import ResidentContext


# Canonical lifecycle event constants
EVENT_REFERRAL_INGESTED = "REFERRAL_INGESTED"
EVENT_CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
EVENT_POLICY_EVALUATED = "POLICY_EVALUATED"
EVENT_CASE_ROUTED = "CASE_ROUTED"
EVENT_TRIAGE_GENERATED = "TRIAGE_GENERATED"


class AuditTracer:
    """
    Manages an execution trace of casework automation events.

    Parameters
    ----------
    log_path : str
        Default file path for persisting execution traces.
        Defaults to "audit/execution_trace.json".
    """

    def __init__(self, log_path: str = "audit/execution_trace.json"):
        self.log_path = log_path
        self._events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Logging API
    # ------------------------------------------------------------------

    def log_event(
        self,
        event_type: str,
        referral_id: str,
        resident_ref: str,
        details: Optional[Dict[str, Any]] = None,
        requested_action: Optional[str] = None,
        outcome: Optional[str] = None,
        rule_id: Optional[str] = None,
        policy_reference: Optional[str] = None,
        destination: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a generic structured audit event.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        event: Dict[str, Any] = {
            "timestamp": timestamp,
            "event_type": event_type,
            "referral_id": referral_id,
            "resident_ref": resident_ref,
            "details": details or {},
        }

        # Include structured optional fields when present
        if requested_action is not None:
            event["requested_action"] = requested_action
        if outcome is not None:
            event["outcome"] = outcome
        if rule_id is not None:
            event["rule_id"] = rule_id
        if policy_reference is not None:
            event["policy_reference"] = policy_reference
        if destination is not None:
            event["destination"] = destination

        self._events.append(event)
        return deepcopy(event)

    def log_referral_loaded(
        self, referral: Referral, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Log a REFERRAL_INGESTED event."""
        extra_details = {
            "source": referral.source,
            "urgency": referral.urgency,
            "received_at": referral.received_at,
        }
        if details:
            extra_details.update(details)

        return self.log_event(
            event_type=EVENT_REFERRAL_INGESTED,
            referral_id=referral.referral_id,
            resident_ref=referral.resident_ref,
            requested_action=referral.requested_action,
            details=extra_details,
        )

    def log_context_retrieved(
        self, context: ResidentContext, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Log a CONTEXT_RETRIEVED event."""
        household_members = context.household.get("household", []) if isinstance(context.household, dict) else []
        event_count = len(context.events.get("events", [])) if isinstance(context.events, dict) else 0

        extra_details = {
            "household_member_count": len(household_members) if isinstance(household_members, list) else 0,
            "event_history_count": event_count,
        }
        if details:
            extra_details.update(details)

        return self.log_event(
            event_type=EVENT_CONTEXT_RETRIEVED,
            referral_id=context.referral.referral_id,
            resident_ref=context.referral.resident_ref,
            requested_action=context.referral.requested_action,
            details=extra_details,
        )

    def log_policy_decision(
        self,
        referral_id: str,
        resident_ref: str,
        decision: PolicyDecision,
        requested_action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a POLICY_EVALUATED event."""
        extra_details = {
            "reason": decision.reason,
            "evidence": decision.evidence,
            "required_action": decision.required_action,
        }
        if details:
            extra_details.update(details)

        return self.log_event(
            event_type=EVENT_POLICY_EVALUATED,
            referral_id=referral_id,
            resident_ref=resident_ref,
            requested_action=requested_action,
            outcome=decision.outcome,
            rule_id=decision.rule_id,
            policy_reference=decision.policy_reference,
            details=extra_details,
        )

    def log_routing(
        self,
        referral_id: str,
        resident_ref: str,
        outcome: str,
        destination: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a CASE_ROUTED event."""
        extra_details = {}
        if details:
            extra_details.update(details)

        return self.log_event(
            event_type=EVENT_CASE_ROUTED,
            referral_id=referral_id,
            resident_ref=resident_ref,
            outcome=outcome,
            destination=destination,
            details=extra_details,
        )

    def log_triage_generated(
        self,
        referral_id: str,
        resident_ref: str,
        destination: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a TRIAGE_GENERATED event for ALLOW cases."""
        extra_details = {}
        if details:
            extra_details.update(details)

        return self.log_event(
            event_type=EVENT_TRIAGE_GENERATED,
            referral_id=referral_id,
            resident_ref=resident_ref,
            outcome="ALLOW",
            destination=destination,
            details=extra_details,
        )

    # ------------------------------------------------------------------
    # Query & Retrieval API
    # ------------------------------------------------------------------

    def get_events(self) -> List[Dict[str, Any]]:
        """Return a copy of all recorded audit events."""
        return deepcopy(self._events)

    def get_events_for_referral(self, referral_id: str) -> List[Dict[str, Any]]:
        """Return all events recorded for a specific referral_id."""
        return [deepcopy(e) for e in self._events if e.get("referral_id") == referral_id]

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Return all events matching a given event_type."""
        return [deepcopy(e) for e in self._events if e.get("event_type") == event_type]

    def get_events_by_outcome(self, outcome: str) -> List[Dict[str, Any]]:
        """Return all events associated with a specific policy outcome."""
        return [deepcopy(e) for e in self._events if e.get("outcome") == outcome]

    def count(self) -> int:
        """Return the total number of events recorded."""
        return len(self._events)

    def clear(self) -> None:
        """Clear all in-memory audit events."""
        self._events.clear()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> str:
        """
        Persist in-memory execution trace to a JSON file.

        Parameters
        ----------
        path : Optional[str]
            Destination path. If omitted, uses self.log_path.

        Returns
        -------
        str
            The file path where trace was written.
        """
        target_path = path or self.log_path
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        payload = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(self._events),
            "events": self._events,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return target_path
