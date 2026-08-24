# CasePilot

**Policy-Aware Caseworker Morning Automation**  
*Brite Spark 2026 — Problem 5*

---

## 1. Project Overview

**CasePilot** is a Python-based agentic caseworker morning automation system designed for social-care operations. It automates the routine ingestion, context assembly, and initial triage drafting of incoming case referrals while strictly enforcing statutory and institutional authority boundaries.

In social-care workflows, automation must never overstep legal, safety, or delegation limits. CasePilot enforces a strict, deterministic policy authority boundary: actions permitted under policy receive structured draft triage notes, while restricted actions, statutory exclusions, or ambiguous cases are safely routed to human caseworkers or supervisor escalation queues.

---

## 2. Problem Being Solved

Social-care caseworkers face high morning case volumes with tight turnaround windows. Manually reviewing incoming referrals, querying resident history records, verifying statutory household constraints, and drafting triage notes creates administrative burden and delays intervention.

However, naive AI/LLM automation is hazardous in this domain:
- Automated systems must not make binding legal findings or eligibility changes.
- Complex household dynamics (such as the presence of minors) require human caseworkers by policy.
- An AI model must never be allowed to self-authorize restricted actions.

CasePilot solves this by decoupling **policy authority** (strictly deterministic and non-overridable) from **triage drafting** (structured and marked as draft for caseworker review).

---

## 3. Key Capabilities

- **Automated Referral Ingestion**: Ingests incoming morning referrals from structured JSON records.
- **Authoritative Context Assembly**: Queries resident history services to build a unified `ResidentContext` (resident profile, historical interactions, household composition).
- **Deterministic Policy Evaluation**: Evaluates statutory rules (`ACA-2026/1` and amendment `ACA-2026/2`) deterministically without using an LLM or network calls.
- **Three-Way Case Routing**:
  - **`ALLOW`**: Permitted routine inquiries proceed to structured triage draft generation.
  - **`HANDOFF`**: Cases involving under-18 household members (Rule 3.9) are routed to human caseworkers.
  - **`ESCALATE`**: Restricted actions (Rules 3.1–3.8) and ambiguous requests (Rule 6.1) are escalated to supervisors.
- **Durable Artifact Persistence**: Writes structured, atomic JSON artifacts to dedicated output directories (`output/triage/`, `output/handoffs/`, `output/escalations/`).
- **Complete Audit Trail**: Records a 5-event immutable lifecycle trace for every referral in `audit/execution_trace.json`.
- **Interactive Monitoring Dashboard**: Provides a Streamlit UI (`ui.py`) for demonstration, queue execution, artifact inspection, and audit review.

---

## 4. Architecture & Workflow

```
Incoming Referral Queue (data/referrals.json)
               │
               ▼
        ReferralLoader
               │ (Referral)
               ▼
        ContextBuilder ◄─── HistoryClient (Mock / Resident History API)
               │
               ▼
        ResidentContext
               │
               ▼
   Deterministic PolicyEvaluator ◄─── PolicyLoader (policy/policy_rules.json)
               │
     ┌─────────┴───────────────────────┐
     ▼                                 ▼
   ALLOW                       HANDOFF / ESCALATE
     │                                 │
     ▼                                 ▼
TriageGenerator                    CaseRouter
     │                                 │
     ▼                                 ▼
output/triage/{id}.json      output/handoffs/ OR output/escalations/
     │                                 │
     └───────────────┬─────────────────┘
                     ▼
                AuditTracer (audit/execution_trace.json)
```

---

## 5. Policy & Safety Model

Policy authority is governed by loaded rules and evaluated through a pure deterministic engine:

### Policy Rules Summary
- **ACA-2026/1 Core Rules**:
  - `3.1` — Entitlement/benefit change → **`ESCALATE`** (Supervisor)
  - `3.2` — Suspension or reinstatement of support → **`ESCALATE`** (Supervisor)
  - `3.3` — Payment initiation or disbursement → **`ESCALATE`** (Supervisor)
  - `3.4` — Modification of payment details → **`ESCALATE`** (Supervisor)
  - `3.5` — Formal/official communication issuance → **`ESCALATE`** (Supervisor)
  - `3.6` — External disclosure of sensitive information → **`ESCALATE`** (Supervisor)
  - `3.7` — Formal finding of fact → **`ESCALATE`** (Supervisor)
  - `3.8` — Any irreversible action → **`ESCALATE`** (Supervisor)
  - `6.1` — Ambiguous, unspecified, or multi-part requested action → **`ESCALATE`** (Supervisor)
- **ACA-2026/2 Amendment**:
  - `3.9` — Household composition includes dependent or resident under 18 years of age → **`HANDOFF`** (Human Caseworker)

### Deterministic Invariants
1. **No LLM in Authority Path**: The decision whether an action is `ALLOW`, `HANDOFF`, or `ESCALATE` is 100% deterministic code.
2. **Pre-Triage Gate**: `TriageGenerator` is only called for `ALLOW` cases. `HANDOFF` and `ESCALATE` cases never enter triage draft generation.
3. **Draft Marking**: All generated triage artifacts are explicitly tagged with `draft_status: "PROPOSED_FOR_CASEWORKER_REVIEW"`.

