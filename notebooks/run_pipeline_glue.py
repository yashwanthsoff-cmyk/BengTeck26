# Databricks notebook source
# Task 2: Pipeline Glue (Section 7.5)
# MAGIC %pip install -q supabase groq

# COMMAND ----------
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

try:
    from groq import Groq
except ImportError:
    Groq = None

# Injected or imported credentials
import os
try:
    import config
    DATABRICKS_CATALOG = getattr(config, "DATABRICKS_CATALOG", "checkpoint_dx")
    DATABRICKS_SCHEMA = getattr(config, "DATABRICKS_SCHEMA", "checkpoints")
    PROJECT_NAME = getattr(config, "PROJECT_NAME", "checkpoint-dx")
    SUPABASE_URL = getattr(config, "SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    SUPABASE_SERVICE_KEY = getattr(config, "SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_SERVICE_KEY", ""))
    GROQ_API_KEY = getattr(config, "GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    GROQ_MODEL = getattr(config, "GROQ_MODEL", "llama-3.3-70b-versatile")
except ImportError:
    DATABRICKS_CATALOG = os.environ.get("DATABRICKS_CATALOG", "checkpoint_dx")
    DATABRICKS_SCHEMA = os.environ.get("DATABRICKS_SCHEMA", "checkpoints")
    PROJECT_NAME = os.environ.get("PROJECT_NAME", "checkpoint-dx")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


@dataclass
class DeadEnd:
    checkpoint_id: str
    dead_end_type: str
    root_cause: str
    suggested_fix: str
    alternative_approaches: List[str] = None
    confidence_score: float = 0.0
    failed_attempts: int = 0
    files_affected: List[str] = None

@dataclass
class Intent:
    checkpoint_id: str
    intent_text: str
    intent_category: str = 'implementation'
    implementation_status: str = 'unknown'
    confidence_score: float = 0.0
    implementation_evidence: str = None

class CheckpointDXGlue:
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if create_client else None
        self.groq = Groq(api_key=GROQ_API_KEY) if (Groq and GROQ_API_KEY) else None
        self.groq_model = GROQ_MODEL
        self.catalog = DATABRICKS_CATALOG
        self.schema = DATABRICKS_SCHEMA

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        if not self.supabase:
            return None
        try:
            r = self.supabase.table("checkpoints").select("*").eq("checkpoint_id", checkpoint_id).execute()
            return r.data[0] if r.data else None
        except Exception:
            return None

    def create_checkpoint(self, checkpoint_id: str, project_name: str, session_id: str = None,
                          branch_name: str = None, commit_hash: str = None, metadata: Dict = None) -> Dict:
        existing = self.get_checkpoint(checkpoint_id)
        if existing:
            return existing
        if not self.supabase:
            return {"id": checkpoint_id, "checkpoint_id": checkpoint_id, "session_id": session_id}
        try:
            r = self.supabase.table("checkpoints").insert({
                "checkpoint_id": checkpoint_id, "session_id": session_id, "project_name": project_name,
                "branch_name": branch_name, "commit_hash": commit_hash, "metadata": metadata or {},
            }).execute()
            return r.data[0]
        except Exception as e:
            print(f"Supabase note on create_checkpoint ({checkpoint_id}): {e}")
            return {"id": checkpoint_id, "checkpoint_id": checkpoint_id, "session_id": session_id}

    def set_requirement_status(self, checkpoint_id: str, requirement_text: str, new_status: str) -> None:
        safe_text = requirement_text.replace("'", "''")
        spark.sql(f"""
            UPDATE {self.catalog}.{self.schema}.requirements
            SET status = '{new_status}'
            WHERE checkpoint_id = '{checkpoint_id}' AND requirement_text = '{safe_text}'
        """)
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint and self.supabase:
            try:
                self.supabase.table("requirements").update({
                    "status": new_status,
                }).eq("checkpoint_id", checkpoint["id"]).eq("requirement_text", requirement_text).execute()
            except Exception:
                pass

    def log_dead_end(self, d: DeadEnd) -> Dict:
        checkpoint = self.get_checkpoint(d.checkpoint_id)
        if d.alternative_approaches:
            escaped = [a.replace("'", "''") for a in d.alternative_approaches]
            approaches_sql = "array(" + ", ".join(f"'{a}'" for a in escaped) + ")"
        else:
            approaches_sql = "CAST(array() AS ARRAY<STRING>)"
        spark.sql(f"""
            INSERT INTO {self.catalog}.{self.schema}.dead_end_traces_fallback
            VALUES ('{d.checkpoint_id}', '{d.dead_end_type}',
                    '{d.root_cause.replace("'", "''")}', '{d.suggested_fix.replace("'", "''")}',
                    {d.confidence_score}, {d.failed_attempts}, {approaches_sql}, current_timestamp())
        """)
        if self.supabase and checkpoint:
            try:
                self.supabase.table("dead_end_summaries").insert({
                    "checkpoint_id": checkpoint["id"],
                    "databricks_trace_id": None, "used_fallback": True,
                    "dead_end_type": d.dead_end_type, "root_cause": d.root_cause, "suggested_fix": d.suggested_fix,
                    "alternative_approaches": d.alternative_approaches or [], "confidence_score": d.confidence_score,
                    "failed_attempts": d.failed_attempts, "files_affected": d.files_affected or [],
                }).execute()
            except Exception as e:
                print(f"Supabase dead-end sync note: {e}")
        return {"trace_id": None, "used_fallback": True}

    def log_intent(self, i: Intent) -> Dict:
        safe_text = i.intent_text.replace("'", "''")
        spark.sql(f"""
            INSERT INTO {self.catalog}.{self.schema}.intent_traces_fallback
            VALUES ('{i.checkpoint_id}', '{safe_text}', '{i.implementation_status}', {i.confidence_score}, current_timestamp())
        """)
        checkpoint = self.get_checkpoint(i.checkpoint_id)
        if self.supabase and checkpoint:
            try:
                self.supabase.table("intent_summaries").insert({
                    "checkpoint_id": checkpoint["id"],
                    "intent_text": i.intent_text, "intent_category": i.intent_category,
                    "implementation_status": i.implementation_status, "confidence_score": i.confidence_score,
                    "databricks_trace_id": None, "used_fallback": True,
                    "implementation_evidence": i.implementation_evidence,
                }).execute()
            except Exception as e:
                print(f"Supabase intent sync note: {e}")
        return {"trace_id": None, "used_fallback": True}

    def store_in_agent_memory(self, checkpoint_id: str, session_id: str, key: str,
                              value: str, confidence: float = 0.8, source: str = "agent") -> None:
        safe_key = key.replace("'", "''")
        safe_value = value.replace("'", "''")
        spark.sql(f"""
            INSERT INTO {self.catalog}.{self.schema}.agent_memory
            VALUES ('{checkpoint_id}', '{session_id}', '{safe_key}', '{safe_value}', {confidence}, '{source}', current_timestamp())
        """)

    def detect_dead_ends(self, transcript_text: str) -> List[Dict]:
        if not self.groq:
            return []
        try:
            completion = self.groq.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "system", "content": (
                    "Analyze this agent transcript for abandoned approaches (dead ends). "
                    "Return ONLY a JSON array of objects with keys: dead_end_type "
                    "(repeated_failure/timeout/api_error/logic_error/resource_exhaustion/unknown), "
                    "root_cause, suggested_fix, confidence (0-1). Return [] if none present — don't invent one."
                )}, {"role": "user", "content": transcript_text}],
                temperature=0,
            )
            return json.loads(completion.choices[0].message.content.strip())
        except Exception:
            return []

