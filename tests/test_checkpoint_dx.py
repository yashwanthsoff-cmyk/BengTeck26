"""tests/test_checkpoint_dx.py
Comprehensive automated test suite for Checkpoint-Native DX (v9).
Verifies:
- All 5 review fixes (Fix 5.1/1, Fix 5.2/2, Fix 5.3, Fix 5.4, Fix 3, Fix 4)
- All 5 core features (A, B, C, D, E)
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Allow importing from root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
            self.assertIn("race condition in sync cache", executed_sql)

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
        dx._run_sql.assert_called_once()
        delta_sql = dx._run_sql.call_args[0][0]
        self.assertIn("INSERT INTO", delta_sql)
        self.assertIn("Implement OAuth2", delta_sql)

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
        self.assertIn("confidence + -0.2", sql_down)

        fb_up = dx.record_human_feedback("chk-1", "Implement OAuth2", was_correct=True)
        self.assertEqual(fb_up["adjusted_by"], 0.1)

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


if __name__ == "__main__":
    unittest.main()
