# Checkpoint-Native DX (v9)

**Checkpoint-Native DX** is an enterprise developer experience platform that captures, structures, and analyzes AI coding agent checkpoints across 5 standalone features. It integrates git/Entire local checkpoints with **Databricks Unity Catalog, Delta Lake, and Supabase** to deliver persistent context, intent conformance, dead-end detection, and reliable agent resume contracts.

---

## 1. Architecture

```
Local machine: `entire checkpoint list --json` (via lib/entire_adapter.py)
        │
        ▼  scripts/export_checkpoints_to_databricks.py uploads to Unity Catalog Volume
        │
        ▼
Checkpoint Ingest Job (Databricks Job, task 1: ingest_and_transform)
        │
        ▼
Pipeline Glue (pipeline_glue.py / notebooks/run_pipeline_glue.py)
  - Powered by Groq LLM (llama-3.3-70b-versatile) for dead-end extraction
  - Syncs checkpoints, requirements, dead-ends (deduped), intents into Supabase
  - Writes a memory entry per synced requirement into agent_memory
  - Reconciles superseded requirements in Supabase AND Delta
        │
        ├───────────┬───────────┬───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   FEATURE A    FEATURE B   FEATURE C   FEATURE D   FEATURE E
   Dead-End     Requirement Intent      Agent       Resume-
   Registry     Ledger      Conformance Resume      Integrity
   (Special)    (Advanced)  Diff (Core) Contract    Checking
                                        (Nuclear)   (Intelligence
                                                     & Resilience)
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                                 ▼
                    Shared data: Databricks Delta + Supabase
```

---

## 2. Five Standalone Features

1. **Feature A (Special Tier) — Dead-End Registry**:
   Persists abandoned technical paths, root causes, and suggested fixes into MLflow Unity Catalog traces (`dead_end_traces`) with seamless Delta fallback (`dead_end_traces_fallback`) using typed array syntax.
2. **Feature B (Advanced Tier) — Requirement Ledger**:
   Maintains the complete lifecycle of natural-language asks (`not_started`, `in_progress`, `done`, `superseded`). Reconciles superseded items with prompt history and keeps Supabase, Delta, and `agent_memory` in full parity.
3. **Feature C (Core Tier) — Intent Conformance Diff**:
   Cross-references segmented prompt clauses with code diff hunks to surface implementation status (`met`, `gap`, `scope_creep`).
4. **Feature D (Nuclear Tier) — Agent Resume Contract**:
   Synthesizes unresolved requirements (B), do-not-retry dead ends (A), flagged gaps (C), and resume safety scores (E) into a structured JSON contract briefing a second agent session to seamlessly continue work.
5. **Feature E (Intelligence & Resilience Tier) — Resume-Integrity Checking & Agent Memory**:
   Verifies whether open requirements have matching session memory, blocks unsafe resumes with human-readable diagnostic reasons, and incorporates real-time human feedback loop adjustments.

---

## 3. Setup & Execution Order

> [!IMPORTANT]
> **Credentials & Clean Checkout Policy**:
> Copy `config.py.example` to `config.py` and fill in real credentials — this repo is not runnable by a third party without supplying their own, by design, since the values are live and belong to one workspace. `config.py` is strictly gitignored for security.

### Step 1: Export Local Checkpoints to Databricks Volume
Bridges local git/Entire checkpoint history to the Databricks Unity Catalog Volume:
```bash
python scripts/export_checkpoints_to_databricks.py
```
*Note: If `entire` CLI is not installed locally, the script automatically exports verified sample checkpoints matching the Section 4.5 schema.*

### Step 2: Apply Supabase Database Schema
Execute the SQL schema in your Supabase project (via SQL Editor in the Supabase Dashboard or `psql`):
```bash
# Option A: Run contents of supabase/schema.sql in Supabase Dashboard SQL Editor
# Option B: Run via psql
psql "<SUPABASE_URL_CONNECTION_STRING>" -f supabase/schema.sql
```

