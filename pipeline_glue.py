"""pipeline_glue.py — Pipeline Glue (Section 7.5)
Syncs checkpoints, requirements, dead-ends (deduped), and intents from Databricks into Supabase.
Writes memory entries into agent_memory and reconciles superseded requirements across Delta & Supabase.
Supports execution both within a Spark notebook and standalone via Databricks SQL API.
"""
from typing import TYPE_CHECKING
from lib.checkpoint_dx import DeadEnd, Intent

if TYPE_CHECKING:
    from lib.checkpoint_dx import CheckpointDX


def _query(spark, dx: "CheckpointDX", sql: str):
    """Executes SQL via Spark if available, otherwise falls back to Databricks SQL API."""
    if spark is not None:
        return spark.sql(sql).collect()
    else:
        # Fallback to Databricks SQL execution API
        class Row:
            def __init__(self, d):
                self.__dict__.update(d)
                self._d = d
            def __getattr__(self, name):
                return self._d.get(name)
            def __getitem__(self, name):
                return self._d.get(name)

        rows = dx._run_sql(sql)
        # Convert raw arrays to Row objects
        # Parse column names from simple SELECT queries
        col_part = sql.strip().split("FROM")[0].replace("SELECT", "").replace("DISTINCT", "").strip()
        cols = [c.strip().split()[-1].split(".")[-1] for c in col_part.split(",")]
        res = []
        for r in rows:
            d = {cols[idx]: r[idx] if idx < len(r) else None for idx in range(len(cols))}
            res.append(Row(d))
        return res


def sync_checkpoints_from_databricks(dx: "CheckpointDX", spark, project_name: str) -> int:
    """Syncs normalized checkpoints from Databricks into Supabase."""
    sql = "SELECT DISTINCT checkpoint_id, session_id, branch FROM checkpoint_dx.checkpoints.checkpoints_normalized"
    rows = _query(spark, dx, sql)
    created = 0
    for r in rows:
        if not dx.get_checkpoint(r.checkpoint_id):
            dx.create_checkpoint(
                checkpoint_id=r.checkpoint_id,
                session_id=r.session_id,
                project_name=project_name,
                branch_name=r.branch,
            )
            created += 1
    return created


