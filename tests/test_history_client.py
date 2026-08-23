"""
tests/test_history_client.py

Unit tests for services/history_client.py.

These tests use unittest.mock to replace the real HTTP call so that the
real History API server does NOT need to be running.

Run with:
    python -m pytest tests/test_history_client.py -v
  or:
    python tests/test_history_client.py
"""

import io
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.history_client import HistoryClient, HistoryClientError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(payload: dict) -> MagicMock:
    """
    Build a fake context-manager response object that returns *payload*
    as JSON bytes when ``read()`` is called.

    This mimics what ``urllib.request.urlopen(...)`` returns inside a
    ``with`` block.
    """
    body = json.dumps(payload).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    # Support `with urlopen(...) as response:`
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestHistoryClientHealthy(unittest.TestCase):
    """Tests for the happy path — server responds with 2xx JSON."""

    def setUp(self):
        self.client = HistoryClient(base_url="http://127.0.0.1:8083")

    # ------------------------------------------------------------------
    # health()
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_health_returns_parsed_dict(self, mock_urlopen):
        """health() parses and returns the server's JSON dict."""
        expected = {"status": "ok", "service": "resident-history", "records": 12}
        mock_urlopen.return_value = _mock_response(expected)

        result = self.client.health()

        self.assertEqual(result, expected)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_health_hits_correct_endpoint(self, mock_urlopen):
        """health() calls /health."""
        mock_urlopen.return_value = _mock_response({"status": "ok"})

        self.client.health()

        url_called = mock_urlopen.call_args[0][0]
        self.assertTrue(
            url_called.endswith("/health"),
            f"Expected /health endpoint, got: {url_called}",
        )

    # ------------------------------------------------------------------
    # get_resident()
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_get_resident_returns_parsed_dict(self, mock_urlopen):
        """get_resident() parses and returns the full resident record."""
        payload = {
            "resident_ref": "R-20500",
            "name": "Test Resident",
            "household": [],
            "events": [],
        }
        mock_urlopen.return_value = _mock_response(payload)

        result = self.client.get_resident("R-20500")

        self.assertEqual(result["resident_ref"], "R-20500")
        self.assertIn("household", result)
        self.assertIn("events", result)

    @patch("urllib.request.urlopen")
    def test_get_resident_hits_correct_endpoint(self, mock_urlopen):
        """get_resident() calls /residents/<ref>."""
        mock_urlopen.return_value = _mock_response({"resident_ref": "R-20500"})

        self.client.get_resident("R-20500")

        url_called = mock_urlopen.call_args[0][0]
        self.assertIn("/residents/R-20500", url_called)

    # ------------------------------------------------------------------
    # get_household()
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_get_household_returns_parsed_dict(self, mock_urlopen):
        """get_household() parses and returns household composition."""
        payload = {
            "resident_ref": "R-20500",
            "household": [{"name": "Jane Doe", "relationship": "partner"}],
        }
        mock_urlopen.return_value = _mock_response(payload)

        result = self.client.get_household("R-20500")

        self.assertEqual(result["resident_ref"], "R-20500")
        self.assertIsInstance(result["household"], list)

    @patch("urllib.request.urlopen")
    def test_get_household_hits_correct_endpoint(self, mock_urlopen):
        """get_household() calls /residents/<ref>/household."""
        mock_urlopen.return_value = _mock_response({"resident_ref": "R-20500", "household": []})

        self.client.get_household("R-20500")

        url_called = mock_urlopen.call_args[0][0]
        self.assertIn("/residents/R-20500/household", url_called)

    # ------------------------------------------------------------------
    # get_events()
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_get_events_returns_parsed_dict(self, mock_urlopen):
        """get_events() parses and returns the events list."""
        payload = {
            "resident_ref": "R-20500",
            "events": [{"date": "2025-01-10", "type": "review"}],
        }
        mock_urlopen.return_value = _mock_response(payload)

        result = self.client.get_events("R-20500")

        self.assertEqual(result["resident_ref"], "R-20500")
        self.assertIsInstance(result["events"], list)

    @patch("urllib.request.urlopen")
    def test_get_events_hits_correct_endpoint(self, mock_urlopen):
        """get_events() calls /residents/<ref>/events."""
        mock_urlopen.return_value = _mock_response({"resident_ref": "R-20500", "events": []})

        self.client.get_events("R-20500")

        url_called = mock_urlopen.call_args[0][0]
        self.assertIn("/residents/R-20500/events", url_called)


class TestHistoryClientErrors(unittest.TestCase):
    """Tests for error handling — server errors and connection failures."""

    def setUp(self):
        self.client = HistoryClient(base_url="http://127.0.0.1:8083")

    # ------------------------------------------------------------------
    # HTTP error (4xx / 5xx)
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_http_404_raises_history_client_error(self, mock_urlopen):
        """A 404 response raises HistoryClientError with status_code=404."""
        error_body = json.dumps({"error": "not_found"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8083/residents/UNKNOWN",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(error_body),
        )

        with self.assertRaises(HistoryClientError) as ctx:
            self.client.get_resident("UNKNOWN")

        self.assertEqual(ctx.exception.status_code, 404)

    @patch("urllib.request.urlopen")
    def test_http_500_raises_history_client_error(self, mock_urlopen):
        """A 500 response raises HistoryClientError with status_code=500."""
        error_body = json.dumps({"error": "internal_server_error"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8083/health",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(error_body),
        )

        with self.assertRaises(HistoryClientError) as ctx:
            self.client.health()

        self.assertEqual(ctx.exception.status_code, 500)

    @patch("urllib.request.urlopen")
    def test_http_error_message_contains_status_code(self, mock_urlopen):
        """The HistoryClientError message mentions the HTTP status code."""
        error_body = b"{}"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8083/residents/X/household",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(error_body),
        )

        with self.assertRaises(HistoryClientError) as ctx:
            self.client.get_household("X")

        self.assertIn("403", str(ctx.exception))

    # ------------------------------------------------------------------
    # Connection failure (server not running, timeout, DNS, …)
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_connection_refused_raises_history_client_error(self, mock_urlopen):
        """A connection-refused error raises HistoryClientError with no status."""
        mock_urlopen.side_effect = urllib.error.URLError(
            reason="[Errno 111] Connection refused"
        )

        with self.assertRaises(HistoryClientError) as ctx:
            self.client.health()

        # status_code should be None for network-level failures
        self.assertIsNone(ctx.exception.status_code)

    @patch("urllib.request.urlopen")
    def test_connection_error_message_is_descriptive(self, mock_urlopen):
        """The HistoryClientError message mentions the unreachable URL."""
        mock_urlopen.side_effect = urllib.error.URLError(
            reason="[Errno 111] Connection refused"
        )

        with self.assertRaises(HistoryClientError) as ctx:
            self.client.get_resident("R-20500")

        self.assertIn("127.0.0.1", str(ctx.exception))


# ---------------------------------------------------------------------------
# Allow running directly: python tests/test_history_client.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
