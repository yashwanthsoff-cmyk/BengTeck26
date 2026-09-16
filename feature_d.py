"""feature_d.py — Feature D (Nuclear): Agent Resume Contract
Synthesizes Feature B (Unfinished Requirements), Feature A (Dead-End Registry),
Feature C (Intent Gaps), and Feature E (Resume-Integrity Checking) into an
actionable JSON contract for subsequent agent sessions.
"""
import json
from datetime import datetime
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.checkpoint_dx import CheckpointDX


def _assemble_contract_payload(dx: "CheckpointDX", checkpoint_id: str, session_id: str):
    """Core synthesis logic for Feature D.
    Synthesizes Feature B (Unfinished Requirements), Feature A (Dead-End Registry),
    Feature C (Intent Gaps), and Feature E (Resume-Integrity Checking) into a raw payload.
    Returns: (contract_payload, checkpoint, failure_reason)
    """
    unresolved = []
    dead_ends = []
    gaps = []
    integrity = {"integrity_score": 0.5, "reason": "Integrity check unverified (backend cold start / degraded)"}
    failure_reason = None
    degraded_reasons = []
    checkpoint = None

    try:
        checkpoint = dx.get_checkpoint(checkpoint_id)
    except Exception as e:
        failure_reason = f"Checkpoint lookup failed: {e}"
        degraded_reasons.append(f"checkpoint lookup failed: {e}")

    # Feature B: Unresolved requirements (Supabase with Delta fallback)
    try:
        if dx.supabase and checkpoint and checkpoint.get("id"):
            try:
                res_req = dx.supabase.table("requirements").select("*") \
                    .eq("checkpoint_id", checkpoint["id"]).in_("status", ["not_started", "in_progress", "blocked"]).execute()
                data = getattr(res_req, "data", None)
                if isinstance(data, list):
                    unresolved = [x for x in data if isinstance(x, dict)]
            except Exception as e:
                unresolved = []
                degraded_reasons.append(f"requirements fetch failed: {e}")

        if not unresolved:
            try:
                req_rows = dx._run_sql(
                    f"SELECT requirement_text, status FROM {dx.catalog}.{dx.schema}.requirements "
                    f"WHERE checkpoint_id = :checkpoint_id AND status IN ('not_started', 'in_progress', 'blocked')",
                    parameters=[{"name": "checkpoint_id", "value": checkpoint_id, "type": "STRING"}],
                )
                if isinstance(req_rows, list):
                    unresolved = [{"requirement_text": str(r[0]), "status": str(r[1]), "priority": 3} for r in req_rows if isinstance(r, (list, tuple)) and len(r) >= 2]
            except Exception as ex:
                if not failure_reason:
                    failure_reason = f"Delta requirements query failed: {ex}"
                degraded_reasons.append(f"delta requirements query failed: {ex}")
    except Exception as e:
        if not failure_reason:
            failure_reason = f"Requirements processing failed: {e}"
        degraded_reasons.append(f"requirements processing failed: {e}")

    # Feature A: Dead ends (Supabase with Delta fallback)
    try:
        raw_des = dx.get_dead_ends(checkpoint_id)
        if isinstance(raw_des, list):
            dead_ends = [d for d in raw_des if isinstance(d, dict)]
    except Exception as e:
        dead_ends = []
        degraded_reasons.append(f"dead-end fetch failed: {e}")

    if not dead_ends:
        try:
            de_rows = dx._run_sql(
                f"SELECT root_cause, suggested_fix FROM {dx.catalog}.{dx.schema}.dead_end_traces_fallback WHERE checkpoint_id = :checkpoint_id",
                parameters=[{"name": "checkpoint_id", "value": checkpoint_id, "type": "STRING"}],
            )
            if isinstance(de_rows, list):
                dead_ends = [{"root_cause": str(r[0]), "suggested_fix": str(r[1]), "used_fallback": True} for r in de_rows if isinstance(r, (list, tuple)) and len(r) >= 2]
        except Exception as ex:
            if not failure_reason:
                failure_reason = f"Delta dead-ends query failed: {ex}"
            degraded_reasons.append(f"delta dead-ends query failed: {ex}")

    # Feature C: Flagged implementation gaps (Supabase with Delta fallback)
    try:
        if dx.supabase and checkpoint and checkpoint.get("id"):
            try:
                res_gaps = dx.supabase.table("intent_summaries").select("*") \
                    .eq("checkpoint_id", checkpoint["id"]).eq("implementation_status", "gap").execute()
                g_data = getattr(res_gaps, "data", None)
                if isinstance(g_data, list):
                    gaps = [g for g in g_data if isinstance(g, dict)]
            except Exception as e:
                gaps = []
                degraded_reasons.append(f"intent-gap fetch failed: {e}")

        if not gaps:
            try:
                gap_rows = dx._run_sql(
                    f"SELECT clause FROM {dx.catalog}.{dx.schema}.intent_conformance WHERE checkpoint_id = :checkpoint_id AND implementation_status = 'gap'",
                    parameters=[{"name": "checkpoint_id", "value": checkpoint_id, "type": "STRING"}],
                )
                if isinstance(gap_rows, list):
                    gaps = [{"intent_text": str(r[0])} for r in gap_rows if isinstance(r, (list, tuple)) and len(r) >= 1]
            except Exception as ex:
                if not failure_reason:
                    failure_reason = f"Delta intent conformance query failed: {ex}"
                degraded_reasons.append(f"delta intent conformance query failed: {ex}")
    except Exception as e:
        if not failure_reason:
            failure_reason = f"Intent gaps processing failed: {e}"
        degraded_reasons.append(f"intent gaps processing failed: {e}")

    # Feature E: Resume safety integrity check
    try:
        raw_int = dx.check_resume_integrity(session_id, checkpoint_id=checkpoint.get("id") if checkpoint else None)
        if isinstance(raw_int, dict):
            integrity = raw_int
        else:
            integrity = {"integrity_score": 0.5, "reason": "Integrity check unverified (backend cold start / degraded)"}
            degraded_reasons.append("integrity check returned non-dict")
    except Exception as ex:
        integrity = {"integrity_score": None, "reason": f"integrity check failed and could not be verified: {ex}"}
        degraded_reasons.append(f"integrity check failed: {ex}")
        if not failure_reason:
            failure_reason = f"Resume integrity check failed: {ex}"

    contract_payload = {
        "checkpoint_id": str(checkpoint_id),
        "session_id": str(session_id),
        "generated_at": datetime.now().isoformat(),
        "version": 1,
        "integrity_check": integrity,
        "unresolved_requirements": (lambda: [
            seen.add(norm_txt) or item
            for r in unresolved
            for txt in [str(r.get("requirement_text", "")).strip()]
            for norm_txt in [txt.lower().rstrip(".,;!").strip()]
            for item in [{
                "text": txt,
                "status": str(r.get("status", "not_started")),
                "priority": int(r["priority"]) if ("priority" in r and isinstance(r["priority"], (int, float))) else 3,
            }]
            if txt and norm_txt not in seen
        ])() if (seen := set()) is not None else [],
        "do_not_retry": (lambda: [
            seen_dnr.add(dnr_key) or item
            for d in dead_ends
            for r_ab in [str(d.get("root_cause", "")).strip() if d.get("root_cause") else None]
            for s_alt in [str(d.get("suggested_fix", "")).strip() if d.get("suggested_fix") else None]
            for dnr_key in [((r_ab or "").lower(), (s_alt or "").lower())]
            for item in [{
                "reason_abandoned": r_ab,
                "suggested_alternative": s_alt,
                "used_fallback_source": bool(d.get("used_fallback", False)),
            }]
            if dnr_key not in seen_dnr and (r_ab or s_alt)
        ])() if (seen_dnr := set()) is not None else [],
        "flagged_gaps": (lambda: [
            seen_gaps.add(g_key) or item
            for g in gaps
            for c_txt in [str(g.get("intent_text", "")).strip()]
            for g_key in [c_txt.lower()]
            for item in [{"clause": c_txt}]
            if c_txt and g_key not in seen_gaps
        ])() if (seen_gaps := set()) is not None else [],
        "degraded": len(degraded_reasons) > 0,
        "degraded_reasons": degraded_reasons,
        "failure_reason": str(failure_reason) if failure_reason else None,
    }

    return contract_payload, checkpoint, failure_reason


def generate_resume_contract(dx: "CheckpointDX", checkpoint_id: str, session_id: str, template: str = "dev") -> Dict:
    """Delegates directly to CheckpointDX.generate_resume_contract as the single source of truth."""
    return dx.generate_resume_contract(checkpoint_id, session_id, template=template)
