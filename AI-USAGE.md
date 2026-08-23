# AI-USAGE.md — AI Use Policy for CasePilot

This document records how AI tools are used during the development of
CasePilot and the boundaries that govern that use.

---

## Permitted uses of AI during development

AI tools (such as large language model assistants) may be used during
development for the following purposes:

| Use | Description |
|---|---|
| **Brainstorming** | Exploring architectural options, naming, or design trade-offs |
| **Code drafting** | Generating initial code scaffolding or boilerplate |
| **Code review** | Reviewing logic, spotting potential bugs, or suggesting improvements |
| **Testing ideas** | Proposing test cases, edge cases, or test strategies |
| **Documentation** | Drafting docstrings, README content, or decision records |

---

## Human review requirement

**All AI-generated code must be reviewed by a human developer before it is
committed to the repository.**

AI output is treated as a first draft. The developer is responsible for:

- Verifying correctness against the specification.
- Ensuring the code does not violate authority boundaries or policy rules.
- Confirming that no real resident or personal data has been introduced.

---

## Runtime policy enforcement

**Runtime policy enforcement will not rely solely on an LLM.**

An LLM may assist with language-level tasks at runtime (e.g. summarising a
referral, drafting a triage note). However, authority boundaries — what the
system is and is not permitted to decide — will be enforced by deterministic
code reading from explicit policy files.

An LLM cannot be the sole gatekeeper for a policy decision. See
[DECISIONS.md → ADR-002](DECISIONS.md) for the rationale.

---

## Data policy

**No real personal or resident data will be introduced into this project.**

- All data used during development and testing must be synthetic or fictional.
- Data files (under `data/`) are excluded from version control via `.gitignore`.
- Any data file committed to the repository must be clearly marked as synthetic.
- If real data is accidentally introduced, it must be removed from the
  repository history immediately.