def sync_extracted_data_to_supabase(dx: "CheckpointDX", spark):
    """Syncs requirements, dead ends (deduped), and intent conformance into Supabase & Delta memory."""
    # 1. Sync Requirements
    req_sql = "SELECT checkpoint_id, session_id, requirement_text FROM checkpoint_dx.checkpoints.requirements"
    new_requirements = _query(spark, dx, req_sql)
    for r in new_requirements:
        checkpoint = dx.get_checkpoint(r.checkpoint_id)
        if not checkpoint:
            continue
        existing = dx.supabase.table("requirements").select("id") \
            .eq("checkpoint_id", checkpoint["id"]).eq("requirement_text", r.requirement_text).execute().data
        if not existing:
            inserted = dx.supabase.table("requirements").insert({
                "checkpoint_id": checkpoint["id"],
                "requirement_text": r.requirement_text,
                "source": "agent_extracted",
            }).execute()
            dx.store_in_agent_memory(
                checkpoint_id=r.checkpoint_id,
                session_id=r.session_id,
                key=r.requirement_text,
                value=f"Requirement extracted from checkpoint {r.checkpoint_id}",
                confidence=0.6,
                source="pipeline_extraction",
            )
            # Gap 1/3/4 fix: enrich every newly-synced requirement
            if inserted.data:
                try:
                    dx.enrich_requirement(
                        requirement_id=inserted.data[0]["id"],
                        requirement_text=r.requirement_text,
                    )
                except Exception as e:
                    logger.warning(f"Requirement enrichment note: {e}")

    # Gap 2 fix: run dependency detection once per checkpoint across all its requirements
    checkpoint_ids_this_batch = list({r.checkpoint_id for r in new_requirements})
    for cp_id in checkpoint_ids_this_batch:
        checkpoint = dx.get_checkpoint(cp_id)
        if not checkpoint:
            continue
        try:
            all_reqs = dx.supabase.table("requirements").select("id, requirement_text") \
                .eq("checkpoint_id", checkpoint["id"]).execute().data
            if all_reqs and len(all_reqs) >= 2:
                edges = dx.detect_requirement_dependencies(all_reqs)
                for edge in edges:
                    try:
                        dx.add_requirement_dependency(**edge)
                    except Exception as e:
                        logger.warning(f"Error saving requirement dependency: {e}")
        except Exception as e:
            logger.warning(f"Dependency detection note: {e}")

    # 2. Sync Dead Ends (with dedup and Groq upgrade)
    deadend_sql = "SELECT checkpoint_id, transcript FROM checkpoint_dx.checkpoints.deadend_candidates"
    new_deadends = _query(spark, dx, deadend_sql)
    for d in new_deadends:
        checkpoint = dx.get_checkpoint(d.checkpoint_id)
        if not checkpoint:
            continue
        transcript = d.transcript or ""
        detections = dx.detect_dead_ends(transcript)
        candidates = detections if detections else [{
            "dead_end_type": "unknown",
            "root_cause": transcript[:280] if transcript else "Unknown dead end",
            "suggested_fix": "",
            "confidence": 0.5,
        }]
        for det in candidates:
            root_cause = det.get("root_cause", transcript[:280])
            # Dedup fix — prevents re-logging on subsequent pipeline runs
            existing = dx.supabase.table("dead_end_summaries").select("id") \
                .eq("checkpoint_id", checkpoint["id"]).eq("root_cause", root_cause).execute().data
            if existing:
                continue
            severity = det.get("severity") or dx._score_severity_rule_based(det.get("dead_end_type", "unknown"), 1)
            dx.log_dead_end(DeadEnd(
                checkpoint_id=d.checkpoint_id,
                dead_end_type=det.get("dead_end_type", "unknown"),
                root_cause=root_cause,
                suggested_fix=det.get("suggested_fix", ""),
                confidence_score=float(det.get("confidence", 0.5)),
                failed_attempts=1,
                severity=severity,
            ))

    # 3. Sync Intent Conformance
    intent_sql = "SELECT checkpoint_id, clause, implementation_status, confidence_score FROM checkpoint_dx.checkpoints.intent_conformance"
    new_intents = _query(spark, dx, intent_sql)
    for i in new_intents:
        checkpoint = dx.get_checkpoint(i.checkpoint_id)
        if not checkpoint:
            continue
        existing = dx.supabase.table("intent_summaries").select("id") \
            .eq("checkpoint_id", checkpoint["id"]).eq("intent_text", i.clause).execute().data
        if not existing:
            dx.log_intent(Intent(
                checkpoint_id=i.checkpoint_id,
                intent_text=i.clause,
                implementation_status=i.implementation_status,
                confidence_score=float(i.confidence_score or 0.5),
            ))


def reconcile_superseded_requirements(dx: "CheckpointDX", spark, session_id: str):
    """Detects prompts indicating abandoned/superseded tasks and marks them superseded in Supabase AND Delta."""
    prompt_sql = f"""
        SELECT prompt_text FROM checkpoint_dx.checkpoints.checkpoints_normalized
        WHERE session_id = '{session_id}' ORDER BY timestamp ASC
    """
    prompt_rows = _query(spark, dx, prompt_sql)
    all_prompts_in_order = [row.prompt_text for row in prompt_rows if row.prompt_text]

    chk_sql = f"SELECT DISTINCT checkpoint_id FROM checkpoint_dx.checkpoints.checkpoints_normalized WHERE session_id = '{session_id}'"
    checkpoint_ids = [row.checkpoint_id for row in _query(spark, dx, chk_sql)]

    cancel_phrases = ["skip", "out of scope", "never mind", "don't need", "cancel", "no longer"]
    for checkpoint_id in checkpoint_ids:
        checkpoint = dx.get_checkpoint(checkpoint_id)
        open_reqs = []
        if checkpoint and dx.supabase:
            try:
                open_reqs = dx.supabase.table("requirements").select("*").eq("checkpoint_id", checkpoint["id"]) \
                    .in_("status", ["not_started", "in_progress"]).execute().data or []
            except Exception:
                open_reqs = []

        # If Supabase has no records or is uninitialized, read open reqs directly from Delta
        if not open_reqs:
            delta_req_rows = _query(spark, dx, f"SELECT requirement_text FROM checkpoint_dx.checkpoints.requirements WHERE checkpoint_id = '{checkpoint_id}' AND status IN ('not_started', 'in_progress')")
            open_reqs = [{"id": None, "requirement_text": r.requirement_text} for r in delta_req_rows]

        for req in open_reqs:
            req_keywords = set(w.lower() for w in req["requirement_text"].split() if len(w) > 3)
            for later_prompt in all_prompts_in_order:
                lc = later_prompt.lower()
                if any(p in lc for p in cancel_phrases) and any(k in lc for k in req_keywords):
                    if req.get("id") and dx.supabase:
                        try:
                            dx.supabase.table("requirements").update({
                                "status": "superseded",
                                "evidence": f"Superseded by later prompt: {later_prompt[:200]}",
                            }).eq("id", req["id"]).execute()
                        except Exception:
                            pass
                    dx.set_requirement_status(checkpoint_id, req["requirement_text"], "superseded")
                    break


