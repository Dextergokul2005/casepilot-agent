"""
services/context_builder.py

Assembles a ResidentContext for one referral by calling the History API
through an injected HistoryClient.

Responsibilities
----------------
- Use ``referral.resident_ref`` as the lookup key.
- Retrieve the full resident record, household composition, and case events.
- Return a ResidentContext holding all three slices plus the original referral.

Out of scope
------------
- Policy evaluation
- Triage generation
- Handoff or escalation routing
- Any LLM call
- Error recovery (errors from HistoryClient propagate to the caller)
"""

from models.referral import Referral
from models.resident_context import ResidentContext


class ContextBuilder:
    """
    Builds a ResidentContext for a given referral.

    Parameters
    ----------
    history_client : HistoryClient
        A configured HistoryClient instance.  Injected rather than
        instantiated here so that tests can supply a mock without
        touching the network.
    """

    def __init__(self, history_client):
        self._client = history_client

    def build(self, referral: Referral) -> ResidentContext:
        """
        Retrieve all resident data for the referral and return a
        populated ResidentContext.

        Parameters
        ----------
        referral : Referral
            The referral whose ``resident_ref`` is used for every API call.

        Returns
        -------
        ResidentContext
            Contains the original referral plus the three data slices
            exactly as returned by the History API.

        Raises
        ------
        HistoryClientError
            Propagated unchanged if any History API call fails.
            The caller decides how to handle partial failures.
        """
        ref = referral.resident_ref

        resident_history = self._client.get_resident(ref)
        household = self._client.get_household(ref)
        events = self._client.get_events(ref)

        return ResidentContext(
            referral=referral,
            resident_history=resident_history,
            household=household,
            events=events,
        )