def sync_checkpoints_from_databricks(dx: CheckpointDXGlue, spark, project_name: str) -> int:
    rows = spark.sql("SELECT DISTINCT checkpoint_id, session_id, branch FROM checkpoint_dx.checkpoints.checkpoints_normalized").collect()
    created = 0
    for r in rows:
        if not dx.get_checkpoint(r.checkpoint_id):
            dx.create_checkpoint(checkpoint_id=r.checkpoint_id, session_id=r.session_id,
                                  project_name=project_name, branch_name=r.branch)
            created += 1
    return created

def sync_extracted_data_to_supabase(dx: CheckpointDXGlue, spark):
    # 1. Requirements
    new_requirements = spark.sql("SELECT checkpoint_id, session_id, requirement_text FROM checkpoint_dx.checkpoints.requirements").collect()
    for r in new_requirements:
        checkpoint = dx.get_checkpoint(r.checkpoint_id)
        if checkpoint and dx.supabase:
            try:
                existing = dx.supabase.table("requirements").select("id") \
                    .eq("checkpoint_id", checkpoint["id"]).eq("requirement_text", r.requirement_text).execute().data
                if not existing:
                    dx.supabase.table("requirements").insert({
                        "checkpoint_id": checkpoint["id"], "requirement_text": r.requirement_text, "source": "agent_extracted",
                    }).execute()
            except Exception:
                pass
        dx.store_in_agent_memory(
            checkpoint_id=r.checkpoint_id, session_id=r.session_id,
            key=r.requirement_text, value=f"Requirement extracted from checkpoint {r.checkpoint_id}",
            confidence=0.6, source="pipeline_extraction",
        )

    # 2. Dead Ends (deduped)
    new_deadends = spark.sql("SELECT checkpoint_id, transcript FROM checkpoint_dx.checkpoints.deadend_candidates").collect()
    for d in new_deadends:
        checkpoint = dx.get_checkpoint(d.checkpoint_id)
        transcript = d.transcript or ""
        detections = dx.detect_dead_ends(transcript)
        candidates = detections if detections else [{
            "dead_end_type": "unknown", "root_cause": transcript[:280] if transcript else "Unknown dead end", "suggested_fix": "", "confidence": 0.5,
        }]
        for det in candidates:
            root_cause = det.get("root_cause", transcript[:280])
            if checkpoint and dx.supabase:
                try:
                    existing = dx.supabase.table("dead_end_summaries").select("id") \
                        .eq("checkpoint_id", checkpoint["id"]).eq("root_cause", root_cause).execute().data
                    if existing:
                        continue
                except Exception:
                    pass
            dx.log_dead_end(DeadEnd(
                checkpoint_id=d.checkpoint_id, dead_end_type=det.get("dead_end_type", "unknown"),
                root_cause=root_cause, suggested_fix=det.get("suggested_fix", ""),
                confidence_score=float(det.get("confidence", 0.5)), failed_attempts=1,
            ))

    # 3. Intent Conformance
    new_intents = spark.sql("SELECT checkpoint_id, clause, implementation_status, confidence_score FROM checkpoint_dx.checkpoints.intent_conformance").collect()
    for i in new_intents:
        checkpoint = dx.get_checkpoint(i.checkpoint_id)
        if checkpoint and dx.supabase:
            try:
                existing = dx.supabase.table("intent_summaries").select("id") \
                    .eq("checkpoint_id", checkpoint["id"]).eq("intent_text", i.clause).execute().data
                if existing:
                    continue
            except Exception:
                pass
        dx.log_intent(Intent(
            checkpoint_id=i.checkpoint_id, intent_text=i.clause,
            implementation_status=i.implementation_status, confidence_score=float(i.confidence_score or 0.5),
        ))

