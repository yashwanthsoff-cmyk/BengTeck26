# Entire Graph Evidence — Checkpoint-Native DX

This document provides formal evidence of Entire Graph capabilities (Semantic Code Search, Impact Analysis, and Semantic Diff) across the Checkpoint-Native DX repository.

---

## Evidence 1: Graph Search

**Query / Prompt:**
> "Show me all functions in this repo that write to the agent_memory table in Databricks"

**Result:**
The dependency graph identifies 5 locations where writes/updates to `agent_memory` occur:

1. **`lib/checkpoint_dx.py` — `CheckpointDX.store_in_agent_memory()`**
   - **Path:** `lib/checkpoint_dx.py#L318-L340`
   - **Operation:** SQL `INSERT INTO {catalog}.{schema}.agent_memory VALUES ('{checkpoint_id}', '{session_id}', '{key}', '{value}', {confidence}, '{source}', current_timestamp())`
   - **Description:** Core insertion method persisting structured session context.

2. **`lib/checkpoint_dx.py` — `CheckpointDX.record_human_feedback()`**
   - **Path:** `lib/checkpoint_dx.py#L371-L380`
   - **Operation:** SQL `UPDATE {catalog}.{schema}.agent_memory SET confidence = LEAST(1.0, GREATEST(0.0, confidence + {adjustment})) WHERE checkpoint_id = '{checkpoint_id}' AND memory_key = '{safe_key}'`
   - **Description:** Adjusts confidence weights (+0.1 for Accept, -0.2 for Reject) based on human-in-the-loop review.

3. **`lib/checkpoint_dx.py` — `CheckpointDX.add_requirements()`**
   - **Path:** `lib/checkpoint_dx.py#L198-L205`
   - **Operation:** Invokes `self.store_in_agent_memory()` for every newly added requirement to ensure full parity between ledger and agent context.

4. **`pipeline_glue.py` — `run_pipeline_glue()`**
   - **Path:** `pipeline_glue.py#L125-L140`
   - **Operation:** Invokes `dx.store_in_agent_memory()` during automated ingestion of prompt requirements.

5. **`notebooks/run_pipeline_glue.py` — `CheckpointDXPipeline.store_in_agent_memory()`**
   - **Path:** `notebooks/run_pipeline_glue.py#L160-L175`
   - **Operation:** Direct Delta write in the Databricks cluster runtime task.

---

## Evidence 2: Impact Analysis

**Query / Prompt:**
> "Before I change the checkpoint_id format from chk-001 to ULID, analyze what files and functions will be affected"

**Impact Graph Analysis:**

```
                        [ checkpoint_id: ULID Migration ]
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   [ Database Schemas ]       [ Core Logic & Engine ]       [ Adapters & UI ]
  • Supabase checkpoints       • lib/checkpoint_dx.py        • lib/entire_adapter.py
  • Databricks Delta:            - get_checkpoint()           • app.py (sidebar select)
    - checkpoints_normalized     - create_checkpoint()        • export_checkpoints_to_
    - requirements               - add_requirements()           databricks.py
    - intent_conformance         - set_requirement_status()   • tests/fixtures/entire_
    - deadend_candidates         - log_dead_end()               checkpoints.json
    - dead_end_traces_fallback   - log_intent()
    - agent_memory               - create_resume_contract()
```

### Affected Components:
1. **Foreign Key Integrity**:
   - Supabase child tables (`requirements`, `dead_end_summaries`, etc.) reference `checkpoints(id)` (Postgres UUID primary key), **not** the alphanumeric `checkpoint_id`. Thus, changing `checkpoint_id` strings does NOT trigger foreign key violations.
2. **Databricks Delta Tables**:
   - 5 Delta tables (`checkpoints_normalized`, `requirements`, `intent_conformance`, `deadend_candidates`, `dead_end_traces_fallback`) use `checkpoint_id` as a partition/filter column. Requires batch `UPDATE` to convert `chk-001..003` to 26-char ULIDs (`01M1TWB9...`).
3. **Entire Adapter & Parser**:
   - `lib/entire_adapter.py` must validate RFC 822 `Entire-Checkpoint: <id>` trailers supporting 26-char Crockford Base32.
4. **Test Fixtures & Verification**:
   - `tests/fixtures/entire_checkpoints.json` and `scripts/comprehensive_verification.py` Section [8/8] must verify `Data Source: REAL` instead of synthetic `chk-`.

---

## Evidence 3: Semantic Diff

**Query / Prompt:**
> "Show me the semantic differences between the initial architecture (first commit) and the final implementation (latest commit)"

**Semantic Evolution Summary:**

1. **Architecture Inception (`a0ab9da` -> `e035dac`)**:
   - Established the baseline 5-panel Streamlit dashboard, Supabase 8-table relational schema, and Databricks Unity Catalog Delta tables.
   - Introduced the Groq fast extraction pipeline (`llama-3.3-70b-versatile`) for dead-end and intent classification.

2. **ULID Checkpoint Native Migration (`1b5fb79` -> `81f0b19`)**:
   - Shifted from arbitrary synthetic strings (`chk-001`) to authentic 26-character Crockford Base32 time-sortable ULIDs (`01M1TWB9RANKAF8EPSTY7JRYE1`).
   - Synced ULID identifiers across Supabase, Databricks Unity Catalog Volume (`/Volumes/.../checkpoints_export.json`), and test fixtures.

3. **Concurrency Resilience & Conflict Handling (`cd193d7` -> `e4542af`)**:
   - Implemented MD5-scoped widget keys in Streamlit to resolve duplicate button key collisions.
   - Introduced automatic retry backoff in `_run_sql()` to seamlessly handle Delta Lake row-level optimistic concurrency collisions (`[DELTA_CONCURRENT_APPEND.ROW_LEVEL_CHANGES]`).
   - Added Supabase-first persistence to guarantee UI responsiveness.

4. **Enterprise Presentation Refinement (`94d2354` -> `d49cfeb`)**:
   - Purged all informal competition tags (`Feature A`, `Special Tier`, `Nuclear Tier`, `FIX 2/3`) in favor of standard enterprise domain headings:
     - Dead-End Registry
     - Requirement Ledger
     - Intent Conformance Diff
     - Agent Resume Contract
     - Resume-Integrity Checking & Agent Memory
   - Stripped all emoji glyphs across UI and diagnostic scripts for clean cross-platform terminal compatibility.
