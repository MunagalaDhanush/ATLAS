"""
ATLAS Streamlit — Plotly chart builders with dark theme.
All charts share BASE_LAYOUT and return go.Figure objects.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# ── Palette ──────────────────────────────────────────────────────────────────
PRIMARY   = "#4DA6FF"
DANGER    = "#E05555"
WARNING   = "#F0A500"
SUCCESS   = "#5DCAA5"
PURPLE    = "#AFA9EC"
SURFACE   = "#0D1526"
GRID      = "rgba(77,166,255,0.08)"
TEXT_DIM  = "#556680"
TEXT_MAIN = "#F0F4FF"

PALETTE = [PRIMARY, SUCCESS, WARNING, DANGER, PURPLE, "#FF8C69", "#67D9E0", "#C3A6FF"]


def _to_rgba(hex_color: str, alpha: float) -> str:
    """Convert 6-char hex color + float alpha to rgba() string for Plotly fillcolor."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# ── Shared layout ─────────────────────────────────────────────────────────────
def _base(height: int = 340, margin: dict | None = None) -> dict:
    m = margin or {"l": 40, "r": 20, "t": 36, "b": 40}
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,21,38,0.5)",
        font=dict(family="Inter, system-ui, sans-serif", color=TEXT_DIM, size=11),
        height=height,
        margin=m,
        xaxis=dict(
            gridcolor=GRID, linecolor="rgba(77,166,255,0.12)",
            tickfont=dict(color=TEXT_DIM, size=10),
            title_font=dict(color=TEXT_DIM, size=10),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=GRID, linecolor="rgba(77,166,255,0.12)",
            tickfont=dict(color=TEXT_DIM, size=10),
            title_font=dict(color=TEXT_DIM, size=10),
            zeroline=False,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT_DIM, size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
        colorway=PALETTE,
    )


# ── Dual-axis KPI line chart (friction rate + NPS) ────────────────────────────
def kpi_dual_line(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["week_start"], y=df["weekly_friction_rate"],
        name="Friction Rate", line=dict(color=DANGER, width=2),
        mode="lines+markers", marker=dict(size=4),
        yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=df["week_start"], y=df["weekly_avg_nps"],
        name="NPS Score", line=dict(color=SUCCESS, width=2, dash="dot"),
        mode="lines+markers", marker=dict(size=4),
        yaxis="y2",
    ))
    layout = _base(height=320)
    layout.update(dict(
        yaxis=dict(**layout["yaxis"], title="Friction Rate", title_standoff=8),
        yaxis2=dict(
            overlaying="y", side="right",
            gridcolor=GRID, linecolor="rgba(77,166,255,0.12)",
            tickfont=dict(color=TEXT_DIM, size=10),
            title="NPS Score", title_font=dict(color=TEXT_DIM, size=10),
            zeroline=False,
        ),
        title=dict(text="Friction Rate vs NPS — 28-week trend",
                   font=dict(color=TEXT_MAIN, size=13), x=0),
    ))
    fig.update_layout(**layout)
    return fig


# ── Single KPI line chart ─────────────────────────────────────────────────────
def kpi_single_line(df: pd.DataFrame, col: str, label: str,
                    color: str = PRIMARY) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["week_start"], y=df[col],
        name=label, line=dict(color=color, width=2.5),
        mode="lines+markers", marker=dict(size=5),
        fill="tozeroy", fillcolor=_to_rgba(color, 0.08),
    ))
    layout = _base(height=250)
    layout.update(title=dict(text=label, font=dict(color=TEXT_MAIN, size=12), x=0))
    fig.update_layout(**layout)
    return fig