def reconcile_superseded_requirements(dx: CheckpointDXGlue, spark, session_id: str):
    prompt_rows = spark.sql(f"""
        SELECT prompt_text FROM checkpoint_dx.checkpoints.checkpoints_normalized
        WHERE session_id = '{session_id}' ORDER BY timestamp ASC
    """).collect()
    all_prompts_in_order = [row.prompt_text for row in prompt_rows if row.prompt_text]
    checkpoint_ids = [row.checkpoint_id for row in spark.sql(
        f"SELECT DISTINCT checkpoint_id FROM checkpoint_dx.checkpoints.checkpoints_normalized WHERE session_id = '{session_id}'"
    ).collect()]
    cancel_phrases = ["skip", "out of scope", "never mind", "don't need", "cancel", "no longer"]
    for checkpoint_id in checkpoint_ids:
        checkpoint = dx.get_checkpoint(checkpoint_id)
        if not checkpoint:
            continue
        if dx.supabase:
            try:
                open_reqs = dx.supabase.table("requirements").select("*").eq("checkpoint_id", checkpoint["id"]) \
                    .in_("status", ["not_started", "in_progress"]).execute().data
                for req in open_reqs:
                    req_keywords = set(w.lower() for w in req["requirement_text"].split() if len(w) > 3)
                    for later_prompt in all_prompts_in_order:
                        lc = later_prompt.lower()
                        if any(p in lc for p in cancel_phrases) and any(k in lc for k in req_keywords):
                            dx.supabase.table("requirements").update({
                                "status": "superseded", "evidence": f"Superseded by later prompt: {later_prompt[:200]}",
                            }).eq("id", req["id"]).execute()
                            dx.set_requirement_status(checkpoint_id, req["requirement_text"], "superseded")
                            break
            except Exception:
                pass

dx_glue = CheckpointDXGlue()
sync_checkpoints_from_databricks(dx_glue, spark, PROJECT_NAME)
sync_extracted_data_to_supabase(dx_glue, spark)
session_ids = [r.session_id for r in spark.sql(
    "SELECT DISTINCT session_id FROM checkpoint_dx.checkpoints.checkpoints_normalized"
).collect() if r.session_id]
for sid in session_ids:
    reconcile_superseded_requirements(dx_glue, spark, sid)
print(f"Pipeline Glue complete: {len(session_ids)} sessions reconciled successfully.")
