"""
services/policy_loader.py

Loads and validates the authority policy rules from disk.

Responsibilities
----------------
- Read policy/policy_rules.json (resolved relative to the project root).
- Validate the top-level structure (policy_reference, effective_from, rules).
- Validate that every rule contains the required fields.
- Return the validated policy data as a plain Python dict.

Out of scope
------------
- Evaluating referrals or resident context.
- Inspecting requested_action, household composition, or minors.
- Creating PolicyDecision objects based on cases.
- Any network or LLM call.

Uses Python standard library only.
"""

import json
import os
from typing import Any, Dict, List


# Fields the top-level policy document must contain.
REQUIRED_TOP_LEVEL_FIELDS = {"policy_reference", "effective_from", "rules"}

# Fields every individual rule must contain.
REQUIRED_RULE_FIELDS = {
    "rule_id",
    "policy_reference",
    "description",
    "outcome",
    "stop_current_action",
    "source",
}


class PolicyLoader:
    """
    Loads the authority policy from a JSON file and returns validated data.

    Parameters
    ----------
    policy_path : str
        Path to the policy JSON file.
        Defaults to ``policy/policy_rules.json`` relative to the project root.
    """

    def __init__(self, policy_path: str = None):
        if policy_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            policy_path = os.path.join(project_root, "policy", "policy_rules.json")
        self.policy_path = policy_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> Dict[str, Any]:
        """
        Read, validate, and return the full policy document.

        Returns
        -------
        dict
            The validated policy document, e.g.::

                {
                    "policy_reference": "ACA-2026/1",
                    "effective_from": "2026-01-01",
                    "rules": [...]
                }

        Raises
        ------
        FileNotFoundError
            If the policy file does not exist.
        ValueError
            If the JSON is malformed, the top-level structure is invalid,
            or any rule is missing required fields.
        """
        raw = self._read_file()
        data = self._parse_json(raw)
        self._validate_top_level(data)
        self._validate_rules(data["rules"])
        return data

    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Convenience method: load and return only the rules list.

        Returns
        -------
        list[dict]
            Each item is a validated rule dict.
        """
        return self.load()["rules"]

    def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
        """
        Return a single rule by its ``rule_id``.

        Parameters
        ----------
        rule_id : str
            The rule identifier, e.g. ``"3.1"``.

        Returns
        -------
        dict
            The matching rule.

        Raises
        ------
        KeyError
            If no rule with that ``rule_id`` exists in the policy file.
        """
        for rule in self.get_rules():
            if rule["rule_id"] == rule_id:
                return rule
        raise KeyError(f"No rule with rule_id={rule_id!r} found in policy.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file(self) -> str:
        """Return the raw text content of the policy file."""
        if not os.path.exists(self.policy_path):
            raise FileNotFoundError(
                f"Policy file not found: {self.policy_path}"
            )
        with open(self.policy_path, encoding="utf-8") as fh:
            return fh.read()

    def _parse_json(self, raw: str) -> dict:
        """Parse raw JSON; raise ValueError if it is not valid JSON."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"policy_rules.json is not valid JSON: {exc}"
            ) from exc

    def _validate_top_level(self, data: Any) -> None:
        """Raise ValueError if the top-level document structure is wrong."""
        if not isinstance(data, dict):
            raise ValueError(
                "policy_rules.json must be a JSON object at the top level, "
                f"got {type(data).__name__}."
            )
        missing = REQUIRED_TOP_LEVEL_FIELDS - data.keys()
        if missing:
            raise ValueError(
                f"policy_rules.json is missing top-level field(s): {sorted(missing)}"
            )
        if not isinstance(data["rules"], list):
            raise ValueError(
                "'rules' must be a JSON array, "
                f"got {type(data['rules']).__name__}."
            )
        if len(data["rules"]) == 0:
            raise ValueError("'rules' must not be an empty list.")

    def _validate_rules(self, rules: list) -> None:
        """Raise ValueError if any rule is missing a required field."""
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValueError(
                    f"Rule at index {index} is not a JSON object "
                    f"(got {type(rule).__name__})."
                )
            missing = REQUIRED_RULE_FIELDS - rule.keys()
            if missing:
                raise ValueError(
                    f"Rule at index {index} (rule_id="
                    f"{rule.get('rule_id', '<unknown>')!r}) is missing "
                    f"required field(s): {sorted(missing)}"
                )
