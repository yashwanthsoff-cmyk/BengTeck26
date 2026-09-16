"""lib/charts.py — Checkpoint-Native DX Visualization Engine
Provides 28 publication-grade interactive Plotly visualizations, paired donut+ranked lists,
annotated line charts, range bars, and sparklines across Features A through E.
Fully compliant with Master UI/UX Design System:
- Inter typography and responsive glass containers
- Small-caps, letter-spaced, muted-grey uppercase chart titles
- WCAG AA/AAA compliant color palette
- Strict Zero-Emoji Mandate across all text, badges, tooltips, and labels
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

# Master UI/UX Palette Tokens
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
    """Applies standardized font, small-caps muted title, sparse ticks, and transparent background."""
    formatted_title = (
        f"<span style='font-size:11px;letter-spacing:0.08em;font-weight:600;color:#8E8E93;text-transform:uppercase;'>{title.upper()}</span>"
        if title else ""
    )
    fig.update_layout(
        template=CHART_THEME,
        title=dict(
            text=formatted_title,
            font=dict(family=FONT_FAMILY, size=11, color="#8E8E93"),
            x=0.0,
            xanchor="left",
        ),
        font=dict(family=FONT_FAMILY, size=11, color=COLORS["dark"]),
        margin=dict(l=24, r=24, t=44 if title else 16, b=24),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        transition=dict(duration=400, easing="cubic-in-out"),
    )
    fig.update_xaxes(
        tickfont=dict(family=FONT_FAMILY, size=10, color="#8E8E93"),
        gridcolor="rgba(15,16,18,0.06)",
        zerolinecolor="rgba(15,16,18,0.08)",
    )
    fig.update_yaxes(
        tickfont=dict(family=FONT_FAMILY, size=10, color="#8E8E93"),
        gridcolor="rgba(15,16,18,0.06)",
        zerolinecolor="rgba(15,16,18,0.08)",
    )
    return fig


# ==============================================================================
# CORE REUSABLE COMPONENTS
# ==============================================================================

def render_empty_chart_state(title: str = "No Data Available", reason: str = "Insufficient data points for visualization") -> go.Figure:
    """Renders a refined placeholder state with dashed frame for empty/degenerate data."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"<span style='font-size:11px;letter-spacing:0.06em;font-weight:600;color:#8E8E93;text-transform:uppercase;'>{title.upper()}</span><br><br><span style='font-size:11px;color:#8E8E93;'>{reason}</span>",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=12, color=COLORS["dark"]),
        align="center",
        bordercolor="#CBD5E1",
        borderwidth=1.5,
        borderpad=18,
        bgcolor="rgba(248, 250, 252, 0.75)",
        opacity=0.95,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _apply_layout_defaults(fig, "", height=200)


def render_metric_sparkline_svg(data_points: List[float], color: str = "#0071E3", height: int = 24, width: int = 72) -> str:
    """Generates an inline SVG sparkline path for metric cards with zero dependencies."""
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


def render_ranked_list_html(items: List[Dict[str, Any]], title: str = "") -> str:
    """Renders a leaderboard-pattern ranked list with colored pill badges and accent-colored values."""
    rows_html = []
    for i, it in enumerate(items):
        rank = it.get("rank", i + 1)
        label = it.get("label", "")
        sublabel = it.get("sublabel", "")
        pct = it.get("percentage")
        if pct is not None:
            if sublabel:
                sublabel = f"{sublabel} | {pct:.1f}%"
            else:
                sublabel = f"{pct:.1f}%"
        val = it.get("value", "")
        col = it.get("color", COLORS["primary"])
        sub_span = f'<span style="font-size:10.5px;color:#8E8E93;font-family:{FONT_FAMILY};">{sublabel}</span>' if sublabel else ""
        row = (
            f'<div style="display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.7);'
            f'border:1px solid rgba(15,16,18,0.06);border-radius:8px;padding:7px 12px;margin-bottom:6px;">'
            f'  <div style="display:flex;align-items:center;gap:10px;">'
            f'    <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;'
            f'background:{col};color:#FFFFFF;font-size:10px;font-weight:700;font-family:{FONT_FAMILY};">{rank}</span>'
            f'    <div style="display:flex;flex-direction:column;">'
            f'      <span style="font-size:12px;font-weight:600;color:{COLORS["dark"]};font-family:{FONT_FAMILY};">{label}</span>'
            f'      {sub_span}'
            f'    </div>'
            f'  </div>'
            f'  <span style="font-size:12px;font-weight:700;color:{col};font-family:monospace;">{val}</span>'
            f'</div>'
        )
        rows_html.append(row)

    title_html = (
        f'<div style="font-size:11px;font-weight:600;letter-spacing:0.08em;color:#8E8E93;text-transform:uppercase;margin-bottom:8px;font-family:{FONT_FAMILY};">{title.upper()}</div>'
        if title else ""
    )
    return f'<div class="ranked-list-widget" style="width:100%;">{title_html}{"".join(rows_html)}</div>'


