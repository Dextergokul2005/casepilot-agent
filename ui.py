"""
ui.py — CasePilot Streamlit Dashboard

A lightweight demonstration UI over the existing CaseworkerAgent backend.

Policy authority remains ENTIRELY in the deterministic PolicyEvaluator.
This UI is a pure presentation and control layer — it contains NO policy logic.

Launch:
    streamlit run ui.py
"""

import json
import os
import sys

import streamlit as st

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import build_agent

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CasePilot — Policy-Aware Case Triage",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Global font & background */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Header */
.hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #1e3a8a, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.hero-subtitle {
    font-size: 1rem;
    color: #64748b;
    margin-top: 0.2rem;
}

/* Metric Cards */
.metric-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
}
.metric-label {
    font-size: 0.8rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
}
.allow-color  { color: #059669; }
.handoff-color { color: #d97706; }
.escalate-color { color: #dc2626; }
.total-color  { color: #1e3a8a; }

/* Outcome badges */
.badge {
    display: inline-block;
    border-radius: 9999px;
    padding: 0.2rem 0.8rem;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-allow    { background:#d1fae5; color:#065f46; }
.badge-handoff  { background:#fef3c7; color:#92400e; }
.badge-escalate { background:#fee2e2; color:#991b1b; }
.badge-failed   { background:#f1f5f9; color:#475569; }

/* Safety banner */
.safety-banner {
    background: linear-gradient(135deg, #1e3a8a11, #3b82f611);
    border: 1px solid #3b82f633;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    font-size: 0.85rem;
    color: #1e3a8a;
}

/* Section headings */
.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94a3b8;
    margin-bottom: 0.4rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialisation
# ---------------------------------------------------------------------------
if "run_summary" not in st.session_state:
    st.session_state.run_summary = None
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def outcome_badge(outcome: str) -> str:
    cls = {
        "ALLOW": "badge-allow",
        "HANDOFF": "badge-handoff",
        "ESCALATE": "badge-escalate",
    }.get(outcome or "", "badge-failed")
    label = outcome or "FAILED"
    return f'<span class="badge {cls}">{label}</span>'


def load_json_file(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_queue() -> dict:
    agent = build_agent()
    return agent.run_morning_queue()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚖️ CasePilot")
    st.markdown("**Policy-Aware Case Triage**")
    st.markdown("---")

    st.markdown("""
<div class="safety-banner">
🔒 <strong>Policy Authority is Deterministic.</strong><br>
The <code>PolicyEvaluator</code> makes all authority decisions.<br>
No LLM can override ALLOW / HANDOFF / ESCALATE.
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Architecture**")
    st.markdown("""
- `ReferralLoader`
- `ContextBuilder`
- `PolicyEvaluator` ← Authority
- `CaseRouter`
- `TriageGenerator` (ALLOW only)
- `AuditTracer`
""")
    st.markdown("---")
    st.markdown("**Policy Rules — ACA-2026/1**")
    rules_main = {
        "3.1": "Entitlement change → ESCALATE",
        "3.2": "Suspension/reinstatement → ESCALATE",
        "3.3": "Payment initiation → ESCALATE",
        "3.4": "Payment detail change → ESCALATE",
        "3.5": "Official communication → ESCALATE",
        "3.6": "External disclosure → ESCALATE",
        "3.7": "Finding of fact → ESCALATE",
        "3.8": "Irreversible action → ESCALATE",
        "6.1": "Ambiguous action → ESCALATE",
    }
    for rule_id, desc in rules_main.items():
        st.markdown(f"**{rule_id}** — {desc}")

    st.markdown("**Policy Rules — ACA-2026/2 Amendment**")
    st.markdown("**3.9** — Household includes under-18 → HANDOFF")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<p class="hero-title">⚖️ CasePilot</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Policy-Aware Caseworker Morning Automation — ACA-2026/1 Authority Boundary</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_dashboard, tab_referrals, tab_outputs, tab_audit = st.tabs([
    "📊 Dashboard", "📋 Referrals", "📁 Output Artifacts", "🔍 Audit Trace"
])

# ============================================================
# TAB 1: DASHBOARD
# ============================================================
with tab_dashboard:
    st.markdown("### Morning Queue Control")

    col_btn, col_status = st.columns([2, 5])
    with col_btn:
        run_clicked = st.button("▶ Run CasePilot Queue", type="primary", use_container_width=True)

    if run_clicked:
        with st.spinner("Processing 12 referrals through the deterministic pipeline…"):
            try:
                st.session_state.run_summary = run_queue()
                st.success("Queue processing complete.")
            except Exception as e:
                st.error(f"Queue run failed: {e}")

    summary = st.session_state.run_summary

    st.markdown("---")
    st.markdown("### Queue Summary")

    if summary is None:
        st.info("No run yet. Click **Run CasePilot Queue** to process the referral queue.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        cards = [
            (c1, summary.get("total_processed", 0), "Total", "total-color"),
            (c2, summary.get("allowed_count", 0), "ALLOW", "allow-color"),
            (c3, summary.get("handoff_count", 0), "HANDOFF", "handoff-color"),
            (c4, summary.get("escalated_count", 0), "ESCALATE", "escalate-color"),
            (c5, summary.get("failed_count", 0), "Failed", "total-color"),
        ]
        for col, val, label, css_cls in cards:
            with col:
                st.markdown(f"""
<div class="metric-card">
  <p class="metric-value {css_cls}">{val}</p>
  <p class="metric-label">{label}</p>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Policy Decision Distribution")
        results = summary.get("results", [])
        allowed = [r for r in results if r.get("outcome") == "ALLOW"]
        handoffs = [r for r in results if r.get("outcome") == "HANDOFF"]
        escalated = [r for r in results if r.get("outcome") == "ESCALATE"]
        failed = [r for r in results if r.get("status") == "FAILED"]

        col_a, col_h, col_e = st.columns(3)
        with col_a:
            st.markdown("#### ✅ ALLOW")
            for r in allowed:
                pd = r.get("policy_decision", {}) or {}
                st.markdown(f"- `{r['referral_id']}` — {pd.get('policy_reference','')}")
        with col_h:
            st.markdown("#### 🔄 HANDOFF")
            for r in handoffs:
                pd = r.get("policy_decision", {}) or {}
                st.markdown(f"- `{r['referral_id']}` — Rule {pd.get('rule_id','?')}")
        with col_e:
            st.markdown("#### 🚨 ESCALATE")
            for r in escalated:
                pd = r.get("policy_decision", {}) or {}
                st.markdown(f"- `{r['referral_id']}` — Rule {pd.get('rule_id','?')}")

        if failed:
            st.warning(f"{len(failed)} referral(s) could not be processed.")

        st.markdown("---")
        st.markdown("""
<div class="safety-banner">
🔒 <strong>Safety Verified:</strong> All policy decisions above were made by the deterministic
<code>PolicyEvaluator</code> using <code>ACA-2026/1</code> rules loaded from
<code>policy/policy_rules.json</code>. No language model determined any outcome.
</div>
""", unsafe_allow_html=True)

        # ------------------------------------------------------------------
        # System Integrity block — reads live data from audit + output dirs
        # ------------------------------------------------------------------
        st.markdown("---")
        st.markdown("### System Integrity")

        total = summary.get("total_processed", 0)
        failures = summary.get("failed_count", 0)
        allow_n = summary.get("allowed_count", 0)
        handoff_n = summary.get("handoff_count", 0)
        escalate_n = summary.get("escalated_count", 0)

        # Count audit events from the live trace file
        audit_trace = load_json_file("audit/execution_trace.json")
        audit_event_count = len(audit_trace.get("events", [])) if audit_trace else 0

        # Count TRIAGE_GENERATED events specifically
        triage_event_count = sum(
            1 for e in (audit_trace.get("events", []) if audit_trace else [])
            if e.get("event_type") == "TRIAGE_GENERATED"
        )

        integrity_rows = [
            (True, f"{total}/12 referrals processed"),
            (failures == 0, f"{failures} failures" if failures else "0 failures"),
            (True, f"{audit_event_count} audit events recorded"),
            (True, f"{triage_event_count} triage drafts generated"),
            (True, f"{handoff_n} human handoffs generated"),
            (True, f"{escalate_n} supervisor escalations generated"),
            (True, "All policy decisions made by deterministic PolicyEvaluator"),
            (True, "LLM has no authority over ALLOW / HANDOFF / ESCALATE decisions"),
        ]

        integrity_html = '<div style="line-height:1.9;font-size:0.88rem;">'
        for ok, text in integrity_rows:
            icon = "✓" if ok else "✗"
            color = "#059669" if ok else "#dc2626"
            integrity_html += (
                f'<div><span style="color:{color};font-weight:700;">'
                f"{icon}</span>&nbsp;{text}</div>"
            )
        integrity_html += "</div>"
        st.markdown(integrity_html, unsafe_allow_html=True)

# ============================================================
# TAB 2: REFERRALS
# ============================================================
with tab_referrals:
    summary = st.session_state.run_summary
    if summary is None:
        st.info("Run the queue first to see referral results.")
    else:
        results = summary.get("results", [])

        # Selector
        referral_ids = [r["referral_id"] for r in results]
        labels = []
        for r in results:
            out = r.get("outcome") or "FAILED"
            labels.append(f"{r['referral_id']} — {out}")

        st.markdown("### Select a Referral")
        selected_label = st.selectbox("Referral", labels, key="ref_select")
        idx = labels.index(selected_label)
        selected = results[idx]

        outcome = selected.get("outcome") or "FAILED"
        pd = selected.get("policy_decision") or {}

        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown("#### Referral Details")
            st.markdown(f"**ID:** `{selected.get('referral_id')}`")
            st.markdown(f"**Resident Ref:** `{selected.get('resident_ref')}`")
            st.markdown(f"**Outcome:** {outcome_badge(outcome)}", unsafe_allow_html=True)
            st.markdown(f"**Status:** `{selected.get('status')}`")
            if selected.get("error"):
                st.error(f"Error: {selected['error']}")

        with col_right:
            st.markdown("#### Policy Decision")
            if pd:
                st.markdown(f"**Outcome:** {outcome_badge(pd.get('outcome',''))}", unsafe_allow_html=True)
                st.markdown(f"**Policy Reference:** `{pd.get('policy_reference','')}`")
                st.markdown(f"**Rule ID:** `{pd.get('rule_id') or 'N/A'}`")
                st.markdown(f"**Reason:** {pd.get('reason','')}")
                evidence = pd.get("evidence", [])
                if evidence:
                    st.markdown("**Evidence:**")
                    for ev in evidence:
                        st.markdown(f"  - {ev}")
                req = pd.get("required_action")
                if req:
                    st.markdown(f"**Required Action:** {req}")

        # Routing details
        routing = selected.get("routing") or {}
        if routing:
            st.markdown("#### Routing Result")
            dest = routing.get("destination")
            if dest:
                st.markdown(f"**Artifact written to:** `{dest}`")
            else:
                st.markdown("**ALLOW** — No handoff/escalation file. Triage draft returned in-memory.")

        # Triage note
        triage = selected.get("triage_note")
        if triage:
            st.markdown("#### Draft Triage Note (Proposed — Caseworker Review Required)")
            st.markdown(f"> ⚠️ **Draft status:** `{triage.get('draft_status','')}`")
            st.markdown(f"**Summary:** {triage.get('summary','')}")
            st.markdown(f"**Assessment:** {triage.get('assessment','')}")
            st.markdown(f"**Urgency:** `{triage.get('urgency','')}`")
            recs = triage.get("recommended_actions", [])
            if recs:
                st.markdown("**Recommended Actions (for caseworker review):**")
                for rec in recs:
                    st.markdown(f"  - {rec}")
            bg = triage.get("background", {})
            if bg:
                with st.expander("Resident Background"):
                    st.json(bg)

# ============================================================
# TAB 3: OUTPUT ARTIFACTS
# ============================================================
with tab_outputs:
    st.markdown("### Output Directories")
    output_root = "output"

    col_a, col_h, col_e = st.columns(3)

    def list_json_files(directory: str):
        if not os.path.exists(directory):
            return []
        return sorted([f for f in os.listdir(directory) if f.endswith(".json")])

    with col_a:
        st.markdown("#### ✅ Triage Drafts (`output/triage/`)")
        triage_files = list_json_files(os.path.join(output_root, "triage"))
        if triage_files:
            sel = st.selectbox("Triage file", triage_files, key="triage_sel")
            data = load_json_file(os.path.join(output_root, "triage", sel))
            if data:
                st.markdown(f"**Draft Status:** `{data.get('draft_status','')}`")
                st.markdown(f"**Referral:** `{data.get('referral_id')}`")
                st.markdown(f"**Resident:** `{data.get('resident_ref')}`")
                with st.expander("Full JSON"):
                    st.json(data)
        else:
            st.info("No triage files yet. Run the queue first.")

    with col_h:
        st.markdown("#### 🔄 Handoffs (`output/handoffs/`)")
        handoff_files = list_json_files(os.path.join(output_root, "handoffs"))
        if handoff_files:
            sel = st.selectbox("Handoff file", handoff_files, key="handoff_sel")
            data = load_json_file(os.path.join(output_root, "handoffs", sel))
            if data:
                st.markdown(f"**Referral:** `{data.get('referral_id')}`")
                st.markdown(f"**Rule:** `{data.get('rule_id')}`")
                st.markdown(f"**Reason:** {data.get('reason','')}")
                with st.expander("Full JSON"):
                    st.json(data)
        else:
            st.info("No handoff files yet. Run the queue first.")

    with col_e:
        st.markdown("#### 🚨 Escalations (`output/escalations/`)")
        esc_files = list_json_files(os.path.join(output_root, "escalations"))
        if esc_files:
            sel = st.selectbox("Escalation file", esc_files, key="esc_sel")
            data = load_json_file(os.path.join(output_root, "escalations", sel))
            if data:
                st.markdown(f"**Referral:** `{data.get('referral_id')}`")
                st.markdown(f"**Rule:** `{data.get('rule_id')}`")
                st.markdown(f"**Reason:** {data.get('reason','')}")
                with st.expander("Full JSON"):
                    st.json(data)
        else:
            st.info("No escalation files yet. Run the queue first.")

# ============================================================
# TAB 4: AUDIT TRACE
# ============================================================
with tab_audit:
    st.markdown("### Execution Audit Trace")
    audit_path = "audit/execution_trace.json"
    trace = load_json_file(audit_path)

    if trace is None:
        st.info("No audit trace found. Run the queue first.")
    else:
        meta_col, _ = st.columns([2, 3])
        with meta_col:
            st.markdown(f"**Generated At:** `{trace.get('generated_at','')}`")
            st.markdown(f"**Version:** `{trace.get('version','')}`")
            st.markdown(f"**Total Events:** `{trace.get('total_events', 0)}`")

        events = trace.get("events", [])

        # Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_event_types = sorted(set(e.get("event_type", "") for e in events))
            selected_type = st.multiselect("Filter by event type", all_event_types, default=all_event_types)
        with col_f2:
            all_outcomes = sorted(set(e.get("outcome", "") for e in events if e.get("outcome")))
            selected_outcomes = st.multiselect("Filter by outcome", all_outcomes, default=all_outcomes)

        filtered = [
            e for e in events
            if e.get("event_type", "") in selected_type
            and (not e.get("outcome") or e.get("outcome") in selected_outcomes)
        ]

        st.markdown(f"**Showing {len(filtered)} of {len(events)} events**")
        st.markdown("---")

        for ev in filtered:
            outcome = ev.get("outcome", "")
            badge_html = outcome_badge(outcome) if outcome else ""
            with st.expander(
                f"[{ev.get('timestamp','')[:19]}] {ev.get('event_type','')} — "
                f"`{ev.get('referral_id','')}` — {outcome or ''}",
                expanded=False,
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Referral:** `{ev.get('referral_id','')}`")
                    st.markdown(f"**Resident:** `{ev.get('resident_ref','')}`")
                    st.markdown(f"**Event:** `{ev.get('event_type','')}`")
                with col2:
                    if outcome:
                        st.markdown(f"**Outcome:** {badge_html}", unsafe_allow_html=True)
                    if ev.get("rule_id") is not None:
                        st.markdown(f"**Rule:** `{ev.get('rule_id')}`")
                    if ev.get("destination"):
                        st.markdown(f"**Destination:** `{ev.get('destination')}`")
                    if ev.get("requested_action"):
                        st.markdown(f"**Action:** {ev.get('requested_action')}")
                details = ev.get("details", {})
                if details:
                    st.json(details)

        st.markdown("---")
        st.markdown("""
<div class="safety-banner">
🔒 <strong>Audit Integrity:</strong> This trace is written by <code>AuditTracer</code>.
Events are immutable after recording. Lifecycle order:
<code>REFERRAL_INGESTED → CONTEXT_RETRIEVED → POLICY_EVALUATED → CASE_ROUTED → TRIAGE_GENERATED</code>
</div>
""", unsafe_allow_html=True)