def cluster_dead_ends(dx: "CheckpointDX", spark=None, project_name: str = "checkpoint-dx") -> int:
    """Clusters unclustered dead-ends by root cause similarity and records into dead_end_clusters table."""
    import re
    from datetime import datetime

    def tokenize(text: str) -> set:
        if not text:
            return set()
        words = re.findall(r'[a-zA-Z0-9_]+', text.lower())
        stopwords = {"with", "that", "this", "from", "have", "been", "will", "using", "into", "over", "after", "the", "and"}
        return {w for w in words if len(w) > 3 and w not in stopwords}

    # Fetch existing clusters
    existing_clusters = dx.get_dead_end_clusters(project_name)

    # Fetch unclustered dead ends from Supabase
    unclustered = []
    try:
        r = dx.supabase.table("dead_end_summaries").select("*").execute()
        unclustered = [d for d in (r.data or []) if not d.get("cluster_id") and not d.get("cluster_key")]
    except Exception:
        pass

    # If Supabase has none or failed, try Databricks Delta fallback
    if not unclustered:
        try:
            sql = f"SELECT checkpoint_id, dead_end_type, root_cause, suggested_fix, confidence FROM {dx.catalog}.{dx.schema}.dead_end_traces_fallback WHERE cluster_key IS NULL"
            rows = _query(spark, dx, sql)
            for row in rows:
                unclustered.append({
                    "id": None,
                    "checkpoint_id": row.checkpoint_id,
                    "dead_end_type": row.dead_end_type,
                    "root_cause": row.root_cause,
                    "suggested_fix": row.suggested_fix,
                    "confidence_score": float(row.confidence or 0.5),
                })
        except Exception:
            pass

    if not unclustered:
        return 0

    assigned_count = 0

    for de in unclustered:
        rc = de.get("root_cause") or ""
        rc_tokens = tokenize(rc)
        if not rc_tokens:
            continue

        best_cluster = None
        best_sim = 0.0

        for c in existing_clusters:
            c_tokens = tokenize(c.get("representative_root_cause", ""))
            intersection = rc_tokens & c_tokens
            union = rc_tokens | c_tokens
            sim = len(intersection) / len(union) if union else 0.0
            if sim > best_sim and sim >= 0.35:
                best_sim = sim
                best_cluster = c

        if best_cluster:
            cluster_id = best_cluster.get("id")
            cluster_key = best_cluster.get("cluster_key")
            new_count = int(best_cluster.get("member_count", 1)) + 1
            best_cluster["member_count"] = new_count

            # Update cluster in Supabase
            try:
                dx.supabase.table("dead_end_clusters").update({
                    "member_count": new_count,
                    "last_seen_at": datetime.now().isoformat(),
                }).eq("id", cluster_id).execute()
            except Exception:
                pass

            # Update cluster in Delta
            try:
                dx._run_sql(f"""
                    UPDATE {dx.catalog}.{dx.schema}.dead_end_clusters
                    SET member_count = {new_count}, last_seen_at = current_timestamp()
                    WHERE cluster_key = '{cluster_key}'
                """)
            except Exception:
                pass
        else:
            # Create a new cluster
            slug = re.sub(r'[^a-z0-9]+', '_', rc.lower()[:30]).strip('_')
            cluster_key = f"de_{slug}_{abs(hash(rc)) % 10000:04d}" if slug else f"de_cluster_{abs(hash(rc)) % 10000:04d}"
            rep_cause = rc[:300]
            common_fix = (de.get("suggested_fix") or "")[:300]
            now_iso = datetime.now().isoformat()

            new_cluster_record = {
                "project_name": project_name,
                "cluster_key": cluster_key,
                "representative_root_cause": rep_cause,
                "member_count": 1,
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
                "common_suggested_fix": common_fix,
            }

            cluster_id = None
            try:
                ins = dx.supabase.table("dead_end_clusters").insert(new_cluster_record).execute()
                if ins.data:
                    cluster_id = ins.data[0]["id"]
            except Exception:
                pass

            # Also persist into Delta dead_end_clusters
            try:
                safe_rep = rep_cause.replace("'", "''")
                safe_fix = common_fix.replace("'", "''")
                dx._run_sql(f"""
                    INSERT INTO {dx.catalog}.{dx.schema}.dead_end_clusters
                    (id, project_name, cluster_key, representative_root_cause, member_count, first_seen_at, last_seen_at, common_suggested_fix)
                    VALUES ('{cluster_id or cluster_key}', '{project_name}', '{cluster_key}', '{safe_rep}', 1, current_timestamp(), current_timestamp(), '{safe_fix}')
                """)
            except Exception:
                pass

            new_cluster_record["id"] = cluster_id or cluster_key
            existing_clusters.append(new_cluster_record)

        # Update dead-end row in Supabase
        if de.get("id"):
            try:
                dx.supabase.table("dead_end_summaries").update({
                    "cluster_id": cluster_id,
                    "cluster_key": cluster_key,
                }).eq("id", de["id"]).execute()
            except Exception:
                pass

        # Update dead-end row in Delta
        try:
            safe_rc = rc.replace("'", "''")
            dx._run_sql(f"""
                UPDATE {dx.catalog}.{dx.schema}.dead_end_traces_fallback
                SET cluster_key = '{cluster_key}'
                WHERE root_cause = '{safe_rc}'
            """)
        except Exception:
            pass

        assigned_count += 1

    return assigned_count


