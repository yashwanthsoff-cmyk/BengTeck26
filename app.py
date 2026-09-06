"""app.py — Checkpoint-Native DX (v9) Interactive Dashboard
5-Panel Interface covering Features A, B, C, D, and E.
"""
import streamlit as st
import json
import pandas as pd
from datetime import datetime

from lib.checkpoint_dx import CheckpointDX, DeadEnd, Intent
from config import PROJECT_NAME, DATABRICKS_CATALOG, DATABRICKS_SCHEMA

st.set_page_config(
    page_title="Checkpoint-Native DX",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling for premium feel
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E2F;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #2D2D44;
        margin-bottom: 12px;
    }
    .badge-met {
        background-color: #065F46;
        color: #6EE7B7;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85em;
    }
    .badge-gap {
        background-color: #7F1D1D;
        color: #FCA5A5;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85em;
    }
    .badge-fallback {
        background-color: #78350F;
        color: #FCD34D;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_dx():
    return CheckpointDX()

dx = get_dx()

# Sidebar: Checkpoint & Session Selection
st.sidebar.title("⚡ Checkpoint DX")
st.sidebar.caption(f"Project: **{PROJECT_NAME}**")

# Fetch available checkpoints from Supabase or Delta
checkpoints = []
try:
    checkpoints_res = dx.supabase.table("checkpoints").select("*").order("created_at", desc=True).execute()
    checkpoints = checkpoints_res.data or []
except Exception:
    pass

if not checkpoints:
    try:
        norm_rows = dx._run_sql(f"SELECT DISTINCT checkpoint_id, session_id, branch FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.checkpoints_normalized")
        checkpoints = [
            {
                "id": f"chk-uuid-{r[0]}",
                "checkpoint_id": r[0],
                "session_id": r[1],
                "branch_name": r[2],
                "status": "active",
            }
            for r in norm_rows
        ]
    except Exception:
        pass

if checkpoints:
    checkpoint_options = {c["checkpoint_id"]: c for c in checkpoints}
    selected_cid = st.sidebar.selectbox(
        "Select Checkpoint",
        options=list(checkpoint_options.keys()),
        index=0,
    )
    selected_cp = checkpoint_options[selected_cid]
    selected_session = selected_cp.get("session_id") or "session-prod-01"
    st.sidebar.markdown(f"**Session:** `{selected_session}`")
    st.sidebar.markdown(f"**Branch:** `{selected_cp.get('branch_name', 'main')}`")
    st.sidebar.markdown(f"**Status:** `{selected_cp.get('status', 'active')}`")
else:
    selected_cid = st.sidebar.text_input("Enter Checkpoint ID", value="chk-001")
    selected_session = st.sidebar.text_input("Enter Session ID", value="session-prod-01")
    selected_cp = None

st.title("Checkpoint-Native DX (v9)")
st.caption("Enterprise developer experience bridging git/Entire checkpoints into Databricks Delta, Unity Catalog, and Supabase.")

# Top Navigation Tabs for 5 Features
tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs([
    "Feature A: Dead-End Registry",
    "Feature B: Requirement Ledger",
    "Feature C: Intent Conformance",
    "Feature D: Resume Contract",
    "Feature E: Resume-Integrity & Memory",
])


# ==============================================================================
# PANEL A: FEATURE A — Dead-End Registry
# ==============================================================================
with tab_a:
    st.header("Feature A — Dead-End Registry (Special Tier)")
    st.markdown("Surfaces abandoned paths, root causes, and suggested alternatives persisted via MLflow Unity Catalog traces with Delta fallback.")

    dead_ends = []
    try:
        dead_ends = dx.get_dead_ends(selected_cid)
    except Exception:
        pass

    if not dead_ends and selected_cid:
        try:
            de_rows = dx._run_sql(f"SELECT dead_end_type, root_cause, suggested_fix, confidence FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback WHERE checkpoint_id = '{selected_cid}'")
            dead_ends = [{"dead_end_type": r[0], "root_cause": r[1], "suggested_fix": r[2], "confidence_score": float(r[3] or 0.5), "used_fallback": True} for r in de_rows]
        except Exception:
            pass

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Dead Ends Logged", len(dead_ends))
    with col2:
        fallback_count = sum(1 for d in dead_ends if d.get("used_fallback"))
        st.metric("Delta Fallback Traces", fallback_count)
    with col3:
        avg_conf = (sum(d.get("confidence_score", 0) for d in dead_ends) / len(dead_ends)) if dead_ends else 0.0
        st.metric("Avg Detection Confidence", f"{avg_conf:.1%}")

    st.subheader("Logged Dead Ends")
    if dead_ends:
        for idx, de in enumerate(dead_ends):
            with st.container():
                st.markdown(f"### #{idx+1} {de.get('dead_end_type', 'unknown').upper()}")
                badge = "⚡ Delta Fallback" if de.get("used_fallback") else "✨ Unity Catalog Trace"
                st.caption(f"Trace Source: **{badge}** | Confidence: `{de.get('confidence_score', 0):.2f}` | Attempts: `{de.get('failed_attempts', 1)}`")

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Root Cause / Abandoned Approach:**")
                    st.error(de.get("root_cause") or "No root cause captured.")
                with c2:
                    st.markdown("**Suggested Fix / Alternative Approach:**")
                    st.success(de.get("suggested_fix") or "Stateless JWT tokens with independent verification.")

                if de.get("alternative_approaches"):
                    st.markdown(f"**Alternative Paths:** {', '.join(de['alternative_approaches'])}")
                st.divider()
    else:
        st.info("No dead ends logged for this checkpoint yet.")

    # Live query helper for demo
    with st.expander("🔍 Live Databricks SQL Trace Query (Demo Script Beat 0:45–1:15)"):
        st.code(f"""
-- Query live Unity Catalog trace fallback table
SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence, created_at
FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback
WHERE checkpoint_id = '{selected_cid}'
ORDER BY created_at DESC LIMIT 5;
        """, language="sql")
        if st.button("Run Live Trace Query on Databricks"):
            try:
                rows = dx._run_sql(f"SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback LIMIT 10")
                st.write(pd.DataFrame(rows, columns=["Checkpoint", "Type", "Root Cause", "Fix", "Confidence"]))
            except Exception as ex:
                st.warning(f"Databricks SQL query result: {ex}")


# ==============================================================================
# PANEL B: FEATURE B — Requirement Ledger
# ==============================================================================
with tab_b:
    st.header("Feature B — Requirement Ledger (Advanced Tier)")
    st.markdown("Closes the context gap by tracking natural-language ask status (`not_started`, `in_progress`, `done`, `superseded`) with supersession reconciliation.")

    # Load requirements for selected checkpoint
    reqs = []
    if selected_cp and dx.supabase:
        try:
            req_res = dx.supabase.table("requirements").select("*").eq("checkpoint_id", selected_cp["id"]).execute()
            reqs = req_res.data or []
        except Exception:
            pass

    if not reqs and selected_cid:
        try:
            delta_reqs = dx._run_sql(f"SELECT requirement_text, status FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.requirements WHERE checkpoint_id = '{selected_cid}'")
            reqs = [{"id": f"req-{idx}", "requirement_text": r[0], "status": r[1], "evidence": "Delta Ledger"} for idx, r in enumerate(delta_reqs)]
        except Exception:
            pass

    # Status counts
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requirements", len(reqs))
    with col2:
        st.metric("Done", sum(1 for r in reqs if r.get("status") == "done"))
    with col3:
        st.metric("In Progress / Open", sum(1 for r in reqs if r.get("status") in ("not_started", "in_progress")))
    with col4:
        superseded_count = sum(1 for r in reqs if r.get("status") == "superseded")
        st.metric("Superseded", superseded_count)

    st.subheader("Requirement Status Breakdown")
    if reqs:
        for r in reqs:
            status = r.get("status", "not_started")
            text = r.get("requirement_text", "")
            evidence = r.get("evidence")

            c1, c2, c3 = st.columns([5, 2, 2])
            with c1:
                if status == "superseded":
                    st.markdown(f"~~{text}~~ *(superseded)*")
                elif status == "done":
                    st.markdown(f"✅ **{text}**")
                else:
                    st.markdown(f"📌 **{text}**")
                if evidence:
                    st.caption(f"ℹ️ {evidence}")
            with c2:
                st.markdown(f"Status: `{status}`")
            with c3:
                new_st = st.selectbox(
                    "Update Status",
                    ["not_started", "in_progress", "done", "superseded"],
                    index=["not_started", "in_progress", "done", "superseded"].index(status) if status in ["not_started", "in_progress", "done", "superseded"] else 0,
                    key=f"req_stat_{r['id']}",
                )
                if new_st != status:
                    dx.set_requirement_status(selected_cid, text, new_st)
                    st.rerun()
            st.divider()
    else:
        st.info("No requirements found for this checkpoint.")

    st.subheader("Add Requirement (FIX 3 Symmetric Parity Test)")
    new_req_text = st.text_input("New Requirement Text")
    if st.button("Add Requirement to Supabase + Delta + Memory"):
        if new_req_text.strip():
            dx.add_requirements(selected_cid, [new_req_text.strip()], source="manual")
            st.success(f"Added requirement: '{new_req_text}' (synced to Supabase, Delta, and agent_memory)")
            st.rerun()


# ==============================================================================
# PANEL C: FEATURE C — Intent Conformance Diff
# ==============================================================================
with tab_c:
    st.header("Feature C — Intent Conformance Diff (Core Tier)")
    st.markdown("Compares segmented prompt clauses with code diff hunks to compute implementation status (`met`, `gap`, `scope_creep`).")

    try:
        sql = f"""
            SELECT ic.checkpoint_id, ic.clause, ic.implementation_status, ic.confidence_score,
                   CASE WHEN d.checkpoint_id IS NOT NULL THEN 'possible_deadend_context' ELSE 'clean' END AS deadend_flag
            FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.intent_conformance ic
            LEFT JOIN {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.deadend_candidates d ON ic.checkpoint_id = d.checkpoint_id
            WHERE ic.checkpoint_id = '{selected_cid}'
            ORDER BY ic.implementation_status
        """
        rows = dx._run_sql(sql)
        df_intent = pd.DataFrame(rows, columns=["Checkpoint", "Clause", "Status", "Confidence", "Deadend Flag"])
    except Exception as ex:
        st.warning(f"Could not load Delta intent conformance ({ex}). Reading from Supabase fallback...")
        if selected_cp:
            intents = dx.supabase.table("intent_summaries").select("*").eq("checkpoint_id", selected_cp["id"]).execute().data or []
            df_intent = pd.DataFrame([
                {"Checkpoint": selected_cid, "Clause": i["intent_text"], "Status": i["implementation_status"], "Confidence": i["confidence_score"], "Deadend Flag": "clean"}
                for i in intents
            ])
        else:
            df_intent = pd.DataFrame()

    if not df_intent.empty:
        st.dataframe(df_intent, use_container_width=True)
    else:
        st.info("No intent conformance records found for this checkpoint.")


# ==============================================================================
# PANEL D: FEATURE D — Agent Resume Contract
# ==============================================================================
with tab_d:
    st.header("Feature D — Agent Resume Contract (Nuclear Tier)")
    st.markdown("Synthesizes Unresolved Requirements (B), Dead-End Approaches (A), Implementation Gaps (C), and Resume-Integrity Safety (E) into a machine-readable briefing contract for subsequent agents.")

    st.markdown("### Generate Contract")
    st.info("Uses **FIX 2 sequence**: Resolves `session_id` from checkpoint first, then generates and persists the contract.")

    if st.button("🚀 Generate Resume Contract", type="primary"):
        with st.spinner("Synthesizing data from Features B, A, C, and E..."):
            try:
                # FIX 2: UI "Generate Contract" button handler order
                checkpoint = dx.get_checkpoint(selected_cid)
                if not checkpoint:
                    st.error(f"Checkpoint {selected_cid} not found.")
                else:
                    session_id = checkpoint.get("session_id") or selected_session
                    result = dx.create_resume_contract(selected_cid, session_id)
                    contract_data = result["contract"]

                    st.success("Resume Contract successfully generated and recorded!")
                    st.json(contract_data)

                    st.download_button(
                        "📥 Download Resume Contract JSON",
                        data=json.dumps(contract_data, indent=2),
                        file_name=f"resume_contract_{selected_cid}.json",
                        mime="application/json",
                    )
            except Exception as e:
                st.error(f"Error generating contract: {e}")

    st.subheader("Historical Contracts for this Checkpoint")
    if selected_cp and dx.supabase:
        try:
            contracts = dx.supabase.table("resume_contracts").select("*").eq("checkpoint_id", selected_cp["id"]).order("created_at", desc=True).execute().data or []
            for c in contracts:
                passed = "✅ PASSED" if c.get("integrity_check_passed") else "⚠️ LOW INTEGRITY"
                with st.expander(f"Contract {c['id'][:8]} — {passed} ({c['created_at']})"):
                    st.json(c.get("contract_sections", {}))
        except Exception:
            pass


# ==============================================================================
# PANEL E: FEATURE E — Resume-Integrity Checking & Agent Memory
# ==============================================================================
with tab_e:
    st.header("Feature E — Resume-Integrity Checking & Agent Memory")
    st.markdown("Intelligence & Resilience tier: verifies memory coverage against open requirements, blocks unsafe resumes with human-readable reasons, and provides active human-feedback learning.")

    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Resume Integrity Score")
        if st.button("Check Resume Safety Now"):
            integrity = dx.check_resume_integrity(selected_session, checkpoint_id=selected_cp["id"] if selected_cp else None)
            score = integrity.get("integrity_score", 0.0)
            reason = integrity.get("reason", "")

            st.metric("Integrity Score", f"{score:.1%}")
            if score > 0.7:
                st.success(f"STATUS: SAFE TO RESUME — {reason}")
            else:
                st.error(f"STATUS: RESUME BLOCKED / UNRELIABLE — {reason}")

    with col2:
        st.subheader("Session Memory Entries")
        try:
            memories = dx.retrieve_from_agent_memory(selected_session)
        except Exception as e:
            memories = []
            st.warning(f"Note on Delta agent_memory query: {e}")

        if memories:
            for m in memories:
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(f"**Key:** `{m['key']}`")
                    st.caption(f"Value: {m['value']}")
                with c2:
                    st.markdown(f"Conf: `{m['confidence']:.2f}`")
                with c3:
                    if st.button("👎", key=f"down_{m['key']}"):
                        dx.record_human_feedback(selected_cid, m['key'], was_correct=False)
                        st.rerun()
                    if st.button("👍", key=f"up_{m['key']}"):
                        dx.record_human_feedback(selected_cid, m['key'], was_correct=True)
                        st.rerun()
                st.divider()
        else:
            st.info("No memory entries found for this session.")
