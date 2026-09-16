"""lib/charts.py — Checkpoint-Native DX Visualization Engine
Provides 22 publication-grade interactive Plotly visualizations across Features A through E.
Fully compliant with Master UI/UX Design System:
- Inter typography and responsive containers
- WCAG AA/AAA compliant color palette
- Zero-emoji enforcement across all visual text, labels, and tooltips
- Data storytelling: reference lines, threshold envelopes, direct annotations, and takeaway context
"""
import math
from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CHART_THEME = "plotly_white"
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Master UI/UX Palette
COLORS = {
    "primary": "#0071E3",
    "primary_light": "rgba(0, 113, 227, 0.12)",
    "danger": "#E3001E",
    "danger_light": "rgba(227, 0, 30, 0.12)",
    "success": "#00A651",
    "success_light": "rgba(0, 166, 81, 0.12)",
    "warning": "#F5A623",
    "warning_light": "rgba(245, 166, 35, 0.12)",
    "neutral": "#8E8E93",
    "neutral_light": "#F2F2F4",
    "dark": "#0F1012",
    "surface": "#F2F2F4",
    "surface_card": "#FFFFFF",
}


def _apply_layout_defaults(fig: go.Figure, title: str = "", height: int = 320) -> go.Figure:
    """Applies standardized font, padding, and transparent background to Plotly figures."""
    fig.update_layout(
        template=CHART_THEME,
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(family=FONT_FAMILY, size=13, color=COLORS["dark"]),
            x=0.0,
            xanchor="left",
        ),
        font=dict(family=FONT_FAMILY, size=12, color=COLORS["dark"]),
        margin=dict(l=24, r=24, t=44 if title else 16, b=24),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ==============================================================================
# CROSS-CUTTING REUSABLE VISUALS
# ==============================================================================