---

## 6. Project Structure

```
casepilot-agent/
├── agent/
│   └── caseworker_agent.py      # Core orchestration loop and pipeline coordinator
├── audit/
│   └── audit_tracer.py          # Structured audit logging & lifecycle tracing
├── data/
│   └── referrals.json           # Challenge input referral queue (12 referrals)
├── models/
│   ├── policy_decision.py       # PolicyDecision domain model and constants
│   ├── referral.py              # Referral domain model
│   └── resident_context.py      # ResidentContext composite domain model
├── output/
│   ├── escalations/             # Supervisor escalation artifacts (*.json)
│   ├── handoffs/                # Caseworker handoff artifacts (*.json)
│   └── triage/                  # ALLOW triage draft artifacts (*.json)
├── policy/
│   └── policy_rules.json        # Statutory rules (ACA-2026/1, ACA-2026/2)
├── services/
│   ├── case_router.py           # Atomic JSON output router for HANDOFF / ESCALATE
│   ├── context_builder.py       # Assembles ResidentContext from HistoryClient
│   ├── history_client.py        # Adapter for resident history endpoints
│   ├── policy_evaluator.py      # Deterministic policy authority evaluation engine
│   ├── policy_loader.py         # JSON policy schema validator and loader
│   ├── referral_loader.py       # Ingests and validates referral queue files
│   └── triage_generator.py      # Structured draft generator for ALLOW cases
├── tests/
│   ├── test_audit_tracer.py
│   ├── test_case_router.py
│   ├── test_caseworker_agent.py
│   ├── test_context_builder.py
│   ├── test_end_to_end.py       # Full pipeline regression test
│   ├── test_history_client.py
│   ├── test_policy_evaluator.py
│   ├── test_policy_loader.py
│   ├── test_referral_loader.py
│   └── test_triage_generator.py
├── main.py                      # CLI entry point for morning batch workflow
├── ui.py                        # Streamlit dashboard interface
├── requirements.txt             # Project dependencies (Standard library + Streamlit)
├── DECISIONS.md                 # Architecture decision records
├── AI-USAGE.md                  # R&D notes and agent usage documentation
└── README.md                    # Project documentation
```

---

## 7. Requirements

- **Python**: 3.10 or higher
- **Core Pipeline**: Standard Python Library (`json`, `os`, `sys`, `urllib`, `dataclasses`, `tempfile`, `datetime`)
- **Dashboard UI**: `streamlit>=1.35`

---

## 8. Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd casepilot-agent
   ```

2. **Set up a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 9. Running the Application

Execute the morning caseworker automation queue via the command line:

```bash
python main.py
```

**What this does**:
- Initializes all components via dependency injection in `main.py`.
- Loads the 12 morning referrals from `data/referrals.json`.
- Fetches resident histories, evaluates policies, routes outputs, generates triage drafts, and logs audit events.
- Prints a clean summary table to stdout.

---

## 10. Running the Test Suite

Run the full automated test suite using Python's standard `unittest` discovery:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

**What this does**:
- Executes all unit tests across all models, services, agent orchestration, and end-to-end flows.
- Validates error handling, mock history servers, atomic file persistence, and policy edge cases.
- **Verified status**: **122 tests passing, 0 failures, 0 errors**.

---

## 11. Running the Streamlit UI

Launch the interactive monitoring dashboard:

```bash
streamlit run ui.py
```

Open your browser at `http://localhost:8501`.

**Dashboard Features**:
- **📊 Dashboard**: Run the morning queue with a single click, view live metric cards, outcome distributions, and verified system integrity status.
- **📋 Referrals**: Inspect individual referral records, policy decisions, rule explanations, evidence, and generated draft triage notes.
- **📁 Output Artifacts**: Browse and view generated JSON files across `output/triage/`, `output/handoffs/`, and `output/escalations/`.
- **🔍 Audit Trace**: Filter and examine the 55 lifecycle audit events from `audit/execution_trace.json`.

---

## 12. Expected Output & Verified Results

When executing `python main.py` on the challenge dataset, the system produces the following verified results:

```
============================================================
           CasePilot — Morning Casework Summary           
============================================================
 Total Referrals Processed : 12
   - ALLOW (Draft Triaged) : 7
   - HANDOFF (Caseworker)  : 3
   - ESCALATE (Supervisor) : 2
   - Failed / Errors       : 0
------------------------------------------------------------
 Audit Trace Saved         : audit/execution_trace.json
============================================================
```

### Breakdown by Outcome:
- **7 ALLOW Cases**: Routine inquiries (e.g., standard check-ins, record reviews) with no minors in the household and no restricted actions.
- **3 HANDOFF Cases**: Cases involving households with individuals under 18 years of age (Rule 3.9).
- **2 ESCALATE Cases**: Cases requesting restricted modifications (e.g., benefit entitlement adjustments or suspension actions under Rules 3.1–3.8).

---

## 13. Output Artifacts