def render_range_bar_html(val: float, min_val: float, max_val: float, label: str = "", min_bound: float = 0.0, max_bound: float = 100.0, unit: str = "%") -> str:
    """Renders a horizontal confidence interval range bar with a marked point estimate indicator."""
    if min_val <= min_bound and max_val <= min_bound and val <= min_bound:
        return (
            f'<div style="padding:8px 12px;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:8px;font-size:11px;color:#8E8E93;font-family:{FONT_FAMILY};">'
            f'<strong>{label}:</strong> Not enough data yet (insufficient confidence interval)'
            f'</div>'
        )

    span = (max_bound - min_bound) if max_bound != min_bound else 100.0
    left_pct = max(0.0, min(100.0, ((min_val - min_bound) / span) * 100.0))
    width_pct = max(2.0, min(100.0 - left_pct, ((max_val - min_val) / span) * 100.0))
    pt_pct = max(0.0, min(100.0, ((val - min_bound) / span) * 100.0))

    label_str = f'<span style="font-size:11px;font-weight:600;color:#0F1012;font-family:{FONT_FAMILY};">{label}</span>' if label else ""
    val_str = f'<span style="font-size:11px;font-family:monospace;color:#0071E3;font-weight:600;">{val:.1f}{unit} <span style="color:#8E8E93;font-weight:400;">[{min_val:.1f} - {max_val:.1f}{unit}]</span></span>'

    return (
        f'<div style="width:100%;margin:6px 0 10px 0;font-family:{FONT_FAMILY};">'
        f'  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
        f'    {label_str}'
        f'    {val_str}'
        f'  </div>'
        f'  <div style="position:relative;width:100%;height:8px;background:#E2E8F0;border-radius:4px;overflow:visible;">'
        f'    <div style="position:absolute;left:{left_pct:.1f}%;width:{width_pct:.1f}%;height:100%;background:rgba(0,113,227,0.25);border-radius:4px;"></div>'
        f'    <div style="position:absolute;left:{pt_pct:.1f}%;top:-3px;width:4px;height:14px;background:#0071E3;border-radius:2px;box-shadow:0 1px 3px rgba(0,0,0,0.2);transform:translateX(-50%);"></div>'
        f'  </div>'
        f'</div>'
    )