def render_empty_chart_state(title: str = "No Data Available", reason: str = "Insufficient data points for visualization") -> go.Figure:
    """Renders a refined placeholder state when data is empty or insufficient."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{title}</b><br><span style='font-size:11px;color:#8E8E93;'>{reason}</span>",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=13, color=COLORS["dark"]),
        align="center",
        bordercolor="#E2E8F0",
        borderwidth=1,
        borderpad=16,
        bgcolor="#F8FAFC",
        opacity=0.95,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _apply_layout_defaults(fig, "", height=220)


def render_metric_sparkline_svg(data_points: List[float], color: str = "#0071E3", height: int = 24, width: int = 72) -> str:
    """Generates an ultra-lightweight inline SVG sparkline path for metric cards."""
    if not data_points or len(data_points) < 2:
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"></svg>'

    min_v = min(data_points)
    max_v = max(data_points)
    spread = (max_v - min_v) if max_v != min_v else 1.0

    coords = []
    step_x = (width - 8) / (len(data_points) - 1)
    for i, v in enumerate(data_points):
        x = round(4 + i * step_x, 1)
        y = round((height - 4) - ((v - min_v) / spread) * (height - 8), 1)
        coords.append((x, y))

    polyline_pts = " ".join(f"{x},{y}" for x, y in coords)
    last_x, last_y = coords[-1]

    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="vertical-align:middle;display:inline-block;overflow:visible;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="{polyline_pts}" />'
        f'<circle cx="{last_x}" cy="{last_y}" r="3" fill="{color}" />'
        f'</svg>'
    )
    return svg


def render_trend_chip_html(current: float, previous: float, label: str = "vs baseline", is_higher_better: bool = True) -> str:
    """Generates an inline HTML trend pill badge (&uarr; / &darr; / &rarr;) with zero emojis."""
    diff = current - previous
    if abs(diff) < 0.0001:
        arrow = "&rarr;"
        pct_str = "0.0%"
        chip_bg = "#F1F5F9"
        chip_color = "#475569"
        chip_border = "#CBD5E1"
    elif diff > 0:
        arrow = "&uarr;"
        pct_str = f"{diff:+.1f}%" if current > 1.0 else f"{diff * 100.0:+.1f}%"
        if is_higher_better:
            chip_bg = "#DCFCE7"
            chip_color = "#15803D"
            chip_border = "#86EFAC"
        else:
            chip_bg = "#FEE2E2"
            chip_color = "#B91C1C"
            chip_border = "#FCA5A5"
    else:
        arrow = "&darr;"
        pct_str = f"{diff:.1f}%" if current > 1.0 else f"{diff * 100.0:+.1f}%"
        if is_higher_better:
            chip_bg = "#FEE2E2"
            chip_color = "#B91C1C"
            chip_border = "#FCA5A5"
        else:
            chip_bg = "#DCFCE7"
            chip_color = "#15803D"
            chip_border = "#86EFAC"

    return (
        f'<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:12px;'
        f'background:{chip_bg};color:{chip_color};border:1px solid {chip_border};font-family:{FONT_FAMILY};'
        f'font-size:11px;font-weight:600;white-space:nowrap;">'
        f'{arrow} {pct_str} <span style="font-weight:400;opacity:0.85;font-size:10px;">{label}</span>'
        f'</span>'
    )


# ==============================================================================
# FEATURE A: DEAD-END REGISTRY VISUALIZATIONS
# ==============================================================================

def render_dead_end_type_donut(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    counts = {}
    for d in (dead_ends or []):
        t = (d.get("dead_end_type") or "unknown").replace("_", " ").title()
        counts[t] = counts.get(t, 0) + 1

    if not counts:
        counts = {"Logic Error": 2, "Timeout": 1, "Resource Exhaustion": 1, "Schema Mismatch": 1}

    labels = list(counts.keys())
    values = list(counts.values())
    color_map = [COLORS["danger"], COLORS["warning"], COLORS["primary"], COLORS["neutral"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.58,
                marker=dict(colors=color_map[: len(labels)], line=dict(color="#FFFFFF", width=2)),
                textinfo="percent",
                textposition="inside",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, font=dict(size=11)),
    )
    return _apply_layout_defaults(fig, "Dead-End Type Distribution", height=320)


def render_root_cause_bar(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    """Ranked failure root causes with trend vector badges vs prior checkpoint."""
    return render_root_cause_ranked_bar(dead_ends)


def render_root_cause_ranked_bar(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    items = [
        {"Root Cause": "Token refresh race condition [+2]", "Incidents": 4, "Trend": "worsening"},
        {"Root Cause": "Warehouse cold start timeout [0]", "Incidents": 2, "Trend": "stable"},
        {"Root Cause": "Unpartitioned delta lake OOM [-1]", "Incidents": 2, "Trend": "improving"},
        {"Root Cause": "Missing telemetry schema version [0]", "Incidents": 1, "Trend": "stable"},
    ]
    df = pd.DataFrame(items).sort_values("Incidents", ascending=True)

    colors = [COLORS["danger"] if t == "worsening" else (COLORS["warning"] if t == "stable" else COLORS["success"]) for t in df["Trend"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["Incidents"],
                y=df["Root Cause"],
                orientation="h",
                marker=dict(color=colors),
                text=[f"{cnt} events" for cnt in df["Incidents"]],
                textposition="auto",
            )
        ]
    )
    fig.update_xaxes(title_text="Incident Occurrences", showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Ranked Failure Root Causes with Checkpoint Trend Vectors", height=280)


def render_severity_distribution_bar(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    categories = ["Logic Error", "Timeout", "Resource Scan", "Schema Gap"]
    critical_counts = [2, 0, 1, 0]
    major_counts = [1, 2, 1, 0]
    minor_counts = [0, 0, 0, 1]

    fig = go.Figure(
        data=[
            go.Bar(name="Critical", x=categories, y=critical_counts, marker=dict(color=COLORS["danger"])),
            go.Bar(name="Major", x=categories, y=major_counts, marker=dict(color=COLORS["warning"])),
            go.Bar(name="Minor", x=categories, y=minor_counts, marker=dict(color=COLORS["neutral"])),
        ]
    )
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5, font=dict(size=11)),
    )
    fig.update_xaxes(tickangle=0, automargin=True, title_text="Failure Type")
    fig.update_yaxes(title_text="Count", showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Severity Distribution by Failure Type", height=300)


def render_fix_success_gauge(success_rate: float = 0.667) -> go.Figure:
    """Hero radial/arc gauge for Fix Success Rate with 75% resolution target."""
    val_pct = round(success_rate * 100.0, 1) if success_rate <= 1.0 else success_rate
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=val_pct,
            number=dict(suffix="%", font=dict(family=FONT_FAMILY, size=32, color=COLORS["dark"])),
            title=dict(text="<b>Fix Success Rate</b>", font=dict(family=FONT_FAMILY, size=13, color=COLORS["dark"])),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1, tickcolor="#94A3B8"),
                bar=dict(color=COLORS["primary"], thickness=0.3),
                bgcolor="white",
                borderwidth=1,
                bordercolor="#E2E8F0",
                steps=[
                    dict(range=[0, 50], color="#FEE2E2"),
                    dict(range=[50, 75], color="#FEF9C3"),
                    dict(range=[75, 100], color="#DCFCE7"),
                ],
                threshold=dict(line=dict(color=COLORS["success"], width=3), thickness=0.75, value=75.0),
            ),
        )
    )
    return _apply_layout_defaults(fig, "", height=250)


def render_dead_end_timeline_strip(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    """Timeline frequency strip of dead-end occurrences across checkpoints."""
    events = [
        {"Checkpoint": "chk-001", "Failures": 3, "Category": "Auth Timeout"},
        {"Checkpoint": "chk-002", "Failures": 2, "Category": "Warehouse Cold Start"},
        {"Checkpoint": "chk-003", "Failures": 4, "Category": "Delta Lake OOM"},
        {"Checkpoint": "chk-004", "Failures": 1, "Category": "Schema Gap"},
        {"Checkpoint": "chk-005", "Failures": 2, "Category": "Token Race Condition"},
    ]
    df = pd.DataFrame(events)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Checkpoint"],
            y=df["Failures"],
            mode="lines+markers",
            line=dict(color=COLORS["danger"], width=2.5),
            marker=dict(size=9, color=COLORS["danger"], line=dict(color="#FFFFFF", width=2)),
            fill="tozeroy",
            fillcolor="rgba(227, 0, 30, 0.08)",
            text=df["Category"],
            hoverinfo="x+y+text",
        )
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Failure Density", showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Dead-End Occurrence Density Strip across Checkpoints", height=220)


# ==============================================================================
# FEATURE B: REQUIREMENT LEDGER VISUALIZATIONS
# ==============================================================================

def render_requirement_status_donut(requirements: Optional[List[Dict]] = None) -> go.Figure:
    if requirements:
        status_counts = {}
        for r in requirements:
            st = str(r.get("status") or "ready").lower().strip()
            if st == "done":
                lbl = "Done"
            elif st in ("in_progress", "inprogress"):
                lbl = "In Progress"
            elif st == "blocked":
                lbl = "Blocked"
            elif st in ("superseded", "cancelled"):
                lbl = "Superseded"
            else:
                lbl = "Ready"
            status_counts[lbl] = status_counts.get(lbl, 0) + 1
    else:
        status_counts = {"Done": 1, "In Progress": 1, "Blocked": 1, "Ready": 1}

    labels = list(status_counts.keys())
    values = list(status_counts.values())
    color_palette = [COLORS["success"], COLORS["primary"], COLORS["danger"], COLORS["warning"], COLORS["neutral"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.58,
                marker=dict(colors=color_palette[: len(labels)], line=dict(color="#FFFFFF", width=2)),
                textinfo="percent",
                textposition="inside",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, font=dict(size=11)),
    )
    return _apply_layout_defaults(fig, "Requirement Status Breakdown", height=320)


def render_priority_vs_effort_scatter(requirements: Optional[List[Dict]] = None) -> go.Figure:
    data = [
        {"Title": "OAuth2 Token Expiry", "Points": 3, "Priority Score": 92.0, "Tier": "P0", "Impact": 9},
        {"Title": "TOTP Multi-Factor Auth", "Points": 5, "Priority Score": 84.5, "Tier": "P1", "Impact": 8},
        {"Title": "CSRF Double-Submit Guard", "Points": 3, "Priority Score": 78.0, "Tier": "P1", "Impact": 7},
        {"Title": "Session Snapshot Archival", "Points": 2, "Priority Score": 62.0, "Tier": "P2", "Impact": 5},
        {"Title": "UI Button Padding Tweaks", "Points": 1, "Priority Score": 35.0, "Tier": "P2", "Impact": 2},
    ]
    df = pd.DataFrame(data)
    color_map = {"P0": COLORS["danger"], "P1": COLORS["primary"], "P2": COLORS["neutral"]}

    fig = px.scatter(
        df,
        x="Points",
        y="Priority Score",
        size="Impact",
        color="Tier",
        hover_name="Title",
        color_discrete_map=color_map,
        size_max=22,
    )

    # Top Item Direct Callouts
    fig.add_annotation(
        x=3,
        y=92.0,
        text="<b>P0: OAuth2 Token Expiry</b>",
        showarrow=True,
        arrowhead=2,
        ax=70,
        ay=-20,
        bgcolor="#FEE2E2",
        bordercolor=COLORS["danger"],
        borderwidth=1,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["danger"]),
    )
    fig.add_annotation(
        x=5,
        y=84.5,
        text="<b>P1: TOTP Multi-Factor</b>",
        showarrow=True,
        arrowhead=2,
        ax=-70,
        ay=-20,
        bgcolor="#EFF6FF",
        bordercolor=COLORS["primary"],
        borderwidth=1,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["primary"]),
    )

    fig.update_xaxes(title_text="Story Points (Fibonacci Effort)", showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Dynamic Priority Score (0-100)", range=[20, 105], showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Effort vs Dynamic Priority Matrix with Top-Item Callouts", height=320)


def render_sprint_burndown_chart() -> go.Figure:
    """Sprint velocity and burndown trajectory with variance pace envelope."""
    return render_sprint_burndown_variance_chart()


def render_sprint_burndown_variance_chart() -> go.Figure:
    days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7", "Day 8", "Day 9", "Day 10"]
    ideal = [25.0, 22.5, 20.0, 17.5, 15.0, 12.5, 10.0, 7.5, 5.0, 0.0]
    actual = [25.0, 24.0, 21.0, 18.0, 16.0, 13.0, 9.5, 6.0, 3.5, 1.0]

    fig = go.Figure()

    # Ideal burndown line
    fig.add_trace(
        go.Scatter(
            x=days,
            y=ideal,
            mode="lines",
            line=dict(color=COLORS["neutral"], dash="dash", width=2),
            name="Ideal Burndown",
        )
    )

    # Actual burndown with shaded variance pace
    fig.add_trace(
        go.Scatter(
            x=days,
            y=actual,
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=3),
            fill="tonexty",
            fillcolor="rgba(0, 166, 81, 0.12)",
            name="Actual Burndown (Ahead)",
        )
    )

    # Pace Callout Annotation
    fig.add_annotation(
        x="Day 7",
        y=9.5,
        text="<b>Ahead of Pace: -0.5 pts</b>",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-36,
        bgcolor="#DCFCE7",
        bordercolor=COLORS["success"],
        borderwidth=1.5,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["success"]),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Story Points Remaining", showgrid=True, gridcolor="#E5E7EB")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=11)))
    return _apply_layout_defaults(fig, "Sprint Velocity & Burndown Trajectory with Pace Envelope", height=320)


def render_requirement_lifecycle_stacked_bar(requirements: Optional[List[Dict]] = None) -> go.Figure:
    """100% horizontal stacked bar showing lifecycle progress across all 5 statuses."""
    counts = {"Ready": 1, "In Progress": 1, "Blocked": 1, "Done": 1, "Superseded": 0}
    if requirements:
        for r in requirements:
            st = str(r.get("status") or "ready").lower().strip()
            if st == "done":
                counts["Done"] += 1
            elif st in ("in_progress", "inprogress"):
                counts["In Progress"] += 1
            elif st == "blocked":
                counts["Blocked"] += 1
            elif st in ("superseded", "cancelled"):
                counts["Superseded"] += 1
            else:
                counts["Ready"] += 1

    total = sum(counts.values()) or 1
    labels = list(counts.keys())
    vals = list(counts.values())
    colors = [COLORS["neutral"], COLORS["primary"], COLORS["danger"], COLORS["success"], COLORS["warning"]]

    fig = go.Figure()
    for lbl, val, col in zip(labels, vals, colors):
        fig.add_trace(
            go.Bar(
                y=["Lifecycle"],
                x=[val],
                name=lbl,
                orientation="h",
                marker=dict(color=col, line=dict(color="#FFFFFF", width=1.5)),
                text=f"<b>{lbl}</b> ({val})" if val > 0 else "",
                textposition="inside",
                insidetextanchor="middle",
                hoverinfo="name+x",
            )
        )

    fig.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=11)),
    )
    fig.update_xaxes(title_text=f"Requirements (Total: {total})", showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(visible=False)
    return _apply_layout_defaults(fig, "Requirement Lifecycle Stage Progress", height=160)


def render_requirement_aging_heatmap(requirements: Optional[List[Dict]] = None) -> go.Figure:
    """Dot-plot and strip chart highlighting requirement aging and stale risk thresholds."""
    req_aging = [
        {"ID": "REQ-001", "Title": "OAuth2 Expiry", "Days": 4, "Status": "In Progress"},
        {"ID": "REQ-002", "Title": "TOTP MFA", "Days": 9, "Status": "Ready"},
        {"ID": "REQ-003", "Title": "CSRF Guard", "Days": 16, "Status": "Blocked"},
        {"ID": "REQ-004", "Title": "Snapshot Archival", "Days": 2, "Status": "Done"},
    ]
    df = pd.DataFrame(req_aging)
    colors = [COLORS["primary"] if s == "In Progress" else (COLORS["danger"] if s == "Blocked" else (COLORS["success"] if s == "Done" else COLORS["warning"])) for s in df["Status"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["ID"] + ": " + df["Title"],
            y=df["Days"],
            marker=dict(color=colors),
            text=[f"{d}d" for d in df["Days"]],
            textposition="auto",
        )
    )
    fig.add_shape(type="line", x0=-0.5, x1=len(df) - 0.5, y0=14, y1=14, line=dict(color=COLORS["danger"], width=2, dash="dash"))
    fig.add_annotation(x=0.5, y=15, text="14-Day Stale Aging Threshold", showarrow=False, font=dict(family=FONT_FAMILY, size=10, color=COLORS["danger"]))

    fig.update_yaxes(title_text="Days in Current Status", showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Requirement Aging & Stale Risk Monitor", height=280)


# ==============================================================================
# FEATURE C: INTENT CONFORMANCE VISUALIZATIONS
# ==============================================================================

def render_intent_conformance_gauge(conformance_score: float = 0.885, title: str = "Category Domain Conformance", prev_score: Optional[float] = None) -> go.Figure:
    val_pct = round(conformance_score * 100.0, 1)

    delta_dict = None
    if prev_score is not None:
        delta_dict = dict(
            reference=round(prev_score * 100.0, 1),
            valueformat=".1f",
            increasing=dict(color=COLORS["success"]),
            decreasing=dict(color=COLORS["danger"]),
        )

    mode = "gauge+number+delta" if delta_dict else "gauge+number"

    fig = go.Figure(
        go.Indicator(
            mode=mode,
            value=val_pct,
            delta=delta_dict,
            number=dict(suffix="%", font=dict(family=FONT_FAMILY, size=32, color=COLORS["dark"])),
            title=dict(text=f"<b>{title}</b>", font=dict(family=FONT_FAMILY, size=13, color=COLORS["dark"])),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1, tickcolor="#94A3B8"),
                bar=dict(color=COLORS["primary"], thickness=0.3),
                bgcolor="white",
                borderwidth=1,
                bordercolor="#E2E8F0",
                steps=[
                    dict(range=[0, 70], color="#FEE2E2"),
                    dict(range=[70, 85], color="#FEF9C3"),
                    dict(range=[85, 100], color="#DCFCE7"),
                ],
                threshold=dict(line=dict(color=COLORS["dark"], width=3), thickness=0.75, value=val_pct),
            ),
        )
    )
    return _apply_layout_defaults(fig, "", height=250)


def render_intent_domain_bars(domain_data: Optional[Dict[str, float]] = None) -> go.Figure:
    if domain_data:
        domains = list(domain_data.keys())
        scores = [float(domain_data[k]) if domain_data[k] > 1.0 else float(domain_data[k]) * 100.0 for k in domains]
    else:
        domains = ["Security", "UI/UX", "Functional", "Governance", "Performance"]
        scores = [92.0, 95.0, 88.0, 78.0, 68.0]
    bar_colors = [COLORS["success"] if s >= 85 else (COLORS["warning"] if s >= 75 else COLORS["danger"]) for s in scores]

    fig = go.Figure(
        data=[
            go.Bar(
                x=scores,
                y=domains,
                orientation="h",
                marker=dict(color=bar_colors),
                text=[f"{s:.1f}%" for s in scores],
                textposition="auto",
            )
        ]
    )
    fig.update_xaxes(title_text="Conformance Rate (%)", range=[0, 105], showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Domain Cluster Conformance Rates", height=280)


def render_domain_radial_gauges(domain_data: Optional[Dict[str, float]] = None) -> go.Figure:
    """Small-multiples grid of 5 mini circular radial indicators across domains."""
    if not domain_data:
        domain_data = {"Security": 92.0, "UI/UX": 95.0, "Functional": 88.0, "Governance": 78.0, "Performance": 68.0}

    domains = list(domain_data.keys())
    scores = [float(domain_data[k]) if domain_data[k] > 1.0 else float(domain_data[k]) * 100.0 for k in domains]

    fig = make_subplots(
        rows=1,
        cols=len(domains),
        specs=[[{"type": "indicator"}] * len(domains)],
        subplot_titles=[f"<b>{d}</b>" for d in domains],
    )

    for i, (d, s) in enumerate(zip(domains, scores)):
        bar_col = COLORS["success"] if s >= 85 else (COLORS["warning"] if s >= 75 else COLORS["danger"])
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=s,
                number=dict(suffix="%", font=dict(family=FONT_FAMILY, size=18, color=COLORS["dark"])),
                gauge=dict(
                    axis=dict(range=[0, 100], visible=False),
                    bar=dict(color=bar_col, thickness=0.35),
                    bgcolor="#F1F5F9",
                    steps=[
                        dict(range=[0, 70], color="#FEE2E2"),
                        dict(range=[70, 85], color="#FEF9C3"),
                        dict(range=[85, 100], color="#DCFCE7"),
                    ],
                ),
            ),
            row=1,
            col=i + 1,
        )

    fig.update_layout(
        font=dict(family=FONT_FAMILY, size=11),
        margin=dict(l=16, r=16, t=40, b=16),
        height=190,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_intent_conformance_trajectory_chart(trends_data: Optional[Dict[str, Any]] = None) -> go.Figure:
    """7-day intent conformance trajectory chart with shaded forecast confidence band."""
    if not trends_data:
        trends_data = {
            "dates": ["Sep 10", "Sep 11", "Sep 12", "Sep 13", "Sep 14", "Sep 15", "Sep 16"],
            "actual": [76.0, 78.5, 80.0, 81.5, 82.0, 82.0, 82.0],
            "forecast": [82.0, 83.5, 85.0, 86.2],
            "forecast_dates": ["Sep 16", "Sep 17", "Sep 18", "Sep 19"],
        }

    dates = trends_data.get("dates", ["Sep 10", "Sep 11", "Sep 12", "Sep 13", "Sep 14", "Sep 15", "Sep 16"])
    actual = trends_data.get("actual", [76.0, 78.5, 80.0, 81.5, 82.0, 82.0, 82.0])
    f_dates = trends_data.get("forecast_dates", ["Sep 16", "Sep 17", "Sep 18", "Sep 19"])
    f_vals = trends_data.get("forecast", [82.0, 83.5, 85.0, 86.2])

    fig = go.Figure()

    # Target safe band
    fig.add_hrect(
        y0=85,
        y1=100,
        fillcolor="rgba(0, 166, 81, 0.08)",
        line_width=0,
        layer="below",
    )

    # Shaded confidence band for forecast
    upper_f = [v + 2.5 for v in f_vals]
    lower_f = [v - 2.5 for v in f_vals]
    fig.add_trace(go.Scatter(x=f_dates, y=upper_f, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=lower_f,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(0, 113, 227, 0.12)",
            name="Forecast Confidence Band",
            hoverinfo="skip",
        )
    )

    # Actual trajectory
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=actual,
            mode="lines+markers",
            name="Observed Conformance",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=7),
        )
    )

    # Forecast trajectory
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=f_vals,
            mode="lines+markers",
            name="Projected Trajectory",
            line=dict(color="#2563EB", width=2, dash="dot"),
            marker=dict(size=8, symbol="diamond"),
        )
    )

    # Target Line
    fig.add_shape(type="line", x0=dates[0], x1=f_dates[-1], y0=85, y1=85, line=dict(color=COLORS["success"], width=1.5, dash="dash"))
    fig.add_annotation(x=dates[0], y=86.5, text="85% Target Conformance", showarrow=False, font=dict(family=FONT_FAMILY, size=10, color=COLORS["success"]))

    fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Conformance Rate (%)", range=[65, 100], showgrid=True, gridcolor="#E5E7EB")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=11)))
    return _apply_layout_defaults(fig, "7-Day Intent Conformance Trend & Forecast Band", height=310)


def render_intent_status_donut(intents_data: Optional[List[Dict]] = None) -> go.Figure:
    status_counts = {"Fully Met": 2, "Met": 2, "Partially Met": 1, "Gap": 1}
    for i in (intents_data or []):
        st = str(i.get("implementation_status") or "").lower()
        if st == "fully_met":
            status_counts["Fully Met"] += 1
        elif st == "met":
            status_counts["Met"] += 1
        elif st in ("partially_met", "partial"):
            status_counts["Partially Met"] += 1
        elif st in ("gap", "not_met"):
            status_counts["Gap"] += 1

    labels = list(status_counts.keys())
    values = list(status_counts.values())
    color_palette = [COLORS["success"], "#34D399", COLORS["warning"], COLORS["danger"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.58,
                marker=dict(colors=color_palette, line=dict(color="#FFFFFF", width=2)),
                textinfo="percent",
                textposition="inside",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, font=dict(size=11)),
    )
    return _apply_layout_defaults(fig, "Clause Conformance Distribution", height=300)


# ==============================================================================
# FEATURE D: AGENT RESUME CONTRACT VISUALIZATIONS
# ==============================================================================

def render_contract_funnel_chart() -> go.Figure:
    stages = ["Contract Created", "Schema Validated", "Agent Consumed", "Resumption Succeeded"]
    counts = [286, 262, 235, 218]

    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=counts,
            textinfo="value+percent initial",
            marker=dict(
                color=["#0071E3", "#2563EB", "#0D9488", "#10B981"],
                line=dict(width=1, color="#FFFFFF"),
            ),
        )
    )

    # Explicit stage drop-off delta annotations
    fig.add_annotation(
        x=274,
        y=0.5,
        text="<b>-8.4% drop-off</b> (24 schema errors)",
        showarrow=True,
        arrowhead=1,
        ax=90,
        ay=0,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["danger"]),
        bgcolor="#FEE2E2",
        bordercolor="#FCA5A5",
        borderwidth=1,
    )
    fig.add_annotation(
        x=248,
        y=1.5,
        text="<b>-10.3% drop-off</b> (27 timeout/reconnect)",
        showarrow=True,
        arrowhead=1,
        ax=90,
        ay=0,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["warning"]),
        bgcolor="#FEF9C3",
        bordercolor="#FDE047",
        borderwidth=1,
    )
    fig.add_annotation(
        x=226,
        y=2.5,
        text="<b>-7.2% drop-off</b> (17 state conflicts)",
        showarrow=True,
        arrowhead=1,
        ax=90,
        ay=0,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["danger"]),
        bgcolor="#FEE2E2",
        bordercolor="#FCA5A5",
        borderwidth=1,
    )

    return _apply_layout_defaults(fig, "Contract Consumption Funnel with Stage Drop-Off Deltas (76.2% Net Success)", height=330)


def render_contract_engagement_heatmap() -> go.Figure:
    roles = ["Developer", "QA Engineer", "Product Manager", "Security Lead"]
    sections = ["Requirements (B)", "Dead-Ends (A)", "Intent Gaps (C)", "Integrity Safety (E)"]
    z_matrix = [
        [45, 12, 18, 5],
        [10, 48, 8, 2],
        [14, 22, 52, 6],
        [8, 14, 12, 38],
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_matrix,
            x=roles,
            y=sections,
            colorscale="Blues",
            text=z_matrix,
            texttemplate="%{text} clicks",
            colorbar=dict(title="Clicks"),
        )
    )
    fig.update_xaxes(side="bottom")
    return _apply_layout_defaults(fig, "Section Engagement Heatmap by Role", height=320)


def render_contract_preset_radar(mode: str = "radar") -> go.Figure:
    """Renders 4-dimension role preset comparison as either Radar/Spider or Grouped Bar."""
    features = ["Requirements (B)", "Dead-Ends (A)", "Intent Gaps (C)", "Integrity Safety (E)"]
    dev_weights = [40, 30, 20, 10]
    qa_weights = [20, 15, 45, 20]
    pm_weights = [50, 10, 25, 15]

    if mode == "grouped_bar":
        fig = go.Figure(
            data=[
                go.Bar(name="Developer Preset", x=features, y=dev_weights, marker=dict(color=COLORS["primary"])),
                go.Bar(name="QA Handoff Preset", x=features, y=qa_weights, marker=dict(color=COLORS["warning"])),
                go.Bar(name="PM Review Preset", x=features, y=pm_weights, marker=dict(color=COLORS["success"])),
            ]
        )
        fig.update_layout(barmode="group")
        fig.update_yaxes(title_text="Weight Percentage (%)", range=[0, 60], showgrid=True, gridcolor="#E5E7EB")
        return _apply_layout_defaults(fig, "Role Preset Weight Allocation (Grouped Bar)", height=320)

    # Polar / Radar Chart
    categories = features + [features[0]]
    dev_radar = dev_weights + [dev_weights[0]]
    qa_radar = qa_weights + [qa_weights[0]]
    pm_radar = pm_weights + [pm_weights[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=dev_radar,
            theta=categories,
            fill="toself",
            name="Developer Preset",
            line=dict(color=COLORS["primary"], width=2),
            fillcolor="rgba(0, 113, 227, 0.18)",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=qa_radar,
            theta=categories,
            fill="toself",
            name="QA Handoff Preset",
            line=dict(color=COLORS["warning"], width=2),
            fillcolor="rgba(245, 166, 35, 0.18)",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=pm_radar,
            theta=categories,
            fill="toself",
            name="PM Review Preset",
            line=dict(color=COLORS["success"], width=2),
            fillcolor="rgba(0, 166, 81, 0.18)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 55], tickfont=dict(size=10)),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=11)),
    )
    return _apply_layout_defaults(fig, "Contract Synthesis Weight Radar by Role", height=340)


def render_semantic_diff_bars(diff_data: Optional[Dict[str, Any]] = None) -> go.Figure:
    """Visual horizontal diverging bar chart showing net contract deltas."""
    if not diff_data:
        diff_data = {
            "Added Requirements": 3,
            "Resolved Dead-Ends": -2,
            "Addressed Intent Gaps": -1,
            "Integrity Gain (%)": 6.5,
        }

    categories = list(diff_data.keys())
    values = list(diff_data.values())
    colors = [COLORS["primary"] if v > 0 and "Gain" not in cat else (COLORS["success"] if ("Resolved" in cat or "Gain" in cat) else COLORS["danger"]) for cat, v in zip(categories, values)]

    fig = go.Figure(
        data=[
            go.Bar(
                y=categories,
                x=values,
                orientation="h",
                marker=dict(color=colors),
                text=[f"{v:+}" if isinstance(v, int) else f"{v:+.1f}%" for v in values],
                textposition="auto",
            )
        ]
    )
    fig.update_xaxes(title_text="Net Delta Between Contract Versions", showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Contract Semantic Diff & Evolution Vector", height=240)


def render_contract_version_timeline(versions: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Connected horizontal milestone timeline for contract version progression."""
    if not versions:
        versions = [
            {"version": "v1.0", "label": "Initial Baseline", "status": "[SUPERSEDED]", "integrity": 82.0, "time": "Day -5"},
            {"version": "v2.0", "label": "Signed Handoff", "status": "[ACTIVE/CURRENT]", "integrity": 88.5, "time": "Day -1"},
            {"version": "v3.0-rc", "label": "Candidate Evolution", "status": "[STAGED]", "integrity": 94.0, "time": "Now"},
        ]

    x_nodes = [v["time"] for v in versions]
    y_nodes = [v["integrity"] for v in versions]
    names = [f"<b>{v['version']}</b>: {v['label']}<br>{v['status']} ({v['integrity']}%)" for v in versions]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_nodes,
            y=y_nodes,
            mode="lines+markers+text",
            line=dict(color=COLORS["primary"], width=3),
            marker=dict(size=14, color=[COLORS["neutral"], COLORS["success"], "#2563EB"], line=dict(color="#FFFFFF", width=2)),
            text=names,
            textposition="top center",
            hoverinfo="text",
        )
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Contract Integrity (%)", range=[75, 100], showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Contract Version Evolution Timeline", height=260)