CasePilot persists durable artifacts atomically to disk:

- **`output/triage/{referral_id}.json`** (7 files):
  Contains structured draft triage notes with summary, assessment, urgency, recommended actions, and resident history context.
- **`output/handoffs/{referral_id}.json`** (3 files):
  Contains handoff packages for human caseworkers detailing the referral, resident reference, triggering Rule 3.9, and reasoning.
- **`output/escalations/{referral_id}.json`** (2 files):
  Contains escalation packages for supervisors detailing the referral, resident reference, triggering restricted rule (e.g. 3.1), evidence, and required actions.

---

## 14. Audit Trail

Every run records an immutable audit trace in `audit/execution_trace.json`. For each referral processed, the following sequential events are logged:

1. `REFERRAL_INGESTED`: Referral loaded and validated from queue.
2. `CONTEXT_RETRIEVED`: Resident record, history events, and household composition assembled.
3. `POLICY_EVALUATED`: Deterministic policy decision rendered (`ALLOW`, `HANDOFF`, or `ESCALATE`).
4. `CASE_ROUTED`: Output written to disk or routed to triage generation.
5. `TRIAGE_GENERATED`: (For `ALLOW` cases only) Structured draft triage note generated and persisted.

Total recorded events for the 12-referral queue: **55 events** (12 × 4 lifecycle events + 7 triage events).

---

## 15. Testing Status

The project maintains comprehensive test coverage:

| Test Module | Coverage Scope |
|-------------|----------------|
| `test_referral_loader.py` | Schema validation, missing fields, corrupted JSON, count verification |
| `test_history_client.py` | Endpoint resolution, 404/500 HTTP handling, mock server responses |
| `test_context_builder.py` | Safe fallback handling, partial context recovery, history stitching |
| `test_policy_loader.py` | Policy schema parsing, rule ID validation, metadata consistency |
| `test_policy_evaluator.py` | Deterministic evaluation of Rules 3.1–3.9, Rule 6.1, precedence ordering |
| `test_case_router.py` | Atomic writes, directory creation, payload schemas for handoffs/escalations |
| `test_triage_generator.py` | Structured draft synthesis, background extraction, non-ALLOW rejection |
| `test_audit_tracer.py` | Event schema integrity, event sequence recording, file writing |
| `test_caseworker_agent.py` | Orchestration loop, error isolation (single failure does not halt queue) |
| `test_end_to_end.py` | Full batch execution on challenge dataset, artifact and audit verification |

**Suite Result**: `Ran 122 tests in ~0.22s — OK (0 failures, 0 errors)`

---

## 16. Important Design Decisions & Authority Boundaries

1. **Strict Separation of Policy and Generation**:
   The policy evaluation logic (`PolicyEvaluator`) has zero dependency on AI/LLMs or heuristic generators. This ensures safety guarantees cannot hallucinate or be prompt-injected.
2. **Atomic File Operations**:
   All disk writes (`CaseRouter`, `CaseworkerAgent`, `AuditTracer`) use temporary files and atomic `os.replace` operations to prevent partial or corrupted writes.
3. **Fault-Tolerant Queue Ingestion**:
   A failure while processing a single referral is isolated, logged as an error, and does not halt execution of subsequent referrals in the queue.
4. **Dependency Injection**:
   Every service is decoupled and instantiated via constructor dependency injection, enabling mock testing without live network or file side-effects.

---

## 17. Demonstration Flow

For a hackathon evaluation or live demonstration:

1. Open a terminal and run the test suite to verify system health:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```
2. Run the main automation workflow:
   ```bash
   python main.py
   ```
3. Launch the presentation dashboard:
   ```bash
   streamlit run ui.py
   ```
4. In the browser:
   - Review the summary counts (**12 processed, 7 ALLOW, 3 HANDOFF, 2 ESCALATE**).
   - Inspect the **System Integrity** checklist verifying policy determinism.
   - Navigate to the **Referrals** tab to compare an `ALLOW` case (with draft note) versus a `HANDOFF` case (Rule 3.9 under-18 flag).
   - Navigate to **Output Artifacts** and **Audit Trace** to view the underlying persisted records.

---

## 18. Documentation Files

- [`README.md`](file:///c:/Users/Asus/Desktop/casepilot-agent/README.md) — Main system documentation and operational guide.
- [`DECISIONS.md`](file:///c:/Users/Asus/Desktop/casepilot-agent/DECISIONS.md) — Architectural decision records detailing design rationale.
- [`AI-USAGE.md`](file:///c:/Users/Asus/Desktop/casepilot-agent/AI-USAGE.md) — Log of AI pair-programming and tool usage throughout development.

---

## 19. Limitations & Scope

- **Mock History Integration**: In the standard test configuration, resident history is retrieved from local mocks or local test services rather than live production databases.
- **Draft Triage Only**: Triage outputs generated by CasePilot are non-final recommendations and must be approved by a human caseworker before formal submission.
- **Single-Node Queue**: The current implementation runs as a synchronous batch worker designed for morning triage processing rather than distributed queue streaming.
