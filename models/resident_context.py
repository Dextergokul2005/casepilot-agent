"""
models/resident_context.py

Holds everything the agent needs to know about one referral and the
resident it concerns, gathered before any policy evaluation takes place.

This module is a pure data container.
No policy logic, no HTTP calls, no derived flags.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict

from models.referral import Referral


@dataclass
class ResidentContext:
    """
    Aggregates the incoming referral with the three slices of resident
    data retrieved from the History API.

    Fields
    ------
    referral : Referral
        The referral that triggered this context lookup.
    resident_history : dict
        Full history record returned by GET /residents/<ref>.
    household : dict
        Household composition returned by GET /residents/<ref>/household.
    events : dict
        Case events returned by GET /residents/<ref>/events.
    """

    referral: Referral
    resident_history: Dict[str, Any]
    household: Dict[str, Any]
    events: Dict[str, Any]

    def to_dict(self) -> dict:
        """
        Return a plain dictionary representation of this context.

        The referral is serialised via its own ``to_dict()`` method;
        the three history slices are included as-is.
        """
        return {
            "referral": self.referral.to_dict(),
            "resident_history": self.resident_history,
            "household": self.household,
            "events": self.events,
        }