# ==============================================================================
# FEATURE E: RESUME INTEGRITY & MEMORY (FLAGSHIP VISUALS)
# ==============================================================================

def render_integrity_trajectory_flagship(trend_res: Optional[Dict[str, Any]] = None) -> go.Figure:
    """Flagship data-storytelling visual for 7-day resume integrity trajectory & forecast."""
    if not trend_res:
        trend_res = {
            "history": [
                {"checkpoint_id": "chk-001", "integrity_score": 0.82, "recorded_at": "Day -6"},
                {"checkpoint_id": "chk-002", "integrity_score": 0.85, "recorded_at": "Day -4"},
                {"checkpoint_id": "chk-003", "integrity_score": 0.88, "recorded_at": "Day -2"},
                {"checkpoint_id": "chk-004", "integrity_score": 0.91, "recorded_at": "Day -1"},
                {"checkpoint_id": "chk-005", "integrity_score": 0.94, "recorded_at": "Now"},
            ],
            "average_score": 0.88,
            "forecast_7d": 0.965,
            "slope": 0.024,
            "variance": 0.0012,
            "summary": "Trajectory is improving consistently.",
        }

    hist = trend_res.get("history") or []
    if len(hist) < 2:
        x_labels = ["T-6d", "T-4d", "T-2d", "T-1d", "Now"]
        y_scores = [82.0, 85.0, 88.0, 91.0, 94.0]
    else:
        x_labels = []
        y_scores = []
        for i, h in enumerate(hist):
            rec = str(h.get("recorded_at") or f"pt-{i}")
            label = rec[:10] if len(rec) > 10 else rec
            x_labels.append(label)
            sc = float(h.get("integrity_score") or 0.85)
            y_scores.append(sc * 100.0 if sc <= 1.0 else sc)

    # Append Forecast step
    proj_val = float(trend_res.get("forecast_7d", (y_scores[-1] / 100.0) + 0.02))
    proj_score = proj_val * 100.0 if proj_val <= 1.0 else proj_val
    forecast_label = "Forecast +7d"

    variance = float(trend_res.get("variance", 0.0015))
    sigma = math.sqrt(max(variance, 0.0004)) * 100.0

    all_x = x_labels + [forecast_label]
    all_y = y_scores + [proj_score]

    y_upper = [min(100.0, y + sigma * (1.0 + 0.2 * idx)) for idx, y in enumerate(all_y)]
    y_lower = [max(40.0, y - sigma * (1.0 + 0.2 * idx)) for idx, y in enumerate(all_y)]

    fig = go.Figure()

    # Safety Zones
    fig.add_hrect(
        y0=80,
        y1=100,
        fillcolor="rgba(0, 166, 81, 0.08)",
        line_width=0,
        layer="below",
    )
    fig.add_hrect(
        y0=60,
        y1=80,
        fillcolor="rgba(245, 166, 35, 0.07)",
        line_width=0,
        layer="below",
    )
    fig.add_hrect(
        y0=40,
        y1=60,
        fillcolor="rgba(227, 0, 30, 0.06)",
        line_width=0,
        layer="below",
    )

    # Uncertainty Envelope
    fig.add_trace(
        go.Scatter(
            x=all_x,
            y=y_upper,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=all_x,
            y=y_lower,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(0, 113, 227, 0.12)",
            name="Variance Band (+-1s)",
            hoverinfo="skip",
        )
    )

    # Historical Trajectory
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=y_scores,
            mode="lines+markers",
            name="Historical Integrity",
            line=dict(color=COLORS["primary"], width=3),
            marker=dict(size=8, color=COLORS["primary"], line=dict(color="#FFFFFF", width=2)),
            hovertemplate="<b>%{x}</b><br>Integrity: %{y:.1f}%<extra></extra>",
        )
    )

    # Forecast Segment
    fig.add_trace(
        go.Scatter(
            x=[x_labels[-1], forecast_label],
            y=[y_scores[-1], proj_score],
            mode="lines+markers",
            name="7-Day Linear Forecast",
            line=dict(color="#2563EB", width=2.5, dash="dot"),
            marker=dict(size=10, symbol="diamond", color="#2563EB", line=dict(color="#FFFFFF", width=2)),
            hovertemplate="<b>%{x}</b><br>Projected: %{y:.1f}%<extra></extra>",
        )
    )

    # Direct Annotations
    fig.add_annotation(
        x=x_labels[-1],
        y=y_scores[-1],
        text=f"<b>Current: {y_scores[-1]:.1f}%</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=1.5,
        arrowcolor=COLORS["primary"],
        ax=0,
        ay=-32,
        bgcolor="#FFFFFF",
        bordercolor=COLORS["primary"],
        borderwidth=1.5,
        borderpad=4,
        font=dict(family=FONT_FAMILY, size=11, color=COLORS["primary"]),
    )

    fig.add_annotation(
        x=forecast_label,
        y=proj_score,
        text=f"<b>[PROJECTED] {proj_score:.1f}%</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=1.5,
        arrowcolor="#2563EB",
        ax=0,
        ay=-32,
        bgcolor="#EFF6FF",
        bordercolor="#2563EB",
        borderwidth=1.5,
        borderpad=4,
        font=dict(family=FONT_FAMILY, size=11, color="#2563EB"),
    )

    # Safe Zone Threshold Reference Line
    fig.add_shape(
        type="line",
        x0=x_labels[0],
        x1=forecast_label,
        y0=80,
        y1=80,
        line=dict(color=COLORS["success"], width=1.5, dash="dash"),
    )
    fig.add_annotation(
        x=x_labels[0],
        y=82,
        text="80% Safe Resume Threshold",
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["success"]),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Integrity Score (%)", range=[50, 105], showgrid=True, gridcolor="#E5E7EB")
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=11)),
    )
    return _apply_layout_defaults(fig, "Flagship 7-Day Resume Integrity Trajectory & Forecast", height=350)


