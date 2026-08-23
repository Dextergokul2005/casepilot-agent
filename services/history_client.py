"""
services/history_client.py

HTTP client for the Calder County Resident History API.

Usage example
-------------
    from services.history_client import HistoryClient, HistoryClientError

    client = HistoryClient()          # connects to http://127.0.0.1:8083
    print(client.health())
    record = client.get_resident("R-20500")

This module uses only the Python standard library.
It contains no policy logic and no LLM logic.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict


class HistoryClientError(Exception):
    """
    Raised when the History API returns an unexpected HTTP status
    or when a network-level connection failure occurs.

    Attributes
    ----------
    message : str
        Human-readable description of what went wrong.
    status_code : int or None
        HTTP status code returned by the server, or ``None`` if the
        request never reached the server (e.g. connection refused).
    """

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class HistoryClient:
    """
    Thin HTTP client for the Resident History API.

    Parameters
    ----------
    base_url : str
        Base URL of the history service, without a trailing slash.
        Defaults to ``http://127.0.0.1:8083``.
    timeout : float
        Socket timeout in seconds for every request.
        Defaults to 10.0 seconds.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8083",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """
        GET /health

        Returns
        -------
        dict
            ``{"status": "ok", "service": "resident-history", "records": <int>}``

        Raises
        ------
        HistoryClientError
            On any HTTP error or connection failure.
        """
        return self._get("/health")

    def get_resident(self, resident_ref: str) -> Dict[str, Any]:
        """
        GET /residents/<resident_ref>

        Returns the full history record for one resident.

        Parameters
        ----------
        resident_ref : str
            The resident identifier, e.g. ``"R-20500"``.

        Returns
        -------
        dict
            Full resident history record as returned by the API.

        Raises
        ------
        HistoryClientError
            On any HTTP error (including 404) or connection failure.
        """
        return self._get(f"/residents/{resident_ref}")

    def get_household(self, resident_ref: str) -> Dict[str, Any]:
        """
        GET /residents/<resident_ref>/household

        Returns household composition for one resident.

        Parameters
        ----------
        resident_ref : str
            The resident identifier, e.g. ``"R-20500"``.

        Returns
        -------
        dict
            ``{"resident_ref": ..., "household": [...]}``

        Raises
        ------
        HistoryClientError
            On any HTTP error (including 404) or connection failure.
        """
        return self._get(f"/residents/{resident_ref}/household")

    def get_events(self, resident_ref: str) -> Dict[str, Any]:
        """
        GET /residents/<resident_ref>/events

        Returns case events for one resident.

        Parameters
        ----------
        resident_ref : str
            The resident identifier, e.g. ``"R-20500"``.

        Returns
        -------
        dict
            ``{"resident_ref": ..., "events": [...]}``

        Raises
        ------
        HistoryClientError
            On any HTTP error (including 404) or connection failure.
        """
        return self._get(f"/residents/{resident_ref}/events")

    # ------------------------------------------------------------------
    # Private helper
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Dict[str, Any]:
        """
        Perform a GET request to ``self.base_url + path`` and return
        the parsed JSON body as a dict.

        Parameters
        ----------
        path : str
            URL path, must start with ``/``.

        Raises
        ------
        HistoryClientError
            - If the server returns a non-2xx status code.
            - If a connection-level error occurs (refused, timeout, etc.).
            - If the response body is not valid JSON.
        """
        url = self.base_url + path

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw)

        except urllib.error.HTTPError as exc:
            # Server responded but with a 4xx / 5xx code.
            try:
                body = json.loads(exc.read())
            except Exception:
                body = {}
            error_detail = body.get("error", exc.reason)
            raise HistoryClientError(
                f"History API returned HTTP {exc.code} for {url!r}: {error_detail}",
                status_code=exc.code,
            ) from exc

        except urllib.error.URLError as exc:
            # Network-level failure: connection refused, DNS failure, timeout…
            raise HistoryClientError(
                f"Could not reach History API at {url!r}: {exc.reason}"
            ) from exc

        except json.JSONDecodeError as exc:
            raise HistoryClientError(
                f"History API response from {url!r} is not valid JSON: {exc}"
            ) from exc
