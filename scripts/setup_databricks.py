# scripts/setup_databricks.py
"""
Setup script for Databricks Unity Catalog, Delta Tables, Volumes, and Ingest Job.
Implements:
- Fix 1: Creation of raw_exports volume
- Fix 2: Ephemeral new_cluster fallback for blank DATABRICKS_CLUSTER_ID
- Fix 3/Check 5: Verified AWS node type m5.large & spark version 14.3.x-scala2.12
- Automatic workspace notebook upload
"""
import os
import sys
import base64
import requests

# Allow importing config when run from project root or scripts directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import (
    DATABRICKS_HOST as host,
    DATABRICKS_TOKEN as token,
    DATABRICKS_CATALOG as catalog,
    DATABRICKS_SCHEMA as schema,
    DATABRICKS_WAREHOUSE_ID as warehouse_id,
    DATABRICKS_CLUSTER_ID as cluster_id,
)

def upload_notebook_to_workspace(local_path: str, workspace_path: str):
    """Uploads a local Python notebook file to Databricks workspace."""
    if not os.path.exists(local_path):
        return
    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Create parent directory
    parent_dir = os.path.dirname(workspace_path).replace("\\", "/")
    requests.post(
        f"{host}/api/2.0/workspace/mkdirs",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"path": parent_dir},
    )

    resp = requests.post(
        f"{host}/api/2.0/workspace/import",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "path": workspace_path,
            "format": "SOURCE",
            "language": "PYTHON",
            "content": b64_content,
            "overwrite": True,
        },
    )
    print(f"Uploaded {local_path} -> {workspace_path}: {resp.status_code}")