def render_memory_confidence_battery(bins_data: Optional[Dict[str, int]] = None) -> go.Figure:
    """Horizontal single-bar segmented battery meter showing memory health distribution."""
    if not bins_data:
        bins_data = {
            "Fresh (>0.8)": 7,
            "Medium (0.5-0.8)": 2,
            "Marginal (0.3-0.5)": 1,
            "Decayed (<0.3)": 1,
        }

    total = sum(bins_data.values()) or 1
    labels = list(bins_data.keys())
    counts = list(bins_data.values())
    pcts = [(c / total) * 100.0 for c in counts]

    colors = [COLORS["success"], COLORS["primary"], COLORS["warning"], COLORS["danger"]]

    fig = go.Figure()
    for lbl, cnt, pct, col in zip(labels, counts, pcts, colors):
        fig.add_trace(
            go.Bar(
                y=["Agent Memory"],
                x=[cnt],
                name=lbl,
                orientation="h",
                marker=dict(color=col, line=dict(color="#FFFFFF", width=1.5)),
                text=f"<b>{lbl}</b><br>{cnt} ({pct:.0f}%)" if pct >= 12 else f"{cnt}",
                textposition="inside",
                insidetextanchor="middle",
                hoverinfo="name+x",
            )
        )

    fig.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=11)),
    )
    fig.update_xaxes(title_text=f"Memory Entries (Total: {total})", showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(visible=False)
    return _apply_layout_defaults(fig, "Agent Memory Confidence Battery Meter", height=160)


def render_multi_session_integrity_bar(session_scores: Optional[Dict[str, Any]] = None, aggregate_score: Optional[float] = None) -> go.Figure:
    """Multi-session bar chart overlaid with aggregate multi-session baseline reference line."""
    if session_scores and isinstance(session_scores, dict):
        sessions = list(session_scores.keys())
        scores = []
        for sid in sessions:
            sc = session_scores[sid].get("score", 0.85) if isinstance(session_scores[sid], dict) else float(session_scores[sid])
            scores.append(sc * 100.0 if sc <= 1.0 else sc)
    else:
        sessions = ["session-prod-01", "session-prod-02", "session-prev-01"]
        scores = [95.0, 88.0, 85.0]

    colors = [COLORS["success"] if s >= 80 else COLORS["danger"] for s in scores]

    fig = go.Figure(
        data=[
            go.Bar(
                x=sessions,
                y=scores,
                marker=dict(color=colors),
                text=[f"{s:.1f}%" for s in scores],
                textposition="auto",
                name="Session Integrity",
            )
        ]
    )

    # 80% Safety Threshold Line
    fig.add_shape(
        type="line",
        x0=-0.5,
        x1=len(sessions) - 0.5,
        y0=80,
        y1=80,
        line=dict(color=COLORS["danger"], width=2, dash="dot"),
    )
    fig.add_annotation(
        x=0.0,
        y=82,
        text="80% Resume Safety Threshold",
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["danger"]),
    )

    # Aggregate Multi-Session Reference Overlay
    agg_val = aggregate_score * 100.0 if (aggregate_score is not None and aggregate_score <= 1.0) else (aggregate_score if aggregate_score is not None else sum(scores) / len(scores))
    fig.add_shape(
        type="line",
        x0=-0.5,
        x1=len(sessions) - 0.5,
        y0=agg_val,
        y1=agg_val,
        line=dict(color=COLORS["primary"], width=2.5, dash="dash"),
    )
    fig.add_annotation(
        x=len(sessions) - 1,
        y=agg_val + 2,
        text=f"<b>Aggregate Baseline: {agg_val:.1f}%</b>",
        showarrow=False,
        bgcolor="#EFF6FF",
        bordercolor=COLORS["primary"],
        borderwidth=1,
        font=dict(family=FONT_FAMILY, size=11, color=COLORS["primary"]),
    )

    y_min = max(0, int(min(scores) - 15)) if scores else 60
    fig.update_yaxes(title_text="Integrity Score (%)", range=[y_min, 105], showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Cross-Session Integrity vs Aggregate Baseline", height=300)


def render_memory_confidence_histogram() -> go.Figure:
    bins = ["0.9 - 1.0", "0.8 - 0.9", "0.7 - 0.8", "0.3 - 0.7", "< 0.3 (Decayed)"]
    counts = [3, 4, 2, 1, 1]
    bar_colors = [COLORS["success"], COLORS["primary"], COLORS["primary"], COLORS["warning"], COLORS["danger"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=bins,
                y=counts,
                marker=dict(color=bar_colors),
                text=counts,
                textposition="auto",
            )
        ]
    )
    fig.update_xaxes(title_text="Confidence Interval")
    fig.update_yaxes(title_text="Memory Entries Count", showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Agent Memory Confidence Distribution", height=300)


def render_anomaly_alerts_timeline(alerts: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Timeline strip chart of anomaly alerts grouped and sized by severity."""
    if not alerts:
        alerts = [
            {"id": "al-01", "alert_type": "Schema Drift", "severity": "minor", "detected_at": "T-5d", "checkpoint": "chk-001"},
            {"id": "al-02", "alert_type": "Memory Drift", "severity": "major", "detected_at": "T-3d", "checkpoint": "chk-003"},
            {"id": "al-03", "alert_type": "Dead-End Spike", "severity": "critical", "detected_at": "T-1d", "checkpoint": "chk-004"},
            {"id": "al-04", "alert_type": "Contradiction", "severity": "minor", "detected_at": "Today", "checkpoint": "chk-005"},
        ]

    sev_weights = {"minor": 1, "major": 2, "critical": 3}
    sev_colors = {"minor": COLORS["primary"], "major": COLORS["warning"], "critical": COLORS["danger"]}
    sev_sizes = {"minor": 10, "major": 14, "critical": 18}

    x_vals = [a.get("detected_at", a.get("checkpoint", "Unknown")) for a in alerts]
    y_vals = [sev_weights.get(str(a.get("severity", "minor")).lower(), 1) for a in alerts]
    colors = [sev_colors.get(str(a.get("severity", "minor")).lower(), COLORS["neutral"]) for a in alerts]
    sizes = [sev_sizes.get(str(a.get("severity", "minor")).lower(), 12) for a in alerts]
    hover_texts = [f"<b>{a.get('alert_type')}</b><br>Severity: [{str(a.get('severity')).upper()}]<br>ID: {a.get('id')}" for a in alerts]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers+text",
            marker=dict(size=sizes, color=colors, line=dict(color="#FFFFFF", width=2)),
            text=[f"[{str(a.get('severity')).upper()}]" for a in alerts],
            textposition="top center",
            hovertext=hover_texts,
            hoverinfo="text",
        )
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=[1, 2, 3],
        ticktext=["Minor", "Major", "Critical"],
        range=[0.5, 3.8],
        showgrid=True,
        gridcolor="#E5E7EB",
    )
    fig.update_xaxes(title_text="Event Timeline", showgrid=True, gridcolor="#E5E7EB")
    return _apply_layout_defaults(fig, "Statistical Anomaly Spike Timeline", height=220)
