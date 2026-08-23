# CasePilot

**Caseworker Morning Automation — Brite Spark 2026, Problem 5**

---

## Purpose

CasePilot is a Python-based agentic system designed to automate the routine
morning workflow of a social-care caseworker. The goal is to handle the
predictable, rule-governed parts of that workflow programmatically —
while strictly respecting the authority boundaries that govern what the
system is and is not permitted to decide on its own.

## Current Status

**Foundation stage.** The project structure has been established and
documented. No business logic, LLM integration, or policy engine has
been implemented yet.

## What the system will do (future stages)

Once the subsequent implementation stages are complete, CasePilot will:

- **Process referrals** — ingest incoming case referrals from structured data.
- **Retrieve resident history** — look up prior case records relevant to each
  referral.
- **Evaluate authority policy** — check each case against the current policy
  rules to determine what the system is authorised to act on.
- **Generate permitted triage output** — produce structured triage decisions
  for cases that fall within the system's authority.
- **Distinguish human handoffs from supervisor escalations** — route cases
  correctly: routine cases go to the human caseworker queue; cases that
  exceed system authority are escalated to a supervisor.
- **Maintain an execution trace** — record every decision and action in an
  audit log so that the caseworker can verify, override, or replay any step.

## Running the project

```bash
python main.py
```

## Project layout

```
casepilot-agent/
├── data/              # Input referral data (not committed)
├── policy/            # Authority policy rules and amendments
│   └── amendments/
├── services/          # External-service adapters (history, notifications…)
├── agent/             # Core agent orchestration logic
├── audit/             # Execution-trace and logging utilities
├── models/            # Data models / schemas
├── tests/             # Automated tests
├── output/
│   ├── escalations/   # Cases escalated to supervisor
│   └── handoffs/      # Cases handed off to human caseworker
├── main.py
├── README.md
├── DECISIONS.md
└── AI-USAGE.md
```