### Step 3: Setup Databricks & Trigger Ingest Job
Initializes Unity Catalog catalogs, schemas, volumes, and Delta tables, uploads notebook tasks, and triggers the ingest & pipeline glue job:
```bash
python scripts/setup_databricks.py
```
*Note: If `DATABRICKS_CLUSTER_ID` is left empty, the script automatically provisions an ephemeral cluster using verified AWS node type `m5.large` and runtime `14.3.x-scala2.12`.*

---

## 4. Re-Running the Export Step

Whenever new checkpoints exist locally that haven't been synced:
```bash
# 1. Re-export new checkpoints to Databricks Volume
python scripts/export_checkpoints_to_databricks.py

# 2. Re-trigger the ingest job
python scripts/setup_databricks.py
```

---

## 5. Launching the 5-Panel Interactive UI

Launch the Streamlit dashboard to explore and interact with all 5 feature panels:
```bash
streamlit run app.py
```

### Panels Overview:
- **Tab A (Dead-End Registry)**: View root causes, suggested fixes, fallback indicators, and execute live Databricks SQL trace queries.
- **Tab B (Requirement Ledger)**: Inspect requirement statuses, view supersession evidence, update statuses, or add new requirements with symmetric memory sync.
- **Tab C (Intent Conformance)**: Review clause conformance diffs (`met`/`gap`/`scope_creep`) and confidence metrics.
- **Tab D (Resume Contract)**: Click **"Generate Resume Contract"** (resolves `session_id` from checkpoint first), view the synthesized JSON briefing, and download it.
- **Tab E (Resume-Integrity & Memory)**: Run real-time integrity safety checks, inspect session memory entries, and vote with thumbs-down/thumbs-up to adjust confidence weights.

---

## 6. Known Limitations & Design Choices (Honest MVP Disclosures)

1. **Entire Checkpoint Adapter Integration**: Real Entire CLI integration is implemented in `lib/entire_adapter.py` via `entire checkpoint list --json` and commit trailers (`Entire-Checkpoint: <id>`). Because native Entire hook sessions require active CLI hook triggers, the system supports both live CLI execution and verified fixture checkpoints in `tests/fixtures/entire_checkpoints.json`.
2. **Groq Fast Extraction**: Utilizes Groq's high-speed `llama-3.3-70b-versatile` model for dead-end identification and intent gap classification from agent transcripts.
3. **Token-Overlap Intent Matching**: Feature C currently uses a lexical token-overlap heuristic to correlate prompt clauses with diff hunks. This serves as an MVP substitute for semantic embeddings.
4. **MLflow Unity Catalog Trace Preview**: MLflow trace storage in Unity Catalog is supported with a seamless fallback to the Delta table (`dead_end_traces_fallback`) with typed array casting.

---

## 7. Live Demo Walkthrough (Video Script)

1. **[0:00 - 0:30] Checkpoint Discovery & Adapter**: Show Entire CLI commit trailer detection and `lib/entire_adapter.py` bridging checkpoint data into Databricks.
2. **[0:30 - 1:00] Databricks & Delta Pipeline**: Demonstrate the Unity Catalog Volume export (`checkpoints_export.json`) and 13 Delta tables synced via `pipeline_glue.py`.
3. **[1:00 - 1:45] Feature A & Feature B (UI)**: In the Streamlit UI, explore the **Dead-End Registry** (surfacing the Redis cache race condition) and the **Requirement Ledger** (showing superseded requirements).
4. **[1:45 - 2:30] Feature C & Feature D (The Agent Handoff)**: Show **Intent Conformance** gaps and click **"Generate Resume Contract"** on `chk-001`. Review the synthesized briefing JSON.
5. **[2:30 - 3:00] Feature E (Resume Integrity)**: Review the `1.0` integrity score and demonstrate human feedback confidence adjustment.

