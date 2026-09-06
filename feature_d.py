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


def generate_resume_contract(dx: "CheckpointDX", checkpoint_id: str, session_id: str) -> Dict:
    checkpoint = dx.get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    # Feature B: Unresolved requirements (Supabase with Delta fallback)
    unresolved = []
    if dx.supabase and checkpoint.get("id"):
        try:
            unresolved = dx.supabase.table("requirements").select("*") \
                .eq("checkpoint_id", checkpoint["id"]).in_("status", ["not_started", "in_progress", "blocked"]).execute().data or []
        except Exception:
            unresolved = []

    if not unresolved:
        try:
            req_rows = dx._run_sql(
                f"SELECT requirement_text, status FROM {dx.catalog}.{dx.schema}.requirements "
                f"WHERE checkpoint_id = '{checkpoint_id}' AND status IN ('not_started', 'in_progress', 'blocked')"
            )
            unresolved = [{"requirement_text": r[0], "status": r[1], "priority": 3} for r in req_rows]
        except Exception:
            unresolved = []

    # Feature A: Dead ends (Supabase with Delta fallback)
    dead_ends = []
    try:
        dead_ends = dx.get_dead_ends(checkpoint_id)
    except Exception:
        dead_ends = []

    if not dead_ends:
        try:
            de_rows = dx._run_sql(
                f"SELECT root_cause, suggested_fix FROM {dx.catalog}.{dx.schema}.dead_end_traces_fallback WHERE checkpoint_id = '{checkpoint_id}'"
            )
            dead_ends = [{"root_cause": r[0], "suggested_fix": r[1], "used_fallback": True} for r in de_rows]
        except Exception:
            dead_ends = []

    # Feature C: Flagged implementation gaps (Supabase with Delta fallback)
    gaps = []
    if dx.supabase and checkpoint.get("id"):
        try:
            gaps = dx.supabase.table("intent_summaries").select("*") \
                .eq("checkpoint_id", checkpoint["id"]).eq("implementation_status", "gap").execute().data or []
        except Exception:
            gaps = []

    if not gaps:
        try:
            gap_rows = dx._run_sql(
                f"SELECT clause FROM {dx.catalog}.{dx.schema}.intent_conformance WHERE checkpoint_id = '{checkpoint_id}' AND implementation_status = 'gap'"
            )
            gaps = [{"intent_text": r[0]} for r in gap_rows]
        except Exception:
            gaps = []

    # Feature E: Resume safety integrity check
    integrity = dx.check_resume_integrity(session_id, checkpoint_id=checkpoint.get("id"))

    contract_payload = {
        "checkpoint_id": checkpoint_id,
        "session_id": session_id,
        "generated_at": datetime.now().isoformat(),
        "integrity_check": integrity,
        "unresolved_requirements": [
            {
                "text": r["requirement_text"],
                "status": r["status"],
                "priority": r.get("priority", 3),
            }
            for r in unresolved
        ],
        "do_not_retry": [
            {
                "reason_abandoned": d.get("root_cause"),
                "suggested_alternative": d.get("suggested_fix"),
                "used_fallback_source": d.get("used_fallback", False),
            }
            for d in dead_ends
        ],
        "flagged_gaps": [{"clause": g.get("intent_text")} for g in gaps],
    }

    record = {"checkpoint_id": checkpoint_id, "status": "generated"}
    if dx.supabase and checkpoint.get("id"):
        try:
            result = dx.supabase.table("resume_contracts").insert({
                "checkpoint_id": checkpoint["id"],
                "contract_text": json.dumps(contract_payload, indent=2),
                "contract_sections": contract_payload,
                "integrity_check_passed": integrity["integrity_score"] > 0.7,
                "integrity_check_details": integrity,
                "integrity_check_timestamp": datetime.now().isoformat(),
            }).execute()
            if result.data:
                record = result.data[0]
        except Exception:
            pass

    return {"contract": contract_payload, "record": record}