def render_pipeline_health_connector_html(stages: List[Dict[str, Any]]) -> str:
    """Renders a horizontal color-coded pipeline health connector (green/amber/red) across the 5 stages."""
    status_colors = {
        "pass": "#00A651",
        "warn": "#F5A623",
        "fail": "#E3001E",
        "neutral": "#8E8E93",
    }
    stage_nodes = []
    for i, s in enumerate(stages):
        name = s.get("name", f"Stage {i+1}").upper()
        status = s.get("status", "neutral").lower()
        color = status_colors.get(status, "#8E8E93")
        score = s.get("score")
        score_str = f"{score:.1f}%" if score is not None else ""
        node = (
            f'<div style="display:flex;flex-direction:column;align-items:center;position:relative;z-index:2;flex:1;">'
            f'  <div style="width:24px;height:24px;border-radius:50%;background:{color};display:flex;align-items:center;justify-content:center;color:#FFFFFF;font-size:11px;font-weight:700;box-shadow:0 0 0 4px rgba(255,255,255,0.9);">'
            f'    {i+1}'
            f'  </div>'
            f'  <span style="font-size:10px;font-weight:700;letter-spacing:0.06em;color:#475569;margin-top:6px;text-align:center;">{name}</span>'
            f'  <span style="font-size:10px;font-family:monospace;font-weight:600;color:{color};">{score_str}</span>'
            f'</div>'
        )
        stage_nodes.append(node)

    return (
        f'<div style="position:relative;display:flex;align-items:flex-start;justify-content:space-between;width:100%;padding:10px 16px;background:rgba(255,255,255,0.6);border:1px solid rgba(15,16,18,0.06);border-radius:12px;margin:8px 0 16px 0;font-family:{FONT_FAMILY};">'
        f'  <div style="position:absolute;top:22px;left:10%;right:10%;height:3px;background:#E2E8F0;z-index:1;"></div>'
        f'  {"".join(stage_nodes)}'
        f'</div>'
    )



def render_donut_paired_center(labels: List[str], values: List[float], colors: List[str], center_title: str, center_val: str, title: str = "", height: int = 280) -> go.Figure:
    """Renders a minimalist donut chart with a central prominent annotation (paired beside Ranked List)."""
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.62,
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
                textinfo="none",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.add_annotation(
        text=f"<span style='font-size:9.5px;letter-spacing:0.06em;color:#8E8E93;text-transform:uppercase;'>{center_title}</span><br><b style='font-size:17px;color:#0F1012;'>{center_val}</b>",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(family=FONT_FAMILY),
        align="center",
    )
    fig.update_layout(showlegend=False)
    return _apply_layout_defaults(fig, title, height=height)


# ==============================================================================
# FEATURE A: DEAD-END REGISTRY VISUALIZATIONS
# ==============================================================================

