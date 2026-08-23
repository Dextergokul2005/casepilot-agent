"""
tests/test_referral_loader.py

Tests for services/referral_loader.py

Run with:
    python -m pytest tests/test_referral_loader.py -v
  or (no external tools required):
    python tests/test_referral_loader.py

These tests work against the real data/referral-queue.json file that
ships with the project.  They verify the loader's happy path only —
error paths (missing file, bad JSON, missing fields) are left for a
later stage when the full test suite is built out.
"""

import sys
import os
import unittest

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path so that `models` and `services`
# can be imported regardless of where pytest / python is launched from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.referral import Referral
from services.referral_loader import ReferralLoader


class TestReferralLoader(unittest.TestCase):
    """Happy-path tests for ReferralLoader."""

    @classmethod
    def setUpClass(cls):
        """
        Load the referral queue once for the whole test class.
        All test methods share the same list so we only hit the disk once.
        """
        loader = ReferralLoader()
        cls.referrals = loader.load_referrals()

    # ------------------------------------------------------------------
    # Test 1 — the file loads without raising any exception
    # ------------------------------------------------------------------
    def test_load_succeeds(self):
        """Referral file loads successfully and returns a list."""
        self.assertIsInstance(
            self.referrals,
            list,
            "load_referrals() should return a list.",
        )

    # ------------------------------------------------------------------
    # Test 2 — correct number of referrals
    # ------------------------------------------------------------------
    def test_total_referrals_is_12(self):
        """Total referrals loaded must equal 12."""
        self.assertEqual(
            len(self.referrals),
            12,
            f"Expected 12 referrals but got {len(self.referrals)}.",
        )

    # ------------------------------------------------------------------
    # Test 3 — every item is a Referral dataclass
    # ------------------------------------------------------------------
    def test_all_items_are_referral_objects(self):
        """Every item returned must be a Referral instance."""
        for i, item in enumerate(self.referrals):
            with self.subTest(index=i):
                self.assertIsInstance(
                    item,
                    Referral,
                    f"Item at index {i} is {type(item).__name__}, expected Referral.",
                )

    # ------------------------------------------------------------------
    # Test 4 — every referral has a non-empty referral_id
    # ------------------------------------------------------------------
    def test_every_referral_has_referral_id(self):
        """Every referral must have a non-empty referral_id."""
        for referral in self.referrals:
            with self.subTest(referral_id=referral.referral_id):
                self.assertTrue(
                    referral.referral_id,
                    "referral_id must not be empty.",
                )

    # ------------------------------------------------------------------
    # Test 5 — every referral has a non-empty resident_ref
    # ------------------------------------------------------------------
    def test_every_referral_has_resident_ref(self):
        """Every referral must have a non-empty resident_ref."""
        for referral in self.referrals:
            with self.subTest(referral_id=referral.referral_id):
                self.assertTrue(
                    referral.resident_ref,
                    f"Referral {referral.referral_id!r} has an empty resident_ref.",
                )


# ---------------------------------------------------------------------------
# Allow running directly:  python tests/test_referral_loader.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
