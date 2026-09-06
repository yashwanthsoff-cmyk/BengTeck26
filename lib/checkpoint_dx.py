"""lib/checkpoint_dx.py
Checkpoint-Native DX Core Python Library (v9)
Includes implementations for Features A, B, C, D, and E.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from supabase import create_client, Client

try:
    import mlflow
    from mlflow.entities.trace_location import UnityCatalog
except ImportError:
    mlflow = None
    UnityCatalog = None

try:
    from databricks.sdk import WorkspaceClient
except ImportError:
    WorkspaceClient = None

try:
    from groq import Groq
except ImportError:
    Groq = None

# Allow importing config when run from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import (
    DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID, DATABRICKS_CATALOG,
    DATABRICKS_SCHEMA, DATABRICKS_USER, SUPABASE_URL, SUPABASE_SERVICE_KEY,
    GROQ_API_KEY, GROQ_MODEL,
)


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


class CheckpointDX:
    def __init__(self):
        # FIX 5 (v9): Uses SUPABASE_SERVICE_KEY for backend operations.
        # This trusted server-side code requires full read/write admin access.
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        self.catalog = DATABRICKS_CATALOG
        self.schema = DATABRICKS_SCHEMA
        self.warehouse_id = DATABRICKS_WAREHOUSE_ID
        self.user = DATABRICKS_USER

        # Databricks SDK client
        if WorkspaceClient:
            try:
                self.databricks_client = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)
            except Exception:
                self.databricks_client = None
        else:
            self.databricks_client = None

        # MLflow Unity Catalog experiment tracking
        self.experiment = None
        if mlflow and UnityCatalog:
            try:
                mlflow.set_tracking_uri("databricks")
                # Set environment variables for MLflow to authenticate with Databricks
                os.environ["DATABRICKS_HOST"] = DATABRICKS_HOST
                os.environ["DATABRICKS_TOKEN"] = DATABRICKS_TOKEN
                exp_name = f"/Workspace/Users/{self.user}/checkpoint-dx-dead-ends"
                self.experiment = mlflow.set_experiment(
                    experiment_name=exp_name,
                    trace_location=UnityCatalog(
                        catalog_name=self.catalog,
                        schema_name=self.schema,
                        table_prefix="dead_end",
                    ),
                )
            except Exception as e:
                # Unity Catalog trace storage fallback is handled per Section 4/8
                self.experiment = None

        # Groq client
        self.groq = Groq(api_key=GROQ_API_KEY) if (Groq and GROQ_API_KEY) else None
        self.groq_model = GROQ_MODEL

    def _run_sql(self, statement: str) -> List[list]:
        """Executes a SQL statement on the Databricks SQL Warehouse and returns rows."""
        import requests
        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json",
        }
        body = {
            "warehouse_id": self.warehouse_id,
            "statement": statement.strip(),
            "wait_timeout": "30s",
        }
        url = f"{DATABRICKS_HOST}/api/2.0/sql/statements"
        resp = requests.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"Databricks SQL API error ({resp.status_code}): {resp.text}")

        res_data = resp.json()
        statement_id = res_data.get("statement_id")
        status = res_data.get("status", {}).get("state")

        # Wait if statement is pending/running
        while status in ("PENDING", "RUNNING"):
            import time
            time.sleep(1)
            poll_resp = requests.get(f"{url}/{statement_id}", headers=headers)
            res_data = poll_resp.json()
            status = res_data.get("status", {}).get("state")

        if status == "FAILED":
            err_msg = res_data.get("status", {}).get("error", {}).get("message", "Unknown SQL failure")
            raise RuntimeError(f"Databricks SQL query failed: {err_msg}")

        return res_data.get("result", {}).get("data_array", [])

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """Fetches a checkpoint record by checkpoint_id from Supabase."""
        try:
            r = self.supabase.table("checkpoints").select("*").eq("checkpoint_id", checkpoint_id).execute()
            if r.data:
                return r.data[0]
        except Exception:
            pass
        return None

    def create_checkpoint(self, checkpoint_id: str, project_name: str, session_id: str = None,
                          branch_name: str = None, commit_hash: str = None, metadata: Dict = None) -> Dict:
        """Creates or returns an existing checkpoint record in Supabase."""
        existing = self.get_checkpoint(checkpoint_id)
        if existing:
            return existing
        r = self.supabase.table("checkpoints").insert({
            "checkpoint_id": checkpoint_id,
            "session_id": session_id,
            "project_name": project_name,
            "branch_name": branch_name,
            "commit_hash": commit_hash,
            "metadata": metadata or {},
        }).execute()
        return r.data[0]

    def add_requirements(self, checkpoint_id: str, requirement_texts: List[str], source: str = "manual") -> List[Dict]:
        """FIX 3 (full parity): Writes requirement texts to Supabase, Databricks Delta requirements,
        and agent_memory. Manually-added requirements are fully symmetric with pipeline-extracted ones."""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found — call create_checkpoint first")
        session_id = checkpoint.get("session_id")
        inserted = []
        for text in requirement_texts:
            req_item = {"checkpoint_id": checkpoint["id"], "requirement_text": text, "source": source}
            try:
                r = self.supabase.table("requirements").insert(req_item).execute()
                inserted.append(r.data[0])
            except Exception:
                inserted.append(req_item)

            if session_id:
                safe_text = text.replace("'", "''")
                self._run_sql(f"""
                    INSERT INTO {self.catalog}.{self.schema}.requirements
                    VALUES ('{checkpoint_id}', '{session_id}', '{safe_text}', 'not_started', current_timestamp())
                """)
                self.store_in_agent_memory(
                    checkpoint_id=checkpoint_id,
                    session_id=session_id,
                    key=text,
                    value=f"Requirement manually added to checkpoint {checkpoint_id}",
                    confidence=0.6,
                    source=source,
                )
        return inserted

    # ---------- Feature B: Requirement Ledger ----------
    def set_requirement_status(self, checkpoint_id: str, requirement_text: str, new_status: str) -> None:
        """Updates requirement status in both Databricks Delta and Supabase."""
        safe_text = requirement_text.replace("'", "''")
        self._run_sql(f"""
            UPDATE {self.catalog}.{self.schema}.requirements
            SET status = '{new_status}'
            WHERE checkpoint_id = '{checkpoint_id}' AND requirement_text = '{safe_text}'
        """)
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint:
            self.supabase.table("requirements").update({
                "status": new_status,
            }).eq("checkpoint_id", checkpoint["id"]).eq("requirement_text", requirement_text).execute()

    # ---------- Feature A: Dead-End Registry ----------
    def log_dead_end(self, d: DeadEnd) -> Dict:
        """Logs a dead-end entry using MLflow Unity Catalog trace with automatic Delta fallback."""
        checkpoint = self.get_checkpoint(d.checkpoint_id)
        used_fallback, trace_id = False, None
        try:
            if not mlflow:
                raise RuntimeError("MLflow not available")
            with mlflow.start_span(name="dead_end_detection") as span:
                span.set_inputs({"checkpoint_id": d.checkpoint_id})
                span.set_outputs({"dead_end_type": d.dead_end_type, "confidence": d.confidence_score})
                with mlflow.start_span(name="analyze_failure") as child:
                    child.set_inputs({"failed_attempts": d.failed_attempts})
                    child.set_outputs({"root_cause": d.root_cause, "suggested_fix": d.suggested_fix})
                trace_id = span.trace_id
        except Exception:
            used_fallback = True
            # FIX 4: Explicit typed empty-array cast CAST(array() AS ARRAY<STRING>)
            # and consistent single-quote escaping.
            if d.alternative_approaches:
                escaped = [a.replace("'", "''") for a in d.alternative_approaches]
                approaches_sql = "array(" + ", ".join(f"'{a}'" for a in escaped) + ")"
            else:
                approaches_sql = "CAST(array() AS ARRAY<STRING>)"
            self._run_sql(f"""
                INSERT INTO {self.catalog}.{self.schema}.dead_end_traces_fallback
                VALUES ('{d.checkpoint_id}', '{d.dead_end_type}',
                        '{d.root_cause.replace("'", "''")}', '{d.suggested_fix.replace("'", "''")}',
                        {d.confidence_score}, {d.failed_attempts}, {approaches_sql}, current_timestamp())
            """)

        self.supabase.table("dead_end_summaries").insert({
            "checkpoint_id": checkpoint["id"] if checkpoint else None,
            "databricks_trace_id": trace_id,
            "used_fallback": used_fallback,
            "dead_end_type": d.dead_end_type,
            "root_cause": d.root_cause,
            "suggested_fix": d.suggested_fix,
            "alternative_approaches": d.alternative_approaches or [],
            "confidence_score": d.confidence_score,
            "failed_attempts": d.failed_attempts,
            "files_affected": d.files_affected or [],
        }).execute()
        return {"trace_id": trace_id, "used_fallback": used_fallback}

    def get_dead_ends(self, checkpoint_id: str) -> List[Dict]:
        """Retrieves dead-end entries for a given checkpoint."""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return []
        r = self.supabase.table("dead_end_summaries").select("*").eq(
            "checkpoint_id", checkpoint["id"]
        ).order("created_at", desc=True).execute()
        return r.data

    # ---------- Feature C: Intent Conformance ----------
    def log_intent(self, i: Intent) -> Dict:
        """Logs an intent conformance entry with MLflow span or fallback to Delta table."""
        checkpoint = self.get_checkpoint(i.checkpoint_id)
        used_fallback, trace_id = False, None
        try:
            if not mlflow:
                raise RuntimeError("MLflow not available")
            with mlflow.start_span(name="intent_conformance") as span:
                span.set_inputs({"checkpoint_id": i.checkpoint_id, "intent_text": i.intent_text})
                span.set_outputs({"implementation_status": i.implementation_status, "confidence": i.confidence_score})
                trace_id = span.trace_id
        except Exception:
            used_fallback = True
            safe_text = i.intent_text.replace("'", "''")
            self._run_sql(f"""
                INSERT INTO {self.catalog}.{self.schema}.intent_traces_fallback
                VALUES ('{i.checkpoint_id}', '{safe_text}', '{i.implementation_status}', {i.confidence_score}, current_timestamp())
            """)
        r = self.supabase.table("intent_summaries").insert({
            "checkpoint_id": checkpoint["id"] if checkpoint else None,
            "intent_text": i.intent_text,
            "intent_category": i.intent_category,
            "implementation_status": i.implementation_status,
            "confidence_score": i.confidence_score,
            "databricks_trace_id": trace_id,
            "used_fallback": used_fallback,
            "implementation_evidence": i.implementation_evidence,
        }).execute()
        return {"trace_id": trace_id, "used_fallback": used_fallback, "record": r.data[0]}

    # ---------- Feature E: Resume-Integrity Checking (Intelligence & Resilience) ----------
    def store_in_agent_memory(self, checkpoint_id: str, session_id: str, key: str,
                              value: str, confidence: float = 0.8, source: str = "agent") -> None:
        """Stores a memory entry in Databricks Delta agent_memory table."""
        safe_key = key.replace("'", "''")
        safe_value = value.replace("'", "''")
        self._run_sql(f"""
            INSERT INTO {self.catalog}.{self.schema}.agent_memory
            VALUES ('{checkpoint_id}', '{session_id}', '{safe_key}', '{safe_value}', {confidence}, '{source}', current_timestamp())
        """)

    def retrieve_from_agent_memory(self, session_id: str) -> List[Dict]:
        """Retrieves stored memory entries for a given session."""
        rows = self._run_sql(
            f"SELECT memory_key, memory_value, confidence FROM {self.catalog}.{self.schema}.agent_memory WHERE session_id = '{session_id}'"
        )
        return [{"key": r[0], "value": r[1], "confidence": float(r[2])} for r in rows]

    def check_resume_integrity(self, session_id: str, checkpoint_id: str = None) -> Dict:
        """Failure-handling half of Feature E. Evaluates whether open requirements are covered by session memory.
        Filters out requirements marked 'done' or 'superseded'. Upserts snapshot into Supabase."""
        memory_rows = self._run_sql(
            f"SELECT memory_key FROM {self.catalog}.{self.schema}.agent_memory WHERE session_id = '{session_id}'"
        )
        requirement_rows = self._run_sql(
            f"SELECT requirement_text FROM {self.catalog}.{self.schema}.requirements "
            f"WHERE session_id = '{session_id}' AND status NOT IN ('done', 'superseded')"
        )
        if not memory_rows:
            result = {"integrity_score": 0.0, "reason": "no memory found for session — cannot verify resume safety"}
        elif not requirement_rows:
            result = {"integrity_score": 1.0, "reason": "no open requirements recorded for this session — nothing to verify against"}
        else:
            memory_keys = {row[0] for row in memory_rows}
            covered = sum(1 for row in requirement_rows if row[0] in memory_keys)
            score = covered / len(requirement_rows)
            reason = "OK" if score > 0.7 else f"only {covered}/{len(requirement_rows)} open requirements have matching memory — resume may be unreliable"
            result = {"integrity_score": score, "reason": reason}

        # Snapshot in Supabase
        try:
            self.supabase.table("agent_memory_snapshots").upsert({
                "databricks_scope": session_id,
                "checkpoint_id": checkpoint_id,
                "integrity_score": result["integrity_score"],
                "integrity_reason": result["reason"],
            }, on_conflict="databricks_scope").execute()
        except Exception:
            pass
        return result

    def record_human_feedback(self, checkpoint_id: str, memory_key: str, was_correct: bool) -> Dict:
        """Learning-loop half of Feature E. Adjusts confidence score (+0.1 if correct, -0.2 if incorrect)."""
        adjustment = 0.1 if was_correct else -0.2
        safe_key = memory_key.replace("'", "''")
        self._run_sql(f"""
            UPDATE {self.catalog}.{self.schema}.agent_memory
            SET confidence = LEAST(1.0, GREATEST(0.0, confidence + {adjustment}))
            WHERE checkpoint_id = '{checkpoint_id}' AND memory_key = '{safe_key}'
        """)
        return {"adjusted_by": adjustment}

    def detect_dead_ends(self, transcript_text: str) -> List[Dict]:
        """Extracts dead-end signals from transcripts using Groq LLM."""
        if not self.groq:
            return []
        try:
            completion = self.groq.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Analyze this agent transcript for abandoned approaches (dead ends). "
                            "Return ONLY a JSON array of objects with keys: dead_end_type "
                            "(repeated_failure/timeout/api_error/logic_error/resource_exhaustion/unknown), "
                            "root_cause, suggested_fix, confidence (0-1). Return [] if none present — don't invent one."
                        ),
                    },
                    {"role": "user", "content": transcript_text},
                ],
                temperature=0,
            )
            content = completion.choices[0].message.content.strip()
            # Remove Markdown code blocks if any
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            return json.loads(content)
        except Exception as e:
            print(f"Groq dead-end detection error: {e}")
            return []

    def create_resume_contract(self, checkpoint_id: str, session_id: str) -> Dict:
        """Invokes Feature D to generate a resume contract synthesizing Features A, B, C, and E."""
        from feature_d import generate_resume_contract
        return generate_resume_contract(self, checkpoint_id, session_id)

    def cache_dashboard_query(self, query_name: str, query_sql: str, result: Any, ttl_hours: int = 1):
        """Caches dashboard query results in Supabase dashboard_cache table."""
        self.supabase.table("dashboard_cache").upsert({
            "query_name": query_name,
            "query_sql": query_sql,
            "cached_result": result,
            "cached_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=ttl_hours)).isoformat(),
            "is_valid": True,
        }, on_conflict="query_name").execute()

    def get_cached_query(self, query_name: str) -> Optional[Any]:
        """Retrieves non-expired cached query result from dashboard_cache."""
        r = self.supabase.table("dashboard_cache").select("*").eq(
            "query_name", query_name
        ).eq("is_valid", True).gt("expires_at", datetime.now().isoformat()).execute()
        return r.data[0]["cached_result"] if r.data else None

    def extract_requirements_from_text(self, text: str) -> List[str]:
        """Extracts discrete requirements from prompt text."""
        import re
        if not text:
            return []
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.split()) > 2]
        keywords = ["add", "implement", "create", "ensure", "support", "validate", "track", "build"]
        reqs = [s for s in sentences if any(k in s.lower() for k in keywords)]
        return reqs if reqs else sentences

    def extract_intents_from_text(self, text: str) -> List[str]:
        """Segments user prompt text into discrete intent clauses."""
        import re
        if not text:
            return []
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.split()) > 2]