def run_pipeline_glue(dx: "CheckpointDX", spark=None, project_name: str = "checkpoint-dx"):
    """Runs complete pipeline glue synchronization."""
    print("  [1/4] Syncing checkpoints from Databricks...")
    cp_count = sync_checkpoints_from_databricks(dx, spark, project_name)
    print(f"        Synced {cp_count} checkpoints.")
    print("  [2/4] Syncing extracted requirements, dead ends, and intents...")
    sync_extracted_data_to_supabase(dx, spark)
    print("  [3/4] Reconciling superseded requirements & scanning memory conflicts...")
    sid_sql = "SELECT DISTINCT session_id FROM checkpoint_dx.checkpoints.checkpoints_normalized"
    session_ids = [r.session_id for r in _query(spark, dx, sid_sql) if r.session_id]
    total_conflicts = 0
    for sid in session_ids:
        reconcile_superseded_requirements(dx, spark, sid)
        found_conflicts = dx.rescan_memory_conflicts(sid)
        total_conflicts += len(found_conflicts)
    print(f"        Reconciled {len(session_ids)} sessions ({total_conflicts} memory conflicts detected).")
    print("  [4/4] Clustering dead-ends by root cause...")
    clustered_count = cluster_dead_ends(dx, spark, project_name)
    print(f"        Clustered {clustered_count} dead ends.")
    return {
        "sessions_reconciled": len(session_ids),
        "checkpoints_synced": cp_count,
        "dead_ends_clustered": clustered_count,
        "memory_conflicts_scanned": total_conflicts,
    }


if __name__ == "__main__":
    from lib.checkpoint_dx import CheckpointDX
    print("--- Starting Pipeline Glue (Databricks -> Supabase) ---")
    dx_inst = CheckpointDX()
    result = run_pipeline_glue(dx_inst)
    print(f"--- Pipeline Glue Finished Successfully: {result} ---")


