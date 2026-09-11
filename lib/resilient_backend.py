"""lib/resilient_backend.py — Dual-Backend Resilient Storage and Query Wrapper.
Ensures seamless, zero-error operation for resume_contracts, contract_versions, and contract_executions.
When remote Supabase PostgREST tables are unmigrated (returning PGRST205),
this wrapper seamlessly persists to and queries from:
1. Databricks Unity Catalog Delta tables (checkpoint_dx.checkpoints.<table_name>)
2. Local durable SQLite store (data/checkpoint_dx_store.db)
"""
import os
import sqlite3
import uuid
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("resilient_backend")

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "checkpoint_dx_store.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_resilient_store():
    """Initializes local tables for dual-backend resilience."""
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS resume_contracts (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            session_id TEXT,
            template TEXT DEFAULT 'dev',
            version INTEGER DEFAULT 1,
            contract_json TEXT,
            schema_valid INTEGER DEFAULT 1,
            validation_errors TEXT DEFAULT '[]',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS contract_versions (
            id TEXT PRIMARY KEY,
            contract_family_id TEXT,
            resume_contract_id TEXT,
            version INTEGER,
            changelog TEXT,
            diff_from_previous TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS contract_executions (
            id TEXT PRIMARY KEY,
            resume_contract_id TEXT,
            consumer_type TEXT,
            consumer_identifier TEXT,
            loaded_at TEXT,
            outcome_reported INTEGER DEFAULT 0,
            outcome_notes TEXT
        );

        CREATE TABLE IF NOT EXISTS integrity_score_history (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            checkpoint_id TEXT,
            integrity_score REAL,
            reason TEXT,
            stale_memory_count INTEGER DEFAULT 0,
            conflict_count INTEGER DEFAULT 0,
            recorded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS memory_conflicts (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            memory_key_a TEXT,
            memory_key_b TEXT,
            conflict_reason TEXT,
            resolved INTEGER DEFAULT 0,
            resolution_notes TEXT,
            created_at TEXT,
            UNIQUE (session_id, memory_key_a, memory_key_b)
        );

        CREATE TABLE IF NOT EXISTS preflight_overrides (
            id TEXT PRIMARY KEY,
            planned_approach TEXT,
            similarity_score REAL,
            matched_dead_end_id TEXT,
            override_reason TEXT,
            override_category TEXT,
            approver TEXT,
            risk_level TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS dead_end_clusters (
            id TEXT PRIMARY KEY,
            project_name TEXT,
            cluster_key TEXT UNIQUE,
            representative_root_cause TEXT,
            member_count INTEGER DEFAULT 1,
            first_seen_at TEXT,
            last_seen_at TEXT,
            common_suggested_fix TEXT,
            custom_name TEXT,
            ai_suggested_name TEXT,
            name_reasoning TEXT
        );

        CREATE TABLE IF NOT EXISTS requirement_status_history (
            id TEXT PRIMARY KEY,
            requirement_id TEXT,
            checkpoint_id TEXT,
            old_status TEXT,
            new_status TEXT,
            changed_by TEXT,
            change_reason TEXT,
            duration_in_prev_status_hours REAL DEFAULT 0.0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            requirement_text TEXT,
            status TEXT DEFAULT 'not_started',
            priority_tier TEXT DEFAULT 'P2',
            moscow TEXT DEFAULT 'should',
            effort_points INTEGER,
            owner TEXT,
            acceptance_criteria TEXT DEFAULT '[]',
            priority_reasoning TEXT,
            status_changed_at TEXT,
            status_changed_by TEXT,
            previous_status TEXT,
            status_change_reason TEXT,
            business_impact_score INTEGER DEFAULT 5,
            urgency_score INTEGER DEFAULT 5,
            risk_score INTEGER DEFAULT 3,
            calculated_priority_score REAL,
            calculated_priority_tier TEXT,
            priority_override_reason TEXT,
            rice_reach INTEGER DEFAULT 5,
            rice_impact INTEGER DEFAULT 5,
            rice_confidence REAL DEFAULT 0.8,
            rice_effort REAL DEFAULT 3.0,
            rice_score REAL,
            rice_rank INTEGER,
            gherkin_scenarios TEXT DEFAULT '[]',
            complexity_factors TEXT DEFAULT '{}',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS compliance_violations (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            clause_id TEXT,
            clause_text TEXT,
            violation_type TEXT DEFAULT 'functional',
            severity TEXT DEFAULT 'medium',
            remediation_deadline TEXT,
            assigned_to TEXT DEFAULT 'unassigned',
            status TEXT DEFAULT 'open',
            resolution_notes TEXT,
            created_at TEXT,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS compliance_history (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            overall_score REAL,
            total_clauses INTEGER,
            compliant_clauses INTEGER,
            recorded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS intent_summaries (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            intent_text TEXT,
            implementation_status TEXT DEFAULT 'met',
            confidence_score REAL DEFAULT 1.0,
            diff_reference TEXT,
            intent_category TEXT DEFAULT 'functional',
            conformance_grade TEXT,
            semantic_similarity REAL,
            code_coverage_score REAL,
            remediation_suggestion TEXT,
            audited_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS custom_templates (
            id TEXT PRIMARY KEY,
            template_name TEXT UNIQUE,
            target_audience TEXT DEFAULT 'dev',
            created_by TEXT DEFAULT 'user',
            sections TEXT DEFAULT '[]',
            theme TEXT DEFAULT '{"layout": "standard", "accent": "#0ea5e9"}',
            is_valid INTEGER DEFAULT 1,
            validation_errors TEXT DEFAULT '[]',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS template_versions (
            id TEXT PRIMARY KEY,
            template_id TEXT,
            version_number INTEGER DEFAULT 1,
            changelog TEXT DEFAULT 'Initial version',
            sections TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'user',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS template_ab_tests (
            id TEXT PRIMARY KEY,
            test_name TEXT,
            variant_a_id TEXT,
            variant_b_id TEXT,
            traffic_split REAL DEFAULT 0.5,
            status TEXT DEFAULT 'running',
            results TEXT DEFAULT '{"variant_a_impressions": 0, "variant_b_impressions": 0, "variant_a_conversions": 0, "variant_b_conversions": 0}',
            start_date TEXT,
            end_date TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS contract_conflicts (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            session_id TEXT,
            conflict_type TEXT DEFAULT 'requirement_vs_dead_end',
            severity TEXT DEFAULT 'medium',
            description TEXT,
            involved_features TEXT DEFAULT '[]',
            resolution_strategies TEXT DEFAULT '[]',
            resolved INTEGER DEFAULT 0,
            resolution_strategy_id TEXT,
            resolution_notes TEXT,
            created_at TEXT,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS contract_interactions (
            id TEXT PRIMARY KEY,
            resume_contract_id TEXT,
            consumer_type TEXT DEFAULT 'human_ui_view',
            interaction_type TEXT DEFAULT 'view',
            section_name TEXT,
            duration_seconds REAL DEFAULT 0.0,
            scroll_depth REAL DEFAULT 0.0,
            details TEXT DEFAULT '{}',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS integrity_trends (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            checkpoint_id TEXT,
            integrity_score REAL,
            integrity_reason TEXT,
            recorded_at TEXT,
            trend_direction TEXT DEFAULT 'stable',
            trend_magnitude REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS integrity_alerts (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            alert_type TEXT DEFAULT 'anomaly_detected',
            severity TEXT DEFAULT 'minor',
            message TEXT,
            detected_at TEXT,
            acknowledged INTEGER DEFAULT 0,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS memory_ttl_config (
            id TEXT PRIMARY KEY,
            session_id TEXT UNIQUE,
            ttl_days INTEGER DEFAULT 30,
            auto_cleanup_enabled INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_memory (
            id TEXT PRIMARY KEY,
            checkpoint_id TEXT,
            session_id TEXT,
            memory_key TEXT,
            memory_value TEXT,
            confidence REAL,
            source TEXT,
            created_at TEXT,
            last_verified_at TEXT
        );
        """)

        # Ensure optional columns in dead_end_clusters if table pre-existed
        try:
            conn.execute("ALTER TABLE dead_end_clusters ADD COLUMN custom_name TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE dead_end_clusters ADD COLUMN ai_suggested_name TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE dead_end_clusters ADD COLUMN name_reasoning TEXT")
        except Exception:
            pass

        # Ensure optional columns in requirements if table pre-existed
        req_cols = [
            ("status_changed_at", "TEXT"), ("status_changed_by", "TEXT"),
            ("previous_status", "TEXT"), ("status_change_reason", "TEXT"),
            ("business_impact_score", "INTEGER DEFAULT 5"), ("urgency_score", "INTEGER DEFAULT 5"),
            ("risk_score", "INTEGER DEFAULT 3"), ("calculated_priority_score", "REAL"),
            ("calculated_priority_tier", "TEXT"), ("priority_override_reason", "TEXT"),
            ("rice_reach", "INTEGER DEFAULT 5"), ("rice_impact", "INTEGER DEFAULT 5"),
            ("rice_confidence", "REAL DEFAULT 0.8"), ("rice_effort", "REAL DEFAULT 3.0"),
            ("rice_score", "REAL"), ("rice_rank", "INTEGER"),
            ("gherkin_scenarios", "TEXT DEFAULT '[]'"), ("complexity_factors", "TEXT DEFAULT '{}'"),
        ]
        for cname, ctype in req_cols:
            try:
                conn.execute(f"ALTER TABLE requirements ADD COLUMN {cname} {ctype}")
            except Exception:
                pass

        # Ensure optional columns in resume_contracts
        try:
            conn.execute("ALTER TABLE resume_contracts ADD COLUMN synthesis_weights TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE resume_contracts ADD COLUMN contract_purpose TEXT")
        except Exception:
            pass


init_resilient_store()


class ResilientResponse:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def __repr__(self):
        return f"<ResilientResponse data={len(self.data)} rows>"


class ResilientQueryBuilder:
    def __init__(self, dx, table_name: str, real_builder=None):
        self.dx = dx
        self.table_name = table_name
        self.real_builder = real_builder
        self._action = "select"
        self._insert_data = None
        self._update_data = None
        self._select_cols = "*"
        self._eq_filters = {}
        self._custom_filters = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None

    def select(self, cols: str = "*"):
        self._action = "select"
        self._select_cols = cols
        if self.real_builder and hasattr(self.real_builder, "select"):
            try:
                self.real_builder = self.real_builder.select(cols)
            except Exception:
                pass
        return self

    def insert(self, data: Any):
        self._action = "insert"
        self._insert_data = data if isinstance(data, list) else [data]
        if self.real_builder and hasattr(self.real_builder, "insert"):
            try:
                self.real_builder = self.real_builder.insert(data)
            except Exception:
                pass
        return self

    def upsert(self, data: Any, on_conflict: str = None):
        self._action = "insert"
        self._insert_data = data if isinstance(data, list) else [data]
        if self.real_builder and hasattr(self.real_builder, "upsert"):
            try:
                self.real_builder = self.real_builder.upsert(data, on_conflict=on_conflict)
            except Exception:
                pass
        return self

    def update(self, data: Dict[str, Any]):
        self._action = "update"
        self._update_data = data
        if self.real_builder and hasattr(self.real_builder, "update"):
            try:
                self.real_builder = self.real_builder.update(data)
            except Exception:
                pass
        return self

    def delete(self):
        self._action = "delete"
        if self.real_builder and hasattr(self.real_builder, "delete"):
            try:
                self.real_builder = self.real_builder.delete()
            except Exception:
                pass
        return self

    def eq(self, col: str, val: Any):
        self._eq_filters[col] = val
        if self.real_builder and hasattr(self.real_builder, "eq"):
            try:
                self.real_builder = self.real_builder.eq(col, val)
            except Exception:
                pass
        return self

    def neq(self, col: str, val: Any):
        self._custom_filters.append((f"{col} != ?", [val]))
        if self.real_builder and hasattr(self.real_builder, "neq"):
            try:
                self.real_builder = self.real_builder.neq(col, val)
            except Exception:
                pass
        return self

    def in_(self, col: str, vals: List[Any]):
        vals_list = list(vals)
        if not vals_list:
            self._custom_filters.append(("1 = 0", []))
        else:
            placeholders = ", ".join(["?"] * len(vals_list))
            self._custom_filters.append((f"{col} IN ({placeholders})", vals_list))
        if self.real_builder and hasattr(self.real_builder, "in_"):
            try:
                self.real_builder = self.real_builder.in_(col, vals)
            except Exception:
                pass
        return self

    def gte(self, col: str, val: Any):
        self._custom_filters.append((f"{col} >= ?", [val]))
        if self.real_builder and hasattr(self.real_builder, "gte"):
            try:
                self.real_builder = self.real_builder.gte(col, val)
            except Exception:
                pass
        return self

    def lte(self, col: str, val: Any):
        self._custom_filters.append((f"{col} <= ?", [val]))
        if self.real_builder and hasattr(self.real_builder, "lte"):
            try:
                self.real_builder = self.real_builder.lte(col, val)
            except Exception:
                pass
        return self

    def gt(self, col: str, val: Any):
        self._custom_filters.append((f"{col} > ?", [val]))
        if self.real_builder and hasattr(self.real_builder, "gt"):
            try:
                self.real_builder = self.real_builder.gt(col, val)
            except Exception:
                pass
        return self

    def lt(self, col: str, val: Any):
        self._custom_filters.append((f"{col} < ?", [val]))
        if self.real_builder and hasattr(self.real_builder, "lt"):
            try:
                self.real_builder = self.real_builder.lt(col, val)
            except Exception:
                pass
        return self

    def order(self, col: str, desc: bool = False):
        self._order_col = col
        self._order_desc = desc
        if self.real_builder and hasattr(self.real_builder, "order"):
            try:
                self.real_builder = self.real_builder.order(col, desc=desc)
            except Exception:
                pass
        return self

    def limit(self, val: int):
        self._limit_val = val
        if self.real_builder and hasattr(self.real_builder, "limit"):
            try:
                self.real_builder = self.real_builder.limit(val)
            except Exception:
                pass
        return self

    def _build_where(self):
        where_parts = []
        vals = []
        for k, v in self._eq_filters.items():
            where_parts.append(f"{k} = ?")
            vals.append(v)
        for clause, params in self._custom_filters:
            where_parts.append(clause)
            vals.extend(params)
        return where_parts, vals

    def execute(self) -> ResilientResponse:
        # Try real Supabase first
        if self.real_builder and hasattr(self.real_builder, "execute"):
            try:
                res = self.real_builder.execute()
                err = getattr(res, "error", None)
                data = getattr(res, "data", None)
                if not err and isinstance(data, list):
                    # Check if PostgREST returned rows
                    # Enrich resume_contracts with top-level fields from contract_sections if missing
                    if self.table_name == "resume_contracts":
                        enriched = []
                        for row in data:
                            r_copy = dict(row)
                            sections = r_copy.get("contract_sections") or {}
                            if isinstance(sections, str):
                                try:
                                    sections = json.loads(sections)
                                except Exception:
                                    sections = {}
                            if r_copy.get("template") is None:
                                r_copy["template"] = sections.get("template", "dev")
                            if r_copy.get("version") is None:
                                r_copy["version"] = sections.get("version", r_copy.get("contract_version", 1))
                            if r_copy.get("schema_valid") is None:
                                r_copy["schema_valid"] = sections.get("schema_valid", True)
                            if r_copy.get("validation_errors") is None:
                                r_copy["validation_errors"] = sections.get("validation_errors", [])
                            if r_copy.get("contract_json") is None:
                                r_copy["contract_json"] = sections
                            enriched.append(r_copy)
                        return ResilientResponse(enriched)
                    return ResilientResponse(data)
            except Exception as ex:
                logger.debug(f"Supabase {self.table_name} query fell back: {ex}")

        # Fallback to Local SQLite + Databricks
        if self._action == "insert":
            inserted_rows = []
            with _get_conn() as conn:
                for row in (self._insert_data or []):
                    r_dict = dict(row)
                    row_id = r_dict.get("id") or str(uuid.uuid4())
                    r_dict["id"] = row_id
                    now_str = datetime.now().isoformat()
                    
                    if self.table_name == "contract_versions":
                        conn.execute("""
                            INSERT OR REPLACE INTO contract_versions
                            (id, contract_family_id, resume_contract_id, version, changelog, diff_from_previous, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("contract_family_id")),
                            str(r_dict.get("resume_contract_id")),
                            int(r_dict.get("version", 1)),
                            str(r_dict.get("changelog", "")),
                            json.dumps(r_dict.get("diff_from_previous"), default=str),
                            r_dict.get("created_at", now_str),
                        ))
                        # Dual-backend sync to Databricks Delta
                        self._sync_to_databricks_version(r_dict)

                    elif self.table_name == "contract_executions":
                        conn.execute("""
                            INSERT OR REPLACE INTO contract_executions
                            (id, resume_contract_id, consumer_type, consumer_identifier, loaded_at, outcome_reported, outcome_notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("resume_contract_id")),
                            str(r_dict.get("consumer_type")),
                            str(r_dict.get("consumer_identifier") or ""),
                            r_dict.get("loaded_at", now_str),
                            1 if r_dict.get("outcome_reported") else 0,
                            r_dict.get("outcome_notes"),
                        ))
                        # Dual-backend sync to Databricks Delta
                        self._sync_to_databricks_execution(r_dict)

                    elif self.table_name == "resume_contracts":
                        conn.execute("""
                            INSERT OR REPLACE INTO resume_contracts
                            (id, checkpoint_id, session_id, template, version, contract_json, schema_valid, validation_errors, synthesis_weights, contract_purpose, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id")),
                            str(r_dict.get("session_id", "")),
                            str(r_dict.get("template", "dev")),
                            int(r_dict.get("version", 1)),
                            json.dumps(r_dict.get("contract_json", {}), default=str),
                            1 if r_dict.get("schema_valid", True) else 0,
                            json.dumps(r_dict.get("validation_errors", []), default=str),
                            json.dumps(r_dict.get("synthesis_weights", {}), default=str) if isinstance(r_dict.get("synthesis_weights"), dict) else str(r_dict.get("synthesis_weights") or ""),
                            str(r_dict.get("contract_purpose") or "development"),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "integrity_score_history":
                        conn.execute("""
                            INSERT OR REPLACE INTO integrity_score_history
                            (id, session_id, checkpoint_id, integrity_score, reason, stale_memory_count, conflict_count, recorded_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("session_id")),
                            str(r_dict.get("checkpoint_id") or ""),
                            float(r_dict.get("integrity_score") or 0.0),
                            str(r_dict.get("reason") or ""),
                            int(r_dict.get("stale_memory_count") or 0),
                            int(r_dict.get("conflict_count") or 0),
                            r_dict.get("recorded_at", now_str),
                        ))
                        self._sync_to_databricks_integrity_history(r_dict)

                    elif self.table_name == "memory_conflicts":
                        conn.execute("""
                            INSERT OR REPLACE INTO memory_conflicts
                            (id, session_id, memory_key_a, memory_key_b, conflict_reason, resolved, resolution_notes, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("session_id")),
                            str(r_dict.get("memory_key_a")),
                            str(r_dict.get("memory_key_b")),
                            str(r_dict.get("conflict_reason") or ""),
                            1 if r_dict.get("resolved") else 0,
                            str(r_dict.get("resolution_notes") or ""),
                            r_dict.get("created_at", now_str),
                        ))
                        self._sync_to_databricks_memory_conflict(r_dict)

                    elif self.table_name == "preflight_overrides":
                        conn.execute("""
                            INSERT OR REPLACE INTO preflight_overrides
                            (id, planned_approach, similarity_score, matched_dead_end_id, override_reason, override_category, approver, risk_level, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("planned_approach") or ""),
                            float(r_dict.get("similarity_score") or 0.0),
                            str(r_dict.get("matched_dead_end_id") or ""),
                            str(r_dict.get("override_reason") or ""),
                            str(r_dict.get("override_category") or "technical_necessity"),
                            str(r_dict.get("approver") or ""),
                            str(r_dict.get("risk_level") or "MODERATE"),
                            r_dict.get("created_at", now_str),
                        ))
                        self._sync_to_databricks_preflight_override(r_dict)

                    elif self.table_name == "dead_end_clusters":
                        conn.execute("""
                            INSERT OR REPLACE INTO dead_end_clusters
                            (id, project_name, cluster_key, representative_root_cause, member_count, first_seen_at, last_seen_at, common_suggested_fix, custom_name, ai_suggested_name, name_reasoning)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("project_name") or "checkpoint-dx"),
                            str(r_dict.get("cluster_key") or f"cluster_{row_id}"),
                            str(r_dict.get("representative_root_cause") or ""),
                            int(r_dict.get("member_count") or 1),
                            r_dict.get("first_seen_at", now_str),
                            r_dict.get("last_seen_at", now_str),
                            str(r_dict.get("common_suggested_fix") or ""),
                            r_dict.get("custom_name"),
                            r_dict.get("ai_suggested_name"),
                            r_dict.get("name_reasoning"),
                        ))
                        self._sync_to_databricks_cluster(r_dict)

                    elif self.table_name == "requirement_status_history":
                        conn.execute("""
                            INSERT OR REPLACE INTO requirement_status_history
                            (id, requirement_id, checkpoint_id, old_status, new_status, changed_by, change_reason, duration_in_prev_status_hours, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("requirement_id") or ""),
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("old_status") or ""),
                            str(r_dict.get("new_status") or ""),
                            str(r_dict.get("changed_by") or "user"),
                            str(r_dict.get("change_reason") or ""),
                            float(r_dict.get("duration_in_prev_status_hours") or 0.0),
                            r_dict.get("created_at", now_str),
                        ))
                        self._sync_to_databricks_status_history(r_dict)

                    elif self.table_name == "requirements":
                        conn.execute("""
                            INSERT OR REPLACE INTO requirements
                            (id, checkpoint_id, requirement_text, status, priority_tier, moscow, effort_points, owner,
                             acceptance_criteria, priority_reasoning, status_changed_at, status_changed_by, previous_status,
                             status_change_reason, business_impact_score, urgency_score, risk_score, calculated_priority_score,
                             calculated_priority_tier, priority_override_reason, rice_reach, rice_impact, rice_confidence,
                             rice_effort, rice_score, rice_rank, gherkin_scenarios, complexity_factors, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("requirement_text") or ""),
                            str(r_dict.get("status") or "not_started"),
                            str(r_dict.get("priority_tier") or "P2"),
                            str(r_dict.get("moscow") or "should"),
                            r_dict.get("effort_points"),
                            r_dict.get("owner"),
                            json.dumps(r_dict.get("acceptance_criteria", []), default=str),
                            r_dict.get("priority_reasoning"),
                            r_dict.get("status_changed_at", now_str),
                            r_dict.get("status_changed_by", "user"),
                            r_dict.get("previous_status"),
                            r_dict.get("status_change_reason"),
                            int(r_dict.get("business_impact_score") or 5),
                            int(r_dict.get("urgency_score") or 5),
                            int(r_dict.get("risk_score") or 3),
                            float(r_dict.get("calculated_priority_score")) if r_dict.get("calculated_priority_score") is not None else None,
                            r_dict.get("calculated_priority_tier"),
                            r_dict.get("priority_override_reason"),
                            int(r_dict.get("rice_reach") or 5),
                            int(r_dict.get("rice_impact") or 5),
                            float(r_dict.get("rice_confidence") or 0.8),
                            float(r_dict.get("rice_effort") or 3.0),
                            float(r_dict.get("rice_score")) if r_dict.get("rice_score") is not None else None,
                            int(r_dict.get("rice_rank")) if r_dict.get("rice_rank") is not None else None,
                            json.dumps(r_dict.get("gherkin_scenarios", []), default=str),
                            json.dumps(r_dict.get("complexity_factors", {}), default=str),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "compliance_violations":
                        conn.execute("""
                            INSERT OR REPLACE INTO compliance_violations
                            (id, checkpoint_id, clause_id, clause_text, violation_type, severity, remediation_deadline, assigned_to, status, resolution_notes, created_at, resolved_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("clause_id") or ""),
                            str(r_dict.get("clause_text") or ""),
                            str(r_dict.get("violation_type") or "functional"),
                            str(r_dict.get("severity") or "medium"),
                            r_dict.get("remediation_deadline"),
                            str(r_dict.get("assigned_to") or "unassigned"),
                            str(r_dict.get("status") or "open"),
                            r_dict.get("resolution_notes"),
                            r_dict.get("created_at", now_str),
                            r_dict.get("resolved_at"),
                        ))
                        self._sync_to_databricks_compliance_violation(r_dict)

                    elif self.table_name == "compliance_history":
                        conn.execute("""
                            INSERT OR REPLACE INTO compliance_history
                            (id, checkpoint_id, overall_score, total_clauses, compliant_clauses, recorded_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            float(r_dict.get("overall_score") or 0.0),
                            int(r_dict.get("total_clauses") or 0),
                            int(r_dict.get("compliant_clauses") or 0),
                            r_dict.get("recorded_at", now_str),
                        ))
                        self._sync_to_databricks_compliance_history(r_dict)

                    elif self.table_name == "intent_summaries":
                        conn.execute("""
                            INSERT OR REPLACE INTO intent_summaries
                            (id, checkpoint_id, intent_text, implementation_status, confidence_score, diff_reference, intent_category, conformance_grade, semantic_similarity, code_coverage_score, remediation_suggestion, audited_at, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("intent_text") or ""),
                            str(r_dict.get("implementation_status") or "met"),
                            float(r_dict.get("confidence_score") or 1.0),
                            str(r_dict.get("diff_reference") or ""),
                            str(r_dict.get("intent_category") or "functional"),
                            r_dict.get("conformance_grade"),
                            float(r_dict.get("semantic_similarity") or 0.0),
                            float(r_dict.get("code_coverage_score") or 0.0),
                            r_dict.get("remediation_suggestion"),
                            r_dict.get("audited_at"),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "custom_templates":
                        conn.execute("""
                            INSERT OR REPLACE INTO custom_templates
                            (id, template_name, target_audience, created_by, sections, theme, is_valid, validation_errors, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("template_name") or ""),
                            str(r_dict.get("target_audience") or "dev"),
                            str(r_dict.get("created_by") or "user"),
                            json.dumps(r_dict.get("sections", []), default=str),
                            json.dumps(r_dict.get("theme", {}), default=str),
                            1 if r_dict.get("is_valid", True) else 0,
                            json.dumps(r_dict.get("validation_errors", []), default=str),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "template_versions":
                        conn.execute("""
                            INSERT OR REPLACE INTO template_versions
                            (id, template_id, version_number, changelog, sections, is_active, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("template_id") or ""),
                            int(r_dict.get("version_number", 1)),
                            str(r_dict.get("changelog") or "Initial version"),
                            json.dumps(r_dict.get("sections", []), default=str),
                            1 if r_dict.get("is_active", True) else 0,
                            str(r_dict.get("created_by") or "user"),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "template_ab_tests":
                        conn.execute("""
                            INSERT OR REPLACE INTO template_ab_tests
                            (id, test_name, variant_a_id, variant_b_id, traffic_split, status, results, start_date, end_date, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("test_name") or ""),
                            str(r_dict.get("variant_a_id") or ""),
                            str(r_dict.get("variant_b_id") or ""),
                            float(r_dict.get("traffic_split") or 0.5),
                            str(r_dict.get("status") or "running"),
                            json.dumps(r_dict.get("results", {}), default=str),
                            r_dict.get("start_date", now_str),
                            r_dict.get("end_date"),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "contract_conflicts":
                        conn.execute("""
                            INSERT OR REPLACE INTO contract_conflicts
                            (id, checkpoint_id, session_id, conflict_type, severity, description, involved_features, resolution_strategies, resolved, resolution_strategy_id, resolution_notes, created_at, resolved_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("session_id") or ""),
                            str(r_dict.get("conflict_type") or "requirement_vs_dead_end"),
                            str(r_dict.get("severity") or "medium"),
                            str(r_dict.get("description") or ""),
                            json.dumps(r_dict.get("involved_features", []), default=str),
                            json.dumps(r_dict.get("resolution_strategies", []), default=str),
                            1 if r_dict.get("resolved") else 0,
                            str(r_dict.get("resolution_strategy_id") or ""),
                            str(r_dict.get("resolution_notes") or ""),
                            r_dict.get("created_at", now_str),
                            r_dict.get("resolved_at"),
                        ))

                    elif self.table_name == "contract_interactions":
                        conn.execute("""
                            INSERT OR REPLACE INTO contract_interactions
                            (id, resume_contract_id, consumer_type, interaction_type, section_name, duration_seconds, scroll_depth, details, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("resume_contract_id") or ""),
                            str(r_dict.get("consumer_type") or "human_ui_view"),
                            str(r_dict.get("interaction_type") or "view"),
                            str(r_dict.get("section_name") or ""),
                            float(r_dict.get("duration_seconds") or 0.0),
                            float(r_dict.get("scroll_depth") or 0.0),
                            json.dumps(r_dict.get("details", {}), default=str),
                            r_dict.get("created_at", now_str),
                        ))

                    elif self.table_name == "integrity_trends":
                        conn.execute("""
                            INSERT OR REPLACE INTO integrity_trends
                            (id, session_id, checkpoint_id, integrity_score, integrity_reason, recorded_at, trend_direction, trend_magnitude)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("session_id") or ""),
                            str(r_dict.get("checkpoint_id") or ""),
                            float(r_dict.get("integrity_score") or 0.0),
                            str(r_dict.get("integrity_reason") or ""),
                            r_dict.get("recorded_at", now_str),
                            str(r_dict.get("trend_direction") or "stable"),
                            float(r_dict.get("trend_magnitude") or 0.0),
                        ))
                        self._sync_to_databricks_integrity_trend(r_dict)

                    elif self.table_name == "integrity_alerts":
                        conn.execute("""
                            INSERT OR REPLACE INTO integrity_alerts
                            (id, session_id, alert_type, severity, message, detected_at, acknowledged, resolved_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("session_id") or ""),
                            str(r_dict.get("alert_type") or "anomaly_detected"),
                            str(r_dict.get("severity") or "minor"),
                            str(r_dict.get("message") or ""),
                            r_dict.get("detected_at", now_str),
                            1 if r_dict.get("acknowledged") else 0,
                            r_dict.get("resolved_at"),
                        ))
                        self._sync_to_databricks_integrity_alert(r_dict)

                    elif self.table_name == "memory_ttl_config":
                        conn.execute("""
                            INSERT OR REPLACE INTO memory_ttl_config
                            (id, session_id, ttl_days, auto_cleanup_enabled, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("session_id") or ""),
                            int(r_dict.get("ttl_days") or 30),
                            1 if r_dict.get("auto_cleanup_enabled", True) else 0,
                            r_dict.get("created_at", now_str),
                            r_dict.get("updated_at", now_str),
                        ))
                        self._sync_to_databricks_memory_ttl_config(r_dict)

                    elif self.table_name == "agent_memory":
                        conn.execute("""
                            INSERT OR REPLACE INTO agent_memory
                            (id, checkpoint_id, session_id, memory_key, memory_value, confidence, source, created_at, last_verified_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_id,
                            str(r_dict.get("checkpoint_id") or ""),
                            str(r_dict.get("session_id") or ""),
                            str(r_dict.get("memory_key") or ""),
                            str(r_dict.get("memory_value") or ""),
                            float(r_dict.get("confidence") or 0.8),
                            str(r_dict.get("source") or "agent_execution"),
                            r_dict.get("created_at", now_str),
                            r_dict.get("last_verified_at"),
                        ))

                    inserted_rows.append(r_dict)
                conn.commit()
            return ResilientResponse(inserted_rows)

        elif self._action == "update":
            with _get_conn() as conn:
                set_parts = []
                vals = []
                for k, v in (self._update_data or {}).items():
                    set_parts.append(f"{k} = ?")
                    if isinstance(v, bool):
                        vals.append(1 if v else 0)
                    elif isinstance(v, (list, dict)):
                        vals.append(json.dumps(v, default=str))
                    else:
                        vals.append(v)
                where_parts, where_vals = self._build_where()
                vals.extend(where_vals)
                sql = f"UPDATE {self.table_name} SET {', '.join(set_parts)}"
                if where_parts:
                    sql += f" WHERE {' AND '.join(where_parts)}"
                conn.execute(sql, vals)
                conn.commit()
            return ResilientResponse([self._update_data or {}])

        elif self._action == "delete":
            with _get_conn() as conn:
                where_parts, vals = self._build_where()
                sql = f"DELETE FROM {self.table_name}"
                if where_parts:
                    sql += f" WHERE {' AND '.join(where_parts)}"
                conn.execute(sql, vals)
                conn.commit()
            return ResilientResponse([])

        elif self._action == "select":
            with _get_conn() as conn:
                where_parts, vals = self._build_where()
                sql = f"SELECT * FROM {self.table_name}"
                if where_parts:
                    sql += f" WHERE {' AND '.join(where_parts)}"
                if self._order_col:
                    sql += f" ORDER BY {self._order_col} {'DESC' if self._order_desc else 'ASC'}"
                if self._limit_val:
                    sql += f" LIMIT {int(self._limit_val)}"
                cursor = conn.execute(sql, vals)
                rows = [dict(r) for r in cursor.fetchall()]

                # Type conversions
                for r in rows:
                    if "schema_valid" in r:
                        r["schema_valid"] = bool(r["schema_valid"])
                    if "outcome_reported" in r:
                        r["outcome_reported"] = bool(r["outcome_reported"])
                    if "contract_json" in r and isinstance(r["contract_json"], str):
                        try:
                            r["contract_json"] = json.loads(r["contract_json"])
                        except Exception:
                            pass
                    if "validation_errors" in r and isinstance(r["validation_errors"], str):
                        try:
                            r["validation_errors"] = json.loads(r["validation_errors"])
                        except Exception:
                            pass
                    if "diff_from_previous" in r and isinstance(r["diff_from_previous"], str):
                        try:
                            r["diff_from_previous"] = json.loads(r["diff_from_previous"])
                        except Exception:
                            pass
                    if "resolved" in r:
                        r["resolved"] = bool(r["resolved"])
                    if "is_valid" in r:
                        r["is_valid"] = bool(r["is_valid"])
                    if "is_active" in r:
                        r["is_active"] = bool(r["is_active"])
                    if "acknowledged" in r:
                        r["acknowledged"] = bool(r["acknowledged"])
                    if "auto_cleanup_enabled" in r:
                        r["auto_cleanup_enabled"] = bool(r["auto_cleanup_enabled"])
                    for jcol in ["sections", "theme", "results", "involved_features", "resolution_strategies", "details", "synthesis_weights"]:
                        if jcol in r and isinstance(r[jcol], str):
                            try:
                                r[jcol] = json.loads(r[jcol])
                            except Exception:
                                pass
                return ResilientResponse(rows)

        return ResilientResponse([])

    def _sync_to_databricks_version(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            row_id = r_dict.get("id")
            fam_id = r_dict.get("contract_family_id")
            rc_id = r_dict.get("resume_contract_id")
            ver = int(r_dict.get("version", 1))
            cl = str(r_dict.get("changelog", "")).replace("'", "''")
            diff_str = json.dumps(r_dict.get("diff_from_previous"), default=str)
            diff = diff_str.replace("'", "''")
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.contract_versions
            VALUES ('{row_id}', '{fam_id}', '{rc_id}', {ver}, '{cl}', '{diff}', current_timestamp())
            """
            self.dx._run_sql(sql)
        except Exception as e:
            logger.debug(f"Databricks version sync note: {e}")

    def _sync_to_databricks_execution(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            row_id = r_dict.get("id")
            rc_id = r_dict.get("resume_contract_id")
            ctype = str(r_dict.get("consumer_type"))
            cident = str(r_dict.get("consumer_identifier") or "")
            rep = "true" if r_dict.get("outcome_reported") else "false"
            if r_dict.get("outcome_notes"):
                safe_notes = str(r_dict.get("outcome_notes")).replace("'", "''")
                notes = f"'{safe_notes}'"
            else:
                notes = "null"
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.contract_executions
            VALUES ('{row_id}', '{rc_id}', '{ctype}', '{cident}', current_timestamp(), {rep}, {notes})
            """
            self.dx._run_sql(sql)
        except Exception as e:
            logger.debug(f"Databricks execution sync note: {e}")

    def _sync_to_databricks_integrity_history(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.integrity_score_history
            VALUES (:id, :session_id, :checkpoint_id, :integrity_score, :reason, :stale_memory_count, :conflict_count, current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "session_id", "value": str(r_dict.get("session_id")), "type": "STRING"},
                    {"name": "checkpoint_id", "value": str(r_dict.get("checkpoint_id") or ""), "type": "STRING"},
                    {"name": "integrity_score", "value": str(r_dict.get("integrity_score") or 0.0), "type": "DOUBLE"},
                    {"name": "reason", "value": str(r_dict.get("reason") or ""), "type": "STRING"},
                    {"name": "stale_memory_count", "value": str(r_dict.get("stale_memory_count") or 0), "type": "INT"},
                    {"name": "conflict_count", "value": str(r_dict.get("conflict_count") or 0), "type": "INT"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks integrity history sync note: {e}")

    def _sync_to_databricks_memory_conflict(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            rep = "true" if r_dict.get("resolved") else "false"
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.memory_conflicts
            VALUES (:id, :session_id, :memory_key_a, :memory_key_b, :conflict_reason, {rep}, :resolution_notes, current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "session_id", "value": str(r_dict.get("session_id")), "type": "STRING"},
                    {"name": "memory_key_a", "value": str(r_dict.get("memory_key_a")), "type": "STRING"},
                    {"name": "memory_key_b", "value": str(r_dict.get("memory_key_b")), "type": "STRING"},
                    {"name": "conflict_reason", "value": str(r_dict.get("conflict_reason") or ""), "type": "STRING"},
                    {"name": "resolution_notes", "value": str(r_dict.get("resolution_notes") or ""), "type": "STRING"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks memory conflict sync note: {e}")

    def _sync_to_databricks_preflight_override(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.preflight_overrides
            VALUES (:id, :planned_approach, :similarity_score, :matched_dead_end_id, :override_reason, :override_category, :approver, :risk_level, current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "planned_approach", "value": str(r_dict.get("planned_approach") or ""), "type": "STRING"},
                    {"name": "similarity_score", "value": str(r_dict.get("similarity_score") or 0.0), "type": "DOUBLE"},
                    {"name": "matched_dead_end_id", "value": str(r_dict.get("matched_dead_end_id") or ""), "type": "STRING"},
                    {"name": "override_reason", "value": str(r_dict.get("override_reason") or ""), "type": "STRING"},
                    {"name": "override_category", "value": str(r_dict.get("override_category") or "technical_necessity"), "type": "STRING"},
                    {"name": "approver", "value": str(r_dict.get("approver") or ""), "type": "STRING"},
                    {"name": "risk_level", "value": str(r_dict.get("risk_level") or "MODERATE"), "type": "STRING"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks preflight override sync note: {e}")

    def _sync_to_databricks_cluster(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.dead_end_clusters
            VALUES (:id, :project_name, :cluster_key, :representative_root_cause, :member_count, current_timestamp(), current_timestamp(), :common_suggested_fix, :custom_name, :ai_suggested_name, :name_reasoning)
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "project_name", "value": str(r_dict.get("project_name") or "checkpoint-dx"), "type": "STRING"},
                    {"name": "cluster_key", "value": str(r_dict.get("cluster_key") or ""), "type": "STRING"},
                    {"name": "representative_root_cause", "value": str(r_dict.get("representative_root_cause") or ""), "type": "STRING"},
                    {"name": "member_count", "value": str(r_dict.get("member_count") or 1), "type": "INT"},
                    {"name": "common_suggested_fix", "value": str(r_dict.get("common_suggested_fix") or ""), "type": "STRING"},
                    {"name": "custom_name", "value": str(r_dict.get("custom_name") or ""), "type": "STRING"},
                    {"name": "ai_suggested_name", "value": str(r_dict.get("ai_suggested_name") or ""), "type": "STRING"},
                    {"name": "name_reasoning", "value": str(r_dict.get("name_reasoning") or ""), "type": "STRING"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks dead_end_clusters sync note: {e}")

    def _sync_to_databricks_status_history(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.requirement_status_history
            VALUES (:id, :requirement_id, :checkpoint_id, :old_status, :new_status, :changed_by, :change_reason, :duration_in_prev_status_hours, current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "requirement_id", "value": str(r_dict.get("requirement_id") or ""), "type": "STRING"},
                    {"name": "checkpoint_id", "value": str(r_dict.get("checkpoint_id") or ""), "type": "STRING"},
                    {"name": "old_status", "value": str(r_dict.get("old_status") or ""), "type": "STRING"},
                    {"name": "new_status", "value": str(r_dict.get("new_status") or ""), "type": "STRING"},
                    {"name": "changed_by", "value": str(r_dict.get("changed_by") or "user"), "type": "STRING"},
                    {"name": "change_reason", "value": str(r_dict.get("change_reason") or ""), "type": "STRING"},
                    {"name": "duration_in_prev_status_hours", "value": str(r_dict.get("duration_in_prev_status_hours") or 0.0), "type": "DOUBLE"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks requirement status history sync note: {e}")

    def _sync_to_databricks_compliance_violation(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.compliance_violations
            VALUES (:id, :checkpoint_id, :clause_id, :clause_text, :violation_type, :severity, :remediation_deadline, :assigned_to, :status, :resolution_notes, current_timestamp(), NULL)
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "checkpoint_id", "value": str(r_dict.get("checkpoint_id") or ""), "type": "STRING"},
                    {"name": "clause_id", "value": str(r_dict.get("clause_id") or ""), "type": "STRING"},
                    {"name": "clause_text", "value": str(r_dict.get("clause_text") or ""), "type": "STRING"},
                    {"name": "violation_type", "value": str(r_dict.get("violation_type") or "functional"), "type": "STRING"},
                    {"name": "severity", "value": str(r_dict.get("severity") or "medium"), "type": "STRING"},
                    {"name": "remediation_deadline", "value": str(r_dict.get("remediation_deadline") or ""), "type": "STRING"},
                    {"name": "assigned_to", "value": str(r_dict.get("assigned_to") or "unassigned"), "type": "STRING"},
                    {"name": "status", "value": str(r_dict.get("status") or "open"), "type": "STRING"},
                    {"name": "resolution_notes", "value": str(r_dict.get("resolution_notes") or ""), "type": "STRING"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks compliance violation sync note: {e}")

    def _sync_to_databricks_compliance_history(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.compliance_history
            VALUES (:id, :checkpoint_id, :overall_score, :total_clauses, :compliant_clauses, current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "checkpoint_id", "value": str(r_dict.get("checkpoint_id") or ""), "type": "STRING"},
                    {"name": "overall_score", "value": str(r_dict.get("overall_score") or 0.0), "type": "DOUBLE"},
                    {"name": "total_clauses", "value": str(r_dict.get("total_clauses") or 0), "type": "INT"},
                    {"name": "compliant_clauses", "value": str(r_dict.get("compliant_clauses") or 0), "type": "INT"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks compliance history sync note: {e}")

    def _sync_to_databricks_integrity_trend(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.integrity_trends
            VALUES (:id, :session_id, :checkpoint_id, :integrity_score, :integrity_reason, current_timestamp(), :trend_direction, :trend_magnitude)
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "session_id", "value": str(r_dict.get("session_id") or ""), "type": "STRING"},
                    {"name": "checkpoint_id", "value": str(r_dict.get("checkpoint_id") or ""), "type": "STRING"},
                    {"name": "integrity_score", "value": str(r_dict.get("integrity_score") or 0.0), "type": "DOUBLE"},
                    {"name": "integrity_reason", "value": str(r_dict.get("integrity_reason") or ""), "type": "STRING"},
                    {"name": "trend_direction", "value": str(r_dict.get("trend_direction") or "stable"), "type": "STRING"},
                    {"name": "trend_magnitude", "value": str(r_dict.get("trend_magnitude") or 0.0), "type": "DOUBLE"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks integrity trend sync note: {e}")

    def _sync_to_databricks_integrity_alert(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.integrity_alerts
            VALUES (:id, :session_id, :alert_type, :severity, :message, current_timestamp(), :acknowledged, NULL)
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "session_id", "value": str(r_dict.get("session_id") or ""), "type": "STRING"},
                    {"name": "alert_type", "value": str(r_dict.get("alert_type") or "anomaly_detected"), "type": "STRING"},
                    {"name": "severity", "value": str(r_dict.get("severity") or "minor"), "type": "STRING"},
                    {"name": "message", "value": str(r_dict.get("message") or ""), "type": "STRING"},
                    {"name": "acknowledged", "value": "true" if r_dict.get("acknowledged") else "false", "type": "BOOLEAN"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks integrity alert sync note: {e}")

    def _sync_to_databricks_memory_ttl_config(self, r_dict: dict):
        if not self.dx or not hasattr(self.dx, "_run_sql"):
            return
        try:
            sql = f"""
            INSERT INTO {self.dx.catalog}.{self.dx.schema}.memory_ttl_config
            VALUES (:id, :session_id, :ttl_days, :auto_cleanup_enabled, current_timestamp(), current_timestamp())
            """
            self.dx._run_sql(
                sql,
                parameters=[
                    {"name": "id", "value": str(r_dict.get("id")), "type": "STRING"},
                    {"name": "session_id", "value": str(r_dict.get("session_id") or ""), "type": "STRING"},
                    {"name": "ttl_days", "value": str(r_dict.get("ttl_days") or 30), "type": "INT"},
                    {"name": "auto_cleanup_enabled", "value": "true" if r_dict.get("auto_cleanup_enabled", True) else "false", "type": "BOOLEAN"},
                ]
            )
        except Exception as e:
            logger.debug(f"Databricks memory ttl config sync note: {e}")



