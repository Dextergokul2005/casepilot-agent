# DECISIONS.md — Architecture Decision Log

This document records key architectural decisions made during the development
of CasePilot. Each entry explains *what* was decided, *why*, and any
alternatives that were considered.

---

## ADR-001 — Separation of concerns across system layers

**Date:** 2026-08-23  
**Status:** Accepted

### Decision

The system is divided into distinct, independently testable layers:

| Layer | Responsibility |
|---|---|
| `agent/` | Orchestration — coordinates the overall workflow |
| `services/` | External adapters — referral ingestion, resident history |
| `policy/` | Authority policy rules and amendments |
| `models/` | Shared data schemas / types |
| `audit/` | Execution tracing and logging |
| `output/` | Final artefacts — handoffs and escalations |

Each of the following concerns has its own dedicated location and must **not**
be mixed into another layer:

- Referral processing
- Policy evaluation
- Resident history retrieval
- Triage generation
- Human handoff routing
- Supervisor escalation routing
- Audit tracing

### Why

Mixing concerns in a single module makes it harder to test, audit, or modify
any single part of the workflow. The competition problem explicitly evolves
during the competition (e.g. policy amendments), so clean boundaries allow
rules to be changed without touching workflow code, and workflow code to be
changed without altering policy rules.

---

## ADR-002 — Policy enforcement must be structural, not prompt-based

**Date:** 2026-08-23  
**Status:** Accepted

### Decision

Authority decisions — what the system is and is not permitted to do — will be
enforced by code that reads from explicit, version-controlled policy files.
An LLM prompt alone will **not** be the enforcement mechanism for policy
boundaries.

### Why

LLMs are non-deterministic and can be manipulated through prompt injection or
edge cases in natural language. Policy boundaries are not negotiable: if the
authority says the system cannot act on a category of case, that must be
enforced deterministically, not by hoping the model interprets the prompt
correctly.

### Consequence

Policy rules live in `policy/` as structured data (e.g. JSON or YAML).
The policy engine in code reads those rules and applies them before any LLM
layer is consulted. The LLM, when introduced, assists with language tasks
(summarisation, drafting) — it does not gate authority decisions.

---

## ADR-003 — Policy rules must remain separate from workflow code

**Date:** 2026-08-23  
**Status:** Accepted

### Decision

Policy rules are stored as data files under `policy/`, not as constants or
conditionals inside workflow modules.

### Why

The competition explicitly introduces changing requirements, including policy
amendments. If rules are embedded as `if`/`else` statements in application
code, every amendment requires a code change, a review, and a retest of the
whole workflow. Keeping rules as data means amendments are isolated: swap the
file, re-run the policy loader, and the workflow behaviour changes without
touching workflow code.

### Consequence

Any new amendment is added to `policy/amendments/` and picked up by the
policy engine at runtime. Workflow code never hard-codes rule values.

---

## ADR-004 — Separate human handoff from supervisor escalation (ACA-2026/2)

**Date:** 2026-08-23  
**Status:** Accepted

### Decision

The system distinguishes between two different non-agent outcomes:

- **Human handoff** — the caseworker receives the case for routine action that
  the agent was not intended to handle autonomously, but that is within normal
  workflow scope.
- **Supervisor escalation** — the case exceeds the agent's authority *and*
  requires a supervisor decision; it is never placed in the ordinary handoff
  queue.

These are routed to separate output directories: `output/handoffs/` and
`output/escalations/`.

### Why

Amendment ACA-2026/2 introduced a formal distinction between these two routing
outcomes. Conflating them would cause supervisor-level cases to appear in the
caseworker queue, violating the authority structure. Keeping them structurally
separate makes it impossible to route an escalation as a handoff accidentally.

### Consequence

The agent layer must always determine which of the two outcomes applies before
writing any output. An audit entry is created for both paths.
