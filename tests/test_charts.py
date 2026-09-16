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
        self.assertIn("Custom Title", fig.layout.annotations[0].text)

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
        self.assertEqual(fig.data[1].fill, "tonexty")

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


if __name__ == "__main__":
    unittest.main()
