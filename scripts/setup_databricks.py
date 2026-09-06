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
            status STRING DEFAULT 'not_started', created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.deadend_candidates (
            checkpoint_id STRING, session_id STRING, timestamp TIMESTAMP, transcript STRING,
            agent_name STRING, model_name STRING) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.dead_end_traces_fallback (
            checkpoint_id STRING, dead_end_type STRING, root_cause STRING, suggested_fix STRING,
            confidence FLOAT, failed_attempts INT, alternative_approaches ARRAY<STRING>, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.intent_traces_fallback (
            checkpoint_id STRING, intent_text STRING, implementation_status STRING,
            confidence FLOAT, created_at TIMESTAMP) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.agent_memory (
            checkpoint_id STRING, session_id STRING, memory_key STRING,
            memory_value STRING, confidence FLOAT, source STRING, created_at TIMESTAMP) USING DELTA""",
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