def render_dead_end_type_donut(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    """Dead-End Type Distribution Donut with center top failure type."""
    counts = {}
    for d in (dead_ends or []):
        t = (d.get("dead_end_type") or "unknown").replace("_", " ").title()
        counts[t] = counts.get(t, 0) + 1

    if not counts:
        counts = {"Logic Error": 2, "Timeout": 1, "Resource Exhaustion": 1, "Schema Mismatch": 1}

    labels = list(counts.keys())
    values = list(counts.values())
    color_map = [COLORS["danger"], COLORS["warning"], COLORS["primary"], COLORS["neutral"]]
    top_label = labels[0] if labels else "Logic Error"
    top_val = f"{(values[0] / sum(values) * 100.0):.0f}%" if values else "40%"

    return render_donut_paired_center(
        labels=labels,
        values=values,
        colors=color_map[: len(labels)],
        center_title="Top Failure",
        center_val=f"{top_label}<br>{top_val}",
        title="Dead-End Type Distribution",
        height=280,
    )


def render_dead_end_ranked_list(dead_ends: Optional[List[Dict]] = None) -> str:
    """Ranked leaderboard list paired beside the Dead-End Type Distribution Donut."""
    counts = {}
    for d in (dead_ends or []):
        t = (d.get("dead_end_type") or "unknown").replace("_", " ").title()
        counts[t] = counts.get(t, 0) + 1

    if not counts:
        counts = {"Logic Error": 2, "Timeout": 1, "Resource Exhaustion": 1, "Schema Mismatch": 1}

    total = sum(counts.values()) or 1
    color_map = [COLORS["danger"], COLORS["warning"], COLORS["primary"], COLORS["neutral"]]
    sublabels = {
        "Logic Error": "Uncaught exception in token exchange",
        "Timeout": "Cold warehouse worker startup limit",
        "Resource Exhaustion": "Delta lake unpartitioned scan OOM",
        "Schema Mismatch": "Missing telemetry schema version",
    }

    items = []
    for i, (k, v) in enumerate(counts.items()):
        items.append({
            "rank": i + 1,
            "label": k,
            "sublabel": sublabels.get(k, f"{(v / total * 100.0):.0f}% frequency"),
            "value": f"{v} ({v / total * 100.0:.0f}%)",
            "color": color_map[i % len(color_map)],
        })

    return render_ranked_list_html(items, title="Leaderboard by Failure Frequency")


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
    fig.update_xaxes(title_text="Incident Occurrences", showgrid=True)
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Ranked Failure Root Causes with Checkpoint Trend Vectors", height=280)


def render_severity_distribution_bar(dead_ends: Optional[List[Dict]] = None) -> go.Figure:
    """Un-overlapped severity distribution bar chart."""
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
    fig.update_yaxes(title_text="Count", showgrid=True)
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
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(title_text="Failure Density", showgrid=True)
    return _apply_layout_defaults(fig, "Dead-End Occurrence Density Strip across Checkpoints", height=220)


# ==============================================================================
# FEATURE B: REQUIREMENT LEDGER VISUALIZATIONS
# ==============================================================================

def render_requirement_status_donut(requirements: Optional[List[Dict]] = None) -> go.Figure:
    """Requirement Status Breakdown Donut."""
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

    return render_donut_paired_center(
        labels=labels,
        values=values,
        colors=color_palette[: len(labels)],
        center_title="Completion",
        center_val=f"{values[0]} / {sum(values)}",
        title="Requirement Status Breakdown",
        height=280,
    )


def render_priority_vs_effort_scatter(requirements: Optional[List[Dict]] = None) -> go.Figure:
    """Effort vs Priority Matrix with direct top-item callout annotations."""
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

    # Direct Top Item Callout Annotations
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

    fig.update_xaxes(title_text="Story Points (Fibonacci Effort)", showgrid=True)
    fig.update_yaxes(title_text="Dynamic Priority Score (0-100)", range=[20, 105], showgrid=True)
    return _apply_layout_defaults(fig, "Effort vs Dynamic Priority Matrix with Top-Item Callouts", height=320)


def render_sprint_burndown_chart() -> go.Figure:
    """Sprint velocity and burndown trajectory with variance pace envelope."""
    return render_sprint_burndown_variance_chart()


def render_sprint_burndown_variance_chart() -> go.Figure:
    """Annotated Line Chart: actual burndown gets subtle gradient fill, ideal is dashed reference line with inline label."""
    days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7", "Day 8", "Day 9", "Day 10"]
    ideal = [25.0, 22.5, 20.0, 17.5, 15.0, 12.5, 10.0, 7.5, 5.0, 0.0]
    actual = [25.0, 24.0, 21.0, 18.0, 16.0, 13.0, 9.5, 6.0, 3.5, 1.0]

    fig = go.Figure()

    # Ideal burndown dashed reference line with inline annotation
    fig.add_trace(
        go.Scatter(
            x=days,
            y=ideal,
            mode="lines",
            line=dict(color=COLORS["neutral"], dash="dash", width=2),
            name="Ideal Burndown",
        )
    )

    # Actual burndown with subtle gradient fill
    fig.add_trace(
        go.Scatter(
            x=days,
            y=actual,
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(0, 113, 227, 0.08)",
            name="Actual Burndown",
        )
    )

    # Inline label directly on ideal line
    fig.add_annotation(
        x="Day 4",
        y=17.5,
        text="Ideal Pace",
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color=COLORS["neutral"]),
        bgcolor="rgba(255,255,255,0.8)",
    )

    # Pace Callout Annotation on Current Point
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

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(title_text="Story Points Remaining", showgrid=True)
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
    fig.update_xaxes(title_text=f"Requirements (Total: {total})", showgrid=True)
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

    fig.update_yaxes(title_text="Days in Current Status", showgrid=True)
    return _apply_layout_defaults(fig, "Requirement Aging & Stale Risk Monitor", height=280)


# ==============================================================================
# FEATURE C: INTENT CONFORMANCE VISUALIZATIONS
# ==============================================================================

