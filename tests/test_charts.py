"""tests/test_charts.py — Unit Tests for Checkpoint-Native DX Visualization Engine
Validates all 22 interactive visual representations, battery meters, radial gauges,
sparklines, trend chips, zero-emoji enforcement, and fallback states.
"""
import unittest
import plotly.graph_objects as go
import lib.charts as lc


class TestChartsEngine(unittest.TestCase):

    def test_empty_chart_state(self):
        fig = lc.render_empty_chart_state("Custom Title", "Custom Reason")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.layout.annotations), 1)
        self.assertIn("CUSTOM TITLE", fig.layout.annotations[0].text)
        self.assertIn("Custom Reason", fig.layout.annotations[0].text)

    def test_metric_sparkline_svg(self):
        # Empty/single data points
        svg_empty = lc.render_metric_sparkline_svg([])
        self.assertIn("<svg", svg_empty)
        svg_single = lc.render_metric_sparkline_svg([10.0])
        self.assertIn("<svg", svg_single)
        
        # Valid series
        svg_valid = lc.render_metric_sparkline_svg([10.0, 15.0, 12.0, 20.0, 25.0])
        self.assertIn("<polyline", svg_valid)
        self.assertIn("<circle", svg_valid)

    def test_trend_chip_html(self):
        # Positive trend (higher is better)
        chip_pos = lc.render_trend_chip_html(85.0, 80.0, label="vs target", is_higher_better=True)
        self.assertIn("&uarr;", chip_pos)
        self.assertIn("+5.0%", chip_pos)
        self.assertIn("vs target", chip_pos)

        # Negative trend (higher is better)
        chip_neg = lc.render_trend_chip_html(70.0, 80.0, label="vs baseline", is_higher_better=True)
        self.assertIn("&darr;", chip_neg)
        self.assertIn("-10.0%", chip_neg)

        # Stable trend
        chip_flat = lc.render_trend_chip_html(80.0, 80.0)
        self.assertIn("&rarr;", chip_flat)
        self.assertIn("0.0%", chip_flat)

    # Feature 5 Flagship Visuals
    def test_render_integrity_trajectory_flagship(self):
        trend_res = {
            "history": [
                {"checkpoint_id": "c1", "integrity_score": 0.85, "recorded_at": "2026-09-10"},
                {"checkpoint_id": "c2", "integrity_score": 0.90, "recorded_at": "2026-09-12"},
            ],
            "average_score": 0.875,
            "forecast_7d": 0.95,
            "slope": 0.025,
            "variance": 0.001,
            "summary": "Consistent improvement",
        }
        fig = lc.render_integrity_trajectory_flagship(trend_res)
        self.assertIsInstance(fig, go.Figure)
        # Verify historical trace, forecast trace, and uncertainty envelope
        trace_names = [t.name for t in fig.data if t.name]
        self.assertIn("Historical Integrity", trace_names)
        self.assertIn("7-Day Linear Forecast", trace_names)
        self.assertIn("Variance Band (+-1s)", trace_names)

    def test_render_memory_confidence_battery(self):
        bins = {"Fresh (>0.8)": 5, "Medium (0.5-0.8)": 3, "Marginal (0.3-0.5)": 1, "Decayed (<0.3)": 1}
        fig = lc.render_memory_confidence_battery(bins)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 4)
        self.assertEqual(fig.layout.barmode, "stack")

    def test_render_multi_session_integrity_bar(self):
        scores = {"session-1": 0.95, "session-2": 0.75}
        fig = lc.render_multi_session_integrity_bar(scores, aggregate_score=0.85)
        self.assertIsInstance(fig, go.Figure)
        # Check that shapes include 80% threshold and aggregate line
        self.assertGreaterEqual(len(fig.layout.shapes), 2)

    def test_render_anomaly_alerts_timeline(self):
        alerts = [
            {"id": "a1", "alert_type": "Schema Drift", "severity": "minor", "checkpoint": "c1"},
            {"id": "a2", "alert_type": "Critical Spike", "severity": "critical", "checkpoint": "c2"},
        ]
        fig = lc.render_anomaly_alerts_timeline(alerts)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data[0].x), 2)

    # Feature 3 Intent Conformance
    def test_render_domain_radial_gauges(self):
        domain_data = {"Security": 95.0, "UI/UX": 90.0, "Functional": 85.0, "Performance": 70.0, "Governance": 80.0}
        fig = lc.render_domain_radial_gauges(domain_data)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 5)

    def test_render_intent_conformance_trajectory_chart(self):
        trends = {
            "dates": ["D1", "D2", "D3"],
            "actual": [80.0, 82.0, 84.0],
            "forecast_dates": ["D3", "D4"],
            "forecast": [84.0, 86.0],
        }
        fig = lc.render_intent_conformance_trajectory_chart(trends)
        self.assertIsInstance(fig, go.Figure)
        trace_names = [t.name for t in fig.data if t.name]
        self.assertIn("Observed Conformance", trace_names)
        self.assertIn("Projected Trajectory", trace_names)

    def test_render_intent_conformance_gauge(self):
        fig = lc.render_intent_conformance_gauge(0.885, title="Conformance Index", prev_score=0.82)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].mode, "gauge+number+delta")

    # Feature 4 Resume Contract
    def test_render_contract_preset_radar(self):
        fig_radar = lc.render_contract_preset_radar(mode="radar")
        self.assertIsInstance(fig_radar, go.Figure)
        self.assertEqual(fig_radar.data[0].type, "scatterpolar")

        fig_bar = lc.render_contract_preset_radar(mode="grouped_bar")
        self.assertIsInstance(fig_bar, go.Figure)
        self.assertEqual(fig_bar.data[0].type, "bar")

    def test_render_contract_funnel_chart(self):
        fig = lc.render_contract_funnel_chart()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].type, "funnel")
        # Ensure drop-off annotations are present
        self.assertGreaterEqual(len(fig.layout.annotations), 3)

    def test_render_semantic_diff_bars(self):
        diff_data = {"Added Reqs": 2, "Resolved Dead-Ends": -1, "Integrity Delta": 5.0}
        fig = lc.render_semantic_diff_bars(diff_data)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data[0].y), 3)

    def test_render_contract_version_timeline(self):
        fig = lc.render_contract_version_timeline()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].mode, "lines+markers+text")

    # Feature 2 Requirement Ledger
    def test_render_sprint_burndown_variance_chart(self):
        fig = lc.render_sprint_burndown_variance_chart()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)
        self.assertEqual(fig.data[1].fill, "tozeroy")

    def test_render_priority_vs_effort_scatter(self):
        fig = lc.render_priority_vs_effort_scatter()
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.layout.annotations), 2)

    def test_render_requirement_lifecycle_stacked_bar(self):
        reqs = [{"status": "done"}, {"status": "in_progress"}, {"status": "blocked"}]
        fig = lc.render_requirement_lifecycle_stacked_bar(reqs)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.layout.barmode, "stack")

    def test_render_requirement_aging_heatmap(self):
        fig = lc.render_requirement_aging_heatmap()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].type, "bar")

    # Feature 1 Dead-End Registry
    def test_render_fix_success_gauge(self):
        fig = lc.render_fix_success_gauge(0.72)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].type, "indicator")

    def test_render_root_cause_ranked_bar(self):
        fig = lc.render_root_cause_ranked_bar()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].type, "bar")

    def test_render_dead_end_timeline_strip(self):
        fig = lc.render_dead_end_timeline_strip()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].type, "scatter")

    # Master UI/UX Components
    def test_range_bar_html(self):
        # Normal confidence interval
        html_normal = lc.render_range_bar_html(84.0, 78.0, 91.0, label="Accuracy")
        self.assertIn("Accuracy", html_normal)
        self.assertIn("84.0%", html_normal)
        self.assertIn("[78.0 - 91.0%]", html_normal)
        self.assertIn("style=\"position:absolute;left:78.0%", html_normal)

        # Degenerate interval (insufficient data fallback)
        html_degen = lc.render_range_bar_html(0.0, 0.0, 0.0, label="Degenerate")
        self.assertIn("Not enough data yet (insufficient confidence interval)", html_degen)

    def test_ranked_list_html(self):
        items = [
            {"label": "Logic Loop", "value": "12", "percentage": 54.5, "sublabel": "Active issue"},
            {"label": "Syntax Error", "value": "6", "percentage": 27.3, "sublabel": "Resolved"},
            {"label": "Timeout", "value": "4", "percentage": 18.2, "sublabel": "Resolved"},
        ]
        html = lc.render_ranked_list_html(items, title="Dead-End Types")
        self.assertIn("DEAD-END TYPES", html)
        self.assertIn("Logic Loop", html)
        self.assertIn("54.5%", html)

    def test_pipeline_health_connector_html(self):
        stages = [
            {"name": "Pre-Flight", "status": "pass", "score": 95.0},
            {"name": "Ledger", "status": "pass", "score": 90.0},
            {"name": "Conformance", "status": "warn", "score": 75.0},
            {"name": "Contract", "status": "pass", "score": 88.0},
            {"name": "Resume", "status": "fail", "score": 58.0},
        ]
        html = lc.render_pipeline_health_connector_html(stages)
        self.assertIn("PRE-FLIGHT", html)
        self.assertIn("#00A651", html)  # pass green
        self.assertIn("#F5A623", html)  # warn amber
        self.assertIn("#E3001E", html)  # fail red

    def test_ab_test_comparison_bars(self):
        tests = [
            {"name": "Template Alpha", "v1_val": 82.0, "v2_val": 94.0, "metric": "Conformance", "unit": "%"},
            {"name": "Template Beta", "v1_val": 70.0, "v2_val": 65.0, "metric": "Latency", "unit": "ms"},
        ]
        fig = lc.render_ab_test_comparison_bars(tests)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)  # Variant A and Variant B

    # ==========================================================================
    # MASTER RULES V2 TESTS (Checkpoint DX Visual Polish Pass)
    # ==========================================================================

    def test_anomaly_alerts_timeline_clustering(self):
        """Rule 1: Verify clustered alerts merge into count badges with zero label overlap."""
        clustered_alerts = [
            {"id": "a1", "alert_type": "Critical Spike", "severity": "critical", "detected_at": "2026-09-16T10:00:00Z"},
            {"id": "a2", "alert_type": "Schema Drift", "severity": "major", "detected_at": "2026-09-16T10:00:00Z"},
            {"id": "a3", "alert_type": "Memory Drift", "severity": "minor", "detected_at": "2026-09-16T10:00:00Z"},
            {"id": "a4", "alert_type": "Single Anomaly", "severity": "minor", "detected_at": "2026-09-16T14:00:00Z"},
        ]
        fig = lc.render_anomaly_alerts_timeline(clustered_alerts)
        self.assertIsInstance(fig, go.Figure)
        # Should have 2 nodes on timeline (1 clustered node of 3 + 1 single node)
        self.assertEqual(len(fig.data[0].x), 2)
        # First node should have count badge [3 ALERTS]
        self.assertEqual(fig.data[0].text[0], "[3 ALERTS]")
        # Second node should have single severity tag [MINOR]
        self.assertEqual(fig.data[0].text[1], "[MINOR]")
        # Clustered node marker size should be proportionally larger
        self.assertGreater(fig.data[0].marker.size[0], fig.data[0].marker.size[1])

    def test_axis_label_collision_guard_and_severity_bar(self):
        """Rule 1: Verify category collision guard and horizontal orientation for long strings."""
        long_categories = ["Resource Exhaustion", "Schema Mismatch", "Agent Logic Error", "Auth Timeout"]
        guard = lc.check_axis_label_collision(long_categories)
        self.assertTrue(guard["prefer_horizontal"])

        short_categories = ["A", "B", "C"]
        guard_short = lc.check_axis_label_collision(short_categories)
        self.assertFalse(guard_short["prefer_horizontal"])

        # Render severity bar with long categories -> horizontal stacked bar with zero collisions
        fig = lc.render_severity_distribution_bar()
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].orientation, "h")

    def test_continuous_arc_gauge_structure(self):
        """Rule 4: Verify single continuous arc gauge, embedded target marker, and center target sub-label."""
        fig = lc.render_fix_success_gauge(0.667, target_rate=75.0)
        self.assertIsInstance(fig, go.Figure)
        # Verify gauge has no outer disconnected ticks
        self.assertFalse(fig.data[0].gauge.axis.visible)
        # Verify threshold is embedded on arc
        self.assertEqual(fig.data[0].gauge.threshold.value, 75.0)
        # Verify center target sub-label annotation exists
        ann_texts = [a.text for a in fig.layout.annotations]
        self.assertTrue(any("Target: 75%" in t for t in ann_texts))

    def test_root_cause_labeled_deltas_and_dynamic_pluralization(self):
        """Rule 5 & 6: Verify explicit labeled deltas and dynamic grammar."""
        self.assertEqual(lc.format_delta_label(0), "[no change]")
        self.assertIn("↑2 vs last checkpoint", lc.format_delta_label(2))
        self.assertIn("↓1 vs last checkpoint", lc.format_delta_label(-1))

        fig = lc.render_root_cause_ranked_bar()
        self.assertIsInstance(fig, go.Figure)
        # Verify labeled deltas in y categories
        y_labels = list(fig.data[0].y)
        self.assertTrue(any("no change" in str(lbl) for lbl in y_labels))
        # Verify dynamic pluralization (1 event vs 2 events)
        bar_texts = list(fig.data[0].text)
        self.assertIn("1 event", bar_texts)
        self.assertTrue(any("events" in str(t) for t in bar_texts if "1 event" not in str(t)))

    def test_requirement_donut_and_stacked_bar_reconciliation(self):
        """Rule 3: Verify requirement donut and stacked bar reconcile 100% on total and 5 statuses."""
        sample_reqs = [
            {"id": f"r{i}", "status": "done"} for i in range(4)
        ] + [
            {"id": f"r{i+4}", "status": "in_progress"} for i in range(2)
        ] + [
            {"id": "r6", "status": "blocked"},
            {"id": "r7", "status": "ready"},
            {"id": "r8", "status": "superseded"},
        ]
        counts = lc.normalize_requirement_counts(sample_reqs)
        self.assertEqual(sum(counts.values()), 9)
        self.assertEqual(counts["Done"], 4)
        self.assertEqual(counts["In Progress"], 2)
        self.assertEqual(counts["Blocked"], 1)
        self.assertEqual(counts["Ready"], 1)
        self.assertEqual(counts["Superseded"], 1)

        donut_fig = lc.render_requirement_status_donut(sample_reqs)
        bar_fig = lc.render_requirement_lifecycle_stacked_bar(sample_reqs)

        # Donut center text must show 4 / 9
        center_ann = [a.text for a in donut_fig.layout.annotations if "4 / 9" in a.text]
        self.assertTrue(len(center_ann) > 0)
        # Stacked bar total in title must show 9 Total
        self.assertIn("9 TOTAL", bar_fig.layout.title.text.upper())

    def test_sparkline_insufficient_data_and_trend_coloring(self):
        """Rule 2: Verify < 5 points produces Insufficient-Data state; >= 5 points produces trend color."""
        # < 5 points -> Insufficient-Data dashed frame state
        svg_degen = lc.render_metric_sparkline_svg([10.0, 12.0, 14.0])
        self.assertIn("&lt;5 PTS", svg_degen)
        self.assertIn("stroke-dasharray", svg_degen)

        # >= 5 points improving -> Green
        svg_improving = lc.render_metric_sparkline_svg([10.0, 12.0, 14.0, 16.0, 20.0])
        self.assertIn("#00A651", svg_improving)

        # >= 5 points declining -> Red
        svg_declining = lc.render_metric_sparkline_svg([20.0, 18.0, 15.0, 12.0, 8.0])
        self.assertIn("#E3001E", svg_declining)


if __name__ == "__main__":
    unittest.main()

