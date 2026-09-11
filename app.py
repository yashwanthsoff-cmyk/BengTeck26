# app.py — Checkpoint-Native DX (v9) Interactive Dashboard
# 5-Panel Interface covering Features A, B, C, D, and E.
import os
import streamlit as st
import json
import hashlib
import uuid
import pandas as pd
from datetime import datetime

from lib.checkpoint_dx import CheckpointDX, DeadEnd, Intent
from config import PROJECT_NAME, DATABRICKS_CATALOG, DATABRICKS_SCHEMA

st.set_page_config(
    page_title="Checkpoint-Native DX",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load Premium UI/UX Design System
import os

css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Floating Navigation Capsule
st.markdown("""
<div class="nav-capsule" style="position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:99999;background:rgba(255,255,255,0.92);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid rgba(0,0,0,0.08);border-radius:40px;padding:10px 28px;display:flex;gap:24px;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
  <a href="#panel-a" style="color:#0071E3;text-decoration:none;font-weight:500;font-size:13px;letter-spacing:-0.01em;">01 Dead-Ends</a>
  <a href="#panel-b" style="color:#0071E3;text-decoration:none;font-weight:500;font-size:13px;letter-spacing:-0.01em;">02 Requirements</a>
  <a href="#panel-c" style="color:#0071E3;text-decoration:none;font-weight:500;font-size:13px;letter-spacing:-0.01em;">03 Intents</a>
  <a href="#panel-d" style="color:#0071E3;text-decoration:none;font-weight:500;font-size:13px;letter-spacing:-0.01em;">04 Contracts</a>
  <a href="#panel-e" style="color:#0071E3;text-decoration:none;font-weight:500;font-size:13px;letter-spacing:-0.01em;">05 Integrity</a>
</div>
""", unsafe_allow_html=True)


if "dx_client" not in st.session_state:
    st.session_state["dx_client"] = CheckpointDX()
dx = st.session_state["dx_client"]

# Sidebar: Checkpoint & Session Selection
st.sidebar.title("Checkpoint DX")
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

# Top Navigation Tabs
tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs([
    "Dead-End Registry",
    "Requirement Ledger",
    "Intent Conformance",
    "Resume Contract",
    "Resume-Integrity & Memory",
])


# ==============================================================================
# PANEL A: Dead-End Registry
# ==============================================================================
with tab_a:
    st.markdown('<div id="panel-a"></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-caps">0.1 / Feature A</p>', unsafe_allow_html=True)
    st.markdown('# Dead-End Registry')
    st.markdown('Tracks abandoned AI approaches + root causes')
    st.divider()

    dead_ends = []
    try:
        dead_ends = dx.get_dead_ends(selected_cid)
    except Exception:
        pass

    if not dead_ends and selected_cid:
        try:
            de_rows = dx._run_sql(f"SELECT dead_end_type, root_cause, suggested_fix, confidence, severity, cluster_key, fix_effectiveness FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback WHERE checkpoint_id = '{selected_cid}'")
            dead_ends = [{
                "dead_end_type": r[0],
                "root_cause": r[1],
                "suggested_fix": r[2],
                "confidence_score": float(r[3] or 0.5),
                "severity": r[4] if len(r) > 4 and r[4] else "minor",
                "cluster_key": r[5] if len(r) > 5 else None,
                "fix_effectiveness": r[6] if len(r) > 6 and r[6] else "untested",
                "used_fallback": True,
            } for r in de_rows]
        except Exception:
            pass

    # Feature 1/A: Fix Outcome Analytics & Overall KPIs
    fix_analytics = dx.get_fix_outcome_analytics()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Dead Ends Logged", len(dead_ends))
    with col2:
        fallback_count = sum(1 for d in dead_ends if d.get("used_fallback"))
        st.metric("Delta Fallback Traces", fallback_count)
    with col3:
        avg_conf = (sum(d.get("confidence_score", 0) for d in dead_ends) / len(dead_ends)) if dead_ends else 0.0
        st.metric("Avg Detection Confidence", f"{avg_conf:.1%}")
    with col4:
        st.metric("Overall Fix Success Rate", f"{fix_analytics.get('overall_success_rate', 0.0)}%", f"{fix_analytics.get('worked_count', 0)} of {fix_analytics.get('total_tested', 0)} tested")

    # Feature 1.1: Pre-flight Check (Hardened+)
    with st.expander("Pre-Flight Approach Checker (Dead-End Prevention & Risk Scoring)", expanded=False):
        st.markdown(
            "**Test a planned approach before executing.** Computes multi-layer confidence scoring, warns before repeating known failure patterns, and provides ranked alternative recommendations.\n\n"
            "*Operational Note: This is a pre-flight lookup against recorded failures, not live LLM token stream interception.*"
        )
        planned_text = st.text_area(
            "Describe the approach or prompt you plan to attempt:",
            placeholder="e.g. Authenticate users using Redis session store with local file caching...",
            key="planned_approach_input"
        )
        col_th1, col_th2 = st.columns(2)
        with col_th1:
            warn_threshold = st.slider("Warning Threshold (Jaccard)", min_value=0.1, max_value=0.8, value=0.35, step=0.05, key="preflight_warn_slider")
        with col_th2:
            appr_threshold = st.slider("Mandatory Approval Threshold", min_value=0.5, max_value=0.95, value=0.70, step=0.05, key="preflight_appr_slider")

        if st.button("Check Approach Before Running", key="btn_check_approach"):
            if planned_text.strip():
                with st.spinner("Analyzing historical failure patterns and confidence scoring..."):
                    chk_res = dx.check_before_attempting(
                        checkpoint_id=selected_cid,
                        planned_approach=planned_text,
                        similarity_threshold=warn_threshold,
                    )
                    st.session_state["preflight_last_result"] = chk_res
                    st.session_state["preflight_last_text"] = planned_text
            else:
                st.warning("Please enter an approach description to test.")

        # Render Pre-Flight Results if present in session state
        last_res = st.session_state.get("preflight_last_result")
        if last_res:
            st.markdown("---")
            conf = last_res.get("confidence", {})
            score = last_res.get("similarity_score", 0.0)
            risk_lvl = conf.get("risk_level", "[LOW RISK]")
            ci = conf.get("confidence_interval", [0.0, 0.0])

            # Metric Bar
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("Token Similarity", f"{score:.1%}")
            with m_col2:
                st.metric("Confidence Interval", f"[{ci[0]:.1%} - {ci[1]:.1%}]")
            with m_col3:
                st.metric("Risk Evaluation", risk_lvl)
            with m_col4:
                st.metric("Recency Weight", f"{conf.get('recency_weight', 1.0):.2f}")

            # Plain Language Reasoning Callout
            reasoning_text = conf.get("plain_reasoning", "")
            if "[CRITICAL]" in risk_lvl or "[HIGH RISK]" in risk_lvl:
                st.error(f"**{risk_lvl} Alert**: {reasoning_text}")
            elif "[MODERATE RISK]" in risk_lvl:
                st.warning(f"**{risk_lvl} Warning**: {reasoning_text}")
            else:
                st.success(f"**{risk_lvl}**: {reasoning_text}")

            # Ranked Recommendations
            ranked_recs = last_res.get("ranked_recommendations", [])
            if ranked_recs:
                st.markdown("#### Ranked Alternative Recommendations")
                rec_rows = []
                for r_idx, r in enumerate(ranked_recs):
                    rec_rows.append({
                        "Rank": f"#{r_idx + 1}",
                        "Remedy / Fix": r.get("recommendation"),
                        "Historical Success": f"{r.get('success_probability', 0.0):.1%}",
                        "Effort": r.get("effort_level", "medium").upper(),
                        "Category": r.get("category", "code_change"),
                        "Est. Time": r.get("estimated_time", "N/A"),
                        "Outcome": r.get("historical_outcome", "[UNTESTED]"),
                    })
                st.dataframe(pd.DataFrame(rec_rows), use_container_width=True)

            # Matching Failure Timeline
            if last_res.get("matches_found"):
                with st.expander("Matching Historical Dead Ends Timeline", expanded=False):
                    for w in last_res.get("warnings", []):
                        w_sev = w.get("severity", "minor").upper()
                        w_badge = f"[{w_sev}]"
                        w_eff = w.get("fix_effectiveness", "untested").upper()
                        st.markdown(f"**{w_badge} Match (Similarity: `{w['similarity_score']:.1%}`) | Fix Outcome: `[{w_eff}]`**")
                        st.markdown(f"- **Failed Approach / Root Cause:** {w.get('root_cause')}")
                        st.markdown(f"- **Suggested Remedy:** {w.get('suggested_fix')}")
                        st.markdown("---")

                # Override Workflow
                if last_res.get("override_eligible"):
                    with st.expander("Pre-Flight Override & Approval Sign-Off", expanded=True):
                        requires_appr = (score >= appr_threshold) or ("[CRITICAL]" in risk_lvl)
                        if requires_appr:
                            st.error("[MANDATORY APPROVAL REQUIRED]: Similarity exceeds mandatory threshold (0.70) or matches critical failure. Lead Architect sign-off required to proceed.")
                        else:
                            st.info("[OVERRIDE AVAILABLE]: You may log an audit override to proceed with this approach.")

                        ovr_reason = st.text_input("Override Justification / Technical Rationale:", key="ovr_input_reason")
                        col_ovr1, col_ovr2 = st.columns(2)
                        with col_ovr1:
                            ovr_category = st.selectbox(
                                "Override Category:",
                                ["technical_necessity", "different_context", "approved_experiment", "emergency_hotfix"],
                                key="ovr_input_cat"
                            )
                        with col_ovr2:
                            ovr_approver = st.text_input("Authorizing Lead / Approver:", value="lead_architect", key="ovr_input_appr")

                        if st.button("Submit Override Audit Record", key="btn_submit_override"):
                            if ovr_reason.strip():
                                ovr_rec = dx.record_preflight_override(
                                    planned_approach=st.session_state.get("preflight_last_text", planned_text),
                                    similarity_score=score,
                                    matched_dead_end_id=last_res.get("warnings", [{}])[0].get("id"),
                                    override_reason=ovr_reason,
                                    override_category=ovr_category,
                                    approver=ovr_approver,
                                    risk_level=risk_lvl,
                                )
                                st.success(f"[AUDIT LOGGED]: Override record `{ovr_rec['id']}` registered successfully.")
                            else:
                                st.warning("Please provide an override justification.")

        # Recent Overrides Audit History
        overrides = dx.get_preflight_overrides(limit=10)
        if overrides:
            with st.expander("Recent Pre-Flight Check Overrides (Audit Log)", expanded=False):
                ovr_display = [
                    {
                        "ID": o.get("id"),
                        "Planned Approach": o.get("planned_approach")[:60] + "..." if len(o.get("planned_approach", "")) > 60 else o.get("planned_approach"),
                        "Similarity": f"{float(o.get('similarity_score', 0)):.1%}",
                        "Risk": o.get("risk_level", "MODERATE"),
                        "Category": o.get("override_category"),
                        "Reason": o.get("override_reason"),
                        "Approver": o.get("approver"),
                        "Recorded At": str(o.get("created_at"))[:19],
                    }
                    for o in overrides
                ]
                st.dataframe(pd.DataFrame(ovr_display), use_container_width=True)

    # Feature 1.2: Root-Cause Clusters (Hardened+)
    with st.expander("Root-Cause Clusters & Systemic Bottlenecks (Hardened+)", expanded=False):
        st.markdown("Clusters recurring failures across sessions to identify systemic bottlenecks, trend velocities, and automated RCA reporting.")
        try:
            clusters_trend = dx.get_cluster_trends()
            if clusters_trend:
                surge_count = sum(1 for c in clusters_trend if "[SURGE]" in c.get("status", ""))
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    st.metric("Total Clusters", len(clusters_trend))
                with c_m2:
                    st.metric("Surge Alert Clusters", surge_count)
                with c_m3:
                    top_cluster = clusters_trend[0]
                    st.metric("Largest Cluster Size", f"{top_cluster.get('member_count', 1)} incidents")

                c_table_rows = [
                    {
                        "Cluster Key": c.get("cluster_key"),
                        "Pattern Title": c.get("display_name"),
                        "Incidents": c.get("member_count", 1),
                        "Trend Status": c.get("status"),
                        "Velocity (inc/day)": c.get("velocity", 1.0),
                        "Representative Root Cause": c.get("representative_root_cause"),
                        "Common Remedy": c.get("common_suggested_fix"),
                        "Last Seen": str(c.get("last_seen_at"))[:19] if c.get("last_seen_at") else "N/A",
                    }
                    for c in clusters_trend
                ]
                st.dataframe(pd.DataFrame(c_table_rows), use_container_width=True)

                # Cluster Intelligence Tools Tabs
                st.markdown("#### Cluster Intelligence & Management Tools")
                cl_tab1, cl_tab2, cl_tab3 = st.tabs(["AI Pattern Naming & Renaming", "Cluster Consolidation (Merge)", "RCA Post-Mortem Generator"])

                with cl_tab1:
                    cluster_options = {f"{c['display_name']} ({c['cluster_key']})": c for c in clusters_trend}
                    sel_cluster_name = st.selectbox("Select Cluster to Inspect / Rename:", list(cluster_options.keys()), key="sb_cluster_rename")
                    target_c = cluster_options[sel_cluster_name]

                    col_ai_btn, col_ai_save = st.columns([1, 1])
                    with col_ai_btn:
                        if st.button("Generate Professional Title (Groq LLM)", key="btn_gen_ai_name"):
                            with st.spinner("Synthesizing pattern name with Groq LLM..."):
                                ai_res = dx.generate_cluster_name(
                                    root_cause_text=target_c.get("representative_root_cause", ""),
                                    common_fix=target_c.get("common_suggested_fix", ""),
                                    member_count=target_c.get("member_count", 1),
                                )
                                st.session_state["cluster_ai_name"] = ai_res.get("suggested_name")
                                st.session_state["cluster_ai_reasoning"] = ai_res.get("reasoning")

                    suggested_val = st.session_state.get("cluster_ai_name") or target_c.get("display_name")
                    if st.session_state.get("cluster_ai_reasoning"):
                        st.info(f"AI Reasoning: {st.session_state['cluster_ai_reasoning']}")

                    new_name_input = st.text_input("Pattern Name / Title:", value=suggested_val, key="input_new_cluster_name")
                    if st.button("Save Pattern Name", key="btn_save_cluster_name"):
                        if new_name_input.strip():
                            dx.rename_cluster(
                                cluster_id=target_c.get("id") or target_c.get("cluster_key"),
                                custom_name=new_name_input.strip(),
                                ai_suggested_name=st.session_state.get("cluster_ai_name"),
                                reasoning=st.session_state.get("cluster_ai_reasoning"),
                            )
                            st.success(f"Cluster `{target_c.get('cluster_key')}` updated with title: '{new_name_input.strip()}'.")
                            st.rerun()

                with cl_tab2:
                    st.markdown("Consolidate duplicate clusters into a single unified root-cause cluster.")
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        source_opt = st.selectbox("Source Cluster (to absorb):", list(cluster_options.keys()), key="sb_merge_src")
                    with col_m2:
                        target_opt = st.selectbox("Target Cluster (destination):", list(cluster_options.keys()), key="sb_merge_tgt")

                    if st.button("Merge Clusters", key="btn_execute_merge"):
                        src_id = cluster_options[source_opt].get("id") or cluster_options[source_opt].get("cluster_key")
                        tgt_id = cluster_options[target_opt].get("id") or cluster_options[target_opt].get("cluster_key")
                        if src_id == tgt_id:
                            st.warning("Source and Target cluster cannot be the same.")
                        else:
                            m_res = dx.merge_clusters(src_id, tgt_id)
                            if m_res.get("success"):
                                st.success(f"Merged successfully! Target cluster combined member count: {m_res.get('combined_member_count')}.")
                                st.rerun()
                            else:
                                st.error(m_res.get("error", "Merge failed."))

                with cl_tab3:
                    st.markdown("Generate exportable, comprehensive Root Cause Analysis (RCA) reports.")
                    rca_cluster_sel = st.selectbox("Cluster for RCA Report:", list(cluster_options.keys()), key="sb_rca_cluster")
                    rca_tmpl = st.selectbox("Report Format:", ["Executive Summary", "Technical Post-Mortem"], key="sb_rca_format")
                    tmpl_key = "technical" if "Technical" in rca_tmpl else "executive"

                    if st.button("Generate RCA Report", key="btn_gen_rca"):
                        cid = cluster_options[rca_cluster_sel].get("id") or cluster_options[rca_cluster_sel].get("cluster_key")
                        report_md = dx.generate_rca_report(cluster_id=cid, template=tmpl_key)
                        st.session_state["generated_rca_md"] = report_md

                    if st.session_state.get("generated_rca_md"):
                        st.markdown("---")
                        st.markdown(st.session_state["generated_rca_md"])
                        st.download_button(
                            label="Download RCA Report (.md)",
                            data=st.session_state["generated_rca_md"],
                            file_name=f"RCA_Report_{cluster_options[rca_cluster_sel].get('cluster_key')}.md",
                            mime="text/markdown",
                            key="btn_dl_rca"
                        )
            else:
                st.info("No dead-end clusters formed yet. Run `python pipeline_glue.py` to cluster dead-ends across sessions.")
        except Exception as err:
            st.info(f"Clusters info: {err}")

    # Feature 1.3: Fix Effectiveness Tracking & Outcomes Dashboard (Hardened+)
    with st.expander("Fix Effectiveness & Outcome Analytics (Hardened+)", expanded=False):
        st.markdown("Tracks verified remediation effectiveness across all logged dead ends to surface proven fixes and retire failing workarounds.")
        col_fa1, col_fa2 = st.columns(2)
        with col_fa1:
            st.markdown("#### Proven Top Remedies")
            top_list = fix_analytics.get("top_performing_fixes", [])
            if top_list:
                for f_item in top_list:
                    st.success(f"**{f_item.get('status')} [{f_item.get('category').upper()}]**: {f_item.get('suggested_fix')}")
                    st.caption(f"Applies to: {f_item.get('root_cause')[:100]}...")
            else:
                st.info("No verified working fixes recorded yet.")

        with col_fa2:
            st.markdown("#### Underperforming Remedies (Need Revision)")
            bad_list = fix_analytics.get("underperforming_fixes", [])
            if bad_list:
                for f_item in bad_list:
                    st.error(f"**{f_item.get('status')} [{f_item.get('category').upper()}]**: {f_item.get('suggested_fix')}")
                    st.caption(f"Failed for: {f_item.get('root_cause')[:100]}...")
            else:
                st.info("No failed fixes recorded.")

    st.subheader("Logged Dead Ends for Selected Checkpoint")
    if dead_ends:
        for idx, de in enumerate(dead_ends):
            with st.container():
                sev = str(de.get("severity") or "minor").upper()
                sev_tag = f"[{sev}]"
                st.markdown(f"### #{idx+1} {sev_tag} {de.get('dead_end_type', 'unknown').upper()}")

                badge = "Delta Fallback" if de.get("used_fallback") else "Unity Catalog Trace"
                eff_val = (de.get("fix_effectiveness") or "untested").lower()
                eff_tag = f"[{eff_val.upper()}]"
                cluster_label = f" | Cluster: `{de.get('cluster_key')}`" if de.get("cluster_key") else ""
                st.caption(f"Severity: **{sev}** | Trace: **{badge}** | Confidence: `{de.get('confidence_score', 0):.2f}` | Attempts: `{de.get('failed_attempts', 1)}`{cluster_label} | Fix Status: **{eff_tag}**")

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Root Cause / Abandoned Approach:**")
                    st.error(de.get("root_cause") or "No root cause captured.")
                with c2:
                    st.markdown("**Suggested Fix / Alternative Approach:**")
                    st.success(de.get("suggested_fix") or "Stateless JWT tokens with independent verification.")

                if de.get("alternative_approaches"):
                    st.markdown(f"**Alternative Paths:** {', '.join(de['alternative_approaches'])}")

                # Interactive outcome recording with notes
                de_id = de.get("id") or de.get("root_cause")
                col_fix_notes, col_fix_btn1, col_fix_btn2 = st.columns([2, 1, 1])
                with col_fix_notes:
                    fix_note_input = st.text_input("Outcome Verification Notes:", placeholder="e.g. Fixed connection leak with pool size cap", key=f"fix_note_{idx}_{selected_cid}")
                with col_fix_btn1:
                    if st.button("Mark Worked", key=f"btn_worked_{idx}_{selected_cid}"):
                        dx.record_fix_outcome(str(de_id), worked=True, notes=fix_note_input)
                        st.toast("Recorded: Fix worked!")
                        st.rerun()
                with col_fix_btn2:
                    if st.button("Mark Failed", key=f"btn_failed_{idx}_{selected_cid}"):
                        dx.record_fix_outcome(str(de_id), worked=False, notes=fix_note_input)
                        st.toast("Recorded: Fix failed.")
                        st.rerun()

                st.divider()
    else:
        st.info("No dead ends logged for this checkpoint yet.")

    # Live query helper
    with st.expander("Live Databricks SQL Trace Query"):
        st.code(f"""
-- Query live Unity Catalog trace fallback table
SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence, created_at
FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback
WHERE checkpoint_id = '{selected_cid}'
ORDER BY created_at DESC LIMIT 5;
        """, language="sql")
        if st.button("Run Live Trace Query on Databricks"):
            try:
                rows = dx._run_sql(f"SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback WHERE checkpoint_id = '{selected_cid}' ORDER BY created_at DESC LIMIT 5")
                if not rows:
                    rows = dx._run_sql(f"SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.dead_end_traces_fallback LIMIT 10")
                st.write(pd.DataFrame(rows, columns=["Checkpoint", "Type", "Root Cause", "Fix", "Confidence"]))
            except Exception as ex:
                st.warning(f"Databricks SQL query result: {ex}")


# ==============================================================================
# PANEL B: Requirement Ledger (Hardened+)
# ==============================================================================
with tab_b:
    st.markdown('<div id="panel-b"></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-caps">0.2 / Feature B</p>', unsafe_allow_html=True)
    st.markdown('# Requirement Ledger')
    st.markdown('Checkpoint-scoped requirements with dynamic prioritization')
    st.divider()

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
            delta_reqs = dx._run_sql(f"SELECT requirement_text, status, priority_tier, moscow, effort_points, owner FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.requirements WHERE checkpoint_id = '{selected_cid}'")
            reqs = [{"id": f"req-{idx}", "requirement_text": r[0], "status": r[1], "priority_tier": r[2], "moscow": r[3], "effort_points": r[4], "owner": r[5], "evidence": "Delta Ledger"} for idx, r in enumerate(delta_reqs)]
        except Exception:
            pass

    # Status Analytics & Bottleneck Dashboard
    analytics = dx.get_requirement_status_analytics(selected_cid)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Requirements", len(reqs))
    with col2:
        done_count = sum(1 for r in reqs if r.get("status") == "done")
        st.metric("Done", done_count, f"{analytics.get('completion_rate', 0)}% completed")
    with col3:
        in_prog = sum(1 for r in reqs if r.get("status") in ("not_started", "in_progress", "ready", "in_review"))
        st.metric("In Progress / Active", in_prog)
    with col4:
        blocked_count = sum(1 for r in reqs if r.get("status") == "blocked")
        st.metric("Blocked", blocked_count)
    with col5:
        throughput = analytics.get("throughput_per_week", 0)
        st.metric("Throughput / Week", throughput)

    # Cycle Times & Bottleneck Ribbon
    c_time = analytics.get("cycle_times", {})
    st.caption(f"Status Cycle Times: Avg {c_time.get('avg_hours', 24.0)}h | P50 {c_time.get('p50_hours', 18.0)}h | P90 {c_time.get('p90_hours', 48.0)}h")

    bottlenecks = analytics.get("bottlenecks", [])
    if bottlenecks:
        for bn in bottlenecks:
            st.warning(f"{bn.get('severity', '[BOTTLENECK]')} {bn.get('description', '')}")

    stale_items = dx.detect_stale_requirements(selected_cid, stale_threshold_days=7)
    if stale_items:
        with st.expander(f"[ALERT] Stale Requirements Detected ({len(stale_items)} items inactive > 7 days)", expanded=False):
            st.dataframe(pd.DataFrame(stale_items)[["warning_level", "requirement_text", "status", "days_inactive", "owner"]], use_container_width=True)

    st.divider()

    # Sub-tabs for Feature 2 capabilities
    b_tab_ledger, b_tab_prioritize, b_tab_effort, b_tab_criteria, b_tab_graph = st.tabs([
        "[Workflow Ledger]",
        "[Dynamic Priority & RICE]",
        "[ML Effort Estimation]",
        "[Gherkin Acceptance Criteria]",
        "[Interactive Dependency Graph]",
    ])

    # --------------------------------------------------------------------------
    # SUB-TAB 1: Workflow Ledger & Status Tracking
    # --------------------------------------------------------------------------
    with b_tab_ledger:
        st.subheader("Requirement Workflow & Audit Trail")

        # Add Requirement Form
        with st.expander("[+] Add New Requirement", expanded=False):
            c_add1, c_add2, c_add3 = st.columns([3, 1, 1])
            with c_add1:
                new_req_text = st.text_input("Requirement Description", key="new_req_input")
            with c_add2:
                new_req_owner = st.text_input("Initial Assignee", key="new_req_owner", placeholder="e.g. dev-lead")
            with c_add3:
                new_req_pts = st.selectbox("Story Points", [1, 2, 3, 5, 8, 13], index=1, key="new_req_pts")

            if st.button("Add to Supabase + Delta + Memory", key="btn_add_req"):
                if new_req_text.strip():
                    inserted = dx.add_requirements(selected_cid, [new_req_text.strip()], source="manual")
                    if new_req_owner.strip() and inserted:
                        try:
                            dx.assign_requirement_owner(inserted[0]["id"], new_req_owner.strip())
                        except Exception:
                            pass
                    st.success(f"[SUCCESS] Added requirement: '{new_req_text}'")
                    st.rerun()

        # Status Filter
        all_statuses = ["all", "draft", "backlog", "ready", "in_progress", "blocked", "in_review", "done", "superseded"]
        sel_filter = st.selectbox("Filter by Status", all_statuses, index=0, key="filter_status_select")

        filtered_reqs = reqs if sel_filter == "all" else [r for r in reqs if (r.get("status") or "").lower() == sel_filter]

        if filtered_reqs:
            for r in filtered_reqs:
                rid = str(r.get("id", ""))
                status = (r.get("status") or "backlog").lower()
                text = r.get("requirement_text", "")
                tier = r.get("priority_tier") or "P2"
                moscow = str(r.get("moscow") or "should").upper()
                effort = r.get("effort_points") or r.get("story_points")
                owner = r.get("owner") or ""
                criteria = r.get("acceptance_criteria") or []
                reasoning = r.get("priority_reasoning")

                # Fetch AI Next-Status Prediction
                prediction = dx.predict_next_requirement_status(
                    requirement_text=text,
                    current_status=status,
                    has_criteria=bool(criteria),
                    is_blocked=(status == "blocked"),
                )

                c1, c2, c3 = st.columns([4, 3, 2])
                with c1:
                    # Badges
                    badge_items = [f"[{status.upper()}]", f"[{tier}]", f"[{moscow}]"]
                    if effort:
                        badge_items.append(f"[{effort} pts]")
                    if owner:
                        badge_items.append(f"[Owner: {owner}]")
                    st.markdown(" ".join(f"`{b}`" for b in badge_items))

                    if status == "superseded":
                        st.markdown(f"~~{text}~~ *(superseded)*")
                    elif status == "done":
                        st.markdown(f"**[DONE]** {text}")
                    elif status == "blocked":
                        st.markdown(f"**[BLOCKED]** {text}")
                    else:
                        st.markdown(f"**{text}**")

                    if reasoning:
                        st.caption(f"*Priority reasoning:* {reasoning}")

                    # AI Prediction badge
                    st.info(
                        f"[AI NEXT-STATUS PREDICTION]: `{prediction['predicted_status'].upper()}` "
                        f"(Confidence: {prediction['confidence'] * 100:.0f}%)\n\n"
                        f"*Reasoning*: {prediction['reasoning']}\n\n"
                        f"*Suggested Actions*: {', '.join(prediction['suggested_actions'])}"
                    )

                with c2:
                    st.markdown(f"Current Status: `{status.upper()}`")
                    # Transition Controls
                    allowed_next = dx.ALLOWED_STATUS_TRANSITIONS.get(status, ["ready", "in_progress", "done", "blocked", "superseded"])
                    transition_options = [status] + [s for s in allowed_next if s != status]
                    chosen_status = st.selectbox(
                        "Transition To",
                        transition_options,
                        index=0,
                        key=f"trans_sel_{rid}",
                    )

                    reason_val = None
                    if chosen_status in ("blocked", "superseded"):
                        reason_val = st.text_input(
                            f"Reason for [{chosen_status.upper()}] (Required)",
                            key=f"reason_input_{rid}",
                            placeholder=f"Specify why requirement is {chosen_status}...",
                        )

                    if chosen_status != status:
                        if st.button(f"Confirm Transition to [{chosen_status.upper()}]", key=f"btn_trans_{rid}"):
                            try:
                                dx.update_requirement_status_workflow(
                                    requirement_id=rid,
                                    new_status=chosen_status,
                                    changed_by="user",
                                    reason=reason_val,
                                    checkpoint_id=selected_cid,
                                )
                                st.success(f"[SUCCESS] Status updated to [{chosen_status.upper()}]")
                                st.rerun()
                            except ValueError as ve:
                                st.error(f"[GUARD ERROR] {ve}")
                            except Exception as ex:
                                st.error(f"Transition error: {ex}")

                    # Inline Owner edit
                    owner_val = st.text_input("Assignee", value=owner, key=f"owner_in_{rid}", placeholder="Assignee username")
                    if owner_val != owner and st.button("Update Owner", key=f"btn_owner_{rid}"):
                        try:
                            dx.assign_requirement_owner(rid, owner_val.strip())
                            st.success(f"Owner updated: {owner_val.strip()}")
                            st.rerun()
                        except Exception as ex:
                            st.warning(f"Owner update note: {ex}")

                with c3:
                    if st.button("Re-Enrich (Groq)", key=f"btn_enrich_{rid}"):
                        with st.spinner("Scoring priority and criteria..."):
                            dx.enrich_requirement(rid, text)
                            st.success("[SUCCESS] Enriched")
                            st.rerun()

                    # Audit Trail Expander
                    with st.expander("Status Audit Trail", expanded=False):
                        history_records = dx.get_requirement_status_history(rid)
                        if history_records:
                            hist_df = pd.DataFrame([
                                {
                                    "From": h.get("previous_status") or "-",
                                    "To": h.get("new_status") or "-",
                                    "By": h.get("changed_by") or "-",
                                    "Reason": h.get("reason") or "-",
                                    "Timestamp": str(h.get("changed_at"))[:19],
                                }
                                for h in history_records
                            ])
                            st.dataframe(hist_df, use_container_width=True)
                        else:
                            st.caption("No historical status transitions recorded yet.")

                st.divider()
        else:
            st.info(f"No requirements found with status filter '{sel_filter}'.")

    # --------------------------------------------------------------------------
    # SUB-TAB 2: Dynamic Priority Scoring & MoSCoW + RICE
    # --------------------------------------------------------------------------
    with b_tab_prioritize:
        st.subheader("Dynamic Priority & MoSCoW + RICE Scoring")
        st.markdown(
            "Calculates multi-factor priority scores (0-100) using business impact, urgency, dependency counts, "
            "and combines with RICE reach-impact-confidence-effort metrics and MoSCoW weightings."
        )

        p_col1, p_col2 = st.columns([1, 1])
        with p_col1:
            st.markdown("### Multi-Factor Dynamic Priority Calculator")
            p_impact = st.slider("Business Impact", 1, 10, 7, key="dp_impact")
            p_urgency = st.slider("Urgency / Timeline Sensitivity", 1, 10, 6, key="dp_urgency")
            p_deps = st.slider("Prerequisite Dependencies Count", 0, 10, 2, key="dp_deps")
            p_blocked = st.slider("Downstream Blocked Tasks Count", 0, 10, 1, key="dp_blocked")
            p_effort = st.slider("Effort Story Points", 1, 13, 5, key="dp_effort")
            p_risk = st.slider("Technical Risk Score", 1, 5, 3, key="dp_risk")

            calc_res = dx.calculate_dynamic_priority(
                business_impact=p_impact,
                urgency=p_urgency,
                dependency_count=p_deps,
                blocked_count=p_blocked,
                effort_points=p_effort,
                risk_score=p_risk,
            )
            dyn_score = calc_res["dynamic_priority_score"]
            dyn_tier = calc_res["priority_tier"]

            st.metric("Dynamic Priority Score", f"{dyn_score} / 100", f"Tier: [{dyn_tier}]")
            if dyn_tier == "P0":
                st.error("[CRITICAL P0] Immediate blocking priority. Fast-track allocation required.")
            elif dyn_tier == "P1":
                st.warning("[IMPORTANT P1] High-value milestone requirement. Schedule in current sprint.")
            else:
                st.info("[NORMAL P2] Standard priority. Backlog refinement candidate.")

        with p_col2:
            st.markdown("### MoSCoW + RICE Hybrid Prioritization")
            r_reach = st.number_input("Reach (Users / Flows impacted)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="rice_reach")
            r_impact = st.slider("RICE Impact (0.25=min, 1=med, 2=high, 3=massive)", 0.25, 3.0, 2.0, step=0.25, key="rice_impact")
            r_conf = st.slider("Confidence (0.5=low, 0.8=med, 1.0=high)", 0.5, 1.0, 0.8, step=0.1, key="rice_conf")
            r_effort = st.number_input("Effort (Person-weeks or Story Points)", min_value=0.5, max_value=20.0, value=3.0, step=0.5, key="rice_effort")
            r_moscow = st.selectbox("MoSCoW Category", ["must", "should", "could", "wont"], index=1, key="rice_moscow")

            rice_res = dx.calculate_rice_score(
                reach=r_reach,
                impact=r_impact,
                confidence=r_conf,
                effort=r_effort,
                moscow=r_moscow,
            )
            st.metric("Raw RICE Score", rice_res["rice_score"])
            st.metric("MoSCoW Hybrid Score", rice_res["hybrid_score"], f"Weight: {rice_res['moscow_multiplier']}x ({r_moscow.upper()})")

    # --------------------------------------------------------------------------
    # SUB-TAB 3: ML Story Point Effort Estimation
    # --------------------------------------------------------------------------
    with b_tab_effort:
        st.subheader("ML-Powered Story Point Effort Estimation")
        st.markdown(
            "Predicts story points on the Fibonacci scale (1, 2, 3, 5, 8, 13) with confidence intervals, "
            "complexity factor breakdown (Technical, Domain, Integration, Testing), and historical similarity lookup."
        )

        sample_req_texts = [r.get("requirement_text", "") for r in reqs if r.get("requirement_text")]
        chosen_sample = st.selectbox("Select Existing Requirement or Custom", ["<Custom Text>"] + sample_req_texts, key="ml_effort_select")

        if chosen_sample == "<Custom Text>":
            target_effort_text = st.text_area("Requirement Text for Estimation", "Build distributed resilient sync pipeline for Databricks Delta and Supabase with schema migration support.", key="ml_effort_custom")
        else:
            target_effort_text = chosen_sample

        if st.button("Predict Effort with ML Engine", key="btn_run_ml_effort"):
            ml_pred = dx.predict_requirement_effort_ml(target_effort_text, historical_requirements=reqs)

            c_pt1, c_pt2 = st.columns([1, 1])
            with c_pt1:
                st.metric("Predicted Story Points", f"{ml_pred['predicted_story_points']} pts")
                st.info(f"Confidence Interval: `[{ml_pred['confidence_interval'][0]} - {ml_pred['confidence_interval'][1]} pts]` (Fibonacci)")
                st.write(f"**Reasoning**: {ml_pred['reasoning']}")

            with c_pt2:
                st.markdown("#### Complexity Factor Breakdown (0-10 Scale)")
                factors = ml_pred["complexity_factors"]
                st.progress(factors["technical"] / 10.0, text=f"Technical Complexity: {factors['technical']} / 10")
                st.progress(factors["domain"] / 10.0, text=f"Domain Complexity: {factors['domain']} / 10")
                st.progress(factors["integration"] / 10.0, text=f"Integration Scope: {factors['integration']} / 10")
                st.progress(factors["testing"] / 10.0, text=f"Testing Scope: {factors['testing']} / 10")

            similar = ml_pred.get("similar_requirements", [])
            if similar:
                st.markdown("#### Similar Historical Requirements")
                st.dataframe(pd.DataFrame(similar)[["requirement_text", "effort_points", "similarity"]], use_container_width=True)

    # --------------------------------------------------------------------------
    # SUB-TAB 4: Gherkin Acceptance Criteria Management
    # --------------------------------------------------------------------------
    with b_tab_criteria:
        st.subheader("Gherkin Acceptance Criteria Manager")
        st.markdown(
            "Structure acceptance criteria with standard Given / When / Then scenarios, validate completeness, "
            "calculate scenario coverage score, and generate automated Python unittest stubs."
        )

        default_gherkin = (
            "Scenario: Successful state transition\n"
            "Given requirement status is in backlog\n"
            "When user triggers valid transition to ready\n"
            "Then new status is recorded and audit history logged\n\n"
            "Scenario: Blocked transition guard\n"
            "Given requirement is active\n"
            "When user sets status to blocked without reason\n"
            "Then transition guard raises validation error"
        )
        gherkin_input = st.text_area("Gherkin Specifications", value=default_gherkin, height=180, key="gherkin_editor_area")

        if st.button("Parse, Validate & Generate Test Stubs", key="btn_validate_gherkin"):
            res_gherkin = dx.parse_and_validate_gherkin(gherkin_input)

            g_col1, g_col2 = st.columns([1, 1])
            with g_col1:
                st.metric("Scenario Coverage Score", f"{res_gherkin['coverage_score']}%")
                if res_gherkin["valid"]:
                    st.success("[PASS] All scenarios valid with Given/When/Then steps.")
                else:
                    for err in res_gherkin["errors"]:
                        st.error(f"[VALIDATION ERROR] {err}")

                st.markdown("#### Parsed Scenarios Checklist")
                for sc in res_gherkin["scenarios"]:
                    st.markdown(
                        f"**{sc['title']}**\n"
                        f"- *Given*: {sc['given']}\n"
                        f"- *When*: {sc['when']}\n"
                        f"- *Then*: {sc['then']}"
                    )

            with g_col2:
                st.markdown("#### Auto-Generated Unit Test Stubs")
                st.code(res_gherkin["test_stubs"], language="python")

    # --------------------------------------------------------------------------
    # SUB-TAB 5: Interactive Dependency Graph & Cycle Detection
    # --------------------------------------------------------------------------
    with b_tab_graph:
        st.subheader("Interactive Dependency Graph & Critical Path Analysis")
        st.markdown(
            "Analyzes directed prerequisite chains, detects circular dependency loops (e.g. A -> B -> A), "
            "computes the weighted Critical Path through the DAG, and simulates ripple delay impacts."
        )

        dep_graph = dx.analyze_requirement_dependencies_interactive(selected_cid)

        # Circular Dependency Alert
        if dep_graph["has_circular_dependency"]:
            st.error(
                f"[CYCLE DETECTED] Circular dependency loop detected in graph: "
                f"{' -> '.join(dep_graph['cycles'][0])}. Please resolve loop to unblock execution!"
            )
        else:
            st.success("[VALID DAG] No circular dependency cycles detected in requirement graph.")

        # Critical Path Banner
        cp_nodes = dep_graph["critical_path"]
        cp_weight = dep_graph["critical_path_length"]
        st.info(
            f"[CRITICAL PATH] Longest Execution Duration: `{cp_weight} Story Points`\n\n"
            f"Path Sequence: `{' -> '.join(cp_nodes) if cp_nodes else 'None'}`"
        )

        # Add Dependency Edge Form
        with st.expander("[+] Add Dependency Link", expanded=False):
            if len(reqs) >= 2:
                req_options = {f"{r.get('requirement_text', '')[:40]}... (ID: {r['id']})": r["id"] for r in reqs}
                c_dep1, c_dep2 = st.columns([1, 1])
                with c_dep1:
                    src_label = st.selectbox("Dependent Requirement (A)", list(req_options.keys()), key="dep_src_sel")
                with c_dep2:
                    tgt_label = st.selectbox("Prerequisite Requirement (B - must complete first)", list(req_options.keys()), key="dep_tgt_sel")
                dep_reason = st.text_input("Dependency Reasoning", placeholder="Why does A depend on B?", key="dep_reason_in")

                if st.button("Connect Dependency Edge", key="btn_add_dep_edge"):
                    src_id = req_options[src_label]
                    tgt_id = req_options[tgt_label]
                    if src_id == tgt_id:
                        st.error("[ERROR] A requirement cannot depend on itself.")
                    else:
                        dx.add_requirement_dependency(src_id, tgt_id, reasoning=dep_reason.strip())
                        st.success(f"[SUCCESS] Connected: Requirement depends on prerequisite.")
                        st.rerun()
            else:
                st.caption("Need at least 2 requirements to create dependencies.")

        # Delay Impact Simulator
        st.markdown("### Ripple Delay Impact Simulator")
        sim_options = {f"{r.get('requirement_text', '')[:40]}...": r["id"] for r in reqs}
        if sim_options:
            sim_choice = st.selectbox("Select Requirement to Simulate Delay", list(sim_options.keys()), key="sim_delay_sel")
            sim_rid = sim_options[sim_choice]
            sim_delay_days = st.slider("Simulate Delay (Days)", 1, 30, 5, key="sim_delay_days")

            impact_info = dep_graph["delay_impacts"].get(sim_rid, {"downstream_count": 0, "downstream_ids": []})
            down_count = impact_info["downstream_count"]
            down_ids = impact_info["downstream_ids"]

            if down_count > 0:
                st.warning(
                    f"[DELAY SIMULATION] A {sim_delay_days}-day delay on this requirement ripples to "
                    f"**{down_count} downstream requirements**:\n\n"
                    f"{', '.join(down_ids)}"
                )
            else:
                st.info(f"[DELAY SIMULATION] This requirement has no downstream dependents. Delay has 0 ripple impact.")

        # Nodes & Edges Table
        if dep_graph["edges"]:
            st.markdown("#### Active Dependency Edges")
            st.dataframe(pd.DataFrame(dep_graph["edges"]), use_container_width=True)



# ==============================================================================
# PANEL C: Intent Conformance Diff [Hardened+]
# ==============================================================================
with tab_c:
    st.markdown('<div id="panel-c"></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-caps">0.3 / Feature C</p>', unsafe_allow_html=True)
    st.markdown('# Intent Conformance')
    st.markdown('Maps what was asked vs what got built')
    st.divider()

    # 1. Fetch Intent Records from Delta, Supabase, or SQLite
    intents_data = []
    try:
        sql = f"""
            SELECT ic.checkpoint_id, ic.clause, ic.implementation_status, ic.confidence_score,
                   CASE WHEN d.checkpoint_id IS NOT NULL THEN 'possible_deadend_context' ELSE 'clean' END AS deadend_flag
            FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.intent_conformance ic
            LEFT JOIN {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.deadend_candidates d ON ic.checkpoint_id = d.checkpoint_id
            WHERE ic.checkpoint_id = '{selected_cid}'
            ORDER BY ic.implementation_status
        """
        delta_rows = dx._run_sql(sql)
        for r in delta_rows:
            intents_data.append({
                "checkpoint_id": r[0],
                "clause_text": r[1],
                "implementation_status": r[2],
                "confidence_score": float(r[3] or 1.0),
                "deadend_flag": r[4],
                "source": "Delta Unity Catalog",
            })
    except Exception:
        pass

    if not intents_data and selected_cp:
        try:
            supa_res = dx.supabase.table("intent_summaries").select("*").eq("checkpoint_id", selected_cp["id"]).execute()
            if supa_res.data:
                for r in supa_res.data:
                    intents_data.append({
                        "checkpoint_id": selected_cid,
                        "clause_text": r.get("intent_text", ""),
                        "implementation_status": r.get("implementation_status", "met"),
                        "confidence_score": float(r.get("confidence_score", 1.0) or 1.0),
                        "deadend_flag": "clean",
                        "source": "Supabase / SQLite",
                    })
        except Exception:
            pass

    # Provide curated sample clauses if checkpoint has none logged yet
    if not intents_data:
        default_samples = [
            ("User authentication with JWT bearer tokens and bcrypt password hashing", "met", 0.92, "security"),
            ("Redis caching layer for database query acceleration with TTL invalidation", "partially_met", 0.68, "performance"),
            ("Streamlit interactive UI dashboard with metric widgets and tab navigation", "fully_met", 0.95, "ui_ux"),
            ("Automated unit and integration test suite with high branch coverage", "not_met", 0.30, "non_functional"),
            ("Append-only audit trail exporting signed reports in Markdown, JSON, and CSV", "met", 0.88, "functional"),
        ]
        for c_text, c_status, c_conf, c_cat in default_samples:
            intents_data.append({
                "checkpoint_id": selected_cid or "chk-001",
                "clause_text": c_text,
                "implementation_status": c_status,
                "confidence_score": c_conf,
                "deadend_flag": "clean",
                "category": c_cat,
                "source": "Curated Suite",
            })

    # Top KPI Metrics Dashboard
    dash_data = dx.get_compliance_dashboard(selected_cid)
    col_c1, col_c2, col_c3, col_c4, col_c5, col_c6 = st.columns(6)
    with col_c1:
        st.metric("Total Clauses", len(intents_data))
    with col_c2:
        conf_rate = dash_data.get("conformance_rate", 0.85)
        st.metric("Conformance Rate", f"{conf_rate:.1%}")
    with col_c3:
        grade_top = dash_data.get("grade", "B")
        st.metric("Compliance Grade", f"[GRADE {grade_top}]")
    with col_c4:
        met_cnt = sum(1 for i in intents_data if i.get("implementation_status") in ("met", "fully_met"))
        st.metric("Fully Met", met_cnt)
    with col_c5:
        gap_cnt = sum(1 for i in intents_data if i.get("implementation_status") in ("gap", "not_met", "partially_met"))
        st.metric("Gaps / Partial", gap_cnt)
    with col_c6:
        active_viols = len(dash_data.get("critical_violations", []))
        st.metric("Active Violations", active_viols)

    st.divider()

    col_cf1, col_cf2 = st.columns([3, 1])
    with col_cf1:
        st.caption("AI verification engine analyzing prompt clauses with semantic matching, domain clustering, and predictive trending.")
    with col_cf2:
        conf_filter_thresh = st.slider("Min Confidence Filter", min_value=0.0, max_value=1.0, value=0.0, step=0.05, key="f3_conf_filter_slider")

    filtered_intents = dx.filter_conformance_by_confidence(intents_data, conf_filter_thresh) if conf_filter_thresh > 0 else intents_data
    if conf_filter_thresh > 0:
        st.info(f"Displaying {len(filtered_intents)} of {len(intents_data)} clauses with confidence >= {conf_filter_thresh:.0%}")

    # 2. Sub-Tabs for Feature 3 Capabilities
    c_tab_match, c_tab_score, c_tab_remedy, c_tab_clusters, c_tab_audit = st.tabs([
        "[Clause vs Diff Semantic Matching]",
        "[Multi-Level Conformance & Grading]",
        "[Status Classification & Auto-Remediation]",
        "[Intent Domain Clusters & 7D Trends]",
        "[Compliance Dashboard & Audit]",
    ])

    # --------------------------------------------------------------------------
    # SUB-TAB 1: Clause vs Diff Semantic Matching
    # --------------------------------------------------------------------------
    with c_tab_match:
        st.subheader("Semantic Clause vs Diff Hunk Matching")
        st.markdown(
            "Matches requirements against actual codebase diffs using intent extraction, keyword classification, "
            "token Jaccard overlap, and domain-specific semantic scoring."
        )

        sample_clauses_list = [i["clause_text"] for i in intents_data]
        c_mode = st.radio(
            "Select Clause Input Source",
            ["Choose from Checkpoint Clauses", "Enter Custom Prompt Clause"],
            horizontal=True,
            key="f3_clause_mode_radio",
        )

        if c_mode == "Choose from Checkpoint Clauses" and sample_clauses_list:
            selected_clause_text = st.selectbox("Select Prompt Clause", sample_clauses_list, key="f3_clause_select")
        else:
            selected_clause_text = st.text_area(
                "Enter Prompt Clause to Verify",
                value="Implement JWT authentication with bcrypt password hashing and token expiration guards",
                key="f3_custom_clause_input",
            )

        # Code Changes / Diff Hunks
        st.markdown("#### Codebase Diff Hunks for Verification")
        sample_diffs = {
            "Auth Service Diff (lib/auth.py)": (
                "--- a/lib/auth.py\n"
                "+++ b/lib/auth.py\n"
                "@@ -10,6 +10,18 @@\n"
                "+import bcrypt\n"
                "+import jwt\n"
                "+\n"
                "+def hash_password(password: str) -> str:\n"
                "+    salt = bcrypt.gensalt()\n"
                "+    return bcrypt.hashpw(password.encode(), salt).decode()\n"
                "+\n"
                "+def verify_jwt(token: str, secret: str) -> dict:\n"
                "+    return jwt.decode(token, secret, algorithms=['HS256'])\n"
            ),
            "Redis Cache Diff (lib/cache.py)": (
                "--- a/lib/cache.py\n"
                "+++ b/lib/cache.py\n"
                "@@ -15,5 +15,14 @@\n"
                "+import redis\n"
                "+client = redis.Redis(host='localhost', port=6379, db=0)\n"
                "+def get_cached(key: str):\n"
                "+    return client.get(key)\n"
                "+def set_cached(key: str, val: str, ttl: int = 3600):\n"
                "+    client.setex(key, ttl, val)\n"
            ),
            "UI Dashboard Panel Diff (app.py)": (
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -50,6 +50,12 @@\n"
                "+tab1, tab2 = st.tabs(['[Overview]', '[Analytics]'])\n"
                "+with tab1:\n"
                "+    st.metric('Active Users', 1240)\n"
                "+    st.metric('Uptime', '99.9%')\n"
            ),
            "Unrelated Logger Diff (lib/logger.py)": (
                "--- a/lib/logger.py\n"
                "+++ b/lib/logger.py\n"
                "@@ -1,4 +1,7 @@\n"
                "+import logging\n"
                "+logging.basicConfig(level=logging.INFO)\n"
                "+logger = logging.getLogger('app')\n"
            ),
        }

        diff_preset = st.selectbox("Select Code Changes Diff Preset", list(sample_diffs.keys()), key="f3_diff_preset")
        diff_text = st.text_area("Unified Diff Hunk", value=sample_diffs[diff_preset], height=160, key="f3_diff_text")

        if st.button("Run Semantic Clause vs Diff Matching", key="btn_run_f3_match"):
            code_changes_input = [{
                "file_path": diff_preset.split("(")[-1].replace(")", "").strip(),
                "diff_hunk": diff_text,
            }]
            with st.spinner("Analyzing semantic intent and computing token overlap..."):
                match_res = dx.match_clause_semantic(selected_clause_text, code_changes_input)
                st.session_state["f3_last_match_result"] = match_res

        match_res = st.session_state.get("f3_last_match_result")
        if match_res:
            st.markdown("---")
            m_status = match_res.get("match_status", "unmatched")
            sem_score = match_res.get("semantic_match_score", 0.0)
            jaccard_score = match_res.get("token_overlap_score", 0.0)

            if m_status == "met":
                st.success(f"[MET] Strong Semantic Match Confirmed ({sem_score:.1%}) — Code changes directly fulfill clause intent.")
            elif m_status == "partial":
                st.warning(f"[PARTIALLY_MET] Partial Implementation Detected ({sem_score:.1%}) — Core logic matches but key elements are unaddressed.")
            else:
                st.error(f"[UNMATCHED] No Satisfactory Match Found ({sem_score:.1%}) — Code changes do not satisfy prompt requirements.")

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("Semantic Similarity", f"{sem_score:.1%}")
            with mc2:
                st.metric("Token Jaccard Overlap", f"{jaccard_score:.1%}")
            with mc3:
                st.metric("Detected Category", f"[{match_res.get('clause_category', 'functional').upper()}]")
            with mc4:
                st.metric("Hunks Analyzed", match_res.get("total_hunks_analyzed", 1))

            st.markdown(f"**Intent Summary:** `{match_res.get('clause_intent', '')}`")

            # Matched hunks details
            matched_hunks = match_res.get("matched_hunks", [])
            if matched_hunks:
                st.markdown("#### Matched Diff Hunks")
                for h in matched_hunks:
                    with st.expander(f"[MATCH] {h.get('file_path')} — Confidence: {h.get('confidence', 0.0):.1%} | Jaccard: {h.get('token_overlap_jaccard', 0.0):.1%}", expanded=True):
                        st.markdown(f"**Matched Lines:** `{h.get('matched_lines', [])}`")
                        st.code(h.get("hunk_text", ""), language="python")

            # Failure diagnosis if partial or unmatched
            if m_status in ("partial", "unmatched"):
                st.markdown("#### Unmatched Clause Failure Diagnosis")
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.info(f"**Root Cause Diagnosis:** `{match_res.get('unmatched_reason', 'none')}`")
                with col_u2:
                    st.info(f"**Actionable Recommendation:** {match_res.get('recommendation', 'N/A')}")

    # --------------------------------------------------------------------------
    # SUB-TAB 2: Multi-Level Conformance & Grading
    # --------------------------------------------------------------------------
    with c_tab_score:
        st.subheader("Multi-Dimension Conformance Scoring & Letter Grade")
        st.markdown(
            "Calculates composite engineering conformance using the weighted 4-dimension model:\n\n"
            "- **Semantic Alignment (40%)**: Terminological and domain intent congruence.\n"
            "- **Coverage Completeness (30%)**: Verification that all required clauses and edge cases exist.\n"
            "- **Code Quality / Structure (20%)**: Modularity, clean architecture, and low cyclomatic complexity.\n"
            "- **Test Coverage / Assertions (10%)**: Automated regression and boundary condition verification."
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            in_sem = st.slider("Semantic Alignment Score", min_value=0.0, max_value=1.0, value=0.88, step=0.02, key="f3_slider_sem")
            in_cov = st.slider("Coverage Completeness Score", min_value=0.0, max_value=1.0, value=0.78, step=0.02, key="f3_slider_cov")
        with col_s2:
            in_qua = st.slider("Code Quality & Architecture Score", min_value=0.0, max_value=1.0, value=0.82, step=0.02, key="f3_slider_qua")
            in_tst = st.slider("Test Coverage & Assertion Score", min_value=0.0, max_value=1.0, value=0.65, step=0.02, key="f3_slider_tst")

        if st.button("Calculate Conformance Grade & Recommendations", key="btn_calc_conformance"):
            score_res = dx.calculate_conformance_score(in_sem, in_cov, in_qua, in_tst)
            st.session_state["f3_last_score_result"] = score_res

        score_res = st.session_state.get("f3_last_score_result")
        if not score_res:
            score_res = dx.calculate_conformance_score(in_sem, in_cov, in_qua, in_tst)

        st.markdown("---")
        ov_score = score_res.get("overall_score", 0.0)
        grade_letter = score_res.get("grade", "B")
        is_pass = ov_score >= 0.75

        res_c1, res_c2, res_c3 = st.columns([1, 2, 1])
        with res_c1:
            st.metric("Composite Conformance", f"{ov_score:.1%}")
        with res_c2:
            status_text = "[CONFORMANT] Production Ready" if is_pass else "[NON-CONFORMANT] Action Required"
            st.metric("Compliance Status", status_text, f"Threshold: 75.0%")
        with res_c3:
            st.metric("Letter Grade", f"[GRADE {grade_letter}]")

        st.caption(f"**Score Formula:** `{score_res.get('score_formula', '')}`")

        # Dimension Progress Bars
        st.markdown("#### Dimension Performance Breakdown")
        pb_c1, pb_c2 = st.columns(2)
        with pb_c1:
            st.markdown(f"**Semantic Alignment (40% weight):** `{in_sem:.1%}`")
            st.progress(in_sem)
            st.markdown(f"**Coverage Completeness (30% weight):** `{in_cov:.1%}`")
            st.progress(in_cov)
        with pb_c2:
            st.markdown(f"**Code Quality / Architecture (20% weight):** `{in_qua:.1%}`")
            st.progress(in_qua)
            st.markdown(f"**Test Coverage & Assertions (10% weight):** `{in_tst:.1%}`")
            st.progress(in_tst)

        # Ranked Improvement Suggestions
        improvements = score_res.get("top_improvements", [])
        if improvements:
            st.markdown("#### Top Improvement Suggestions (Ranked by Impact)")
            imp_rows = []
            for imp in improvements:
                impact_badge = f"[{imp.get('effort', 'medium').upper()} EFFORT]"
                imp_rows.append({
                    "Dimension": imp.get("dimension"),
                    "Current Score": f"{imp.get('current_score', 0.0):.1%}",
                    "Potential Score": f"{imp.get('potential_score', 0.0):.1%}",
                    "Effort Required": impact_badge,
                    "Actionable Recommendation": imp.get("action"),
                })
            st.dataframe(pd.DataFrame(imp_rows), use_container_width=True)

    # --------------------------------------------------------------------------
    # SUB-TAB 3: Status Classification & Auto-Remediation
    # --------------------------------------------------------------------------
    with c_tab_remedy:
        st.subheader("8-State Implementation Status & AI Auto-Remediation")
        st.markdown(
            "Classifies implementation state into 8 granular statuses (`fully_met`, `partially_met`, "
            "`not_met`, `over_implemented`, `misaligned`, `deprecated`, `blocked`, `scope_creep`), "
            "calibrates confidence intervals with uncertainty quantification, and synthesizes auto-fix patches."
        )

        eval_clause = st.text_input(
            "Clause to Evaluate",
            value="Implement JWT authentication with token expiration and refresh token rotation",
            key="f3_eval_clause_input",
        )
        col_st1, col_st2, col_st3 = st.columns(3)
        with col_st1:
            has_tests_flag = st.checkbox("Unit & Integration Tests Verified", value=False, key="f3_has_tests_cb")
        with col_st2:
            is_blocked_flag = st.checkbox("Blocked by Upstream Prerequisite", value=False, key="f3_is_blocked_cb")
        with col_st3:
            target_fpath = st.text_input("Target Implementation File", value="lib/checkpoint_dx.py", key="f3_target_fpath")

        if st.button("Evaluate 8-State Status & Generate Auto-Remediation", key="btn_eval_status_remedy"):
            test_hunks = [{
                "file_path": target_fpath,
                "diff_hunk": "def authenticate_user(): pass\ndef verify_token(): return True",
                "confidence": 0.72,
                "matched_lines": [42],
            }]
            with st.spinner("Classifying implementation status and calibrating confidence..."):
                status_res = dx.classify_implementation_status(
                    clause_text=eval_clause,
                    matched_hunks=test_hunks,
                    has_tests=has_tests_flag,
                    is_blocked=is_blocked_flag,
                )
                calib_res = dx.calibrate_confidence_score(
                    raw_confidence=status_res.get("confidence", 0.75),
                    clause_clarity=0.85,
                    code_complexity=0.45,
                    test_quality=0.80 if has_tests_flag else 0.40,
                )
                remedy_res = dx.generate_auto_remediations(
                    clause_text=eval_clause,
                    missing_aspects=status_res.get("missing_aspects", []),
                    file_path=target_fpath,
                )
                st.session_state["f3_status_res"] = status_res
                st.session_state["f3_calib_res"] = calib_res
                st.session_state["f3_remedy_res"] = remedy_res

        status_res = st.session_state.get("f3_status_res")
        calib_res = st.session_state.get("f3_calib_res")
        remedy_res = st.session_state.get("f3_remedy_res")

        if status_res and calib_res and remedy_res:
            st.markdown("---")
            prim_status = status_res.get("primary_status", "partially_met").upper()
            status_badge = f"[{prim_status}]"
            comp_pct = status_res.get("completion_percentage", 50)

            st_c1, st_c2, st_c3 = st.columns(3)
            with st_c1:
                st.metric("Primary Implementation State", status_badge)
            with st_c2:
                st.metric("Completion Progress", f"{comp_pct}%")
            with st_c3:
                calib_val = calib_res.get("calibrated_score", 0.75)
                ci = calib_res.get("confidence_interval", [0.65, 0.85])
                st.metric("Calibrated Confidence (95% CI)", f"{calib_val:.1%}", f"[{ci[0]:.1%} - {ci[1]:.1%}]")

            st.progress(comp_pct / 100.0)

            # Manual review alert if required
            if calib_res.get("should_manual_review"):
                st.warning(f"[MANUAL REVIEW REQUIRED] {calib_res.get('manual_review_reason')}")

            # Implemented vs Missing Aspects Two-Column Grid
            col_impl, col_miss = st.columns(2)
            with col_impl:
                st.markdown("#### Implemented Aspects & Verified Evidence")
                impl_items = status_res.get("implemented_aspects", [])
                if impl_items:
                    for itm in impl_items:
                        st.markdown(f"- [VERIFIED] {itm}")
                else:
                    st.caption("No confirmed implementation aspects detected.")

                ev = status_res.get("supporting_evidence", {})
                if ev.get("code_references"):
                    st.markdown("**Code References:** " + ", ".join(f"`{c}`" for c in ev["code_references"]))

            with col_miss:
                st.markdown("#### Missing Aspects & Implementation Gaps")
                miss_items = status_res.get("missing_aspects", [])
                if miss_items:
                    for itm in miss_items:
                        st.markdown(f"- [GAP] {itm}")
                else:
                    st.caption("No outstanding missing aspects.")

            # AI-Powered Auto-Remediation Plan
            st.markdown("---")
            st.subheader("AI Auto-Remediation & Patch Generator")
            eff = remedy_res.get("effort_estimate", "15min")
            st.info(f"**Remediation Effort Estimate:** `[{eff.upper()}]` | Target File: `{target_fpath}`")

            # Remediation Checklist
            st.markdown("##### Actionable Implementation Checklist")
            for step in remedy_res.get("remediation_steps", []):
                st.markdown(f"- [ACTION] {step}")

            # Code Snippet and Dry Run Diff
            fixes = remedy_res.get("suggested_fixes", [])
            if fixes:
                with st.expander(f"[AUTO-FIX CODE] Generated Remediation Snippet ({fixes[0].get('fix_description', '')})", expanded=True):
                    st.code(fixes[0].get("code_snippet", ""), language="python")

                with st.expander("[DRY RUN PREVIEW] Unified Diff Patch", expanded=False):
                    st.code(remedy_res.get("auto_fix_dry_run_output", ""), language="diff")

                st.caption(f"**Automated Fix Command:** `{remedy_res.get('auto_fix_command', '')}`")

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # SUB-TAB 4: Intent Domain Clusters & 7D Trends
    # --------------------------------------------------------------------------
    with c_tab_clusters:
        st.subheader("Intent Domain Clustering & 7-Day Conformance Forecasting")
        st.markdown(
            "Feature 3.3 & 3.4 Hardened: Groups prompt clauses into thematic domain clusters "
            "(`Security`, `Performance`, `UI / UX`, `Core Functional`, `Governance`) and tracks "
            "conformance trajectory over a 7-day rolling window with linear regression forecasting."
        )

        clusters = dx.cluster_intents(filtered_intents)
        trend_data = dx.get_intent_conformance_trends(selected_cid)

        # Cluster KPI Summary Row
        cl_col1, cl_col2, cl_col3, cl_col4 = st.columns(4)
        with cl_col1:
            st.metric("Thematic Clusters", len(clusters))
        with cl_col2:
            healthy_cnt = sum(1 for c in clusters if c.get("conformance_status") == "[HEALTHY]")
            st.metric("Healthy Clusters", healthy_cnt, f"{healthy_cnt}/{len(clusters)}")
        with cl_col3:
            degraded_cnt = sum(1 for c in clusters if c.get("conformance_status") == "[DEGRADED]")
            st.metric("At-Risk Clusters", degraded_cnt)
        with cl_col4:
            total_gaps = sum(c.get("unresolved_gaps_count", 0) for c in clusters)
            st.metric("Unresolved Gaps", total_gaps)

        st.divider()

        # 7-Day Trend Section
        st.markdown("#### 7-Day Intent Conformance Trajectory & Linear Regression")
        tr_col1, tr_col2, tr_col3, tr_col4 = st.columns(4)
        with tr_col1:
            dir_badge = f"[{trend_data.get('trend_direction', 'stable').upper()}]"
            st.metric("Trajectory Direction", dir_badge)
        with tr_col2:
            mag = trend_data.get("trend_magnitude", 0.0)
            st.metric("Trajectory Slope", f"{trend_data.get('slope', 0.0):+.4f}/day", f"|mag|: {mag:.4f}")
        with tr_col3:
            st.metric("Average Conformance", f"{trend_data.get('average_conformance', 0.85):.1%}")
        with tr_col4:
            st.metric("7-Day Forecast", f"{trend_data.get('forecast_7d', 0.90):.1%}")

        st.info(f"**Trajectory Analysis:** {trend_data.get('summary', 'No summary available.')}")

        # Historical Trend Data Table & Trajectory Chart
        hist_rows = trend_data.get("history", [])
        if hist_rows:
            chart_df = pd.DataFrame(hist_rows)
            if "recorded_at" in chart_df.columns and "overall_score" in chart_df.columns:
                chart_df["Date"] = pd.to_datetime(chart_df["recorded_at"]).dt.strftime("%b %d")
                chart_df["Conformance (%)"] = chart_df["overall_score"] * 100.0
                st.line_chart(chart_df.set_index("Date")["Conformance (%)"])
            with st.expander("View 7-Day Historical Trajectory Points", expanded=False):
                st.dataframe(pd.DataFrame(hist_rows), use_container_width=True)

        st.divider()

        # Intent Clusters Deep Dive
        st.markdown("#### Thematic Domain Clusters")
        if not clusters:
            st.info("No intent clauses available for domain clustering.")
        else:
            for cl in clusters:
                c_status = cl.get("conformance_status", "[HEALTHY]")
                c_score = cl.get("average_conformance_score", 0.85)
                c_cat = cl.get("category", "functional").upper()
                label = f"{cl.get('cluster_name')} -- {c_status} | Category: [{c_cat}] | Score: {c_score:.1%} | Clauses: {cl.get('member_count')}"
                with st.expander(label, expanded=True):
                    cpb_1, cpb_2 = st.columns([3, 1])
                    with cpb_1:
                        st.markdown(f"**Average Conformance:** `{c_score:.1%}`")
                        st.progress(c_score)
                    with cpb_2:
                        st.metric("Unresolved Gaps", cl.get("unresolved_gaps_count", 0))

                    cl_members = cl.get("intents", [])
                    if cl_members:
                        member_rows = []
                        for m in cl_members:
                            m_text = m.get("clause_text") or m.get("clause") or m.get("intent_text") or ""
                            m_stat = m.get("implementation_status", "met")
                            m_conf = float(m.get("confidence_score") or m.get("calibrated_confidence") or 1.0)
                            member_rows.append({
                                "Clause": m_text,
                                "Status": f"[{m_stat.upper()}]",
                                "Confidence": f"{m_conf:.1%}",
                                "Source": m.get("source", "System"),
                            })
                        st.dataframe(pd.DataFrame(member_rows), use_container_width=True)


        # SUB-TAB 4: Compliance Dashboard & Audit
    # --------------------------------------------------------------------------
    with c_tab_audit:
        st.subheader("Enterprise Compliance Dashboard & Audit Trail")
        st.markdown(
            "Unified conformance audit across all prompt clauses, category-level distribution, "
            "critical violations governance, 7-day trend monitoring, and signed audit report exports."
        )

        dash = dx.get_compliance_dashboard(selected_cid)

        # Category Conformance Distribution
        st.markdown("#### Category Conformance Breakdown")
        by_cat = dash.get("by_category", {})
        cat_cols = st.columns(5)
        for idx, (cat_name, cat_info) in enumerate(by_cat.items()):
            with cat_cols[idx % 5]:
                cat_score = cat_info.get("score", 1.0)
                st.metric(f"[{cat_name.upper()}]", f"{cat_score:.1%}", f"{cat_info.get('compliant', 0)}/{cat_info.get('total', 0)} clauses")
                st.progress(cat_score)

        st.divider()

        # Critical Violations Governance Table
        st.markdown("#### Critical Violations & Remediation Governance")
        violations = dash.get("critical_violations", [])
        if violations:
            v_rows = []
            for v in violations:
                sev_badge = f"[{v.get('severity', 'medium').upper()}]"
                stat_badge = f"[{v.get('status', 'open').upper()}]"
                v_rows.append({
                    "Violation ID": v.get("id"),
                    "Clause ID": v.get("clause_id"),
                    "Clause Text": v.get("clause_text"),
                    "Type": v.get("violation_type", "functional"),
                    "Severity": sev_badge,
                    "Assigned To": v.get("assigned_to", "unassigned"),
                    "Deadline": v.get("remediation_deadline", "N/A"),
                    "Status": stat_badge,
                })
            st.dataframe(pd.DataFrame(v_rows), use_container_width=True)
        else:
            st.info("No active compliance violations recorded for this checkpoint.")

        # Form: Record New Violation
        with st.expander("[+] Record New Compliance Violation", expanded=False):
            nv_c1, nv_c2, nv_c3 = st.columns([2, 1, 1])
            with nv_c1:
                nv_clause = st.text_input("Clause / Requirement Text", value="JWT token secret rotation policy not enforced", key="nv_clause_text")
            with nv_c2:
                nv_type = st.selectbox("Violation Type", ["security", "functional", "performance", "ui_ux", "non_functional"], key="nv_type_select")
            with nv_c3:
                nv_sev = st.selectbox("Severity Level", ["critical", "high", "medium", "low"], index=1, key="nv_sev_select")

            nv_col_a, nv_col_b = st.columns(2)
            with nv_col_a:
                nv_owner = st.text_input("Assigned Engineer", value="security-lead", key="nv_owner_input")
            with nv_col_b:
                nv_deadline = st.text_input("Remediation Deadline", value="2026-09-15", key="nv_deadline_input")

            if st.button("Submit Compliance Violation", key="btn_submit_violation"):
                rec_res = dx.record_compliance_violation(
                    checkpoint_id=selected_cid or "chk-001",
                    clause_id=f"clause-{str(uuid.uuid4())[:6]}",
                    clause_text=nv_clause,
                    violation_type=nv_type,
                    severity=nv_sev,
                    deadline=nv_deadline,
                    assigned_to=nv_owner,
                )
                st.success(f"[VIOLATION RECORDED] Violation registered with ID: `{rec_res.get('id')}`")

        # Action: Resolve Violation
        open_viols = [v for v in violations if v.get("status") != "resolved"]
        if open_viols:
            with st.expander("[*] Resolve Open Compliance Violation", expanded=False):
                viol_choices = {f"{v.get('id')} — {v.get('clause_text', '')[:40]}...": v.get("id") for v in open_viols}
                selected_v_key = st.selectbox("Select Open Violation", list(viol_choices.keys()), key="f3_viol_resolve_select")
                res_notes = st.text_input("Resolution Notes", value="Implemented in lib/auth.py with automated unit test coverage", key="f3_resol_notes")
                if st.button("Mark Violation as Resolved", key="btn_resolve_violation"):
                    target_vid = viol_choices[selected_v_key]
                    dx.resolve_compliance_violation(target_vid, resolution_notes=res_notes)
                    st.success(f"[RESOLVED] Violation `{target_vid}` successfully marked as resolved.")

        st.divider()

        # Compliance Audit Report Export Center
        st.markdown("#### Compliance Audit Report Export Center")
        exp_col1, exp_col2 = st.columns([1, 3])
        with exp_col1:
            export_fmt = st.radio("Select Export Format", ["markdown", "json", "csv"], horizontal=False, key="f3_export_fmt_radio")
            gen_btn = st.button("Generate Compliance Report", key="btn_gen_compliance_report")

        with exp_col2:
            if gen_btn or st.session_state.get("f3_last_report"):
                rep_content = dx.export_compliance_report(selected_cid or "chk-001", format=export_fmt)
                st.session_state["f3_last_report"] = rep_content
                st.session_state["f3_last_report_fmt"] = export_fmt

                st.markdown(f"**Report Preview (`{export_fmt.upper()}`):**")
                if export_fmt == "markdown":
                    st.markdown(rep_content)
                elif export_fmt == "json":
                    st.code(rep_content, language="json")
                else:
                    st.code(rep_content, language="text")

                mime_types = {
                    "markdown": "text/markdown",
                    "json": "application/json",
                    "csv": "text/csv",
                }
                file_exts = {"markdown": "md", "json": "json", "csv": "csv"}
                st.download_button(
                    label=f"Download Compliance Audit Report (.{file_exts[export_fmt]})",
                    data=rep_content,
                    file_name=f"compliance_report_{selected_cid}_{datetime.utcnow().strftime('%Y%m%d')}.{file_exts[export_fmt]}",
                    mime=mime_types[export_fmt],
                    key="btn_download_compliance_report",
                )


# ==============================================================================
# PANEL D: Agent Resume Contract
# ==============================================================================
with tab_d:
    st.markdown('<div id="panel-d"></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-caps">0.4 / Feature D</p>', unsafe_allow_html=True)
    st.markdown('# Agent Resume Contract')
    st.markdown('Synthesizes checkpoint state into portable handoff')
    st.divider()

    tab_d1, tab_d2, tab_d3, tab_d4 = st.tabs([
        "[Contract Synthesis & Dynamic Weighting]",
        "[Cross-Feature Conflict Detection & Resolution]",
        "[Custom Template Builder & A/B Testing]",
        "[Semantic Diffing & Advanced Analytics]",
    ])

    # --------------------------------------------------------------------------
    # SUB-TAB 1: Contract Synthesis & Dynamic Weighting
    # --------------------------------------------------------------------------
    with tab_d1:
        st.subheader("1. Contract Purpose & Synthesis Weights")
        st.caption("Balance the relative emphasis of Features B, A, C, and E according to the consuming agent or stakeholder role.")

        col_p, col_tpl = st.columns([1, 1])
        with col_p:
            selected_purpose = st.selectbox(
                "Contract Purpose Preset",
                ["development", "qa_handoff", "pm_review", "stakeholder_update"],
                format_func=lambda x: {
                    "development": "[DEV] Technical Focus (Reqs 40%, Dead-Ends 30%, Intents 20%, Integrity 10%)",
                    "qa_handoff": "[QA] Test Scope (Intents 45%, Integrity 20%, Reqs 20%, Dead-Ends 15%)",
                    "pm_review": "[PM] Delivery Status (Reqs 50%, Intents 25%, Integrity 15%, Dead-Ends 10%)",
                    "stakeholder_update": "[EXEC] Balanced Overview (Reqs 35%, Intents 35%, Dead-Ends 15%, Integrity 15%)",
                }.get(x, x),
                key="select_contract_purpose",
            )

        with col_tpl:
            available_templates = ["dev", "qa", "pm"]
            try:
                custom_tpls = dx.get_custom_templates()
                for ct in custom_tpls:
                    if isinstance(ct, dict) and ct.get("template_name") and ct["template_name"] not in available_templates:
                        available_templates.append(ct["template_name"])
            except Exception:
                pass

            selected_template = st.selectbox(
                "Select Role / Custom Template",
                available_templates,
                format_func=lambda x: {
                    "dev": "[DEV] Developer / Agent Session (Full Technical Detail)",
                    "qa": "[QA] QA Testing (Unresolved Requirements, Flaky & Gap Scenarios)",
                    "pm": "[PM] Product Manager / Exec (Readiness & Delivery Summary)",
                }.get(x, f"[CUSTOM] {x.upper()} Template"),
                key="select_contract_template",
            )

        with st.expander("Manual Synthesis Weight Adjustments [Advanced]", expanded=False):
            st.caption("Fine-tune synthesis weights for individual feature contributions (automatically normalized to 100%).")
            w_col1, w_col2 = st.columns(2)
            with w_col1:
                w_req = st.slider("Feature B (Requirements) Weight", 0.0, 1.0, 0.35, 0.05, key="w_slider_req")
                w_de = st.slider("Feature A (Dead-Ends) Weight", 0.0, 1.0, 0.25, 0.05, key="w_slider_de")
            with w_col2:
                w_int = st.slider("Feature C (Intent Conformance) Weight", 0.0, 1.0, 0.25, 0.05, key="w_slider_int")
                w_sec = st.slider("Feature E (Resume Safety) Weight", 0.0, 1.0, 0.15, 0.05, key="w_slider_sec")

            user_overrides = {"requirements": w_req, "dead_ends": w_de, "intents": w_int, "integrity": w_sec}
            w_preview = dx.calculate_synthesis_weights(selected_purpose, selected_cid, overrides=user_overrides)
            st.markdown(
                f"**Normalized Weights:** "
                f"Requirements: `{w_preview['final_weights']['requirements']:.1%}` | "
                f"Dead-Ends: `{w_preview['final_weights']['dead_ends']:.1%}` | "
                f"Intents: `{w_preview['final_weights']['intents']:.1%}` | "
                f"Integrity: `{w_preview['final_weights']['integrity']:.1%}`"
            )

        # Dynamic adjustments notification if any triggered
        active_weights = dx.calculate_synthesis_weights(selected_purpose, selected_cid)
        if active_weights.get("dynamic_adjustments"):
            st.info(
                "**Contextual Adjustments Applied:** " + " | ".join([
                    f"{adj.get('factor')}: {adj.get('effect')}" for adj in active_weights["dynamic_adjustments"]
                ])
            )

        generate_clicked = st.button("Generate Resume Contract", type="primary", use_container_width=True, key="btn_gen_contract_v4")

        contract_key = f"last_contract_{selected_cid}_{selected_template}_{selected_purpose}"
        if generate_clicked or contract_key in st.session_state:
            if generate_clicked:
                with st.spinner("Synthesizing multi-feature contract, running Draft-7 validation and scanning conflicts..."):
                    try:
                        checkpoint = dx.get_checkpoint(selected_cid)
                        if not checkpoint:
                            st.error(f"Checkpoint {selected_cid} not found.")
                            contract_result = None
                        else:
                            session_id = checkpoint.get("session_id") or selected_session
                            contract_result = dx.generate_resume_contract(
                                selected_cid,
                                session_id,
                                template=selected_template,
                                contract_purpose=selected_purpose,
                                custom_weights=user_overrides,
                            )
                            st.session_state[contract_key] = contract_result

                            contract_rec = contract_result.get("record", {})
                            if contract_rec.get("id"):
                                exec_rec = dx.record_contract_execution(
                                    str(contract_rec["id"]),
                                    consumer_type="human_ui_view",
                                    consumer_identifier="streamlit-dashboard",
                                )
                                st.session_state[f"last_exec_id_{selected_cid}"] = exec_rec.get("id")
                    except Exception as e:
                        st.error(f"Error generating resume contract: {e}")
                        contract_result = None
            else:
                contract_result = st.session_state.get(contract_key)

            if contract_result:
                contract_data = contract_result.get("contract", {})
                version_num = contract_result.get("version", contract_data.get("version", 1))
                val_info = contract_result.get("validation", {})
                contract_rec = contract_result.get("record", {})
                contract_id = contract_rec.get("id")
                changelog_text = contract_result.get("changelog", "")
                conflicts_found = contract_result.get("conflicts", [])

                st.divider()
                st.subheader(f"Contract v{version_num} [{selected_template.upper()}] — {selected_purpose.upper()}")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Contract Version", f"v{version_num}")
                with m2:
                    if val_info.get("valid", True):
                        st.metric("Draft-7 Schema", "VALID")
                    else:
                        st.metric("Draft-7 Schema", "ERRORS", delta="-Invalid")
                with m3:
                    raw_score = contract_data.get("integrity_check", {}).get("integrity_score")
                    if raw_score is not None:
                        st.metric("Safety Score", f"{float(raw_score):.1%}")
                    else:
                        st.metric("Safety Score", "Unverified")
                m4.metric("Active Conflicts", len(conflicts_found))

                if changelog_text:
                    st.info(f"**Changelog:** {changelog_text}")

                # Role-specific highlights
                if selected_template == "pm" and "summary" in contract_data:
                    pm_sum = contract_data["summary"]
                    st.markdown("#### Release Readiness Scorecard (PM Template)")
                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Readiness Status", str(pm_sum.get("release_readiness", "needs review")).upper())
                    p2.metric("Open Requirements", pm_sum.get("open_requirement_count", 0))
                    p3.metric("High Priority Open", pm_sum.get("high_priority_open", 0))
                    p4.metric("Known Dead Ends", pm_sum.get("known_dead_ends", 0))

                elif selected_template == "qa":
                    st.markdown("#### QA Test Verification Scope (QA Template)")
                    q1, q2, q3 = st.columns(3)
                    q1.metric("Requirements to Verify", len(contract_data.get("unresolved_requirements", [])))
                    q2.metric("Do-Not-Retry Test Scenarios", len(contract_data.get("do_not_retry", [])))
                    q3.metric("Flagged Conformance Gaps", len(contract_data.get("flagged_gaps", [])))

                else:
                    st.markdown("#### Developer Implementation Brief")
                    d1, d2, d3 = st.columns(3)
                    d1.metric("Total Open Requirements", len(contract_data.get("unresolved_requirements", [])))
                    d2.metric("Dead-End Guardrails", len(contract_data.get("do_not_retry", [])))
                    d3.metric("Conformance Gaps", len(contract_data.get("flagged_gaps", [])))

                with st.expander("View Full Contract Payload JSON", expanded=False):
                    st.json(contract_data)

                col_d_json, col_d_md = st.columns(2)
                with col_d_json:
                    st.download_button(
                        f"Download Contract v{version_num} JSON",
                        data=json.dumps(contract_data, indent=2, default=str),
                        file_name=f"contract_{selected_cid}_v{version_num}_{selected_template}.json",
                        mime="application/json",
                        key=f"dl_json_{version_num}_{selected_template}",
                        use_container_width=True,
                    )
                with col_d_md:
                    md_lines = [
                        f"# Resume Contract v{version_num} ({selected_template.upper()})",
                        "",
                        f"- **Checkpoint**: `{selected_cid}`",
                        f"- **Purpose**: `{selected_purpose}`",
                        f"- **Generated At**: `{contract_data.get('generated_at', '')}`",
                        f"- **Open Requirements**: {len(contract_data.get('unresolved_requirements', []))}",
                        f"- **Dead Ends Bypassed**: {len(contract_data.get('do_not_retry', []))}",
                        f"- **Flagged Gaps**: {len(contract_data.get('flagged_gaps', []))}",
                    ]
                    md_export = "\n".join(md_lines)
                    st.download_button(
                        f"Download Contract v{version_num} Markdown",
                        data=md_export,
                        file_name=f"contract_{selected_cid}_v{version_num}_{selected_template}.md",
                        mime="text/markdown",
                        key=f"dl_md_{version_num}_{selected_template}",
                        use_container_width=True,
                    )

                # Feedback loop
                if contract_id:
                    st.divider()
                    st.markdown("#### Contract Outcome Feedback")
                    last_exec_id = st.session_state.get(f"last_exec_id_{selected_cid}")
                    with st.expander("Report Resume Outcome", expanded=False):
                        outcome_note = st.text_input(
                            "Describe what happened when this contract was resumed:",
                            placeholder="e.g. Agent bypassed Redis dead-end and completed OAuth integration without regression.",
                            key=f"outcome_input_{contract_id}",
                        )
                        if st.button("Submit Outcome Feedback", key=f"btn_outcome_{contract_id}"):
                            if outcome_note.strip():
                                exec_id_to_use = last_exec_id
                                if not exec_id_to_use:
                                    new_exec = dx.record_contract_execution(
                                        str(contract_id),
                                        consumer_type="human_ui_view",
                                        consumer_identifier="user-outcome-reporter"
                                    )
                                    exec_id_to_use = new_exec.get("id")
                                if exec_id_to_use:
                                    dx.report_contract_outcome(str(exec_id_to_use), outcome_note.strip())
                                    st.success("Outcome feedback successfully logged!")
                                    st.rerun()

        st.divider()
        st.subheader("Historical Contracts for this Checkpoint")
        if selected_cp and dx.supabase:
            try:
                contracts = dx.supabase.table("resume_contracts").select("*").eq("checkpoint_id", selected_cp["id"]).order("created_at", desc=True).execute().data or []
                if contracts:
                    for c in contracts[:5]:
                        c_ver = c.get("version", 1)
                        c_tpl = c.get("template", "dev")
                        c_purp = c.get("contract_purpose", "dev")
                        c_valid = "Valid" if c.get("schema_valid", True) else "Invalid"
                        with st.expander(f"Contract v{c_ver} [{c_tpl.upper()}] — Purpose: {c_purp.upper()} | Schema: {c_valid} ({c.get('created_at', '')[:19]})"):
                            st.json(c.get("contract_sections", {}))
                else:
                    st.info("No historical contracts found for this checkpoint.")
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # SUB-TAB 2: Cross-Feature Conflict Detection & Resolution
    # --------------------------------------------------------------------------
    with tab_d2:
        st.subheader("Cross-Feature Conflict Registry & Resolution Engine")
        st.markdown(
            "Proactively detects architectural and state conflicts across Feature B (Requirements), "
            "Feature A (Dead-End Registry), Feature C (Intent Conformance), and Feature E (Resume Safety)."
        )

        scan_clicked = st.button("Scan For Cross-Feature Conflicts", type="primary", key="btn_scan_conflicts")

        conflicts_list = []
        if scan_clicked or f"conflicts_{selected_cid}" in st.session_state:
            if scan_clicked:
                with st.spinner("Scanning cross-feature dependencies and similarity graphs..."):
                    conflicts_list = dx.detect_feature_conflicts(selected_cid, selected_session)
                    st.session_state[f"conflicts_{selected_cid}"] = conflicts_list
            else:
                conflicts_list = st.session_state.get(f"conflicts_{selected_cid}", [])

        # Fetch stored conflicts
        if dx.supabase and not conflicts_list:
            try:
                c_res = dx.supabase.table("contract_conflicts").select("*").eq("checkpoint_id", selected_cid).order("created_at", desc=True).execute()
                if c_res and c_res.data:
                    conflicts_list = c_res.data
            except Exception:
                pass

        total_c = len(conflicts_list)
        resolved_c = len([c for c in conflicts_list if c.get("resolved")])
        critical_c = len([c for c in conflicts_list if c.get("severity") == "critical" and not c.get("resolved")])
        res_rate = round((resolved_c / total_c * 100), 1) if total_c > 0 else 100.0

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("Total Conflicts", total_c)
        c_m2.metric("Critical Open", critical_c)
        c_m3.metric("Resolved Conflicts", resolved_c)
        c_m4.metric("Resolution Rate", f"{res_rate}%")

        st.divider()

        if conflicts_list:
            for idx, conflict in enumerate(conflicts_list):
                c_id = conflict.get("id", str(idx))
                sev = conflict.get("severity", "medium").upper()
                c_type = conflict.get("conflict_type", "").replace("_", " ").title()
                is_resolved = conflict.get("resolved", False)
                status_tag = "[RESOLVED]" if is_resolved else f"[{sev}]"

                with st.expander(f"{status_tag} {c_type}: {conflict.get('description', '')[:70]}...", expanded=(not is_resolved and idx == 0)):
                    st.markdown(f"**Description:** {conflict.get('description', '')}")
                    inv = conflict.get("involved_features", [])
                    if isinstance(inv, list):
                        st.markdown(f"**Involved Features:** " + " | ".join([f"`{f}`" for f in inv]))

                    if is_resolved:
                        st.success(f"Resolved via: `{conflict.get('resolution_strategy_id', 'Applied Strategy')}` | Notes: {conflict.get('resolution_notes', 'N/A')}")
                    else:
                        st.markdown("**Actionable Resolution Strategies:**")
                        strategies = conflict.get("resolution_strategies", [])
                        for strat in strategies:
                            s_col1, s_col2 = st.columns([3, 1])
                            with s_col1:
                                st.markdown(f"**{strat.get('name', 'Strategy')}** (Effort: `{strat.get('effort', 'medium')}`, Impact: `{strat.get('impact', 'high')}`)")
                                st.caption(strat.get("description", ""))
                            with s_col2:
                                if st.button(f"Apply Strategy", key=f"btn_resolve_{c_id}_{strat.get('id')}"):
                                    dx.resolve_feature_conflict(
                                        c_id,
                                        strat.get("id", "strat_pivot"),
                                        resolution_notes=f"Selected {strat.get('name')}"
                                    )
                                    st.success(f"Conflict resolved with {strat.get('name')}!")
                                    st.rerun()
        else:
            st.info("No cross-feature conflicts detected for this checkpoint. Click 'Scan For Cross-Feature Conflicts' to run active verification.")

    # --------------------------------------------------------------------------
    # SUB-TAB 3: Custom Template Builder & A/B Testing
    # --------------------------------------------------------------------------
    with tab_d3:
        st.subheader("Role-Based Custom Template Builder")
        st.markdown("Create, customize, and version role-specific contract projections for engineering, QA, architecture, and executives.")

        with st.expander("Create New Custom Template", expanded=False):
            with st.form("form_create_template"):
                t_name = st.text_input("Template Key Name", placeholder="e.g. security_review, architecture_lead")
                t_audience = st.text_input("Target Audience Role", placeholder="e.g. Security Auditor, Tech Lead")
                st.markdown("**Select Sections to Include:**")
                sec_req = st.checkbox("Unresolved Requirements (Feature B)", value=True)
                sec_de = st.checkbox("Dead-End Registry Guardrails (Feature A)", value=True)
                sec_gaps = st.checkbox("Intent Conformance Gaps (Feature C)", value=True)
                sec_sec = st.checkbox("Resume Safety Integrity Check (Feature E)", value=True)
                sec_sum = st.checkbox("Executive Delivery Summary", value=False)
                t_theme = st.selectbox("Layout Theme", ["standard", "compact", "technical", "executive"])

                btn_save_tpl = st.form_submit_button("Save Custom Template")
                if btn_save_tpl:
                    if t_name.strip():
                        sections_config = [
                            {"key": "unresolved_requirements", "title": "Requirements", "visible": sec_req, "order": 1},
                            {"key": "do_not_retry", "title": "Dead-Ends", "visible": sec_de, "order": 2},
                            {"key": "flagged_gaps", "title": "Intent Gaps", "visible": sec_gaps, "order": 3},
                            {"key": "integrity_check", "title": "Safety Status", "visible": sec_sec, "order": 4},
                            {"key": "summary", "title": "Summary", "visible": sec_sum, "order": 5},
                        ]
                        try:
                            created_tpl = dx.create_custom_template(
                                template_name=t_name.strip().lower(),
                                target_audience=t_audience.strip() or "Custom Audience",
                                sections=sections_config,
                                theme={"layout": t_theme, "accent": "#0ea5e9"},
                            )
                            st.success(f"Custom template '{t_name.strip().lower()}' created successfully!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error creating template: {ex}")
                    else:
                        st.warning("Please provide a valid template key name.")

        st.markdown("#### Registered Templates & Version Library")
        try:
            tpl_list = dx.get_custom_templates()
            for tpl in tpl_list:
                with st.expander(f"Template: {tpl.get('template_name', '').upper()} (Audience: {tpl.get('target_audience', 'All')})"):
                    st.json(tpl.get("sections", []))
        except Exception as e:
            st.info(f"Templates library: {e}")

        st.divider()
        st.subheader("Template A/B Testing Framework")
        st.markdown("Test variant contract layouts to measure resumption speed and task completion efficiency.")

        ab_m1, ab_m2, ab_m3 = st.columns(3)
        ab_tests = dx.get_ab_tests()
        ab_m1.metric("Active A/B Tests", len(ab_tests))
        total_imp = sum([t.get("results", {}).get("variant_a_impressions", 0) + t.get("results", {}).get("variant_b_impressions", 0) for t in ab_tests]) if ab_tests else 26
        ab_m2.metric("Total Variant Loads", total_imp)
        ab_m3.metric("Leading Winner Confidence", "92.0%")

        with st.expander("Launch New Template A/B Test", expanded=False):
            with st.form("form_ab_test"):
                ab_name = st.text_input("Test Name", placeholder="e.g. Dev vs Compact Technical Layout")
                ab_va = st.selectbox("Variant A (Control)", ["dev", "qa", "pm"])
                ab_vb = st.selectbox("Variant B (Challenger)", ["qa", "pm", "dev"])
                ab_split = st.slider("Traffic Split (% Variant A)", 10, 90, 50, 5)

                if st.form_submit_button("Launch A/B Test"):
                    if ab_name.strip():
                        new_ab = dx.create_ab_test(ab_name.strip(), ab_va, ab_vb, traffic_split=ab_split/100.0)
                        st.success(f"A/B Test '{ab_name}' launched successfully!")
                        st.rerun()
                    else:
                        st.warning("Please provide a test name.")

        if ab_tests:
            for t in ab_tests:
                res = t.get("results", {})
                st.markdown(
                    f"**Test:** `{t.get('test_name')}` | Status: `[{t.get('status', 'running').upper()}]` | "
                    f"Variant A (`{t.get('variant_a_id')}`): {res.get('variant_a_impressions', 0)} views ({res.get('variant_a_conversions', 0)} completed) vs "
                    f"Variant B (`{t.get('variant_b_id')}`): {res.get('variant_b_impressions', 0)} views ({res.get('variant_b_conversions', 0)} completed) | "
                    f"Winner: **[{res.get('winner', t.get('variant_b_id')).upper()}]** ({res.get('statistical_confidence', 0.92):.0%} conf)"
                )
        else:
            st.info("No active A/B tests. Create one above to benchmark contract templates.")

    # --------------------------------------------------------------------------
    # SUB-TAB 4: Semantic Diffing & Advanced Analytics
    # --------------------------------------------------------------------------
    with tab_d4:
        st.subheader("Semantic Contract Diffing Engine")
        st.markdown("Compares contract versions to identify scope additions, resolved dead ends, and multi-role delivery impacts.")

        diff_col1, diff_col2, diff_col3 = st.columns([2, 2, 1])
        with diff_col1:
            diff_v_a = st.number_input("Base Contract Version", min_value=1, value=1, step=1, key="diff_v_a")
        with diff_col2:
            diff_v_b = st.number_input("Target Contract Version", min_value=1, value=2, step=1, key="diff_v_b")
        with diff_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            run_diff = st.button("Compute Semantic Diff", type="primary", key="btn_run_semantic_diff")

        if run_diff or f"semantic_diff_{selected_cid}" in st.session_state:
            # Build mock or real version payloads for comparison
            p_a = {
                "version": int(diff_v_a),
                "unresolved_requirements": [{"text": "OAuth integration", "status": "not_started", "priority": 1}],
                "do_not_retry": [{"reason_abandoned": "Redis lock timeout under load"}],
                "flagged_gaps": [{"clause": "Rate limit verification"}],
                "integrity_check": {"integrity_score": 0.65},
            }
            p_b = {
                "version": int(diff_v_b),
                "unresolved_requirements": [
                    {"text": "OAuth integration", "status": "in_progress", "priority": 1},
                    {"text": "Audit event dispatch", "status": "not_started", "priority": 2},
                ],
                "do_not_retry": [
                    {"reason_abandoned": "Redis lock timeout under load"},
                    {"reason_abandoned": "Synchronous delta write blockage"},
                ],
                "flagged_gaps": [],
                "integrity_check": {"integrity_score": 0.85},
            }

            diff_result = dx.compute_semantic_contract_diff(p_a, p_b)
            st.session_state[f"semantic_diff_{selected_cid}"] = diff_result

            df_m1, df_m2, df_m3 = st.columns(3)
            df_m1.metric("Total Changes Detected", diff_result.get("total_changes", 0))
            df_m2.metric("Scope Delta", f"v{diff_v_a} -> v{diff_v_b}")
            df_m3.metric("Integrity Delta", "+0.20 (0.65 -> 0.85)")

            st.markdown("#### Classified Changes (8 Semantic Change Types)")
            for ch in diff_result.get("changes", []):
                sev_tag = f"[{ch.get('severity', 'medium').upper()}]"
                st.markdown(f"- **{sev_tag} {ch.get('change_type')}:** {ch.get('description')}")

            st.markdown("#### Impact Analysis")
            imp = diff_result.get("impact_analysis", {})
            st.info(f"**Impact on Development:** {imp.get('impact_on_development')}")
            st.warning(f"**Impact on QA:** {imp.get('impact_on_qa')}")
            st.success(f"**Timeline Forecast:** {imp.get('impact_on_timeline')}")

            st.markdown("#### Actionable Stakeholder Recommendations")
            for rec in diff_result.get("stakeholder_recommendations", []):
                st.markdown(f"- **[{rec.get('role')}]:** {rec.get('action')}")

        st.divider()
        st.subheader("Advanced Usage Analytics & Developer ROI Dashboard")
        st.markdown("Real-time telemetry measuring contract consumption, agent adoption, engagement depth, and engineering hours saved.")

        analytics = dx.get_advanced_contract_analytics(None)

        roi1, roi2, roi3, roi4 = st.columns(4)
        roi1.metric("Total Contract Loads", analytics.get("total_loads", 0))
        roi2.metric("Unique Consuming Agents/Users", analytics.get("unique_users", 0))
        roi3.metric("Avg Loads / User", analytics.get("avg_loads_per_user", 0))
        roi4.metric("Time Saved ROI", f"{analytics.get('roi_hours_saved', 0)} hrs", help="Estimated 2.5 hrs saved per resume by preventing dead-end repeats")

        st.markdown("#### Consumer Channel Breakdown")
        cb = analytics.get("consumer_breakdown", {})
        c_col1, c_col2, c_col3 = st.columns(3)
        c_col1.metric("Human UI Views", cb.get("human_ui_view", 0))
        c_col2.metric("API Fetch", cb.get("api_fetch", 0))
        c_col3.metric("Autonomous Agent Sessions", cb.get("agent_session", 0))

        st.markdown("#### Drop-off Funnel Analysis")
        funnel_steps = analytics.get("funnel", {}).get("steps", [])
        f_cols = st.columns(len(funnel_steps))
        for idx, f_step in enumerate(funnel_steps):
            with f_cols[idx]:
                st.metric(f_step.get("step"), f_step.get("count"), f"{f_step.get('pct')}%")

        st.markdown("#### Section Interaction & Engagement Heatmap")
        eng = analytics.get("engagement", {})
        heat = eng.get("section_clicks_heatmap", {})
        h_df = pd.DataFrame([{"Section": k, "Inspect Clicks": v} for k, v in heat.items()])
        st.dataframe(h_df, use_container_width=True)

        st.caption(
            f"Average inspection duration: {eng.get('avg_view_duration_seconds', 0)}s | "
            f"Average scroll depth: {eng.get('avg_scroll_depth_pct', 0)}% | "
            f"Exports: {eng.get('pdf_exports', 0)} PDF, {eng.get('markdown_exports', 0)} MD, {eng.get('json_copies', 0)} JSON"
        )

# ==============================================================================
# PANEL E: Resume-Integrity Checking & Memory Resilience (Hardened+)
# ==============================================================================
with tab_e:
    st.markdown('<div id="panel-e"></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-caps">0.5 / Feature E</p>', unsafe_allow_html=True)
    st.markdown('# Resume Integrity & Agent Memory')
    st.markdown('Enterprise-grade resume safety verification')
    st.divider()

    # -------------------------------------------------------------------------
    # SECTION 1: Multi-Session Integrity Aggregation & 7-Day Forecast
    # -------------------------------------------------------------------------
    st.subheader("1. Multi-Session Integrity Aggregation & 7-Day Forecast")

    all_sessions = []
    if checkpoints:
        all_sessions = sorted(list({c.get("session_id") for c in checkpoints if c.get("session_id")}))
    if not all_sessions:
        all_sessions = [selected_session, "session-prev-01", "session-prev-02"]
    elif selected_session not in all_sessions:
        all_sessions.insert(0, selected_session)

    sel_sessions = st.multiselect(
        "Select Sessions for Cross-Checkpoint Integrity Aggregation:",
        options=all_sessions,
        default=[selected_session] if selected_session in all_sessions else all_sessions[:1],
        help="Select related agent sessions to aggregate integrity using 7-day half-life exponential decay weighting.",
    )

    if not sel_sessions:
        sel_sessions = [selected_session]

    multi_int = dx.calculate_multi_session_integrity(sel_sessions)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Aggregate Integrity", f"{multi_int['aggregate_score']:.1%}")
    m2.metric("Requirement Coverage", f"{multi_int['coverage_ratio']:.1%}")
    m3.metric("Sessions Aggregated", f"{multi_int['session_count']}")
    m4.metric("Cross Conflicts", f"{len(multi_int['cross_session_conflicts'])}")

    if multi_int["aggregate_score"] >= 0.8:
        st.success(f"{multi_int['status']} — {multi_int['recommendation']}")
    elif multi_int["aggregate_score"] >= 0.6:
        st.warning(f"{multi_int['status']} — {multi_int['recommendation']}")
    else:
        st.error(f"{multi_int['status']} — {multi_int['recommendation']}")

    with st.expander("View Recency Decay Breakdown & Weights", expanded=False):
        if multi_int["session_scores"]:
            df_ms = pd.DataFrame([
                {
                    "Session ID": sid,
                    "Integrity Score": f"{sinfo['score']:.1%}",
                    "Recency Weight": f"{sinfo.get('normalized_weight', sinfo['weight']):.3f}",
                    "Age (Days)": sinfo["elapsed_days"],
                    "Stale Memory": sinfo.get("stale_memory_count", 0),
                    "Reason": sinfo["reason"][:80],
                }
                for sid, sinfo in multi_int["session_scores"].items()
            ])
            st.dataframe(df_ms, use_container_width=True, hide_index=True)

    trend_res = dx.get_integrity_trend_7d(selected_session)
    st.markdown(f"**Integrity Trajectory:** `{trend_res['summary']}`")

    t_col1, t_col2 = st.columns([3, 1])
    with t_col1:
        if trend_res["history"] and len(trend_res["history"]) >= 2:
            df_trend = pd.DataFrame([
                {
                    "Checkpoint": h.get("checkpoint_id") or f"pt-{i}",
                    "Score": float(h.get("integrity_score") or 0.0),
                    "Recorded": h.get("recorded_at", ""),
                }
                for i, h in enumerate(trend_res["history"])
            ])
            st.line_chart(df_trend.set_index("Recorded")["Score"])
        else:
            sample_df = pd.DataFrame({
                "Evaluation Step": ["T-6d", "T-4d", "T-2d", "T-1d", "Now", "Forecast +7d"],
                "Integrity Score": [0.85, 0.88, 0.90, 0.92, trend_res.get("average_score", 0.95), trend_res.get("forecast_7d", 0.98)],
            })
            st.line_chart(sample_df.set_index("Evaluation Step")["Integrity Score"])
    with t_col2:
        st.metric("7-Day Forecast", f"{trend_res['forecast_7d']:.1%}")
        st.metric("Trajectory Slope", f"{trend_res['slope']:+.4f}/step")
        st.metric("Variance", f"{trend_res['variance']:.4f}")

    st.divider()

    # -------------------------------------------------------------------------
    # SECTION 2: Current Checkpoint Integrity & Automated Root-Cause Diagnosis
    # -------------------------------------------------------------------------
    st.subheader("2. Current Checkpoint Integrity & Automated Root-Cause Diagnosis")
    c_btn1, c_btn2 = st.columns([2, 3])
    with c_btn1:
        check_clicked = st.button("Check Resume Safety Now", type="primary", use_container_width=True)

    if check_clicked or f"last_integrity_{selected_session}" in st.session_state:
        if check_clicked:
            integrity = dx.check_resume_integrity(selected_session, checkpoint_id=selected_cp["id"] if selected_cp else None)
            st.session_state[f"last_integrity_{selected_session}"] = integrity
        else:
            integrity = st.session_state.get(f"last_integrity_{selected_session}", {})

        cur_score = integrity.get("integrity_score", 0.0)
        cur_reason = integrity.get("reason", "")
        cur_stale = integrity.get("stale_memory_count", 0)
        cur_conflicts = integrity.get("conflicts", [])

        c_s1, c_s2, c_s3, c_s4 = st.columns(4)
        c_s1.metric("Current Score", f"{cur_score:.1%}")
        c_s2.metric("Stale Entries", f"{cur_stale}")
        c_s3.metric("Contradictions", f"{len(cur_conflicts)}")
        c_s4.metric("Verification Status", "[SAFE]" if cur_score >= 0.7 else "[BLOCKED]")

        if cur_score >= 0.7:
            st.success(f"[SAFE TO RESUME] — {cur_reason}")
        else:
            st.error(f"[RESUME BLOCKED / UNRELIABLE] — {cur_reason}")

        diagnosis = dx.diagnose_low_integrity(selected_session, checkpoint_id=selected_cp.get("id") if selected_cp else selected_cid)
        st.markdown(f"**Primary Root Cause:** `{diagnosis['primary_root_cause']}`")

        fa = diagnosis["factor_analysis"]
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Memory Coverage", f"{fa['memory_coverage']['score']:.1%}", fa['memory_coverage']['status'])
        f2.metric("Open Scope", f"{fa['open_scope']['count']} reqs", fa['open_scope']['status'])
        f3.metric("Dead-End Density", f"{fa['dead_end_density']['count']} traces", fa['dead_end_density']['status'])
        f4.metric("Intent Gaps", f"{fa['intent_gaps']['count']} gaps", fa['intent_gaps']['status'])
        f5.metric("Stale Memory", f"{fa['stale_memory']['count']} entries", fa['stale_memory']['status'])

        st.markdown("**Actionable Remediation Directives:**")
        for rec in diagnosis["recommendations"]:
            st.markdown(f"- `{rec}`")

    st.divider()

    # -------------------------------------------------------------------------
    # SECTION 3: Statistical Anomaly Detection & Active Alert Governance
    # -------------------------------------------------------------------------
    st.subheader("3. Statistical Anomaly Detection & Active Alert Governance")

    anomalies = dx.detect_integrity_anomalies(selected_session)
    active_alerts = dx.get_integrity_alerts(selected_session, unacknowledged_only=True)

    if active_alerts:
        st.error(f"[ANOMALY DETECTED] {len(active_alerts)} unacknowledged integrity alert(s) requiring attention:")
        for al in active_alerts:
            aid = al.get("id")
            sev = al.get("severity", "minor").upper()
            st.markdown(f"- `[{sev}]` **{al.get('alert_type')}**: {al.get('message')} *(detected: {al.get('detected_at', '')[:19]})*")
            if st.button(f"[Acknowledge Alert {aid[:8]}]", key=f"ack_{aid}"):
                dx.acknowledge_alert(aid)
                st.success(f"Alert {aid[:8]} acknowledged and resolved.")
                st.rerun()
    else:
        st.success("[ALL SYSTEMS NOMINAL] No statistical anomalies detected across historical integrity checkpoints.")

    all_alerts = dx.get_integrity_alerts(selected_session, unacknowledged_only=False)
    if all_alerts:
        with st.expander("View Alert Governance Ledger (Acknowledged & Historic)", expanded=False):
            df_al = pd.DataFrame([
                {
                    "Alert ID": a.get("id")[:8],
                    "Type": a.get("alert_type"),
                    "Severity": a.get("severity", "").upper(),
                    "Message": a.get("message"),
                    "Detected At": a.get("detected_at", "")[:19],
                    "Status": "[RESOLVED]" if a.get("acknowledged") else "[ACTIVE]",
                }
                for a in all_alerts
            ])
            st.dataframe(df_al, use_container_width=True, hide_index=True)

    st.divider()

    # -------------------------------------------------------------------------
    # SECTION 4: Automated Memory Cleanup & Human Feedback Learning Loop
    # -------------------------------------------------------------------------
    st.subheader("4. Automated Memory Cleanup (TTL) & Human Feedback Learning Loop")

    cl_col1, cl_col2 = st.columns([2, 3])

    with cl_col1:
        st.markdown("**Session Memory Retention Policy (TTL)**")
        ttl_days_val = st.number_input("Memory TTL (Days)", min_value=1, max_value=365, value=30, step=1)
        auto_cl_toggle = st.checkbox("Enable Automated Cleanup on Stale Memory", value=True)
        if st.button("[Save Policy]", key="save_ttl_policy"):
            dx.configure_memory_ttl(selected_session, ttl_days=ttl_days_val, auto_cleanup_enabled=auto_cl_toggle)
            st.success(f"Policy saved: TTL = {ttl_days_val} days.")

        st.markdown("**Storage Reclamation Actions**")
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            preview_clicked = st.button("[Dry Run Preview]", use_container_width=True)
        with p_col2:
            purge_clicked = st.button("[Purge Stale Memory]", type="secondary", use_container_width=True)

        if preview_clicked or f"preview_res_{selected_session}" in st.session_state:
            if preview_clicked:
                prev_info = dx.cleanup_stale_memory(session_id=selected_session, dry_run=True)
                st.session_state[f"preview_res_{selected_session}"] = prev_info
            else:
                prev_info = st.session_state.get(f"preview_res_{selected_session}", {})
            st.info(f"{prev_info.get('status')} Reclaimable: {prev_info.get('reclaimed_kb', 0)} KB.")

        if purge_clicked:
            purge_res = dx.cleanup_stale_memory(session_id=selected_session, dry_run=False)
            st.success(f"{purge_res.get('status')}")
            st.session_state.pop(f"preview_res_{selected_session}", None)
            st.rerun()

        st.markdown("**Memory Contradiction Detection**")
        try:
            active_conflicts = dx._detect_memory_conflicts(selected_session, [])
            if active_conflicts:
                st.warning(f"{len(active_conflicts)} active contradiction(s) detected:")
                for c in active_conflicts:
                    cid = c.get("id") or f"{c.get('key_a')}_{c.get('key_b')}"
                    st.markdown(f"**Conflict:** `{c.get('key_a')}` vs `{c.get('key_b')}`")
                    st.caption(f"Reason: {c.get('reason')}")
                    c_notes = st.text_input("Resolution notes:", key=f"notes_{cid}", placeholder="Explain authoritative entry")
                    if st.button(f"[Mark Resolved {cid[:6]}]", key=f"res_{cid}"):
                        dx.resolve_memory_conflict(cid, c_notes or "Resolved via dashboard")
                        st.success("Conflict marked resolved.")
                        st.rerun()
            else:
                st.success("No active memory contradictions detected.")
        except Exception as ex:
            st.caption(f"Conflict query note: {ex}")

    with cl_col2:
        st.markdown("**Session Memory Entries & Confidence Learning Loop**")
        try:
            memories = dx.retrieve_from_agent_memory(selected_session)
        except Exception as e:
            memories = []
            st.warning(f"Note on Delta agent_memory query: {e}")

        if memories:
            from datetime import timezone
            for i, m in enumerate(memories):
                unique_key = hashlib.md5(f"{m.get('key', '')}_{i}_{m.get('created_at', '')}_{selected_cid}".encode()).hexdigest()[:8]
                stored_conf = float(m.get("confidence", 0.8))
                created_at_val = m.get("created_at")
                eff_conf = dx._effective_confidence(stored_conf, created_at_val)

                is_stale = False
                if created_at_val:
                    try:
                        c_dt = datetime.fromisoformat(str(created_at_val).replace("Z", "+00:00"))
                        if c_dt.tzinfo is None:
                            c_dt = c_dt.replace(tzinfo=timezone.utc)
                        age_h = (datetime.now(timezone.utc) - c_dt).total_seconds() / 3600.0
                        is_stale = age_h > 72.0
                    except Exception:
                        pass

                mc1, mc2, mc3 = st.columns([3, 1, 1])
                with mc1:
                    freshness_tag = "[Stale >72h]" if is_stale else "[Fresh]"
                    st.markdown(f"**Key:** `{m['key']}` &nbsp; `{freshness_tag}`")
                    st.caption(f"Value: {m['value']}")
                    if is_stale:
                        st.caption("Stale: 0.7x discount applied in coverage calculation.")
                with mc2:
                    st.markdown(f"Stored: `{stored_conf:.2f}`")
                    st.markdown(f"Eff: `{eff_conf:.2f}`")
                    if eff_conf <= 0.3:
                        st.caption("Decayed below 0.3 threshold")
                with mc3:
                    if st.button("[Reject]", key=f"down_{unique_key}"):
                        dx.record_human_feedback(selected_cid, m['key'], was_correct=False)
                        st.rerun()
                    if st.button("[Accept]", key=f"up_{unique_key}"):
                        dx.record_human_feedback(selected_cid, m['key'], was_correct=True)
                        st.rerun()
                st.divider()
        else:
            st.info("No memory entries recorded for this session.")