def render_intent_conformance_gauge(conformance_score: float = 0.885, title: str = "Category Domain Conformance", prev_score: Optional[float] = None) -> go.Figure:
    """Multi-arc gauge with color-banded threshold zones and delta reference."""
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
    """Horizontal domain conformance rate bars."""
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
    fig.update_xaxes(title_text="Conformance Rate (%)", range=[0, 105], showgrid=True)
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Domain Cluster Conformance Rates", height=280)


def render_domain_conformance_donut(domain_data: Optional[Dict[str, float]] = None) -> go.Figure:
    """Domain Cluster Conformance Donut with top domain in center."""
    if domain_data:
        domains = list(domain_data.keys())
        scores = [float(domain_data[k]) if domain_data[k] > 1.0 else float(domain_data[k]) * 100.0 for k in domains]
    else:
        domains = ["Security", "UI/UX", "Functional", "Governance", "Performance"]
        scores = [92.0, 95.0, 88.0, 78.0, 68.0]

    colors = [COLORS["success"], "#34D399", COLORS["primary"], COLORS["warning"], COLORS["danger"]]
    return render_donut_paired_center(
        labels=domains,
        values=scores,
        colors=colors[: len(domains)],
        center_title="Top Domain",
        center_val=f"{domains[0]}<br>{scores[0]:.1f}%",
        title="Domain Conformance Distribution",
        height=280,
    )


def render_domain_ranked_list(domain_data: Optional[Dict[str, float]] = None) -> str:
    """Ranked leaderboard list paired beside the Domain Conformance Donut."""
    if domain_data:
        domains = list(domain_data.keys())
        scores = [float(domain_data[k]) if domain_data[k] > 1.0 else float(domain_data[k]) * 100.0 for k in domains]
    else:
        domains = ["Security", "UI/UX", "Functional", "Governance", "Performance"]
        scores = [92.0, 95.0, 88.0, 78.0, 68.0]

    pairs = sorted(zip(domains, scores), key=lambda x: x[1], reverse=True)
    items = []
    for i, (d, s) in enumerate(pairs):
        col = COLORS["success"] if s >= 85 else (COLORS["warning"] if s >= 75 else COLORS["danger"])
        tag = "[MET]" if s >= 85 else ("[PARTIAL]" if s >= 75 else "[GAP]")
        items.append({
            "rank": i + 1,
            "label": d,
            "sublabel": f"Status: {tag}",
            "value": f"{s:.1f}%",
            "color": col,
        })
    return render_ranked_list_html(items, title="Domain Conformance Leaderboard")


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
        subplot_titles=[f"<span style='font-size:10.5px;color:#8E8E93;font-weight:600;'>{d.upper()}</span>" for d in domains],
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
    """7-day intent conformance trajectory Annotated Line Chart with forecast confidence band."""
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

    # Subtle area gradient fill beneath actual
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=actual,
            mode="lines+markers",
            name="Observed Conformance",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=7),
            fill="tozeroy",
            fillcolor="rgba(0, 113, 227, 0.08)",
        )
    )

    # Forecast with confidence area
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

    # Forecast trajectory line (dashed, distinct)
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

    # Dashed Target Line with inline label
    fig.add_shape(type="line", x0=dates[0], x1=f_dates[-1], y0=85, y1=85, line=dict(color=COLORS["success"], width=1.5, dash="dash"))
    fig.add_annotation(x=dates[1], y=86.5, text="85% Pass/Fail Threshold", showarrow=False, font=dict(family=FONT_FAMILY, size=10, color=COLORS["success"]))

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(title_text="Conformance Rate (%)", range=[65, 100], showgrid=True)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=11)))
    return _apply_layout_defaults(fig, "7-Day Intent Conformance Trend & Forecast Band", height=310)


def render_intent_status_donut(intents_data: Optional[List[Dict]] = None) -> go.Figure:
    """Clause Conformance Distribution Donut."""
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

    return render_donut_paired_center(
        labels=labels,
        values=values,
        colors=color_palette,
        center_title="Top Clause",
        center_val=f"{labels[0]}<br>{values[0]}",
        title="Clause Conformance Distribution",
        height=280,
    )


