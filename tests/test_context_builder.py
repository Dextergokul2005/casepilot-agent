"""
tests/test_context_builder.py

Unit tests for services/context_builder.py.

All tests use a mock HistoryClient so the real History API does not
need to be running.

Run with:
    python -m pytest tests/test_context_builder.py -v
  or:
    python tests/test_context_builder.py
"""

import sys
import os
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Project root on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.referral import Referral
from models.resident_context import ResidentContext
from services.context_builder import ContextBuilder
from services.history_client import HistoryClientError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_referral(**overrides) -> Referral:
    """Return a minimal Referral suitable for testing."""
    defaults = dict(
        referral_id="RF-2026-0412",
        received_at="2026-03-17T04:42:00",
        resident_ref="R-20500",
        source="Housing Options",
        summary="Resident reports rent arrears.",
        requested_action="Review award",
        urgency="Standard",
    )
    defaults.update(overrides)
    return Referral(**defaults)


def _make_mock_client(
    history=None,
    household=None,
    events=None,
) -> MagicMock:
    """
    Return a mock HistoryClient whose methods return the supplied dicts.

    Defaults are minimal but structurally correct responses.
    """
    mock = MagicMock()
    mock.get_resident.return_value = history or {
        "resident_ref": "R-20500",
        "name": "Alex Doe",
        "household": [],
        "events": [],
    }
    mock.get_household.return_value = household or {
        "resident_ref": "R-20500",
        "household": [{"name": "Sam Doe", "relationship": "partner"}],
    }
    mock.get_events.return_value = events or {
        "resident_ref": "R-20500",
        "events": [{"date": "2025-06-01", "type": "review"}],
    }
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContextBuilderHappyPath(unittest.TestCase):
    """build() succeeds and returns correct ResidentContext."""

    def setUp(self):
        self.referral = _make_referral()
        self.mock_client = _make_mock_client()
        self.builder = ContextBuilder(self.mock_client)
        self.context = self.builder.build(self.referral)

    # ------------------------------------------------------------------
    # Test 1 — returns a ResidentContext
    # ------------------------------------------------------------------
    def test_build_returns_resident_context(self):
        """build() returns a ResidentContext instance."""
        self.assertIsInstance(self.context, ResidentContext)

    # ------------------------------------------------------------------
    # Test 2 — correct resident_ref passed to get_resident
    # ------------------------------------------------------------------
    def test_get_resident_called_with_correct_ref(self):
        """get_resident() is called with referral.resident_ref."""
        self.mock_client.get_resident.assert_called_once_with("R-20500")

    # ------------------------------------------------------------------
    # Test 3 — correct resident_ref passed to get_household
    # ------------------------------------------------------------------
    def test_get_household_called_with_correct_ref(self):
        """get_household() is called with referral.resident_ref."""
        self.mock_client.get_household.assert_called_once_with("R-20500")

    # ------------------------------------------------------------------
    # Test 4 — correct resident_ref passed to get_events
    # ------------------------------------------------------------------
    def test_get_events_called_with_correct_ref(self):
        """get_events() is called with referral.resident_ref."""
        self.mock_client.get_events.assert_called_once_with("R-20500")

    # ------------------------------------------------------------------
    # Test 5a — referral stored unchanged
    # ------------------------------------------------------------------
    def test_referral_stored_unchanged(self):
        """The original Referral object is stored on the context unchanged."""
        self.assertIs(self.context.referral, self.referral)

    # ------------------------------------------------------------------
    # Test 5b — resident_history stored unchanged
    # ------------------------------------------------------------------
    def test_resident_history_stored_unchanged(self):
        """resident_history is exactly what get_resident() returned."""
        self.assertIs(
            self.context.resident_history,
            self.mock_client.get_resident.return_value,
        )

    # ------------------------------------------------------------------
    # Test 5c — household stored unchanged
    # ------------------------------------------------------------------
    def test_household_stored_unchanged(self):
        """household is exactly what get_household() returned."""
        self.assertIs(
            self.context.household,
            self.mock_client.get_household.return_value,
        )

    # ------------------------------------------------------------------
    # Test 5d — events stored unchanged
    # ------------------------------------------------------------------
    def test_events_stored_unchanged(self):
        """events is exactly what get_events() returned."""
        self.assertIs(
            self.context.events,
            self.mock_client.get_events.return_value,
        )

    # ------------------------------------------------------------------
    # Test 7 — to_dict() structure
    # ------------------------------------------------------------------
    def test_to_dict_contains_all_keys(self):
        """to_dict() returns a dict with the four expected top-level keys."""
        result = self.context.to_dict()
        self.assertIsInstance(result, dict)
        for key in ("referral", "resident_history", "household", "events"):
            with self.subTest(key=key):
                self.assertIn(key, result)

    def test_to_dict_referral_is_serialised(self):
        """to_dict()['referral'] is a dict, not a Referral object."""
        result = self.context.to_dict()
        self.assertIsInstance(result["referral"], dict)

    def test_to_dict_referral_id_round_trips(self):
        """to_dict()['referral']['referral_id'] matches the original referral."""
        result = self.context.to_dict()
        self.assertEqual(result["referral"]["referral_id"], self.referral.referral_id)

    def test_to_dict_resident_ref_is_correct_in_referral(self):
        """to_dict()['referral']['resident_ref'] matches the original referral."""
        result = self.context.to_dict()
        self.assertEqual(result["referral"]["resident_ref"], "R-20500")


class TestContextBuilderErrorPropagation(unittest.TestCase):
    """HistoryClient errors must propagate — no silent swallowing."""

    def _builder_with_failing(self, method_name: str) -> ContextBuilder:
        """Return a ContextBuilder whose client raises on *method_name*."""
        mock_client = _make_mock_client()
        getattr(mock_client, method_name).side_effect = HistoryClientError(
            f"Simulated failure in {method_name}", status_code=500
        )
        return ContextBuilder(mock_client)

    # ------------------------------------------------------------------
    # Test 6a — get_resident failure propagates
    # ------------------------------------------------------------------
    def test_get_resident_error_propagates(self):
        """If get_resident() raises, build() propagates the error."""
        builder = self._builder_with_failing("get_resident")
        with self.assertRaises(HistoryClientError):
            builder.build(_make_referral())

    # ------------------------------------------------------------------
    # Test 6b — get_household failure propagates
    # ------------------------------------------------------------------
    def test_get_household_error_propagates(self):
        """If get_household() raises, build() propagates the error."""
        builder = self._builder_with_failing("get_household")
        with self.assertRaises(HistoryClientError):
            builder.build(_make_referral())

    # ------------------------------------------------------------------
    # Test 6c — get_events failure propagates
    # ------------------------------------------------------------------
    def test_get_events_error_propagates(self):
        """If get_events() raises, build() propagates the error."""
        builder = self._builder_with_failing("get_events")
        with self.assertRaises(HistoryClientError):
            builder.build(_make_referral())

    # ------------------------------------------------------------------
    # Test 6d — different resident_ref is forwarded correctly too
    # ------------------------------------------------------------------
    def test_different_resident_ref_is_forwarded(self):
        """build() uses referral.resident_ref, not a hard-coded value."""
        mock_client = _make_mock_client()
        builder = ContextBuilder(mock_client)
        referral = _make_referral(resident_ref="R-99999")
        builder.build(referral)

        mock_client.get_resident.assert_called_once_with("R-99999")
        mock_client.get_household.assert_called_once_with("R-99999")
        mock_client.get_events.assert_called_once_with("R-99999")


# ---------------------------------------------------------------------------
# Allow running directly: python tests/test_context_builder.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
