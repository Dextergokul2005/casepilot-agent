"""
models/referral.py

Defines the Referral dataclass — the canonical in-memory representation
of a single incoming referral.

No business logic lives here. This module is a plain data container.
"""

from dataclasses import dataclass, asdict


@dataclass
class Referral:
    """
    One referral from the morning queue.

    Fields mirror the structure of data/referral-queue.json exactly so
    that the loader can construct instances with no transformation.
    """

    referral_id: str       # e.g. "RF-2026-0412"
    received_at: str       # ISO-8601 timestamp string, e.g. "2026-03-17T04:42:00"
    resident_ref: str      # e.g. "R-20500"
    source: str            # originating team or channel, e.g. "Housing Options"
    summary: str           # free-text description of the referral
    requested_action: str  # what the referral asks the caseworker to do
    urgency: str           # "Low" | "Standard" | "High"

    def to_dict(self) -> dict:
        """Return the referral as a plain dictionary."""
        return asdict(self)
