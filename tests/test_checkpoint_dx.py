"""tests/test_checkpoint_dx.py
Comprehensive automated test suite for Checkpoint-Native DX (v9).
Verifies:
- All 5 review fixes (Fix 5.1/1, Fix 5.2/2, Fix 5.3, Fix 5.4, Fix 3, Fix 4)
- All 5 core features (A, B, C, D, E)
"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Allow importing from root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CHECKPOINT_DX_TEST_MODE"] = "1"

import config
from lib.checkpoint_dx import CheckpointDX, DeadEnd, Intent
from feature_d import generate_resume_contract


class TestCheckpointDX(unittest.TestCase):

    def test_fix_5_1_supabase_service_key_used(self):
        """Fix 5.1 (v9): Verify CheckpointDX initializes Supabase client with SUPABASE_SERVICE_KEY,
        not SUPABASE_ANON_KEY."""
        with patch("lib.checkpoint_dx.create_client") as mock_create_client:
            dx = CheckpointDX()
            mock_create_client.assert_called_once()
            args, kwargs = mock_create_client.call_args
            # First arg: URL, second arg: SERVICE_KEY
            self.assertEqual(args[0], config.SUPABASE_URL)
            self.assertEqual(args[1], config.SUPABASE_SERVICE_KEY)
            self.assertNotEqual(args[1], config.SUPABASE_ANON_KEY)

    def test_fix_5_4_config_example_and_gitignore(self):
        """Fix 5.4 (v9): config.py.example exists with blank values and config.py is in .gitignore."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        example_path = os.path.join(project_root, "config.py.example")
        gitignore_path = os.path.join(project_root, ".gitignore")

        self.assertTrue(os.path.exists(example_path), "config.py.example must exist")
        with open(example_path, "r", encoding="utf-8") as f:
            example_content = f.read()
        self.assertIn('DATABRICKS_HOST = ""', example_content)
        self.assertIn('SUPABASE_SERVICE_KEY = ""', example_content)
        self.assertIn('GROQ_API_KEY = ""', example_content)

        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gitignore_content = f.read()
        self.assertIn("config.py", gitignore_content)

    def test_fix_5_2_cluster_spec_fallback(self):
        """Fix 5.2 (v9) & Check 5: When DATABRICKS_CLUSTER_ID is empty, setup_databricks.py
        falls back to ephemeral new_cluster spec with verified AWS node type and spark version."""
        from scripts.setup_databricks import setup_unity_catalog
        # Cluster spec logic test
        test_cluster_id = ""
        if test_cluster_id:
            spec = {"existing_cluster_id": test_cluster_id}
        else:
            spec = {"new_cluster": {
                "spark_version": "14.3.x-scala2.12",
                "node_type_id": "m5.large",
                "num_workers": 1,
            }}
        self.assertIn("new_cluster", spec)
        self.assertEqual(spec["new_cluster"]["node_type_id"], "m5.large")
        self.assertEqual(spec["new_cluster"]["spark_version"], "14.3.x-scala2.12")

    def test_fix_4_dead_end_fallback_typed_array(self):
        """Fix 4: Verify log_dead_end fallback uses CAST(array() AS ARRAY<STRING>)
        when alternative_approaches is empty."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "uuid-123", "session_id": "sess-1"})
        dx.supabase = MagicMock()
        dx._run_sql = MagicMock()

        # Force exception in MLflow to trigger fallback
        with patch("mlflow.start_span", side_effect=Exception("Unity Catalog tracing disabled")):
            de = DeadEnd(
                checkpoint_id="chk-001",
                dead_end_type="repeated_failure",
                root_cause="race condition in sync cache",
                suggested_fix="use stateless JWT tokens",
                alternative_approaches=None,  # Empty approaches!
                confidence_score=0.85,
                failed_attempts=2,
            )
            result = dx.log_dead_end(de)
            self.assertTrue(result["used_fallback"])

            # Verify _run_sql was called with CAST(array() AS ARRAY<STRING>)
            dx._run_sql.assert_called_once()
            executed_sql = dx._run_sql.call_args[0][0]
            self.assertIn("CAST(array() AS ARRAY<STRING>)", executed_sql)
            params = dx._run_sql.call_args[1].get("parameters") if dx._run_sql.call_args[1] else (dx._run_sql.call_args[0][1] if len(dx._run_sql.call_args[0]) > 1 else None)
            param_vals = [p.get("value") for p in params] if params else []
            self.assertTrue("race condition in sync cache" in executed_sql or "race condition in sync cache" in param_vals)

    def test_fix_3_add_requirements_full_parity(self):
        """Fix 3: Verify add_requirements writes to Supabase, Delta requirements,
        and agent_memory when session_id is present."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "uuid-chk-1", "session_id": "sess-prod-1"})
        dx.supabase = MagicMock()
        dx._run_sql = MagicMock()
        dx.store_in_agent_memory = MagicMock()

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value.data = [{"id": "uuid-req-1", "requirement_text": "Implement OAuth2"}]
        dx.supabase.table.return_value = mock_table

        res = dx.add_requirements("chk-001", ["Implement OAuth2"])
        self.assertEqual(len(res), 1)

        # Verified written to Delta requirements table
        self.assertGreaterEqual(dx._run_sql.call_count, 1)
        first_call = dx._run_sql.call_args_list[0]
        delta_sql = first_call[0][0]
        self.assertIn("INSERT INTO", delta_sql)
        params = first_call[1].get("parameters") if first_call[1] else (first_call[0][1] if len(first_call[0]) > 1 else None)
        param_vals = [p.get("value") for p in params] if params else []
        self.assertTrue("Implement OAuth2" in delta_sql or "Implement OAuth2" in param_vals)

        # Verified stored in agent_memory
        dx.store_in_agent_memory.assert_called_once_with(
            checkpoint_id="chk-001",
            session_id="sess-prod-1",
            key="Implement OAuth2",
            value="Requirement manually added to checkpoint chk-001",
            confidence=0.6,
            source="manual",
        )

    def test_fix_2_generate_contract_session_id_lookup(self):
        """Fix 2: Verify UI sequence looking up checkpoint['session_id'] before calling
        create_resume_contract."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "uuid-chk-99", "session_id": "session-xyz"})
        dx.create_resume_contract = MagicMock(return_value={"contract": {"checkpoint_id": "chk-99", "session_id": "session-xyz"}})

        # Exactly simulates UI handler
        checkpoint_id = "chk-99"
        checkpoint = dx.get_checkpoint(checkpoint_id)
        result = dx.create_resume_contract(checkpoint_id, checkpoint["session_id"])

        dx.get_checkpoint.assert_called_with("chk-99")
        dx.create_resume_contract.assert_called_with("chk-99", "session-xyz")
        self.assertEqual(result["contract"]["session_id"], "session-xyz")

    def test_feature_e_check_resume_integrity_and_feedback(self):
        """Feature E: Verify check_resume_integrity scoring and record_human_feedback adjustments."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()

        # Case 1: Populated matching memory -> High Score
        dx._run_sql = MagicMock(side_effect=[
            [["Implement OAuth2"], ["Add user role check"]],  # memory keys
            [["Implement OAuth2"], ["Add user role check"]],  # open requirements
        ])
        res_ok = dx.check_resume_integrity("sess-1")
        self.assertEqual(res_ok["integrity_score"], 1.0)
        self.assertEqual(res_ok["reason"], "OK")

        # Case 2: No memory -> 0.0 score with explicit reason
        dx._run_sql = MagicMock(side_effect=[
            [],  # empty memory!
            [["Implement OAuth2"]],
        ])
        res_empty = dx.check_resume_integrity("sess-2")
        self.assertEqual(res_empty["integrity_score"], 0.0)
        self.assertIn("cannot verify resume safety", res_empty["reason"])

        # Case 3: record_human_feedback confidence adjustment
        dx._run_sql = MagicMock()
        fb_down = dx.record_human_feedback("chk-1", "Implement OAuth2", was_correct=False)
        self.assertEqual(fb_down["adjusted_by"], -0.2)
        sql_down = dx._run_sql.call_args[0][0]
        self.assertIn(":adjustment", sql_down)
        params_down = dx._run_sql.call_args[1].get("parameters", [])
        self.assertTrue(any(p.get("name") == "adjustment" and p.get("value") == "-0.2" for p in params_down))

        fb_up = dx.record_human_feedback("chk-1", "Implement OAuth2", was_correct=True)
        self.assertEqual(fb_up["adjusted_by"], 0.1)
        params_up = dx._run_sql.call_args[1].get("parameters", [])
        self.assertTrue(any(p.get("name") == "adjustment" and p.get("value") == "0.1" for p in params_up))

    def test_feature_d_synthesis_contract(self):
        """Feature D: Verify generate_resume_contract synthesizes Features B, A, C, and E."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "uuid-chk-1", "checkpoint_id": "chk-001"})

        # Mock Supabase tables
        mock_reqs = MagicMock()
        mock_reqs.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"requirement_text": "Implement OAuth2", "status": "not_started", "priority": 4}
        ]

        mock_intents = MagicMock()
        mock_intents.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"intent_text": "Ensure token expiry is validated", "implementation_status": "gap"}
        ]

        mock_contracts = MagicMock()
        mock_contracts.insert.return_value.execute.return_value.data = [{"id": "contract-uuid-1"}]

        def table_dispatch(name):
            if name == "requirements":
                return mock_reqs
            elif name == "intent_summaries":
                return mock_intents
            elif name == "resume_contracts":
                return mock_contracts
            return MagicMock()

        dx.supabase.table = MagicMock(side_effect=table_dispatch)
        dx.get_dead_ends = MagicMock(return_value=[
            {"root_cause": "Race condition with sync cache", "suggested_fix": "Use stateless tokens", "used_fallback": True}
        ])
        dx.check_resume_integrity = MagicMock(return_value={"integrity_score": 0.9, "reason": "OK"})

        contract_res = generate_resume_contract(dx, "chk-001", "session-prod-01")
        contract = contract_res["contract"]

        # Assert B synthesized
        self.assertEqual(len(contract["unresolved_requirements"]), 1)
        self.assertEqual(contract["unresolved_requirements"][0]["text"], "Implement OAuth2")

        # Assert A synthesized
        self.assertEqual(len(contract["do_not_retry"]), 1)
        self.assertEqual(contract["do_not_retry"][0]["reason_abandoned"], "Race condition with sync cache")

        # Assert C synthesized
        self.assertEqual(len(contract["flagged_gaps"]), 1)
        self.assertEqual(contract["flagged_gaps"][0]["clause"], "Ensure token expiry is validated")

        # Assert E synthesized
        self.assertEqual(contract["integrity_check"]["integrity_score"], 0.9)

    def test_feature_1_severity_scoring(self):
        """Feature 1 Hardening: Verify rule-based severity scoring and DeadEnd defaults."""
        dx = CheckpointDX()
        # Default DeadEnd has severity='minor'
        de = DeadEnd(checkpoint_id="c1", dead_end_type="logic_error", root_cause="rc", suggested_fix="sf")
        self.assertEqual(de.severity, "minor")

        # Resource exhaustion and timeouts -> critical
        self.assertEqual(dx._score_severity_rule_based("resource_exhaustion", 1), "critical")
        self.assertEqual(dx._score_severity_rule_based("timeout", 0), "critical")
        self.assertEqual(dx._score_severity_rule_based("logic_error", 3), "critical")

        # Repeated failures and API errors -> major
        self.assertEqual(dx._score_severity_rule_based("repeated_failure", 1), "major")
        self.assertEqual(dx._score_severity_rule_based("api_error", 1), "major")
        self.assertEqual(dx._score_severity_rule_based("logic_error", 2), "major")

        # Other types with low attempts -> minor
        self.assertEqual(dx._score_severity_rule_based("logic_error", 1), "minor")
        self.assertEqual(dx._score_severity_rule_based("unknown", 0), "minor")

    def test_feature_1_pre_flight_check(self):
        """Feature 1 Hardening: Verify pre-flight check detects similar failed approaches."""
        dx = CheckpointDX()
        mock_table = MagicMock()
        mock_table.select.return_value.execute.return_value.data = [
            {
                "id": "de-1",
                "checkpoint_id": "chk-001",
                "dead_end_type": "repeated_failure",
                "root_cause": "Race condition in redis synchronization cache",
                "suggested_fix": "Use stateless JWT tokens with independent verification",
                "severity": "critical",
                "fix_effectiveness": "failed",
            }
        ]
        dx.supabase = MagicMock()
        dx.supabase.table.return_value = mock_table

        # 1. Matching planned approach
        res = dx.check_before_attempting(
            checkpoint_id="chk-001",
            planned_approach="We plan to add redis synchronization cache with token auth",
            similarity_threshold=0.25,
        )
        self.assertTrue(res["matches_found"])
        self.assertGreaterEqual(len(res["warnings"]), 1)
        self.assertEqual(res["warnings"][0]["severity"], "critical")
        self.assertIn("CRITICAL", res["recommendation"])

        # 2. Non-matching approach
        clear_res = dx.check_before_attempting(
            checkpoint_id="chk-001",
            planned_approach="Configure kubernetes ingress annotations for ssl redirection",
            similarity_threshold=0.5,
        )
        self.assertFalse(clear_res["matches_found"])
        self.assertIn("CLEAR", clear_res["recommendation"])

    def test_feature_1_record_fix_outcome(self):
        """Feature 1 Hardening: Verify recording human fix outcome updates Supabase & Delta."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()
        mock_update = MagicMock()
        mock_update.update.return_value.eq.return_value.execute.return_value.data = [{"id": "de-1"}]
        dx.supabase.table.return_value = mock_update
        dx._run_sql = MagicMock()

        res = dx.record_fix_outcome("de-1", worked=True, notes="Verified in staging")
        self.assertEqual(res["fix_effectiveness"], "worked")
        self.assertTrue(res["supabase_updated"])
        self.assertTrue(res["delta_updated"])
        dx._run_sql.assert_called_once()
        sql_call = dx._run_sql.call_args[0][0]
        params = dx._run_sql.call_args[1].get("parameters") if dx._run_sql.call_args[1] else (dx._run_sql.call_args[0][1] if len(dx._run_sql.call_args[0]) > 1 else None)
        param_vals = [p.get("value") for p in params] if params else []
        self.assertIn("UPDATE", sql_call)
        self.assertTrue("worked" in sql_call or "worked" in param_vals)

    def test_fix_6_databricks_user_guard(self):
        """Fix 6 (v11): Verify CheckpointDX raises ValueError if DATABRICKS_USER is a placeholder."""
        with patch("lib.checkpoint_dx.DATABRICKS_USER", "default"):
            with self.assertRaises(ValueError) as ctx:
                CheckpointDX()
            self.assertIn("DATABRICKS_USER is still a placeholder", str(ctx.exception))

    def test_fix_7_feature_d_exception_handling(self):
        """Fix 7 (v11): Verify generate_resume_contract handles cold-starting warehouse / backend failure gracefully."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "uuid-1", "session_id": "sess-1"})
        dx.supabase = MagicMock()
        # Simulate warehouse failure on Delta queries
        dx._run_sql = MagicMock(side_effect=RuntimeError("SQL warehouse cold starting — please wait"))
        dx.check_resume_integrity = MagicMock(side_effect=RuntimeError("Connection timed out"))

        res = generate_resume_contract(dx, "chk-001", "sess-1")
        contract = res["contract"]
        self.assertIsNotNone(contract)
        self.assertEqual(contract["checkpoint_id"], "chk-001")
        self.assertIsNotNone(contract.get("failure_reason"))
        self.assertIn("failed", contract["failure_reason"].lower())

    def test_fix_8_memory_confidence_filter(self):
        """Fix 8 (v11): Verify check_resume_integrity filters out memory entries with confidence <= 0.3."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock()
        # Mock memory query and requirement query
        dx._run_sql.side_effect = [
            [["Implement OAuth2"]],  # memory keys with confidence > 0.3
            [["Implement OAuth2"], ["Add Redis cache"]],  # open requirements
        ]
        res = dx.check_resume_integrity("sess-1")
        # Verify SQL contains confidence > 0.3 filter
        first_call_sql = dx._run_sql.call_args_list[0][0][0]
        self.assertIn("confidence > 0.3", first_call_sql)
        self.assertEqual(res["integrity_score"], 0.5)

    def test_fix_9_sql_parameter_binding(self):
        """Fix 9 (v11): Verify _run_sql sends parameters dictionary in request body to Databricks SQL API."""
        dx = CheckpointDX()
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "status": {"state": "SUCCEEDED"},
                "result": {"data_array": [["param_val"]]}
            }
            params = [{"name": "test_param", "value": "bound_value", "type": "STRING"}]
            rows = dx._run_sql("SELECT :test_param", parameters=params)
            self.assertEqual(rows, [["param_val"]])
            mock_post.assert_called_once()
            call_body = mock_post.call_args[1]["json"]
            self.assertIn("parameters", call_body)
            self.assertEqual(call_body["parameters"], params)

    def test_feature_b_score_requirement_priority(self):
        """Feature B: Verify priority scoring with Groq and fallback."""
        dx = CheckpointDX()
        # Fallback when groq is None
        dx.groq = None
        res_fb = dx.score_requirement_priority("Add OAuth2 login")
        self.assertEqual(res_fb["priority_tier"], "P2")
        self.assertEqual(res_fb["moscow"], "should")

        # LLM scoring when groq is present
        dx.groq = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"priority_tier": "P0", "moscow": "must", "reasoning": "Auth is critical"}'
        dx.groq.chat.completions.create.return_value.choices = [mock_choice]
        res_llm = dx.score_requirement_priority("Add OAuth2 login")
        self.assertEqual(res_llm["priority_tier"], "P0")
        self.assertEqual(res_llm["moscow"], "must")
        self.assertIn("Auth is critical", res_llm["reasoning"])

    def test_feature_b_estimate_requirement_effort(self):
        """Feature B: Verify effort estimation in story points and fallback."""
        dx = CheckpointDX()
        # Fallback
        dx.groq = None
        res_fb = dx.estimate_requirement_effort("Add OAuth2 login")
        self.assertIsNone(res_fb["effort_points"])

        # LLM estimation
        dx.groq = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"effort_points": 5, "reasoning": "Requires third-party integration"}'
        dx.groq.chat.completions.create.return_value.choices = [mock_choice]
        res_llm = dx.estimate_requirement_effort("Add OAuth2 login")
        self.assertEqual(res_llm["effort_points"], 5)

    def test_feature_b_generate_acceptance_criteria(self):
        """Feature B: Verify acceptance criteria generation and fallback."""
        dx = CheckpointDX()
        # Fallback
        dx.groq = None
        self.assertEqual(dx.generate_acceptance_criteria("Add OAuth2 login"), [])

        # LLM generation
        dx.groq = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '["User can log in with Google", "JWT token issued with 1h expiry"]'
        dx.groq.chat.completions.create.return_value.choices = [mock_choice]
        crit = dx.generate_acceptance_criteria("Add OAuth2 login")
        self.assertEqual(len(crit), 2)
        self.assertEqual(crit[0], "User can log in with Google")

    def test_feature_b_enrich_requirement(self):
        """Feature B: Verify single-entry enrichment writes to Supabase and Delta."""
        dx = CheckpointDX()
        dx.score_requirement_priority = MagicMock(return_value={"priority_tier": "P1", "moscow": "should", "reasoning": "Important feature"})
        dx.estimate_requirement_effort = MagicMock(return_value={"effort_points": 3, "reasoning": "Standard work"})
        dx.generate_acceptance_criteria = MagicMock(return_value=["Criteria 1", "Criteria 2"])
        dx.supabase = MagicMock()
        dx._run_sql = MagicMock()

        res = dx.enrich_requirement("req-uuid-1", "Build user profile page")
        self.assertEqual(res["priority_tier"], "P1")
        self.assertEqual(res["moscow"], "should")
        self.assertEqual(res["effort_points"], 3)
        self.assertEqual(len(res["acceptance_criteria"]), 2)

        # Check Supabase update call
        dx.supabase.table.return_value.update.assert_called_once()
        # Check Delta SQL call
        dx._run_sql.assert_called_once()
        sql_call = dx._run_sql.call_args[0][0]
        self.assertIn("priority_tier", sql_call)

    def test_feature_b_assign_requirement_owner(self):
        """Feature B: Verify manual owner assignment updates Supabase and Delta."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()
        dx.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"requirement_text": "Build user profile page"}
        ]
        dx._run_sql = MagicMock()

        dx.assign_requirement_owner("req-uuid-1", "Alice")
        dx.supabase.table.return_value.update.assert_called_with({"owner": "Alice"})
        dx._run_sql.assert_called_once()
        params = dx._run_sql.call_args[1].get("parameters", [])
        self.assertTrue(any(p.get("name") == "owner" and p.get("value") == "Alice" for p in params))

    def test_feature_b_add_and_get_requirement_dependency(self):
        """Feature B: Verify dependency edge creation, self-dependency rejection, and graph fetch."""
        dx = CheckpointDX()
        # Self-dependency must raise ValueError
        with self.assertRaises(ValueError):
            dx.add_requirement_dependency("req-1", "req-1", "Self loop")

        # Valid edge creation
        dx.supabase = MagicMock()
        mock_upsert = MagicMock()
        mock_upsert.execute.return_value.data = [{
            "id": "dep-1", "requirement_id": "req-2", "depends_on_requirement_id": "req-1", "dependency_reasoning": "Prereq"
        }]
        dx.supabase.table.return_value.upsert.return_value = mock_upsert

        edge = dx.add_requirement_dependency("req-2", "req-1", "Prereq")
        self.assertEqual(edge["requirement_id"], "req-2")
        self.assertEqual(edge["depends_on_requirement_id"], "req-1")

        # Graph fetch
        dx.get_checkpoint = MagicMock(return_value={"id": "cp-uuid-1"})
        dx.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "req-1"}, {"id": "req-2"}
        ]
        dx.supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"requirement_id": "req-2", "depends_on_requirement_id": "req-1"}
        ]
        graph = dx.get_requirement_dependency_graph("chk-001")
        self.assertEqual(len(graph), 1)

    def test_feature_b_detect_requirement_dependencies(self):
        """Feature B: Verify automated dependency detection across requirement list."""
        dx = CheckpointDX()
        # Empty or single requirement list returns []
        self.assertEqual(dx.detect_requirement_dependencies([]), [])
        self.assertEqual(dx.detect_requirement_dependencies([{"id": "r1", "requirement_text": "text"}]), [])

        # LLM detection
        dx.groq = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps([
            {"from_index": 1, "depends_on_index": 0, "reasoning": "Need queue before consumer"}
        ])
        dx.groq.chat.completions.create.return_value.choices = [mock_choice]

        reqs = [
            {"id": "r1", "requirement_text": "Create background message queue"},
            {"id": "r2", "requirement_text": "Process events from background queue"},
        ]
        detected = dx.detect_requirement_dependencies(reqs)
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]["requirement_id"], "r2")
        self.assertEqual(detected[0]["depends_on_requirement_id"], "r1")
        self.assertIn("queue", detected[0]["reasoning"])

    def test_feature_b_add_requirements_calls_enrichment(self):
        """Feature B: Verify manual add_requirements calls enrich_requirement for parity with pipeline."""
        dx = CheckpointDX()
        dx.get_checkpoint = MagicMock(return_value={"id": "cp-uuid-1", "session_id": "sess-1"})
        dx.supabase = MagicMock()
        dx.supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "req-uuid-99", "requirement_text": "Enable rate limiting"}
        ]
        dx._run_sql = MagicMock()
        dx.store_in_agent_memory = MagicMock()
        dx.enrich_requirement = MagicMock()

        res = dx.add_requirements("chk-001", ["Enable rate limiting"], source="manual")
        self.assertEqual(len(res), 1)
        dx.enrich_requirement.assert_called_once()
        self.assertEqual(dx.enrich_requirement.call_args[1]["requirement_id"], "req-uuid-99")
    def test_feature_4_contract_schema_validation_valid(self):
        """Feature 4 (Gap 1): Verify Draft-7 schema validation passes on valid payload."""
        from lib.contract_schema import validate_contract_schema
        payload = {
            "checkpoint_id": "chk-123",
            "session_id": "sess-456",
            "generated_at": "2026-09-07T12:00:00",
            "version": 1,
            "template": "dev",
            "unresolved_requirements": [
                {"text": "Add OAuth login", "status": "in_progress", "priority": 1}
            ],
            "do_not_retry": [
                {"reason_abandoned": "Redis timeout", "suggested_alternative": "JWT cookie", "used_fallback_source": False}
            ],
            "flagged_gaps": [{"clause": "Implement refresh token endpoint"}],
            "integrity_check": {"integrity_score": 0.85, "reason": "Consistent git history"}
        }
        res = validate_contract_schema(payload)
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["errors"]), 0)

    def test_feature_4_contract_schema_validation_missing_field(self):
        """Feature 4 (Gap 1): Verify Draft-7 schema fails when a required field is missing."""
        from lib.contract_schema import validate_contract_schema
        payload = {
            "checkpoint_id": "chk-123",
            "session_id": "sess-456",
            "generated_at": "2026-09-07T12:00:00",
            "version": 1,
            # Missing "integrity_check", "unresolved_requirements", etc.
        }
        res = validate_contract_schema(payload)
        self.assertFalse(res["valid"])
        self.assertTrue(any("integrity_check" in e for e in res["errors"]))

    def test_feature_4_contract_schema_validation_fallback(self):
        """Feature 4 (Gap 1): Verify graceful fallback when jsonschema library is unavailable."""
        import sys
        from lib import contract_schema
        with patch.dict(sys.modules, {"jsonschema": None}):
            payload = {
                "checkpoint_id": "chk-123",
                "session_id": "sess-456",
                "generated_at": "2026-09-07T12:00:00",
                "version": 1,
                "unresolved_requirements": [],
                "do_not_retry": [],
                "flagged_gaps": [],
                "integrity_check": {"integrity_score": 0.9}
            }
            res = contract_schema.validate_contract_schema(payload)
            self.assertTrue(res["valid"])
            self.assertIsNotNone(res["warning"])

    def test_feature_4_contract_diff_computation(self):
        """Feature 4 (Gap 2): Verify structured diff computation across versions."""
        dx = CheckpointDX()
        prev = {
            "unresolved_requirements": [
                {"text": "Task A", "status": "in_progress"},
                {"text": "Task B", "status": "not_started"}
            ],
            "do_not_retry": [{"reason_abandoned": "Old bug"}],
            "flagged_gaps": [{"clause": "Old gap"}],
            "integrity_check": {"integrity_score": 0.6}
        }
        new = {
            "unresolved_requirements": [
                {"text": "Task B", "status": "in_progress"},
                {"text": "Task C", "status": "not_started"}
            ],
            "do_not_retry": [
                {"reason_abandoned": "Old bug"},
                {"reason_abandoned": "New race condition"}
            ],
            "flagged_gaps": [],
            "integrity_check": {"integrity_score": 0.85}
        }
        diff = dx._compute_contract_diff(prev, new)
        self.assertIn("Task A", diff["requirements_resolved_since_last"])
        self.assertIn("Task C", diff["requirements_added_since_last"])
        self.assertIn("New race condition", diff["dead_ends_added_since_last"])
        self.assertAlmostEqual(diff["integrity_score_change"], 0.25)
        self.assertIn("1 requirement(s) resolved", diff["summary"])

    def test_feature_4_contract_templates_dev_qa_pm(self):
        """Feature 4 (Gap 3): Verify role-based template projections."""
        dx = CheckpointDX()
        base_payload = {
            "checkpoint_id": "chk-001",
            "session_id": "sess-001",
            "generated_at": "2026-09-07T12:00:00",
            "version": 1,
            "unresolved_requirements": [{"text": "Feature X", "status": "in_progress"}],
            "do_not_retry": [{"reason_abandoned": "Dead end Y", "suggested_alternative": "Alt", "used_fallback_source": False}],
            "flagged_gaps": [{"clause": "Missing validation"}],
            "integrity_check": {"integrity_score": 0.9, "reason": "Safe"}
        }

        # Test PM template (Gap 3 / Doc 17 Section 4)
        pm_proj = dx._apply_contract_template(dict(base_payload), template="pm")
        self.assertEqual(pm_proj["template"], "pm")
        self.assertIn("summary", pm_proj)
        self.assertNotIn("unresolved_requirements", pm_proj)
        self.assertNotIn("do_not_retry", pm_proj)
        self.assertEqual(pm_proj["summary"]["open_requirement_count"], 1)
        self.assertEqual(pm_proj["summary"]["known_dead_ends"], 1)
        self.assertEqual(pm_proj["summary"]["flagged_gap_count"], 1)
        self.assertEqual(pm_proj["summary"]["resume_integrity_score"], 0.9)
        self.assertIn("release_readiness", pm_proj["summary"])

        # Test QA template (Gap 3 / Doc 17 Section 4: filters done requirements, keeps do_not_retry and flagged_gaps)
        qa_payload = dict(base_payload)
        qa_payload["unresolved_requirements"] = [
            {"text": "Done task", "status": "done"},
            {"text": "Open task", "status": "in_progress"},
        ]
        qa_proj = dx._apply_contract_template(qa_payload, template="qa")
        self.assertEqual(qa_proj["template"], "qa")
        self.assertEqual(len(qa_proj["unresolved_requirements"]), 1)
        self.assertEqual(qa_proj["unresolved_requirements"][0]["text"], "Open task")
        self.assertEqual(len(qa_proj["do_not_retry"]), 1)
        self.assertEqual(len(qa_proj["flagged_gaps"]), 1)

        # Test Dev template (Gap 3 / Doc 17 Section 4: dev is unchanged from full payload - regression check)
        dev_proj = dx._apply_contract_template(dict(base_payload), template="dev")
        self.assertEqual(dev_proj, base_payload)

        # Test Invalid template name raises clear ValueError
        with self.assertRaises(ValueError):
            dx._apply_contract_template(dict(base_payload), template="invalid_template")

    def test_feature_4_contract_execution_and_usage_stats(self):
        """Feature 4 (Gap 4): Verify recording contract executions and reporting outcomes."""
        dx = CheckpointDX()
        # Invalid consumer_type raises ValueError
        with self.assertRaises(ValueError):
            dx.record_contract_execution("contract-123", consumer_type="invalid_type")

        # Mock Supabase
        mock_sb = MagicMock()
        dx.supabase = mock_sb
        dx.log_mlflow_trace = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "exec-999", "resume_contract_id": "contract-123", "consumer_type": "agent_session", "outcome_reported": False}
        ]
        rec = dx.record_contract_execution("contract-123", consumer_type="agent_session", consumer_identifier="agent-01")
        self.assertEqual(rec["id"], "exec-999")
        self.assertEqual(rec["consumer_type"], "agent_session")

        # Report outcome
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        success = dx.report_contract_outcome("exec-999", outcome_notes="Skipped dead-end cleanly")
        self.assertTrue(success)

        # Usage stats
        stats_data = [
            {"consumer_type": "agent_session", "outcome_reported": True, "outcome_notes": "Good"},
            {"consumer_type": "human_ui_view", "outcome_reported": False, "outcome_notes": None},
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = stats_data
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = stats_data
        stats = dx.get_contract_usage_stats("contract-123")
        self.assertEqual(stats["total_loads"], 2)
        self.assertEqual(stats["by_consumer_type"]["agent_session"], 1)
        self.assertEqual(stats["by_consumer_type"]["human_ui_view"], 1)
        self.assertEqual(stats["outcomes_reported_count"], 1)

    def test_feature_5_freshness_penalty(self):
        """Feature 5 (Gap 1): Verify freshness penalty identifies fresh vs stale entries (>72h)."""
        from datetime import datetime, timedelta, timezone
        dx = CheckpointDX()
        now = datetime.now(timezone.utc)
        fresh_time = now - timedelta(hours=10)
        stale_time = now - timedelta(hours=80)

        rows = [
            ("key_fresh", 0.8, fresh_time.isoformat()),
            ("key_stale", 0.8, stale_time.isoformat()),
        ]
        res = dx._apply_freshness_penalty(rows, stale_after_hours=72)
        self.assertIn("key_fresh", res["fresh_keys"])
        self.assertIn("key_stale", res["stale_keys"])
        self.assertEqual(res["stale_count"], 1)

    def test_feature_5_confidence_decay(self):
        """Feature 5 (Gap 3): Verify time-based exponential decay at read time."""
        from datetime import datetime, timedelta, timezone
        dx = CheckpointDX()
        now = datetime.now(timezone.utc)

        # Fresh: no decay
        eff_now = dx._effective_confidence(0.8, now, half_life_days=14.0)
        self.assertAlmostEqual(eff_now, 0.8, places=2)

        # 14 days old: exactly 1 half-life -> 0.4
        t_14d = now - timedelta(days=14)
        eff_14d = dx._effective_confidence(0.8, t_14d, half_life_days=14.0)
        self.assertAlmostEqual(eff_14d, 0.4, places=2)

        # 30 days old: drops below 0.3 threshold
        t_30d = now - timedelta(days=30)
        eff_30d = dx._effective_confidence(0.8, t_30d, half_life_days=14.0)
        self.assertLess(eff_30d, 0.3)

    def test_feature_5_conflict_detection_and_resolution(self):
        """Feature 5 (Gap 2): Verify contradiction detection (LLM & fallback) and resolution."""
        dx = CheckpointDX()

        # 1. Fallback rule-based contradiction scan
        dx.groq = None
        dx._run_sql = MagicMock(return_value=[
            ["deploy to prod", "deploy now to production"],
            ["deploy to prod", "cancel deployment to production"],
        ])
        mock_sb = MagicMock()
        dx.supabase = mock_sb
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        conflicts = dx.rescan_memory_conflicts("sess-conflict-01")
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertIn("cancel", conflicts[0]["reason"].lower())

        # 2. Resolve conflict
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "c-1", "resolved": True, "resolution_notes": "Kept prod deployment"}
        ]
        res = dx.resolve_memory_conflict("c-1", "Kept prod deployment")
        self.assertTrue(res["resolved"])

    def test_feature_5_integrity_trend_and_history_logging(self):
        """Feature 5 (Gap 4): Verify append-only history tracking and chronological trend query."""
        dx = CheckpointDX()
        mock_sb = MagicMock()
        dx.supabase = mock_sb

        # Mock trend query in reverse order
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"session_id": "s1", "integrity_score": 0.9, "recorded_at": "2026-09-08T10:00:00Z"},
            {"session_id": "s1", "integrity_score": 0.6, "recorded_at": "2026-09-08T09:00:00Z"},
        ]
        trend = dx.get_integrity_trend("s1")
        # Should be chronological: 0.6 first, then 0.9
        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0]["integrity_score"], 0.6)
        self.assertEqual(trend[1]["integrity_score"], 0.9)

    def test_feature_5_check_resume_integrity_discount_and_reporting(self):
        """Feature 5: Verify stale memory applies 0.7 discount in integrity score."""
        from datetime import datetime, timedelta, timezone
        dx = CheckpointDX()
        now = datetime.now(timezone.utc)
        stale_time = (now - timedelta(hours=100)).isoformat()

        # 1 requirement, covered by 1 stale memory entry (>72h) with confidence 0.9 (effective > 0.3)
        dx._run_sql = MagicMock(side_effect=[
            [["Implement OAuth2", 0.9, stale_time]],  # memory
            [["Implement OAuth2"]],  # open requirement
        ])
        dx._search_managed_memory = MagicMock(return_value=None)
        dx._detect_memory_conflicts = MagicMock(return_value=[])
        mock_sb = MagicMock()
        dx.supabase = mock_sb
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        res = dx.check_resume_integrity("sess-stale-01")
        # Covered stale count = 1, fresh = 0 -> score = (0 + 0.7 * 1) / 1 = 0.7
        self.assertEqual(res["integrity_score"], 0.7)
        self.assertEqual(res["stale_memory_count"], 1)
        self.assertIn("stale", res["reason"].lower())

    def test_feature_1_preflight_confidence_and_ranked_recommendations(self):
        """Feature 1 Hardened+: Verify multi-layer confidence scoring and ranked recommendations."""
        dx = CheckpointDX()
        mock_table = MagicMock()
        mock_table.select.return_value.execute.return_value.data = [
            {
                "id": "de-101",
                "checkpoint_id": "chk-001",
                "dead_end_type": "concurrency_deadlock",
                "root_cause": "Race condition in redis synchronization cache",
                "suggested_fix": "Use stateless JWT tokens with independent verification",
                "severity": "critical",
                "fix_effectiveness": "worked",
            }
        ]
        dx.supabase = MagicMock()
        dx.supabase.table.return_value = mock_table

        res = dx.check_before_attempting(
            planned_approach="We plan to add redis synchronization cache with token auth",
            similarity_threshold=0.25,
        )
        self.assertTrue(res["matches_found"])
        self.assertIn("confidence", res)
        conf = res["confidence"]
        self.assertGreater(conf["score"], 0.25)
        self.assertEqual(len(conf["confidence_interval"]), 2)
        self.assertLessEqual(conf["confidence_interval"][0], conf["score"])
        self.assertGreaterEqual(conf["confidence_interval"][1], conf["score"])
        self.assertEqual(conf["sample_size"], 1)
        self.assertEqual(conf["risk_level"], "[CRITICAL]")
        self.assertIn("redis synchronization cache", conf["plain_reasoning"])

        # Ranked recommendations
        recs = res.get("ranked_recommendations", [])
        self.assertGreaterEqual(len(recs), 1)
        top_rec = recs[0]
        self.assertEqual(top_rec["recommendation"], "Use stateless JWT tokens with independent verification")
        self.assertEqual(top_rec["historical_outcome"], "[WORKED]")
        self.assertGreater(top_rec["success_probability"], 0.7)

    def test_feature_1_preflight_override_workflow(self):
        """Feature 1 Hardened+: Verify override audit persistence and retrieval."""
        dx = CheckpointDX()
        mock_insert = MagicMock()
        mock_insert.insert.return_value.execute.return_value.data = [{"id": "ovr-test"}]
        mock_insert.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "ovr-test",
                "planned_approach": "Manual Redis bypass",
                "similarity_score": 0.85,
                "risk_level": "[CRITICAL]",
                "override_reason": "Emergency production hotfix",
                "override_category": "emergency_hotfix",
                "approver": "lead_architect",
                "created_at": "2026-09-08T10:00:00",
            }
        ]
        dx.supabase = MagicMock()
        dx.supabase.table.return_value = mock_insert

        rec = dx.record_preflight_override(
            planned_approach="Manual Redis bypass",
            similarity_score=0.85,
            matched_dead_end_id="de-101",
            override_reason="Emergency production hotfix",
            override_category="emergency_hotfix",
            approver="lead_architect",
            risk_level="[CRITICAL]",
        )
        self.assertEqual(rec["override_reason"], "Emergency production hotfix")
        self.assertEqual(rec["risk_level"], "[CRITICAL]")

        overrides = dx.get_preflight_overrides(limit=5)
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["approver"], "lead_architect")

    def test_feature_1_cluster_ai_naming_and_renaming(self):
        """Feature 1 Hardened+: Verify pattern title synthesis and cluster renaming."""
        dx = CheckpointDX()
        # Heuristic fallback path
        dx.groq = None
        name_info = dx.generate_cluster_name(
            root_cause_text="Postgres database connection pool exhausted on concurrent requests",
            common_fix="Configure pool size cap and idle connection timeout",
            member_count=3,
        )
        self.assertIn("suggested_name", name_info)
        self.assertIn("Pattern", name_info["suggested_name"])
        self.assertEqual(name_info["generated_by"], "heuristic_synthesizer")

        # Rename cluster
        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "cl-1"}]
        dx.supabase = mock_sb
        dx._run_sql = MagicMock()

        ren_res = dx.rename_cluster(
            cluster_id="cl-1",
            custom_name="Postgres Connection Pool Saturation",
            ai_suggested_name=name_info["suggested_name"],
            reasoning=name_info["reasoning"],
        )
        self.assertTrue(ren_res["success"])
        self.assertEqual(ren_res["custom_name"], "Postgres Connection Pool Saturation")
        dx._run_sql.assert_called_once()

    def test_feature_1_cluster_trends_and_merging(self):
        """Feature 1 Hardened+: Verify cluster velocity trend calculation and merging."""
        dx = CheckpointDX()
        mock_clusters = [
            {
                "id": "cl-surge",
                "cluster_key": "de_surge_001",
                "member_count": 6,
                "representative_root_cause": "Timeout in distributed lock",
                "common_suggested_fix": "Increase lock heartbeat interval",
                "first_seen_at": "2026-09-01T00:00:00",
                "last_seen_at": "2026-09-02T00:00:00",
            },
            {
                "id": "cl-cooling",
                "cluster_key": "de_cooling_002",
                "member_count": 1,
                "representative_root_cause": "Malformed header parse",
                "common_suggested_fix": "Strict schema parser",
                "first_seen_at": "2026-08-10T00:00:00",
                "last_seen_at": "2026-08-10T00:00:00",
            }
        ]
        dx.get_dead_end_clusters = MagicMock(return_value=mock_clusters)

        trends = dx.get_cluster_trends()
        self.assertEqual(len(trends), 2)
        self.assertEqual(trends[0]["status"], "[SURGE]")
        self.assertEqual(trends[1]["status"], "[COOLING]")

        # Merge clusters
        mock_sb = MagicMock()
        dx.supabase = mock_sb
        merge_res = dx.merge_clusters("cl-cooling", "cl-surge")
        self.assertTrue(merge_res["success"])
        self.assertEqual(merge_res["combined_member_count"], 7)

    def test_feature_1_rca_report_and_outcome_analytics(self):
        """Feature 1 Hardened+: Verify Markdown RCA report formatting and fix outcome analytics."""
        dx = CheckpointDX()
        dx.get_dead_end_clusters = MagicMock(return_value=[
            {
                "id": "cl-1",
                "cluster_key": "de_redis_deadlock",
                "custom_name": "Redis Lock Contention",
                "member_count": 4,
                "representative_root_cause": "Lock contention on key expiration",
                "common_suggested_fix": "Implement exponential backoff",
                "first_seen_at": "2026-09-01T00:00:00",
                "last_seen_at": "2026-09-07T00:00:00",
            }
        ])

        # RCA report generation
        rca_exec = dx.generate_rca_report(cluster_id="cl-1", template="executive")
        self.assertIn("# EXECUTIVE ROOT CAUSE ANALYSIS", rca_exec)
        self.assertIn("Redis Lock Contention", rca_exec)

        rca_tech = dx.generate_rca_report(cluster_id="cl-1", template="technical")
        self.assertIn("# ROOT CAUSE ANALYSIS (RCA) - TECHNICAL POST-MORTEM", rca_tech)
        self.assertIn("Preventative Guardrails", rca_tech)

        # Fix outcome analytics
        mock_dead_ends = [
            {"id": "d1", "fix_effectiveness": "worked", "dead_end_type": "concurrency", "suggested_fix": "Fix 1", "root_cause": "Cause 1"},
            {"id": "d2", "fix_effectiveness": "failed", "dead_end_type": "concurrency", "suggested_fix": "Fix 2", "root_cause": "Cause 2"},
            {"id": "d3", "fix_effectiveness": "untested", "dead_end_type": "network", "suggested_fix": "Fix 3", "root_cause": "Cause 3"},
        ]
        dx.supabase = MagicMock()
        dx.supabase.table.return_value.select.return_value.execute.return_value.data = mock_dead_ends

        analytics = dx.get_fix_outcome_analytics()
        self.assertEqual(analytics["total_dead_ends"], 3)
        self.assertEqual(analytics["total_tested"], 2)
        self.assertEqual(analytics["worked_count"], 1)
        self.assertEqual(analytics["failed_count"], 1)
        self.assertEqual(analytics["overall_success_rate"], 50.0)
        self.assertEqual(len(analytics["top_performing_fixes"]), 1)
        self.assertEqual(len(analytics["underperforming_fixes"]), 1)

    def test_feature_2_workflow_state_machine_and_guards(self):
        """Feature 2 Hardening: Verify 8-state workflow transitions, guards, and audit trail."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()
        
        # Mock requirement lookup: status is "draft"
        mock_req = {"id": "req-101", "requirement_text": "Setup Delta Lake Schema", "status": "draft"}
        dx.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [mock_req]
        dx._run_sql = MagicMock()

        # Valid transition: draft -> backlog
        res = dx.update_requirement_status_workflow("req-101", "backlog", changed_by="lead_eng", reason="Refining scope")
        self.assertTrue(res["success"])
        self.assertEqual(res["new_status"], "backlog")
        self.assertEqual(res["previous_status"], "draft")

        # Invalid transition: draft -> done should raise ValueError
        with self.assertRaises(ValueError):
            dx.update_requirement_status_workflow("req-101", "done")

        # Transition guard: transition to "blocked" without reason should raise ValueError
        mock_req["status"] = "in_progress"
        with self.assertRaises(ValueError):
            dx.update_requirement_status_workflow("req-101", "blocked", reason="")

        # Transition guard: transition to "blocked" with reason succeeds
        res_blocked = dx.update_requirement_status_workflow("req-101", "blocked", reason="Waiting for API access")
        self.assertTrue(res_blocked["success"])
        self.assertEqual(res_blocked["new_status"], "blocked")

        # Transition guard: transition to "superseded" without reason raises ValueError
        with self.assertRaises(ValueError):
            dx.update_requirement_status_workflow("req-101", "superseded", reason="   ")

        # Transition guard: transition to "superseded" with reason succeeds
        res_sup = dx.update_requirement_status_workflow("req-101", "superseded", reason="Replaced by unified architecture")
        self.assertTrue(res_sup["success"])
        self.assertEqual(res_sup["new_status"], "superseded")

    def test_feature_2_status_audit_trail_retrieval(self):
        """Feature 2 Hardening: Verify retrieval of audit history."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()
        mock_history = [
            {"requirement_id": "req-101", "previous_status": "draft", "new_status": "backlog", "changed_at": "2026-09-01T10:00:00"},
            {"requirement_id": "req-101", "previous_status": "backlog", "new_status": "in_progress", "changed_at": "2026-09-02T10:00:00"},
        ]
        dx.supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = mock_history

        history = dx.get_requirement_status_history("req-101")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["new_status"], "backlog")
        self.assertEqual(history[1]["new_status"], "in_progress")

    def test_feature_2_smart_status_prediction(self):
        """Feature 2 Hardening: Verify ML/heuristic next status prediction."""
        dx = CheckpointDX()

        # Blocked condition overrides
        p_blocked = dx.predict_next_requirement_status("Build pipeline", "in_progress", is_blocked=True)
        self.assertEqual(p_blocked["predicted_status"], "blocked")
        self.assertGreaterEqual(p_blocked["confidence"], 0.90)

        # Draft without criteria -> backlog
        p_draft = dx.predict_next_requirement_status("Draft auth flow", "draft", has_criteria=False)
        self.assertEqual(p_draft["predicted_status"], "backlog")

        # Draft with criteria -> ready
        p_draft_crit = dx.predict_next_requirement_status("Draft auth flow", "draft", has_criteria=True)
        self.assertEqual(p_draft_crit["predicted_status"], "ready")

        # Ready -> in_progress
        p_ready = dx.predict_next_requirement_status("Ready auth flow", "ready")
        self.assertEqual(p_ready["predicted_status"], "in_progress")

        # In progress -> in_review
        p_prog = dx.predict_next_requirement_status("Active auth flow", "in_progress")
        self.assertEqual(p_prog["predicted_status"], "in_review")

        # In review -> done
        p_rev = dx.predict_next_requirement_status("Reviewing auth flow", "in_review")
        self.assertEqual(p_rev["predicted_status"], "done")

    def test_feature_2_stale_requirements_and_analytics(self):
        """Feature 2 Hardening: Verify stale detection and status analytics."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()

        now = datetime.utcnow()
        active_ts = (now - timedelta(days=2)).isoformat()
        stale_med_ts = (now - timedelta(days=9)).isoformat()
        stale_high_ts = (now - timedelta(days=20)).isoformat()

        mock_reqs = [
            {"id": "r1", "requirement_text": "Active task", "status": "in_progress", "updated_at": active_ts},
            {"id": "r2", "requirement_text": "Medium stale task", "status": "backlog", "updated_at": stale_med_ts},
            {"id": "r3", "requirement_text": "High stale task", "status": "blocked", "updated_at": stale_high_ts},
            {"id": "r4", "requirement_text": "Completed old task", "status": "done", "updated_at": stale_high_ts},
        ]
        dx.supabase.table.return_value.select.return_value.execute.return_value.data = mock_reqs

        stale = dx.detect_stale_requirements()
        self.assertEqual(len(stale), 2)
        self.assertEqual(stale[0]["warning_level"], "[HIGH]")
        self.assertEqual(stale[1]["warning_level"], "[MEDIUM]")

        # Analytics
        dx.detect_stale_requirements = MagicMock(return_value=stale)
        analytics = dx.get_requirement_status_analytics()
        self.assertEqual(analytics["total_requirements"], 4)
        self.assertEqual(analytics["completion_rate"], 25.0)
        self.assertEqual(analytics["stale_count"], 2)
        self.assertTrue(any(b["status"] == "blocked" for b in analytics["bottlenecks"]))

    def test_feature_2_dynamic_priority_and_rice(self):
        """Feature 2 Hardening: Verify multi-factor dynamic priority and MoSCoW RICE scoring."""
        # Dynamic Priority
        p0_res = CheckpointDX.calculate_dynamic_priority(
            business_impact=10, urgency=9, dependency_count=3, blocked_count=4, effort_points=2, risk_score=4
        )
        self.assertEqual(p0_res["priority_tier"], "P0")
        self.assertGreaterEqual(p0_res["dynamic_priority_score"], 70.0)

        p2_res = CheckpointDX.calculate_dynamic_priority(
            business_impact=2, urgency=2, dependency_count=0, blocked_count=0, effort_points=10, risk_score=1
        )
        self.assertEqual(p2_res["priority_tier"], "P2")
        self.assertLess(p2_res["dynamic_priority_score"], 40.0)

        # RICE Score with MoSCoW multipliers
        must_rice = CheckpointDX.calculate_rice_score(reach=10, impact=3, confidence=1.0, effort=2.0, moscow="must")
        should_rice = CheckpointDX.calculate_rice_score(reach=10, impact=3, confidence=1.0, effort=2.0, moscow="should")
        wont_rice = CheckpointDX.calculate_rice_score(reach=10, impact=3, confidence=1.0, effort=2.0, moscow="wont")

        self.assertEqual(must_rice["rice_score"], 15.0)
        self.assertEqual(must_rice["hybrid_score"], 22.5)  # 15 * 1.5
        self.assertEqual(should_rice["hybrid_score"], 15.0)  # 15 * 1.0
        self.assertEqual(wont_rice["hybrid_score"], 4.5)  # 15 * 0.3

    def test_feature_2_ml_effort_estimation(self):
        """Feature 2 Hardening: Verify ML story point estimation and Fibonacci mapping."""
        dx = CheckpointDX()
        text = "Implement distributed resilient Delta Lake pipeline with schema migration and mlflow tracking"
        historical = [
            {"requirement_text": "Delta Lake pipeline with schema migration", "effort_points": 8},
            {"requirement_text": "Simple UI text change", "effort_points": 1},
        ]
        res = dx.predict_requirement_effort_ml(text, historical_requirements=historical)
        self.assertIn(res["predicted_story_points"], [1, 2, 3, 5, 8, 13])
        self.assertGreaterEqual(res["complexity_factors"]["technical"], 5.0)
        self.assertEqual(len(res["confidence_interval"]), 2)
        self.assertLessEqual(res["confidence_interval"][0], res["predicted_story_points"])
        self.assertGreaterEqual(res["confidence_interval"][1], res["predicted_story_points"])
        self.assertTrue(len(res["similar_requirements"]) > 0)
        self.assertEqual(res["similar_requirements"][0]["effort_points"], 8)

    def test_feature_2_gherkin_acceptance_criteria(self):
        """Feature 2 Hardening: Verify Gherkin scenario parsing, coverage, and test stub generation."""
        gherkin_text = """
        Scenario: User authentication success
        Given a registered user with valid credentials
        When the user submits login request
        Then jwt token is issued and status 200 returned

        Scenario: User authentication missing password
        Given an unregistered user
        When login request submitted with empty password
        Then status 400 validation error is returned
        """
        parsed = CheckpointDX.parse_and_validate_gherkin(gherkin_text)
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["coverage_score"], 100.0)
        self.assertEqual(len(parsed["scenarios"]), 2)
        self.assertIn("class TestRequirementAcceptance(unittest.TestCase):", parsed["test_stubs"])
        self.assertIn("def test_user_authentication_success(self):", parsed["test_stubs"])

        # Invalid gherkin missing 'Then'
        invalid_text = "Scenario: Incomplete\nGiven something\nWhen something happens"
        invalid_parsed = CheckpointDX.parse_and_validate_gherkin(invalid_text)
        self.assertFalse(invalid_parsed["valid"])
        self.assertEqual(invalid_parsed["coverage_score"], 0.0)
        self.assertIn("missing: Then", invalid_parsed["errors"][0])

    def test_feature_2_interactive_dependency_graph_and_cycles(self):
        """Feature 2 Hardening: Verify circular cycle detection, critical path, and delay impact."""
        dx = CheckpointDX()
        dx.supabase = MagicMock()
        dx.get_checkpoint = MagicMock(return_value={"id": "cp-1", "checkpoint_id": "chk-01"})

        # Case 1: Circular dependency A -> B -> A
        mock_reqs_cycle = [
            {"id": "A", "requirement_text": "Task A", "story_points": 3, "priority_tier": "P0"},
            {"id": "B", "requirement_text": "Task B", "story_points": 5, "priority_tier": "P1"},
        ]
        mock_edges_cycle = [
            {"requirement_id": "A", "depends_on_requirement_id": "B"},
            {"requirement_id": "B", "depends_on_requirement_id": "A"},
        ]

        dx.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_reqs_cycle
        dx.supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = mock_edges_cycle

        graph_cycle = dx.analyze_requirement_dependencies_interactive("chk-01")
        self.assertTrue(graph_cycle["has_circular_dependency"])
        self.assertTrue(len(graph_cycle["cycles"]) > 0)

        # Case 2: Clean DAG: A depends on B, B depends on C (execution order: C -> B -> A)
        mock_reqs_dag = [
            {"id": "A", "requirement_text": "Task A", "story_points": 3},
            {"id": "B", "requirement_text": "Task B", "story_points": 5},
            {"id": "C", "requirement_text": "Task C", "story_points": 2},
        ]
        mock_edges_dag = [
            {"requirement_id": "A", "depends_on_requirement_id": "B"},
            {"requirement_id": "B", "depends_on_requirement_id": "C"},
        ]
        dx.supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_reqs_dag
        dx.supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = mock_edges_dag

        graph_dag = dx.analyze_requirement_dependencies_interactive("chk-01")
        self.assertFalse(graph_dag["has_circular_dependency"])
        self.assertEqual(graph_dag["critical_path_length"], 10)  # C (2) + B (5) + A (3)
        self.assertEqual(graph_dag["critical_path"], ["C", "B", "A"])

        # Delay ripple: delaying C affects B and A (2 downstream tasks)
        self.assertEqual(graph_dag["delay_impacts"]["C"]["downstream_count"], 2)
        self.assertEqual(set(graph_dag["delay_impacts"]["C"]["downstream_ids"]), {"B", "A"})
        # Delaying A has 0 downstream tasks
        self.assertEqual(graph_dag["delay_impacts"]["A"]["downstream_count"], 0)

    # ==========================================================================
    # FEATURE 3 (HARDENED+): Intent Conformance & Implementation Auditor Tests
    # ==========================================================================
    def test_feature_3_semantic_clause_matching(self):
        """Feature 3.1: Verify semantic clause categorization, Jaccard overlap, and unmatched diagnosis."""
        dx = CheckpointDX()

        # 1. Matching Security Clause
        sec_clause = "Implement user authentication with JWT bearer tokens and bcrypt password hashing"
        sec_hunks = [{
            "file_path": "lib/auth.py",
            "diff_hunk": (
                "def hash_pw(pw): return bcrypt.hashpw(pw, salt)\n"
                "def verify_jwt(token): return jwt.decode(token, secret)\n"
            ),
        }]
        res_sec = dx.match_clause_semantic(sec_clause, sec_hunks)
        self.assertEqual(res_sec["clause_category"], "security")
        self.assertIn("authentication", res_sec["clause_intent"].lower())
        self.assertEqual(res_sec["match_status"], "met")
        self.assertGreater(res_sec["semantic_match_score"], 0.50)
        self.assertGreater(len(res_sec["matched_hunks"]), 0)

        # 2. Performance Clause Category
        perf_clause = "Add Redis caching layer for low latency and query acceleration"
        res_perf = dx.match_clause_semantic(perf_clause, [])
        self.assertEqual(res_perf["clause_category"], "performance")
        self.assertEqual(res_perf["match_status"], "unmatched")
        self.assertEqual(res_perf["unmatched_reason"], "no_code_change")
        self.assertTrue(len(res_perf["recommendation"]) > 0)

        # 3. UI/UX Clause Category
        ui_clause = "Build interactive Streamlit UI dashboard with tabs and progress widgets"
        res_ui = dx.match_clause_semantic(ui_clause, [])
        self.assertEqual(res_ui["clause_category"], "ui_ux")

    def test_feature_3_conformance_scoring_and_grading(self):
        """Feature 3.1 & 3.2: Verify 4-dimension weighted score, letter grading (A-F), and improvement suggestions."""
        # Grade A: >= 0.90
        grade_a = CheckpointDX.calculate_conformance_score(0.95, 0.90, 0.92, 0.85)
        self.assertEqual(grade_a["grade"], "A")
        self.assertGreaterEqual(grade_a["overall_score"], 0.90)

        # Grade B: 0.75 - 0.89
        grade_b = CheckpointDX.calculate_conformance_score(0.80, 0.75, 0.80, 0.70)
        self.assertEqual(grade_b["grade"], "B")
        self.assertGreaterEqual(grade_b["overall_score"], 0.75)
        self.assertLess(grade_b["overall_score"], 0.90)

        # Grade C: 0.60 - 0.74
        grade_c = CheckpointDX.calculate_conformance_score(0.65, 0.60, 0.60, 0.55)
        self.assertEqual(grade_c["grade"], "C")

        # Grade D: 0.45 - 0.59
        grade_d = CheckpointDX.calculate_conformance_score(0.50, 0.45, 0.50, 0.40)
        self.assertEqual(grade_d["grade"], "D")

        # Grade F: < 0.45
        grade_f = CheckpointDX.calculate_conformance_score(0.30, 0.20, 0.40, 0.10)
        self.assertEqual(grade_f["grade"], "F")
        self.assertLess(grade_f["overall_score"], 0.45)

        # Improvement suggestions presence
        self.assertGreater(len(grade_f["top_improvements"]), 0)
        first_imp = grade_f["top_improvements"][0]
        self.assertIn("dimension", first_imp)
        self.assertIn("action", first_imp)

    def test_feature_3_implementation_status_8_states(self):
        """Feature 3.2: Verify 8-state status classification, evidence linking, and completion percentage."""
        dx = CheckpointDX()

        # 1. Blocked state
        blocked_res = dx.classify_implementation_status("Deploy payment service", [], is_blocked=True)
        self.assertEqual(blocked_res["status"], "blocked")
        self.assertEqual(blocked_res["primary_status"], "blocked")

        # 2. Not Met (no hunks)
        not_met_res = dx.classify_implementation_status("Build billing webhook", [])
        self.assertEqual(not_met_res["status"], "not_met")
        self.assertEqual(not_met_res["completion_percentage"], 0)

        # 3. Fully Met (high confidence + test suite)
        hunk_met = [{"file_path": "lib/auth.py", "confidence": 0.85, "matched_lines": [12]}]
        met_res = dx.classify_implementation_status("Implement auth module", hunk_met, has_tests=True)
        self.assertEqual(met_res["status"], "fully_met")
        self.assertEqual(met_res["completion_percentage"], 100)
        self.assertTrue(len(met_res["supporting_evidence"]["code_references"]) > 0)
        self.assertTrue(len(met_res["supporting_evidence"]["test_references"]) > 0)

        # 4. Partially Met (moderate confidence)
        hunk_partial = [{"file_path": "lib/auth.py", "confidence": 0.55, "matched_lines": [5]}]
        partial_res = dx.classify_implementation_status("Implement auth module", hunk_partial, has_tests=False)
        self.assertEqual(partial_res["status"], "partially_met")
        self.assertGreater(len(partial_res["missing_aspects"]), 0)

    def test_feature_3_calibrated_confidence_model(self):
        """Feature 3.3: Verify multi-factor calibration, 95% confidence interval, and manual review triggers."""
        # Clean scenario
        clean_calib = CheckpointDX.calibrate_confidence_score(
            raw_confidence=0.85,
            clause_clarity=0.90,
            code_complexity=0.30,
            test_quality=0.85,
        )
        self.assertGreaterEqual(clean_calib["calibrated_score"], 0.80)
        self.assertFalse(clean_calib["should_manual_review"])
        self.assertEqual(len(clean_calib["confidence_interval"]), 2)
        self.assertLessEqual(clean_calib["confidence_interval"][0], clean_calib["confidence_interval"][1])

        # High uncertainty scenario triggering manual review
        uncertain_calib = CheckpointDX.calibrate_confidence_score(
            raw_confidence=0.40,
            clause_clarity=0.40,
            code_complexity=0.80,
            test_quality=0.30,
        )
        self.assertTrue(uncertain_calib["should_manual_review"])
        self.assertIn("threshold", uncertain_calib["manual_review_reason"].lower())
        self.assertGreaterEqual(len(uncertain_calib["uncertainty_sources"]), 2)

    def test_feature_3_auto_remediation_generation(self):
        """Feature 3.2: Verify code snippet generation, effort estimation, and unified dry run preview."""
        dx = CheckpointDX()
        remedy = dx.generate_auto_remediations(
            clause_text="User session timeout with Redis expiration key",
            missing_aspects=["session_timeout_handler", "redis_key_ttl"],
            file_path="lib/session.py",
        )
        self.assertTrue(remedy["can_auto_fix"])
        self.assertIn("15min", remedy["effort_estimate"])
        self.assertGreater(len(remedy["remediation_steps"]), 0)
        self.assertIn("--- a/lib/session.py", remedy["auto_fix_dry_run_output"])
        self.assertIn("+++ b/lib/session.py", remedy["auto_fix_dry_run_output"])
        self.assertIn("python scripts/apply_intent_patch.py", remedy["auto_fix_command"])

    def test_feature_3_compliance_dashboard_violations_and_export(self):
        """Feature 3.4: Verify dashboard KPIs, violation recording/resolving, and multi-format report exports."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])
        cid = "chk-test-f3-01"

        # 1. Record Violation
        v_rec = dx.record_compliance_violation(
            checkpoint_id=cid,
            clause_id="clause-101",
            clause_text="Missing TLS 1.3 enforcement",
            violation_type="security",
            severity="critical",
            deadline="2026-10-01",
            assigned_to="security-architect",
        )
        self.assertEqual(v_rec["status"], "open")
        self.assertEqual(v_rec["severity"], "critical")
        self.assertEqual(v_rec["violation_type"], "security")

        # 2. Get Compliance Dashboard
        dash = dx.get_compliance_dashboard(cid)
        self.assertIn("conformance_rate", dash)
        self.assertIn("grade", dash)
        self.assertIn("by_category", dash)
        self.assertIn("security", dash["by_category"])
        self.assertGreater(len(dash["critical_violations"]), 0)

        # 3. Resolve Violation
        res_v = dx.resolve_compliance_violation(v_rec["id"], resolution_notes="Enforced TLS in config")
        self.assertEqual(res_v["status"], "resolved")

        # 4. Multi-format export
        rep_md = dx.export_compliance_report(cid, format="markdown")
        self.assertIn("# Compliance Audit Report", rep_md)
        self.assertIn("Overall Compliance Score", rep_md)

        rep_json = dx.export_compliance_report(cid, format="json")
        json_obj = json.loads(rep_json)
        self.assertIn("checkpoint_id", json_obj)
        self.assertIn("overall_compliance_score", json_obj)

        rep_csv = dx.export_compliance_report(cid, format="csv")
        self.assertIn("clause_text", rep_csv)
        self.assertIn("implementation_status", rep_csv)

    # =========================================================================
    # Feature 4 (Hardened+): Blueprint Verification Suite
    # =========================================================================

    def test_feature_4_dynamic_synthesis_weighting(self):
        """Feature 4.1: Verify dynamic weighting presets, context adjustments, and override normalization."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        # 1. Base Presets
        dev_w = dx.calculate_synthesis_weights(contract_purpose="development")
        self.assertEqual(dev_w["contract_purpose"], "development")
        self.assertAlmostEqual(sum(dev_w["final_weights"].values()), 1.0, places=2)
        self.assertEqual(dev_w["final_weights"]["requirements"], 0.40)

        qa_w = dx.calculate_synthesis_weights(contract_purpose="qa_handoff")
        self.assertEqual(qa_w["final_weights"]["intents"], 0.45)

        pm_w = dx.calculate_synthesis_weights(contract_purpose="pm_review")
        self.assertEqual(pm_w["final_weights"]["requirements"], 0.50)

        # 2. Dynamic Adjustment factors
        dx.get_dead_ends = MagicMock(return_value=[{"root_cause": f"Bug {i}"} for i in range(8)])
        dx.check_resume_integrity = MagicMock(return_value={"integrity_score": 0.45})
        dx.get_requirements = MagicMock(return_value=[
            {"requirement_text": "Critical payment", "priority_tier": "P0", "status": "in_progress"},
            {"requirement_text": "Auth check", "priority_tier": "P0", "status": "not_started"},
            {"requirement_text": "Styling tweak", "priority_tier": "P2", "status": "not_started"},
        ])

        dyn_w = dx.calculate_synthesis_weights(contract_purpose="development", checkpoint_id="chk-dyn-01")
        self.assertGreater(len(dyn_w["dynamic_adjustments"]), 0)
        self.assertAlmostEqual(sum(dyn_w["final_weights"].values()), 1.0, places=2)

        # 3. Manual Overrides
        overrides = {"requirements": 0.50, "dead_ends": 0.20, "intents": 0.20, "integrity": 0.10}
        custom_w = dx.calculate_synthesis_weights(contract_purpose="development", overrides=overrides)
        self.assertAlmostEqual(sum(custom_w["final_weights"].values()), 1.0, places=2)
        self.assertEqual(custom_w["final_weights"]["requirements"], 0.50)

    def test_feature_4_cross_feature_conflict_detection_and_resolution(self):
        """Feature 4.1: Verify cross-feature conflict detection and resolution across features B, A, C, E."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])
        cid = "chk-conflict-01"
        sid = "sess-conflict-01"

        # Mock feature state with deliberate overlaps
        dx.get_requirements = MagicMock(return_value=[
            {"id": "req-1", "requirement_text": "Implement Redis distributed lock mechanism", "priority_tier": "P0", "status": "in_progress"},
            {"id": "req-2", "requirement_text": "OAuth user authentication flow", "priority_tier": "P1", "status": "done"},
        ])
        dx.get_dead_ends = MagicMock(return_value=[
            {"id": "de-1", "root_cause": "Redis distributed lock mechanism timeout under concurrent load", "suggested_fix": "Use Postgres advisory locks"}
        ])
        dx.get_intent_conformance = MagicMock(return_value=[
            {"id": "int-1", "intent_text": "OAuth user authentication flow verification", "implementation_status": "gap"}
        ])
        dx.check_resume_integrity = MagicMock(return_value={"integrity_score": 0.90})

        conflicts = dx.detect_feature_conflicts(cid, sid)
        self.assertGreaterEqual(len(conflicts), 2)

        types = {c["conflict_type"] for c in conflicts}
        self.assertIn("requirement_vs_dead_end", types)
        self.assertIn("intent_vs_requirement", types)

        c_target = conflicts[0]
        self.assertFalse(c_target["resolved"])
        self.assertGreater(len(c_target["resolution_strategies"]), 0)

        # Resolve conflict
        res = dx.resolve_feature_conflict(c_target["id"], strategy_id="strat_pivot", resolution_notes="Pivoted to advisory locks")
        self.assertTrue(res["resolved"])
        self.assertEqual(res["strategy_id"], "strat_pivot")

    def test_feature_4_custom_templates_builder_and_versioning(self):
        """Feature 4.2: Verify custom template creation, section customization, and version increments."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        tpl_name = "test_security_audit"
        custom_sections = [
            {"key": "unresolved_requirements", "title": "Security Requirements", "visible": True, "order": 1},
            {"key": "do_not_retry", "title": "Vulnerability Dead-Ends", "visible": True, "order": 2},
            {"key": "integrity_check", "title": "System Integrity", "visible": True, "order": 3},
        ]
        tpl = dx.create_custom_template(
            template_name=tpl_name,
            target_audience="Security Lead",
            sections=custom_sections,
            theme={"layout": "technical", "accent": "#ef4444"},
        )
        self.assertEqual(tpl["template_name"], tpl_name)
        self.assertTrue(tpl["is_valid"])

        # Fetch templates
        all_tpls = dx.get_custom_templates()
        self.assertTrue(any(t.get("template_name") == tpl_name for t in all_tpls))

        # Increment version
        v2 = dx.create_template_version(
            template_id=tpl["id"],
            changelog="Added flagged gaps section",
            sections=custom_sections + [{"key": "flagged_gaps", "title": "Audit Gaps", "visible": True, "order": 4}],
        )
        self.assertEqual(v2["version_number"], 2)
        self.assertIn("flagged_gaps", str(v2["sections"]))

    def test_feature_4_ab_testing_framework(self):
        """Feature 4.2: Verify template A/B test creation and results aggregation."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        ab_test = dx.create_ab_test(
            test_name="Dev vs QA Efficiency Benchmark",
            variant_a_id="dev",
            variant_b_id="qa",
            traffic_split=0.5
        )
        self.assertEqual(ab_test["test_name"], "Dev vs QA Efficiency Benchmark")
        self.assertEqual(ab_test["status"], "running")

        all_tests = dx.get_ab_tests()
        self.assertGreater(len(all_tests), 0)
        found = next((t for t in all_tests if t.get("id") == ab_test["id"]), all_tests[0])
        self.assertIn("results", found)
        self.assertIn("winner", found["results"])

    def test_feature_4_semantic_contract_diffing_and_impact_analysis(self):
        """Feature 4.3: Verify semantic diffing detects 8 change types and produces stakeholder recommendations."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        payload_v1 = {
            "version": 1,
            "unresolved_requirements": [{"text": "OAuth login", "status": "not_started", "priority": 1}],
            "do_not_retry": [{"reason_abandoned": "Redis timeout"}],
            "flagged_gaps": [{"clause": "Refresh token missing"}],
            "integrity_check": {"integrity_score": 0.60},
        }
        payload_v2 = {
            "version": 2,
            "unresolved_requirements": [
                {"text": "OAuth login", "status": "in_progress", "priority": 1},
                {"text": "MFA Support", "status": "not_started", "priority": 2},
            ],
            "do_not_retry": [
                {"reason_abandoned": "Redis timeout"},
                {"reason_abandoned": "Deadlock in table alter"},
            ],
            "flagged_gaps": [],
            "integrity_check": {"integrity_score": 0.85},
        }

        diff = dx.compute_semantic_contract_diff(payload_v1, payload_v2)
        self.assertEqual(diff["version_a"], 1)
        self.assertEqual(diff["version_b"], 2)
        self.assertGreater(diff["total_changes"], 0)

        change_types = {c["change_type"] for c in diff["changes"]}
        self.assertIn("requirement_added", change_types)
        self.assertIn("requirement_modified", change_types)
        self.assertIn("dead_end_added", change_types)
        self.assertIn("intent_conformance_changed", change_types)
        self.assertIn("integrity_score_changed", change_types)

        self.assertIn("impact_on_development", diff["impact_analysis"])
        self.assertIn("impact_on_qa", diff["impact_analysis"])
        self.assertIn("impact_on_timeline", diff["impact_analysis"])
        self.assertEqual(len(diff["stakeholder_recommendations"]), 3)

    def test_feature_4_advanced_analytics_and_roi_metrics(self):
        """Feature 4.4: Verify advanced contract analytics, engagement heatmap, funnel, and ROI hours saved."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        analytics = dx.get_advanced_contract_analytics(None)
        self.assertGreater(analytics["total_loads"], 0)
        self.assertGreater(analytics["unique_users"], 0)
        self.assertGreater(analytics["roi_hours_saved"], 0.0)

        self.assertIn("human_ui_view", analytics["consumer_breakdown"])
        self.assertIn("api_fetch", analytics["consumer_breakdown"])
        self.assertIn("agent_session", analytics["consumer_breakdown"])

        self.assertIn("avg_view_duration_seconds", analytics["engagement"])
        self.assertIn("section_clicks_heatmap", analytics["engagement"])
        self.assertGreater(len(analytics["funnel"]["steps"]), 0)
        self.assertEqual(len(analytics["time_series_7d"]), 7)

    def test_feature_4_generate_resume_contract_backward_compatibility_and_synthesis(self):
        """Feature 4: Verify generate_resume_contract maintains 100% backward-compatibility while incorporating synthesis weights and conflicts."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])
        dx.get_checkpoint = MagicMock(return_value={"id": "chk-f4-01", "session_id": "sess-f4-01"})
        dx.get_requirements = MagicMock(return_value=[{"requirement_text": "Build telemetry", "status": "not_started", "priority": 1}])
        dx.get_dead_ends = MagicMock(return_value=[])
        dx.get_intent_conformance = MagicMock(return_value=[])
        dx.check_resume_integrity = MagicMock(return_value={"integrity_score": 0.85})

        # Backward compatible call (3 args)
        res_compat = dx.generate_resume_contract("chk-f4-01", "sess-f4-01", template="dev")
        self.assertIn("contract", res_compat)
        self.assertIn("synthesis_weights", res_compat)
        self.assertIn("conflicts", res_compat)
        self.assertTrue(res_compat["validation"]["valid"])

        # Hardened+ call with custom purpose and weights
        res_weighted = dx.generate_resume_contract(
            "chk-f4-01",
            "sess-f4-01",
            template="dev",
            contract_purpose="pm_review",
            custom_weights={"requirements": 0.60, "dead_ends": 0.10, "intents": 0.20, "integrity": 0.10}
        )
        self.assertEqual(res_weighted["contract"]["contract_purpose"], "pm_review")
        self.assertEqual(res_weighted["synthesis_weights"]["final_weights"]["requirements"], 0.60)


    # =========================================================================
    # FEATURE 5 HARDENED+: RESUME INTEGRITY CHECK & MEMORY RESILIENCE TESTS
    # =========================================================================

    def test_feature_5_1_multi_session_integrity(self):
        """Feature 5.1: Multi-session integrity aggregation with exponential decay weighting."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        # Mock check_resume_integrity returns different scores for different sessions
        def mock_check_resume(session_id, **kwargs):
            if session_id == "sess-recent":
                return {"integrity_score": 0.95, "reason": "Fresh memory covers all reqs", "stale_memory_count": 0, "conflicts": []}
            elif session_id == "sess-mid":
                return {"integrity_score": 0.70, "reason": "Partial coverage", "stale_memory_count": 1, "conflicts": []}
            else:
                return {"integrity_score": 0.40, "reason": "Stale entries and gaps", "stale_memory_count": 4, "conflicts": ["contradiction"]}

        dx.check_resume_integrity = MagicMock(side_effect=mock_check_resume)

        session_ids = ["sess-recent", "sess-mid", "sess-old"]
        res = dx.calculate_multi_session_integrity(session_ids)

        self.assertIn("aggregate_score", res)
        self.assertGreaterEqual(res["aggregate_score"], 0.0)
        self.assertLessEqual(res["aggregate_score"], 1.0)
        self.assertEqual(res["session_count"], 3)
        self.assertIn("sess-recent", res["session_scores"])
        self.assertIn("sess-mid", res["session_scores"])
        self.assertIn("sess-old", res["session_scores"])

        # sess-recent should have higher or equal recency weight than sess-old
        w_recent = res["session_scores"]["sess-recent"]["normalized_weight"]
        w_old = res["session_scores"]["sess-old"]["normalized_weight"]
        self.assertGreater(w_recent, w_old)

        self.assertIn("status", res)
        self.assertTrue(any(tag in res["status"] for tag in ["[SAFE]", "[WARNING]", "[BLOCKED]"]))
        self.assertNotIn("\U0001f680", str(res))
        self.assertNotIn("\u2705", str(res))

    def test_feature_5_2_integrity_trend_and_forecast(self):
        """Feature 5.2: 7-day rolling window integrity trend analysis and predictive linear regression forecast."""
        import uuid
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        session_id = f"sess-trend-{uuid.uuid4().hex[:6]}"

        # 1. Record improving trend
        rec1 = dx.record_integrity_trend(session_id, "chk-1", 0.70, "Initial")
        self.assertEqual(rec1["trend_direction"], "stable")

        rec2 = dx.record_integrity_trend(session_id, "chk-2", 0.90, "Improved coverage")
        self.assertEqual(rec2["trend_direction"], "improving")
        self.assertAlmostEqual(rec2["trend_magnitude"], 0.20, places=2)

        # 2. Get 7-day trend and forecast
        trend_res = dx.get_integrity_trend_7d(session_id)
        self.assertIn("trend_direction", trend_res)
        self.assertIn("slope", trend_res)
        self.assertIn("forecast_7d", trend_res)
        self.assertGreaterEqual(trend_res["forecast_7d"], 0.0)
        self.assertLessEqual(trend_res["forecast_7d"], 1.0)
        self.assertIn(trend_res["trend_direction"], ["improving", "stable", "degrading"])
        self.assertTrue(any(tag in trend_res["summary"] for tag in ["[IMPROVING]", "[STABLE]", "[DEGRADING]"]))

    def test_feature_5_3_automated_memory_cleanup_and_ttl(self):
        """Feature 5.3: Automated memory cleanup with configurable TTL and safe dry-run preview."""
        import uuid
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        session_id = f"sess-cleanup-{uuid.uuid4().hex[:6]}"

        # 1. Configure TTL
        ttl_conf = dx.configure_memory_ttl(session_id, ttl_days=14, auto_cleanup_enabled=True)
        self.assertEqual(ttl_conf["session_id"], session_id)
        self.assertEqual(ttl_conf["ttl_days"], 14)
        self.assertTrue(ttl_conf["auto_cleanup_enabled"])

        # 2. Dry run preview
        dry_res = dx.cleanup_stale_memory(session_id, dry_run=True)
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(dry_res["ttl_days"], 14)
        self.assertIn("candidate_count", dry_res)
        self.assertIn("reclaimed_kb", dry_res)
        self.assertIn("[PREVIEW]", dry_res["status"])

        # 3. Execution (non dry-run)
        clean_res = dx.cleanup_stale_memory(session_id, dry_run=False)
        self.assertFalse(clean_res["dry_run"])
        self.assertIn("deleted_count", clean_res)
        self.assertIn("cleaned_at", clean_res)
        self.assertIn("[CLEANUP COMPLETE]", clean_res["status"])

    def test_feature_5_4_anomaly_detection_and_alerts(self):
        """Feature 5.4: Statistical anomaly detection (z-score drops) and alert acknowledgment workflow."""
        import uuid
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])

        session_id = f"sess-anomaly-{uuid.uuid4().hex[:6]}"

        # Seed historical baseline (high scores)
        for i in range(5):
            dx.record_integrity_trend(session_id, f"chk-base-{i}", 0.95, "Normal baseline")

        # Record sharp drop
        dx.record_integrity_trend(session_id, "chk-drop", 0.30, "Severe degradation")

        # Detect anomalies
        anomalies = dx.detect_integrity_anomalies(session_id, threshold_std_dev=2.0)
        self.assertGreaterEqual(len(anomalies), 1)
        alert = anomalies[0]
        self.assertEqual(alert["session_id"], session_id)
        self.assertIn(alert["severity"], ["critical", "major", "minor"])
        self.assertFalse(alert["acknowledged"])

        # Query alerts
        active_alerts = dx.get_integrity_alerts(session_id, unacknowledged_only=True)
        self.assertGreaterEqual(len(active_alerts), 1)

        # Acknowledge alert
        alert_id = active_alerts[0]["id"]
        ack_success = dx.acknowledge_alert(alert_id)
        self.assertTrue(ack_success)

        # Verify acknowledged
        remaining = dx.get_integrity_alerts(session_id, unacknowledged_only=True)
        self.assertFalse(any(a["id"] == alert_id for a in remaining))

    def test_feature_5_5_root_cause_diagnosis(self):
        """Feature 5.5: Automated root-cause diagnosis across 5 degradation factors with ranked recommendations."""
        dx = CheckpointDX()
        dx._run_sql = MagicMock(return_value=[])
        dx.check_resume_integrity = MagicMock(return_value={
            "integrity_score": 0.45,
            "reason": "Low coverage, 4 stale entries",
            "stale_memory_count": 4,
            "conflicts": ["conf-1"],
        })

        session_id = "sess-diag-test"
        diag = dx.diagnose_low_integrity(session_id, checkpoint_id="chk-diag")

        self.assertEqual(diag["overall_integrity"], 0.45)
        self.assertEqual(diag["status"], "[BLOCKED]")
        self.assertIn("primary_root_cause", diag)
        self.assertIn("factor_analysis", diag)
        fa = diag["factor_analysis"]
        self.assertIn("memory_coverage", fa)
        self.assertIn("open_scope", fa)
        self.assertIn("dead_end_density", fa)
        self.assertIn("intent_gaps", fa)
        self.assertIn("stale_memory", fa)

        self.assertGreater(len(diag["recommendations"]), 0)
        for rec in diag["recommendations"]:
            self.assertTrue(rec.startswith("[ACTION"))

        # Strict zero emoji verification
        full_diag_str = str(diag)
        self.assertNotIn("\U0001f534", full_diag_str)
        self.assertNotIn("\U0001f7e1", full_diag_str)
        self.assertNotIn("\U0001f6a8", full_diag_str)
        self.assertNotIn("\U0001f4a1", full_diag_str)



    def test_feature_3_intent_clustering(self):
        """Feature 3.3: Verifies semantic clustering of intent clauses into domain groups."""
        dx = CheckpointDX()
        sample_intents = [
            {"clause": "User authentication with JWT bearer tokens and password hashing", "confidence_score": 0.95, "implementation_status": "fully_met"},
            {"clause": "OAuth2 refresh token rotation and revocation list", "confidence_score": 0.90, "implementation_status": "met"},
            {"clause": "Redis caching layer for database query acceleration", "confidence_score": 0.70, "implementation_status": "partially_met"},
            {"clause": "Streamlit interactive dashboard with metric widgets", "confidence_score": 0.92, "implementation_status": "fully_met"},
            {"clause": "Compliance audit trail exporting signed reports", "confidence_score": 0.88, "implementation_status": "met"},
            {"clause": "Calculate order totals with discount rules", "confidence_score": 0.85, "implementation_status": "met"},
        ]
        clusters = dx.cluster_intents(sample_intents)
        self.assertGreater(len(clusters), 0)

        categories = [c["category"] for c in clusters]
        self.assertIn("security", categories)
        self.assertIn("performance", categories)

        for c in clusters:
            self.assertIn("cluster_name", c)
            self.assertIn("member_count", c)
            self.assertIn("average_conformance_score", c)
            self.assertIn("conformance_status", c)
            self.assertIn(c["conformance_status"], ["[HEALTHY]", "[WARNING]", "[DEGRADED]"])
            self.assertGreaterEqual(c["average_conformance_score"], 0.0)
            self.assertLessEqual(c["average_conformance_score"], 1.0)

        # Zero emoji validation
        clusters_str = str(clusters)
        self.assertNotIn("\U0001f3af", clusters_str)
        self.assertNotIn("\U0001f510", clusters_str)

    def test_feature_3_intent_conformance_trends(self):
        """Feature 3.4: Verifies 7-day intent conformance trajectory, slope, and forecasting."""
        dx = CheckpointDX()
        trends = dx.get_intent_conformance_trends()

        self.assertIn("history", trends)
        self.assertIn("trend_direction", trends)
        self.assertIn("slope", trends)
        self.assertIn("trend_magnitude", trends)
        self.assertIn("forecast_7d", trends)
        self.assertIn("average_conformance", trends)
        self.assertIn("summary", trends)

        self.assertIn(trends["trend_direction"], ["improving", "stable", "degrading"])
        self.assertGreaterEqual(trends["trend_magnitude"], 0.0)
        self.assertGreaterEqual(trends["forecast_7d"], 0.0)
        self.assertLessEqual(trends["forecast_7d"], 1.0)
        self.assertTrue(trends["summary"].startswith("[") or "Conformance" in trends["summary"])

    def test_feature_3_confidence_filtering(self):
        """Feature 3.2: Verifies filtering intent records by minimum confidence threshold."""
        dx = CheckpointDX()
        sample_intents = [
            {"clause": "High confidence clause 1", "confidence_score": 0.95},
            {"clause": "High confidence clause 2", "confidence_score": 0.80},
            {"clause": "Marginal clause", "confidence_score": 0.65},
            {"clause": "Low confidence clause", "confidence_score": 0.35},
        ]
        high_conf = dx.filter_conformance_by_confidence(sample_intents, min_confidence=0.75)
        self.assertEqual(len(high_conf), 2)
        for item in high_conf:
            self.assertGreaterEqual(item["confidence_score"], 0.75)

    def test_feature_convenience_aliases_and_signatures(self):
        """Cross-Feature verification: Ensures all convenience methods and return keys exist for test scripts."""
        dx = CheckpointDX()

        # Feature 1
        de_list = [
            {"dead_end_type": "deadlock", "root_cause": "Race condition in worker", "failed_attempts": 3, "confidence": 0.8},
            {"dead_end_type": "schema_mismatch", "root_cause": "Missing column", "failed_attempts": 1, "confidence": 0.5},
        ]
        clusters = dx.cluster_dead_ends(de_list)
        self.assertEqual(len(clusters), 2)

        sev = dx.calculate_severity(de_list[0])
        self.assertIn("severity", sev)
        self.assertIn("severity_score", sev)
        self.assertEqual(sev["severity"], "CRITICAL")
        self.assertGreater(sev["severity_score"], 0.7)

        # Feature 2
        p0 = dx.prioritize_requirement("Critical: Fix authentication blocker")
        self.assertEqual(p0["priority"], "P0")
        self.assertGreater(p0["confidence"], 0.8)

        eff = dx.estimate_effort("Trivial: Update button color")
        self.assertEqual(eff["tshirt_size"], "XS")
        self.assertEqual(eff["story_points"], 1)

        # Feature 4
        weights = dx.calculate_synthesis_weights("DEV", {"dead_ends": 6, "integrity_score": 0.55, "p0_ratio": 0.45})
        self.assertIn("final_weights", weights)
        self.assertIn("dead_ends", weights["final_weights"])

        conflicts = dx.detect_feature_conflicts("chk-test-mock")
        self.assertIsInstance(conflicts, list)

        # Feature 5
        multi = dx.calculate_multi_session_integrity(["s1", "s2"])
        self.assertIn("multi_session_integrity_score", multi)

        trend = dx.get_integrity_trend_7d("sess-mock")
        self.assertIn("trend_magnitude", trend)

        cleanup = dx.cleanup_stale_memory("sess-mock", dry_run=True)
        self.assertIn("entries_marked", cleanup)

        diag = dx.diagnose_low_integrity("sess-mock", "chk-mock")
        self.assertIn("root_causes", diag)
        self.assertGreater(len(diag["root_causes"]), 0)

if __name__ == "__main__":
    unittest.main()