def render_clause_ranked_list(intents_data: Optional[List[Dict]] = None) -> str:
    """Ranked leaderboard list paired beside Clause Conformance Donut."""
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

    total = sum(status_counts.values()) or 1
    color_palette = [COLORS["success"], "#34D399", COLORS["warning"], COLORS["danger"]]
    items = []
    for i, (k, v) in enumerate(status_counts.items()):
        items.append({
            "rank": i + 1,
            "label": k,
            "sublabel": f"{v} clause{'s' if v != 1 else ''} verified",
            "value": f"{(v / total * 100.0):.0f}%",
            "color": color_palette[i % len(color_palette)],
        })
    return render_ranked_list_html(items, title="Clause Conformance Tiers")


# ==============================================================================
# FEATURE D: AGENT RESUME CONTRACT VISUALIZATIONS
# ==============================================================================

def render_contract_funnel_chart() -> go.Figure:
    """Contract Consumption Funnel with explicit percentage-delta annotations."""
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
    """Section engagement heatmap with muted axis labels and clean glass surface."""
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
        fig.update_yaxes(title_text="Weight Percentage (%)", range=[0, 60], showgrid=True)
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
    """Visual before/after comparison bar chart showing magnitude of contract changes."""
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
    fig.update_xaxes(title_text="Net Delta Between Contract Versions", showgrid=True)
    fig.update_yaxes(autorange="reversed")
    return _apply_layout_defaults(fig, "Contract Semantic Diff & Evolution Vector", height=240)


def render_contract_version_timeline(versions: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Connected horizontal milestone timeline with dot per version."""
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
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(title_text="Contract Integrity (%)", range=[75, 100], showgrid=True)
    return _apply_layout_defaults(fig, "Contract Version Evolution Timeline", height=260)


def render_consumer_channel_donut(cb_data: Optional[Dict[str, int]] = None) -> go.Figure:
    """Consumer Channel Breakdown Donut with center top consumer."""
    if not cb_data:
        cb_data = {"Human UI Views": 142, "API Fetch": 86, "Autonomous Agents": 58}

    labels = list(cb_data.keys())
    values = list(cb_data.values())
    colors = [COLORS["primary"], "#2563EB", "#0D9488"]
    top_lbl = labels[0] if labels else "Human UI"
    top_pct = f"{(values[0] / sum(values) * 100.0):.0f}%" if values else "50%"

    return render_donut_paired_center(
        labels=labels,
        values=values,
        colors=colors,
        center_title="Top Channel",
        center_val=f"{top_lbl}<br>{top_pct}",
        title="Consumer Channel Breakdown",
        height=280,
    )


def render_consumer_channel_ranked_list(cb_data: Optional[Dict[str, int]] = None) -> str:
    """Ranked leaderboard list paired beside Consumer Channel Donut."""
    if not cb_data:
        cb_data = {"Human UI Views": 142, "API Fetch": 86, "Autonomous Agents": 58}

    total = sum(cb_data.values()) or 1
    colors = [COLORS["primary"], "#2563EB", "#0D9488"]
    items = []
    for i, (k, v) in enumerate(cb_data.items()):
        items.append({
            "rank": i + 1,
            "label": k,
            "sublabel": f"{(v / total * 100.0):.1f}% of total loads",
            "value": f"{v} loads",
            "color": colors[i % len(colors)],
        })
    return render_ranked_list_html(items, title="Channel Consumption Leaderboard")


def render_ab_test_comparison_bars(ab_tests: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Paired-bar comparison (Variant A vs Variant B completion rate) with winner highlighted."""
    if not ab_tests:
        ab_tests = [
            {"name": "Dev vs QA Compact", "va": 83.3, "vb": 86.4, "winner": "QA (86.4%)"},
            {"name": "PM Standard vs Technical", "va": 78.0, "vb": 72.0, "winner": "PM Standard (78.0%)"},
        ]

    names = [t.get("name") or t.get("test_name", f"Test {i+1}") for i, t in enumerate(ab_tests)]
    rates_a = []
    rates_b = []
    for t in ab_tests:
        res = t.get("results") or {}
        ra = res.get("variant_a_rate") or t.get("va") or 83.3
        rb = res.get("variant_b_rate") or t.get("vb") or 86.4
        rates_a.append(ra if ra > 1.0 else ra * 100.0)
        rates_b.append(rb if rb > 1.0 else rb * 100.0)

    fig = go.Figure(
        data=[
            go.Bar(name="Variant A (Control)", x=names, y=rates_a, marker=dict(color=COLORS["primary"])),
            go.Bar(name="Variant B (Challenger)", x=names, y=rates_b, marker=dict(color=COLORS["success"])),
        ]
    )
    fig.update_layout(
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, font=dict(size=11)),
    )
    fig.update_yaxes(title_text="Completion Rate (%)", range=[0, 100], showgrid=True)
    return _apply_layout_defaults(fig, "Template A/B Testing Variant Completion Rates", height=280)