# ── Priority bar chart (top N hotspots) ──────────────────────────────────────
def priority_bar(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    d = df.head(top_n).copy()
    d["label"] = (d["product_involved"].str.replace("_", " ").str.title()
                  + " · " + d["region"] + " · " + d["dominant_channel"])
    colors = [DANGER if s > 60 else WARNING if s > 40 else PRIMARY
              for s in d["priority_score"]]
    fig = go.Figure(go.Bar(
        x=d["priority_score"], y=d["label"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=d["priority_score"].round(1),
        textposition="inside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    layout = _base(height=max(320, top_n * 26), margin={"l": 200, "r": 20, "t": 36, "b": 40})
    layout.update(
        title=dict(text="Priority Score by Segment", font=dict(color=TEXT_MAIN, size=13), x=0),
        xaxis=dict(**layout["xaxis"], title="Priority Score (0–100)"),
        yaxis=dict(**layout["yaxis"], autorange="reversed"),
    )
    fig.update_layout(**layout)
    return fig


# ── Theme bar chart ───────────────────────────────────────────────────────────
def theme_bar(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("event_count", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["event_count"], y=d["theme"],
        orientation="h",
        name="Count",
        marker=dict(color=PRIMARY, opacity=0.8),
        text=d["event_count"],
        textposition="inside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    layout = _base(height=300, margin={"l": 120, "r": 20, "t": 36, "b": 40})
    layout.update(
        title=dict(text="LLM Theme Distribution (n=500)", font=dict(color=TEXT_MAIN, size=13), x=0),
        xaxis=dict(**layout["xaxis"], title="Event Count"),
    )
    fig.update_layout(**layout)
    return fig


# ── Sentiment by channel bar ──────────────────────────────────────────────────
def sentiment_channel_bar(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("avg_sentiment")
    colors = [SUCCESS if s > 0.3 else DANGER if s < -0.3 else WARNING
              for s in d["avg_sentiment"]]
    fig = go.Figure(go.Bar(
        x=d["channel"], y=d["avg_sentiment"],
        marker=dict(color=colors, line=dict(width=0)),
        text=d["avg_sentiment"].round(3),
        textposition="outside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1)
    layout = _base(height=280)
    layout.update(
        title=dict(text="Avg Sentiment by Channel", font=dict(color=TEXT_MAIN, size=13), x=0),
        yaxis=dict(**layout["yaxis"], title="Avg Sentiment Score"),
    )
    fig.update_layout(**layout)
    return fig


# ── Unresolved rate by channel bar ────────────────────────────────────────────
def unresolved_channel_bar(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("unresolved_rate", ascending=False)
    pct = d["unresolved_rate"] * 100
    colors = [DANGER if v > 70 else WARNING if v > 40 else SUCCESS for v in pct]
    fig = go.Figure(go.Bar(
        x=d["channel"], y=pct,
        marker=dict(color=colors),
        text=pct.round(1).astype(str) + "%",
        textposition="outside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    layout = _base(height=260)
    layout.update(
        title=dict(text="Unresolved Rate by Channel", font=dict(color=TEXT_MAIN, size=13), x=0),
        yaxis=dict(**layout["yaxis"], title="Unresolved %", range=[0, 120]),
    )
    fig.update_layout(**layout)
    return fig


# ── Friction rate by region bar ───────────────────────────────────────────────
def friction_by_region_bar(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("friction_rate", ascending=False)
    colors = [DANGER if r > 0.025 else WARNING if r > 0.02 else PRIMARY
              for r in d["friction_rate"]]
    fig = go.Figure(go.Bar(
        x=d["region"], y=d["friction_rate"] * 100,
        marker=dict(color=colors),
        text=(d["friction_rate"] * 100).round(2).astype(str) + "%",
        textposition="outside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    layout = _base(height=270)
    layout.update(
        title=dict(text="Friction Rate by Region", font=dict(color=TEXT_MAIN, size=13), x=0),
        yaxis=dict(**layout["yaxis"], title="Friction Rate %"),
    )
    fig.update_layout(**layout)
    return fig


# ── Top channel sequences horizontal bar ──────────────────────────────────────
def sequence_bar(df: pd.DataFrame) -> go.Figure:
    d = df.head(10).sort_values("friction_rate", ascending=True)
    fig = go.Figure(go.Bar(
        x=d["friction_rate"] * 100, y=d["channel_sequence"],
        orientation="h",
        marker=dict(color=DANGER, opacity=0.75, line=dict(width=0)),
        text=(d["friction_rate"] * 100).round(1).astype(str) + "%",
        textposition="inside",
        textfont=dict(color=TEXT_MAIN, size=10),
    ))
    layout = _base(height=300, margin={"l": 160, "r": 20, "t": 36, "b": 40})
    layout.update(
        title=dict(text="Top Channel Sequences by Friction Rate", font=dict(color=TEXT_MAIN, size=13), x=0),
        xaxis=dict(**layout["xaxis"], title="Friction Rate %"),
    )
    fig.update_layout(**layout)
    return fig


# ── Scatter: friction score vs episode duration ───────────────────────────────
def friction_vs_duration_scatter(df: pd.DataFrame) -> go.Figure:
    sample = df.sample(min(1500, len(df)), random_state=42)
    colors = [DANGER if x else PRIMARY for x in sample["is_friction_episode"]]
    fig = go.Figure(go.Scatter(
        x=sample["episode_duration_hours"],
        y=sample["friction_score"],
        mode="markers",
        marker=dict(color=colors, size=4, opacity=0.5),
        text=sample.get("product_involved", ""),
    ))
    layout = _base(height=320)
    layout.update(
        title=dict(text="Friction Score vs Episode Duration", font=dict(color=TEXT_MAIN, size=13), x=0),
        xaxis=dict(**layout["xaxis"], title="Episode Duration (hrs)"),
        yaxis=dict(**layout["yaxis"], title="Friction Score"),
    )
    fig.update_layout(**layout)
    return fig


# ── ARIMA forecast table visual (bar with current vs forecast) ────────────────
def arima_comparison_bar(df: pd.DataFrame) -> go.Figure:
    kpis = df["kpi_name"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Current", x=kpis, y=df["current_value"],
        marker=dict(color=PRIMARY, opacity=0.8),
    ))
    fig.add_trace(go.Bar(
        name="Forecast", x=kpis, y=df["forecast_value"],
        marker=dict(color=[DANGER if a else SUCCESS for a in df["alert_fired"]], opacity=0.8),
    ))
    layout = _base(height=300)
    layout.update(
        title=dict(text="Current vs Forecast Value per KPI", font=dict(color=TEXT_MAIN, size=13), x=0),
        barmode="group",
        xaxis=dict(**layout["xaxis"], tickangle=-15),
    )
    fig.update_layout(**layout)
    return fig


# ── Multi-metric KPI chart (week-range + style controls) ─────────────────────
_METRIC_MAP = {
    "Friction Rate":    ("weekly_friction_rate",           DANGER),
    "NPS Score":        ("weekly_avg_nps",                 SUCCESS),
    "Escalation Rate":  ("weekly_channel_escalation_rate", WARNING),
    "Resolution Rate":  ("weekly_resolution_rate",         PURPLE),
}

def kpi_multi_line(df: pd.DataFrame, metrics: list[str], style: str = "Line") -> go.Figure:
    """Dynamic KPI chart with selectable metrics and chart style.
    NPS is put on a second y-axis when combined with rate metrics."""
    fig = go.Figure()
    has_nps  = "NPS Score" in metrics
    has_rate = any(m != "NPS Score" for m in metrics)
    use_dual = has_nps and has_rate

    for metric in metrics:
        if metric not in _METRIC_MAP:
            continue
        col, color = _METRIC_MAP[metric]
        if col not in df.columns:
            continue
        y_axis = "y2" if (use_dual and metric == "NPS Score") else "y1"
        vals   = df[col]

        if style == "Bar":
            fig.add_trace(go.Bar(
                x=df["week_start"], y=vals, name=metric,
                marker=dict(color=color, opacity=0.7),
                yaxis=y_axis,
            ))
        elif style == "Area":
            fig.add_trace(go.Scatter(
                x=df["week_start"], y=vals, name=metric,
                line=dict(color=color, width=2),
                mode="lines",
                fill="tozeroy", fillcolor=_to_rgba(color, 0.09),
                yaxis=y_axis,
            ))
        else:  # Line (default)
            fig.add_trace(go.Scatter(
                x=df["week_start"], y=vals, name=metric,
                line=dict(color=color, width=2.5),
                mode="lines+markers", marker=dict(size=5),
                yaxis=y_axis,
            ))

    layout = _base(height=330)
    layout.update(title=dict(
        text="KPI Trend — " + ", ".join(metrics),
        font=dict(color=TEXT_MAIN, size=13), x=0,
    ))
    if use_dual:
        layout["yaxis"].update(title="Rate")
        layout["yaxis2"] = dict(
            overlaying="y", side="right",
            gridcolor=GRID, zeroline=False,
            tickfont=dict(color=TEXT_DIM, size=10),
            title="NPS Score", title_font=dict(color=TEXT_DIM, size=10),
        )
    fig.update_layout(**layout)
    return fig


# ── Theme + sentiment combo chart ─────────────────────────────────────────────
def theme_sentiment_combo(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("event_count", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["theme"], y=d["event_count"],
        name="Event Count", marker=dict(color=PRIMARY, opacity=0.7),
        yaxis="y1",
    ))
    sent_colors = [SUCCESS if s > 0.3 else DANGER if s < -0.3 else WARNING
                   for s in d["avg_sentiment_score"]]
    fig.add_trace(go.Scatter(
        x=d["theme"], y=d["avg_sentiment_score"],
        name="Avg Sentiment", mode="markers+lines",
        marker=dict(color=sent_colors, size=10),
        line=dict(color="rgba(255,255,255,0.2)", width=1),
        yaxis="y2",
    ))
    layout = _base(height=320)
    layout.update(dict(
        yaxis=dict(**layout["yaxis"], title="Event Count"),
        yaxis2=dict(
            overlaying="y", side="right",
            gridcolor=GRID, zeroline=False,
            tickfont=dict(color=TEXT_DIM, size=10),
            title="Avg Sentiment", title_font=dict(color=TEXT_DIM, size=10),
            range=[-1.2, 1.2],
        ),
        title=dict(text="Theme Volume & Sentiment", font=dict(color=TEXT_MAIN, size=13), x=0),
        barmode="group",
        xaxis=dict(**layout["xaxis"], tickangle=-20),
    ))
    fig.update_layout(**layout)
    return fig