def setup_unity_catalog():
    print(f"Setting up Unity Catalog: {catalog}.{schema}...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Create Catalog & Schema
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient(host=host, token=token)
        for step in [lambda: client.catalogs.create(catalog), lambda: client.schemas.create(name=schema, catalog_name=catalog)]:
            try:
                step()
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Note on catalog/schema step: {e}")
    except Exception as e:
        print(f"SDK Client initialization note: {e}")

    # 2. Create memory store (if supported)
    try:
        mem_resp = requests.put(
            f"{host}/api/2.1/unity-catalog/memory-stores/{catalog}.{schema}.ledger_memory",
            headers=headers,
            json={"comment": "Checkpoint requirement/dead-end memory for resume-integrity checks"},
        )
        print(f"Memory store creation: {mem_resp.status_code}")
    except Exception as e:
        print(f"Memory store note: {e}")

    # 3. Create Tables and Volumes via SQL Statements API
    ddls = [
        # FIX 1: Volume created before anything tries to read/write it
        f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw_exports",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.requirements (
            checkpoint_id STRING, session_id STRING, requirement_text STRING,
            status STRING DEFAULT 'not_started', created_at TIMESTAMP,
            priority_tier STRING, moscow STRING, effort_points INT, owner STRING) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.requirements ADD COLUMNS (priority_tier STRING, moscow STRING, effort_points INT, owner STRING, status_changed_at TIMESTAMP, status_changed_by STRING, previous_status STRING, status_change_reason STRING, business_impact_score INT, urgency_score INT, risk_score INT, calculated_priority_score DOUBLE, calculated_priority_tier STRING, priority_override_reason STRING, rice_reach INT, rice_impact INT, rice_confidence DOUBLE, rice_effort DOUBLE, rice_score DOUBLE, rice_rank INT, gherkin_scenarios STRING, complexity_factors STRING)",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.requirement_status_history (
            id STRING, requirement_id STRING, checkpoint_id STRING, old_status STRING,
            new_status STRING, changed_by STRING, change_reason STRING,
            duration_in_prev_status_hours DOUBLE, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.deadend_candidates (
            checkpoint_id STRING, session_id STRING, timestamp TIMESTAMP, transcript STRING,
            agent_name STRING, model_name STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.dead_end_traces_fallback (
            checkpoint_id STRING, dead_end_type STRING, root_cause STRING, suggested_fix STRING,
            confidence FLOAT, failed_attempts INT, alternative_approaches ARRAY<STRING>, created_at TIMESTAMP,
            severity STRING, cluster_key STRING, fix_effectiveness STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.dead_end_clusters (
            id STRING, project_name STRING, cluster_key STRING, representative_root_cause STRING,
            member_count INT, first_seen_at TIMESTAMP, last_seen_at TIMESTAMP, common_suggested_fix STRING,
            custom_name STRING, ai_suggested_name STRING, name_reasoning STRING) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.dead_end_clusters ADD COLUMNS (custom_name STRING, ai_suggested_name STRING, name_reasoning STRING)",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.preflight_overrides (
            id STRING, checkpoint_id STRING, session_id STRING, candidate_approach STRING,
            jaccard_similarity DOUBLE, warning_threshold DOUBLE, matched_failures STRING,
            override_reason STRING, override_category STRING, requires_approval BOOLEAN,
            approval_status STRING, approved_by STRING, risk_score INT, risk_category STRING,
            fix_applied STRING, fix_outcome STRING, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.intent_traces_fallback (
            checkpoint_id STRING, intent_text STRING, implementation_status STRING,
            confidence FLOAT, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.agent_memory (
            checkpoint_id STRING, session_id STRING, memory_key STRING,
            memory_value STRING, confidence FLOAT, source STRING, created_at TIMESTAMP,
            last_verified_at TIMESTAMP) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.agent_memory ADD COLUMNS (last_verified_at TIMESTAMP)",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.integrity_score_history (
            id STRING, session_id STRING, checkpoint_id STRING, integrity_score DOUBLE,
            reason STRING, stale_memory_count INT, conflict_count INT, recorded_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.memory_conflicts (
            id STRING, session_id STRING, memory_key_a STRING, memory_key_b STRING,
            conflict_reason STRING, resolved BOOLEAN, resolution_notes STRING, created_at TIMESTAMP) USING DELTA""",
        # Compliance Violations & Compliance History (Feature 3 Hardened+)
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.compliance_violations (
            id STRING, checkpoint_id STRING, clause_id STRING, clause_text STRING,
            violation_type STRING, severity STRING, remediation_deadline STRING,
            assigned_to STRING, status STRING, resolution_notes STRING, created_at TIMESTAMP, resolved_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.compliance_history (
            id STRING, checkpoint_id STRING, overall_score DOUBLE, total_clauses INT,
            compliant_clauses INT, recorded_at TIMESTAMP) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.intent_conformance ADD COLUMNS (conformance_grade STRING, semantic_alignment DOUBLE, coverage_completeness DOUBLE, code_quality DOUBLE, test_coverage DOUBLE, calibrated_confidence DOUBLE)",
        # Resume Contracts & Governance System (Feature 4 Hardened+)
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.resume_contracts (
            id STRING, checkpoint_id STRING, session_id STRING, template STRING,
            version INT, contract_json STRING, schema_valid BOOLEAN, validation_errors STRING,
            synthesis_weights STRING, contract_purpose STRING, created_at TIMESTAMP) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.resume_contracts ADD COLUMNS (synthesis_weights STRING, contract_purpose STRING)",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.contract_versions (
            id STRING, contract_family_id STRING, resume_contract_id STRING,
            version INT, changelog STRING, diff_from_previous STRING, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.contract_executions (
            id STRING, resume_contract_id STRING, consumer_type STRING, consumer_identifier STRING,
            loaded_at TIMESTAMP, outcome_reported BOOLEAN, outcome_notes STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.custom_templates (
            id STRING, template_name STRING, target_audience STRING, created_by STRING,
            sections STRING, theme STRING, is_valid BOOLEAN, validation_errors STRING, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.template_versions (
            id STRING, template_id STRING, version_number INT, changelog STRING,
            sections STRING, is_active BOOLEAN, created_by STRING, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.template_ab_tests (
            id STRING, test_name STRING, variant_a_id STRING, variant_b_id STRING,
            traffic_split DOUBLE, status STRING, results STRING, start_date TIMESTAMP,
            end_date TIMESTAMP, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.contract_conflicts (
            id STRING, checkpoint_id STRING, session_id STRING, conflict_type STRING,
            severity STRING, description STRING, involved_features STRING, resolution_strategies STRING,
            resolved BOOLEAN, resolution_strategy_id STRING, resolution_notes STRING,
            created_at TIMESTAMP, resolved_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.contract_interactions (
            id STRING, resume_contract_id STRING, consumer_type STRING, interaction_type STRING,
            section_name STRING, duration_seconds DOUBLE, scroll_depth DOUBLE, details STRING,
            created_at TIMESTAMP) USING DELTA""",
        # Resume Integrity Check (Feature 5 Hardened+)
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.integrity_trends (
            id STRING, session_id STRING, checkpoint_id STRING, integrity_score DOUBLE,
            integrity_reason STRING, recorded_at TIMESTAMP, trend_direction STRING, trend_magnitude DOUBLE) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.integrity_alerts (
            id STRING, session_id STRING, alert_type STRING, severity STRING,
            message STRING, detected_at TIMESTAMP, acknowledged BOOLEAN, resolved_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.memory_ttl_config (
            id STRING, session_id STRING, ttl_days INT, auto_cleanup_enabled BOOLEAN,
            created_at TIMESTAMP, updated_at TIMESTAMP) USING DELTA""",
        f"ALTER TABLE {catalog}.{schema}.agent_memory ADD COLUMNS (multi_session_integrity_score DOUBLE, multi_session_integrity_reason STRING, integrity_trend_7d DOUBLE, integrity_anomaly_detected BOOLEAN, last_cleanup_at TIMESTAMP)",
        # Core tables populated by transform job
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.checkpoints_normalized (
            checkpoint_id STRING, session_id STRING, branch STRING, prompt_text STRING,
            file_changes ARRAY<STRUCT<file_path: STRING, diff_hunk: STRING>>,
            agent_name STRING, model_name STRING, timestamp STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.prompt_clauses (
            checkpoint_id STRING, session_id STRING, clause STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.intent_conformance (
            checkpoint_id STRING, clause STRING, implementation_status STRING,
            confidence_score DOUBLE) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.dead_end_traces (
            trace_id STRING, start_time TIMESTAMP, tags MAP<STRING, STRING>,
            spans ARRAY<STRUCT<outputs: MAP<STRING, STRING>>>) USING DELTA""",
        f"""CREATE OR REPLACE VIEW {catalog}.{schema}.intent_metrics AS
            SELECT
              tags['checkpoint_id'] AS checkpoint_id,
              tags['project_name'] AS project_name,
              tags['intent_status'] AS status,
              tags['intent_category'] AS category,
              COUNT(*) AS num_intents,
              AVG(CAST(spans[0].outputs['confidence'] AS DOUBLE)) AS avg_confidence,
              MIN(CAST(spans[0].outputs['confidence'] AS DOUBLE)) AS min_confidence,
              MAX(CAST(spans[0].outputs['confidence'] AS DOUBLE)) AS max_confidence,
              MIN(start_time) AS first_seen,
              MAX(start_time) AS last_seen,
              COUNT(DISTINCT trace_id) AS trace_count
            FROM {catalog}.{schema}.dead_end_traces
            WHERE tags['feature'] = 'intent_conformance'
            GROUP BY tags['checkpoint_id'], tags['project_name'], tags['intent_status'], tags['intent_category']""",
        f"""CREATE OR REPLACE VIEW {catalog}.{schema}.dead_end_metrics AS
            SELECT
              tags['checkpoint_id'] AS checkpoint_id,
              tags['project_name'] AS project_name,
              spans[0].outputs['dead_end_type'] AS type,
              spans[0].outputs['root_cause'] AS cause,
              spans[0].outputs['suggested_fix'] AS suggested_fix,
              CAST(spans[0].outputs['confidence'] AS DOUBLE) AS confidence,
              CAST(spans[0].outputs['failed_attempts'] AS INT) AS failed_attempts,
              start_time,
              trace_id,
              DATE_FORMAT(start_time, 'yyyy-MM-dd') AS date_bucket
            FROM {catalog}.{schema}.dead_end_traces
            WHERE tags['feature'] = 'dead_end_registry'
            ORDER BY start_time DESC""",
        f"""CREATE OR REPLACE VIEW {catalog}.{schema}.checkpoint_health AS
            SELECT
              tags['checkpoint_id'] AS checkpoint_id,
              COUNT(CASE WHEN tags['intent_status'] = 'met' THEN 1 END) AS intents_met,
              COUNT(CASE WHEN tags['intent_status'] = 'partial' THEN 1 END) AS intents_partial,
              COUNT(CASE WHEN tags['intent_status'] = 'missing' THEN 1 END) AS intents_missing,
              COUNT(CASE WHEN tags['intent_status'] = 'drift' THEN 1 END) AS intents_drift,
              COUNT(DISTINCT CASE WHEN tags['feature'] = 'dead_end_registry' THEN trace_id END) AS dead_end_count,
              AVG(CASE WHEN tags['feature'] = 'intent_conformance'
                  THEN CAST(spans[0].outputs['confidence'] AS DOUBLE) END) AS avg_intent_confidence,
              MAX(start_time) AS last_activity,
              COUNT(DISTINCT trace_id) AS total_traces
            FROM {catalog}.{schema}.dead_end_traces
            GROUP BY tags['checkpoint_id']""",
    ]

    for ddl in ddls:
        resp = requests.post(
            f"{host}/api/2.0/sql/statements",
            headers=headers,
            json={"warehouse_id": warehouse_id, "statement": ddl, "wait_timeout": "30s"},
        )
        print(f" - Executed DDL ({resp.status_code}): {ddl.split('(')[0].split('USING')[0].strip()[:60]}...")

    # 4. Upload Notebooks & Supporting Modules to Databricks Workspace
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    upload_notebook_to_workspace(
        os.path.join(project_root, "notebooks", "transform.py"),
        "/Workspace/checkpoint_dx/transform",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "notebooks", "run_pipeline_glue.py"),
        "/Workspace/checkpoint_dx/run_pipeline_glue",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "config.py"),
        "/Workspace/checkpoint_dx/config",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "pipeline_glue.py"),
        "/Workspace/checkpoint_dx/pipeline_glue",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "feature_d.py"),
        "/Workspace/checkpoint_dx/feature_d",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "lib", "__init__.py"),
        "/Workspace/checkpoint_dx/lib/__init__",
    )
    upload_notebook_to_workspace(
        os.path.join(project_root, "lib", "checkpoint_dx.py"),
        "/Workspace/checkpoint_dx/lib/checkpoint_dx",
    )

    # FIX 2 (v9) & Check 5: Cluster specification & Serverless support
    # If a cluster ID is supplied, use it; otherwise, use serverless compute (default on modern Databricks)
    # with an automatic fallback to ephemeral new_cluster (m5.large on AWS) if classic compute is required.
    if cluster_id:
        cluster_spec = {"existing_cluster_id": cluster_id}
        print(f"Using existing cluster: {cluster_id}")
    else:
        # Serverless compute is preferred/enforced in modern workspaces (no cluster_spec needed)
        cluster_spec = {}
        print("No DATABRICKS_CLUSTER_ID set — utilizing Databricks Serverless Compute.")

    def build_payload(spec):
        return {
            "run_name": "checkpoint_dx_ingest_and_glue",
            "tasks": [
                {
                    "task_key": "ingest_and_transform",
                    "notebook_task": {"notebook_path": "/Workspace/checkpoint_dx/transform"},
                    **spec,
                },
                {
                    "task_key": "pipeline_glue",
                    "depends_on": [{"task_key": "ingest_and_transform"}],
                    "notebook_task": {"notebook_path": "/Workspace/checkpoint_dx/run_pipeline_glue"},
                    **spec,
                },
            ],
        }

    job_resp = requests.post(
        f"{host}/api/2.1/jobs/runs/submit",
        headers=headers,
        json=build_payload(cluster_spec),
    )

    # If serverless is not supported and classic compute is required, retry with ephemeral new_cluster
    if job_resp.status_code == 400 and "serverless" not in job_resp.text.lower():
        print("Serverless compute not default, falling back to ephemeral new_cluster...")
        ephemeral_spec = {
            "new_cluster": {
                "spark_version": "14.3.x-scala2.12",
                "node_type_id": "m5.large",
                "num_workers": 1,
            }
        }
        job_resp = requests.post(
            f"{host}/api/2.1/jobs/runs/submit",
            headers=headers,
            json=build_payload(ephemeral_spec),
        )

    print("Job submitted:", job_resp.status_code, job_resp.text[:300])
    print(f"Setup complete: {catalog}.{schema}")
    return job_resp.status_code in (200, 201)

if __name__ == "__main__":
    setup_unity_catalog()