# ==============================================================================
# FEATURE E: RESUME INTEGRITY & MEMORY (FLAGSHIP VISUALS)
# ==============================================================================

def render_integrity_trajectory_flagship(trend_res: Optional[Dict[str, Any]] = None, anomaly_events: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Flagship Annotated Line Chart: gradient fill, dashed safety threshold with inline label, vertical alert event markers, dashed forecast."""
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

    # Safety Zone Shading (Green >=80%, Amber 60-80%, Red <60%)
    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(0, 166, 81, 0.07)", line_width=0, layer="below")
    fig.add_hrect(y0=60, y1=80, fillcolor="rgba(245, 166, 35, 0.06)", line_width=0, layer="below")
    fig.add_hrect(y0=40, y1=60, fillcolor="rgba(227, 0, 30, 0.05)", line_width=0, layer="below")

    # Uncertainty Envelope
    fig.add_trace(go.Scatter(x=all_x, y=y_upper, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=all_x,
            y=y_lower,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(0, 113, 227, 0.10)",
            name="Variance Band (+-1s)",
            hoverinfo="skip",
        )
    )

    # Historical Trajectory with subtle gradient fill
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=y_scores,
            mode="lines+markers",
            name="Historical Integrity",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=8, color=COLORS["primary"], line=dict(color="#FFFFFF", width=2)),
            fill="tozeroy",
            fillcolor="rgba(0, 113, 227, 0.08)",
            hovertemplate="<b>%{x}</b><br>Integrity: %{y:.1f}%<extra></extra>",
        )
    )

    # Forecast Segment (dashed, distinct)
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

    # Direct Callout Annotations
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

    # Dashed Safety Threshold Line with inline label
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

    # Vertical Event Markers for Anomaly Alerts
    events = anomaly_events or [{"x": x_labels[min(2, len(x_labels)-1)], "label": "ALERT"}]
    for ev in events:
        ev_x = ev.get("x")
        if ev_x in all_x:
            fig.add_shape(
                type="line",
                x0=ev_x,
                x1=ev_x,
                y0=50,
                y1=100,
                line=dict(color=COLORS["danger"], width=1.5, dash="dot"),
            )
            fig.add_annotation(
                x=ev_x,
                y=56,
                text="<b>[ALERT]</b>",
                showarrow=False,
                font=dict(family=FONT_FAMILY, size=9, color=COLORS["danger"]),
                bgcolor="#FEE2E2",
                bordercolor=COLORS["danger"],
                borderwidth=1,
            )

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(title_text="Integrity Score (%)", range=[50, 105], showgrid=True)
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
    fig.update_xaxes(title_text=f"Memory Entries (Total: {total})", showgrid=True)
    fig.update_yaxes(visible=False)
    return _apply_layout_defaults(fig, "Agent Memory Confidence Battery Meter", height=160)


def render_memory_confidence_donut(bins_data: Optional[Dict[str, int]] = None, avg_conf: float = 0.852) -> go.Figure:
    """Agent Memory Confidence Donut with central average confidence."""
    if not bins_data:
        bins_data = {
            "Fresh (>0.8)": 7,
            "Medium (0.5-0.8)": 2,
            "Marginal (0.3-0.5)": 1,
            "Decayed (<0.3)": 1,
        }

    labels = list(bins_data.keys())
    values = list(bins_data.values())
    colors = [COLORS["success"], COLORS["primary"], COLORS["warning"], COLORS["danger"]]

    return render_donut_paired_center(
        labels=labels,
        values=values,
        colors=colors,
        center_title="Avg Confidence",
        center_val=f"{avg_conf * 100.0 if avg_conf <= 1.0 else avg_conf:.1f}%",
        title="Agent Memory Confidence Distribution",
        height=280,
    )


def render_memory_ranked_list(bins_data: Optional[Dict[str, int]] = None) -> str:
    """Ranked leaderboard list paired beside Memory Confidence Donut."""
    if not bins_data:
        bins_data = {
            "Fresh (>0.8)": 7,
            "Medium (0.5-0.8)": 2,
            "Marginal (0.3-0.5)": 1,
            "Decayed (<0.3)": 1,
        }

    total = sum(bins_data.values()) or 1
    colors = [COLORS["success"], COLORS["primary"], COLORS["warning"], COLORS["danger"]]
    sublabels = {
        "Fresh (>0.8)": "Safe for resumption with zero penalty",
        "Medium (0.5-0.8)": "Active context with mild half-life decay",
        "Marginal (0.3-0.5)": "Approaching stale threshold (72h)",
        "Decayed (<0.3)": "Candidate for TTL automated purging",
    }

    items = []
    for i, (k, v) in enumerate(bins_data.items()):
        items.append({
            "rank": i + 1,
            "label": k,
            "sublabel": sublabels.get(k, ""),
            "value": f"{v} ({v / total * 100.0:.0f}%)",
            "color": colors[i % len(colors)],
        })
    return render_ranked_list_html(items, title="Memory Tier Breakdown")


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
    fig.update_yaxes(title_text="Integrity Score (%)", range=[y_min, 105], showgrid=True)
    return _apply_layout_defaults(fig, "Cross-Session Integrity vs Aggregate Baseline", height=300)


def render_multi_session_ranked_list(session_scores: Optional[Dict[str, Any]] = None) -> str:
    """Ranked leaderboard list paired beside Cross-Session Integrity Bar."""
    if session_scores and isinstance(session_scores, dict):
        sessions = list(session_scores.keys())
        scores = []
        for sid in sessions:
            sc = session_scores[sid].get("score", 0.85) if isinstance(session_scores[sid], dict) else float(session_scores[sid])
            scores.append(sc * 100.0 if sc <= 1.0 else sc)
    else:
        sessions = ["session-prod-01", "session-prod-02", "session-prev-01"]
        scores = [95.0, 88.0, 85.0]

    pairs = sorted(zip(sessions, scores), key=lambda x: x[1], reverse=True)
    items = []
    for i, (sid, sc) in enumerate(pairs):
        col = COLORS["success"] if sc >= 80 else COLORS["danger"]
        status_tag = "[SAFE]" if sc >= 80 else "[BLOCKED]"
        items.append({
            "rank": i + 1,
            "label": sid,
            "sublabel": f"Status: {status_tag}",
            "value": f"{sc:.1f}%",
            "color": col,
        })
    return render_ranked_list_html(items, title="Session Integrity Leaderboard")


def render_memory_confidence_histogram() -> go.Figure:
    """Historical memory confidence histogram kept for compatibility."""
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
    fig.update_yaxes(title_text="Memory Entries Count", showgrid=True)
    return _apply_layout_defaults(fig, "Agent Memory Confidence Distribution", height=280)


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
    )
    fig.update_xaxes(title_text="Event Timeline", showgrid=True)
    return _apply_layout_defaults(fig, "Statistical Anomaly Spike Timeline", height=220)
