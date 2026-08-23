"""
services/referral_loader.py

Loads and validates the morning referral queue from disk.

Responsibilities
----------------
- Read data/referral-queue.json (relative to the project root).
- Confirm the JSON is a list.
- Confirm every item contains all required fields.
- Return a list of Referral objects.

This module does NOT evaluate policy, contact external services,
or invoke an LLM.  It is purely a data-loading concern.
"""

import json
import os
from typing import List

from models.referral import Referral


# Fields every referral record must contain.
REQUIRED_FIELDS = {
    "referral_id",
    "received_at",
    "resident_ref",
    "source",
    "summary",
    "requested_action",
    "urgency",
}


class ReferralLoader:
    """
    Loads referrals from the JSON queue file and returns validated
    Referral objects.

    Parameters
    ----------
    data_path : str
        Path to the referral queue JSON file.
        Defaults to ``data/referral-queue.json`` relative to the
        project root (the directory containing this file's parent).
    """

    def __init__(self, data_path: str = None):
        if data_path is None:
            # Resolve project root: go up one level from services/
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(project_root, "data", "referral-queue.json")
        self.data_path = data_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_referrals(self) -> List[Referral]:
        """
        Read, validate, and return all referrals from the queue file.

        Returns
        -------
        List[Referral]
            One Referral object per record in the queue.

        Raises
        ------
        FileNotFoundError
            If the queue file does not exist at ``self.data_path``.
        ValueError
            If the JSON is not a list, or if any record is missing a
            required field.
        """
        raw = self._read_file()
        records = self._parse_json(raw)
        self._validate_records(records)
        return [self._build_referral(r) for r in records]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file(self) -> str:
        """Return the raw text content of the queue file."""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(
                f"Referral queue file not found: {self.data_path}"
            )
        with open(self.data_path, encoding="utf-8") as fh:
            return fh.read()

    def _parse_json(self, raw: str) -> list:
        """Parse raw JSON text and confirm it is a list."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"referral-queue.json is not valid JSON: {exc}") from exc

        if not isinstance(data, list):
            raise ValueError(
                "referral-queue.json must contain a JSON array at the top level, "
                f"but got {type(data).__name__}."
            )
        return data

    def _validate_records(self, records: list) -> None:
        """Raise ValueError if any record is missing a required field."""
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(
                    f"Record at index {index} is not a JSON object (got "
                    f"{type(record).__name__})."
                )
            missing = REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(
                    f"Record at index {index} (referral_id="
                    f"{record.get('referral_id', '<unknown>')!r}) is missing "
                    f"required field(s): {sorted(missing)}"
                )

    def _build_referral(self, record: dict) -> Referral:
        """Construct a Referral dataclass from a validated dict."""
        return Referral(
            referral_id=record["referral_id"],
            received_at=record["received_at"],
            resident_ref=record["resident_ref"],
            source=record["source"],
            summary=record["summary"],
            requested_action=record["requested_action"],
            urgency=record["urgency"],
        )
