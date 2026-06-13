"""
ATLAS — KPI Monitor
28-week trend charts, ARIMA forecast, per-KPI alerts
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st

from utils.atlas_style import (
    inject_css, live_badge, atlas_page_header, section_header,
    alert_banner, render_sidebar_guide,
)
from utils.db import get_kpi_weekly, get_kpi_alerts
from utils.charts import kpi_single_line, arima_comparison_bar, kpi_multi_line
from utils.ai import generate_kpi_story

_ENV_PATH = _APP_DIR.parents[1] / ".env"   # ATLAS/.env

st.set_page_config(page_title="ATLAS — KPI Monitor", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()
st.markdown(live_badge(), unsafe_allow_html=True)
render_sidebar_guide()
atlas_page_header("KPI Monitor", "28-week trends + ARIMA forecasts")

kpi_df = get_kpi_weekly()
alerts = get_kpi_alerts()

if not kpi_df.empty and not pd.api.types.is_datetime64_any_dtype(kpi_df["week_start"]):
    kpi_df["week_start"] = pd.to_datetime(kpi_df["week_start"])

fired = alerts[alerts["alert_fired"] == True]
if len(fired):
    names   = fired["kpi_name"].str.replace("weekly_", "").str.replace("_", " ").tolist()
    summary = " | ".join(
        f"{n}: {row['pct_change']:+.1f}%"
        for n, (_, row) in zip(names, fired.iterrows())
    )
    st.markdown(alert_banner(len(fired), summary), unsafe_allow_html=True)

with st.expander("📖 What is a forecast alert?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">A forecast alert fires when a KPI's ARIMA model predicts a change
of more than 10%</strong> from the current value to next week. Each alert shows:
<br><br>
<ul style="margin:0 0 8px 16px; padding:0;">
  <li><strong style="color:#F0F4FF;">Current value</strong> — the most recent week's actual measurement</li>
  <li><strong style="color:#F0F4FF;">Forecast value</strong> — ARIMA's predicted value for next week</li>
  <li><strong style="color:#F0F4FF;">% Change</strong> — the gap between the two, coloured red (deteriorating) or green (improving)</li>
  <li><strong style="color:#F0F4FF;">ADF p-value</strong> — how confident we are the series is stationary before fitting. p &lt; 0.05 means stationary; above it, the series is differenced (d=1) before ARIMA fitting.</li>
</ul>
<strong style="color:#F0F4FF;">Why it matters:</strong> These alerts give operations teams a 7-day
window to intervene before customers experience degraded service. Even a 1-week head start on
staffing or process fixes can meaningfully reduce the downstream friction impact.
</div>
""", unsafe_allow_html=True)

# ── ARIMA overview ─────────────────────────────────────────────────────────────
st.markdown(section_header("ARIMA Forecast vs Current"), unsafe_allow_html=True)
st.plotly_chart(arima_comparison_bar(alerts), use_container_width=True)

with st.expander("📖 How does ARIMA forecasting work here?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">ARIMA</strong> (AutoRegressive Integrated Moving Average) is a
classical time-series model that captures three effects:
<br><br>
<ul style="margin:0 0 8px 16px; padding:0;">
  <li><strong style="color:#F0F4FF;">AR(2)</strong> — the value this week depends on the two most recent values</li>
  <li><strong style="color:#F0F4FF;">I(d)</strong> — differencing removes trends; d=1 if ADF test says series is not stationary</li>
  <li><strong style="color:#F0F4FF;">MA(2)</strong> — smooths out short-term shocks using the two most recent forecast errors</li>
</ul>
The model is fitted on all 28 available weekly data points and produces a single one-step-ahead
forecast. The chart above shows current vs forecast side-by-side for each KPI.<br><br>
<em style="color:#556680; font-size:12px;">Important caveat: ARIMA is most reliable for stable,
long-running series. With only 28 weeks, treat forecast direction (up vs down) as more meaningful
than the exact magnitude.</em>
</div>
""", unsafe_allow_html=True)

# ── Alert status rows ──────────────────────────────────────────────────────────
st.markdown(section_header("KPI Alert Status"), unsafe_allow_html=True)

for _, row in alerts.iterrows():
    fired_flag = bool(row["alert_fired"])
    pct        = float(row["pct_change"])
    direction  = str(row.get("direction", ""))
    color      = ("#E05555" if (fired_flag and "deteriorating" in direction)
                  else "#5DCAA5" if (fired_flag and "improving" in direction)
                  else "#556680")
    badge_text  = "ALERT" if fired_flag else "CLEAR"
    badge_bg    = "rgba(224,85,85,0.1)" if fired_flag else "rgba(85,102,128,0.08)"
    badge_color = "#E05555" if fired_flag else "#556680"
    kpi_label   = str(row["kpi_name"]).replace("weekly_", "").replace("_", " ").title()
    adf_raw     = row.get("adf_pvalue", 0)
    adf_p       = float(adf_raw) if adf_raw is not None and not pd.isna(adf_raw) else 0.0

    st.markdown(f"""
<div style="background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-radius:8px; padding:14px 18px; margin-bottom:8px;
            display:flex; align-items:center; gap:16px;">
  <div style="padding:3px 10px; border-radius:4px; font-size:10px; font-weight:700;
              background:{badge_bg}; color:{badge_color}; letter-spacing:1px; flex-shrink:0;"
  >{badge_text}</div>
  <div style="flex:1;">
    <div style="color:#F0F4FF; font-weight:600; font-size:13px;">{kpi_label}</div>
    <div style="color:#556680; font-size:11px; margin-top:2px;">
      Current: {float(row['current_value']):.4f} &rarr; Forecast: {float(row['forecast_value']):.4f}
      &nbsp;&middot;&nbsp; ADF p={adf_p:.3f}
      &nbsp;&middot;&nbsp; <span style="color:{color};">{direction}</span>
    </div>
  </div>
  <div style="color:{color}; font-size:18px; font-weight:800; flex-shrink:0;">{pct:+.1f}%</div>
</div>
""", unsafe_allow_html=True)

# ── Chart controls ─────────────────────────────────────────────────────────────
st.markdown(section_header("Trend Chart Controls"), unsafe_allow_html=True)

st.markdown("""
<div style="background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-radius:8px; padding:12px 16px; margin-bottom:12px;">
  <span style="font-size:10px; color:#4DA6FF; letter-spacing:1.5px;
               text-transform:uppercase; font-weight:700;">Chart Controls</span>
</div>
""", unsafe_allow_html=True)

ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
with ctrl1:
    week_range = st.slider(
        "Week range",
        min_value=1, max_value=max(len(kpi_df), 1),
        value=(1, len(kpi_df)),
        key="kpi_week_range",
    )
with ctrl2:
    y_metrics = st.multiselect(
        "Metrics to show",
        options=["Friction Rate", "NPS Score", "Escalation Rate", "Resolution Rate"],
        default=["Friction Rate", "NPS Score"],
        key="kpi_metric_select",
    )
with ctrl3:
    chart_style = st.selectbox(
        "Style", options=["Line", "Area", "Bar"], key="kpi_chart_style",
    )

filtered_kpi = kpi_df.iloc[week_range[0] - 1 : week_range[1]]
if y_metrics and not filtered_kpi.empty:
    st.plotly_chart(kpi_multi_line(filtered_kpi, y_metrics, chart_style),
                    use_container_width=True)

# ── Per-KPI sparklines ─────────────────────────────────────────────────────────
st.markdown(section_header("Individual KPI Trends"), unsafe_allow_html=True)

_kpis = [
    ("weekly_friction_rate",           "Friction Rate",           "#E05555"),
    ("weekly_avg_nps",                 "Avg NPS Score",           "#5DCAA5"),
    ("weekly_channel_escalation_rate", "Channel Escalation Rate", "#F0A500"),
    ("weekly_resolution_rate",         "Resolution Rate",         "#AFA9EC"),
    ("weekly_avg_episode_duration",    "Avg Episode Duration (h)","#4DA6FF"),
]
for i in range(0, len(_kpis), 2):
    cols = st.columns(2)
    for j, (col_name, label, color) in enumerate(_kpis[i:i+2]):
        with cols[j]:
            st.plotly_chart(kpi_single_line(kpi_df, col_name, label, color),
                            use_container_width=True)

# ── AI Story panel ────────────────────────────────────────────────────────────
st.markdown(section_header("AI Forecast Briefing"), unsafe_allow_html=True)

if not kpi_df.empty:
    week_options = kpi_df["week_start"].dt.strftime("%Y-%m-%d").tolist()
    default_week = week_options[-2] if len(week_options) >= 2 else week_options[-1]

    sel_week = st.select_slider(
        "Select a week to analyse forecast implications",
        options=week_options,
        value=default_week,
        key="kpi_week_selector",
    )

    if st.button("⚡ Generate forecast briefing", key="kpi_story_btn"):
        idx      = week_options.index(sel_week)
        prev_idx = max(0, idx - 1)
        w_row    = kpi_df.iloc[idx]
        p_row    = kpi_df.iloc[prev_idx]

        def _v(row, col):
            v = row[col]
            return 0.0 if pd.isna(v) else float(v)

        week_data = {
            "week":          sel_week,
            "friction_rate": _v(w_row, "weekly_friction_rate"),
            "nps":           _v(w_row, "weekly_avg_nps"),
            "escalation":    _v(w_row, "weekly_channel_escalation_rate"),
            "resolution":    _v(w_row, "weekly_resolution_rate"),
            "duration":      _v(w_row, "weekly_avg_episode_duration"),
        }
        prev_data = {
            "week":          week_options[prev_idx],
            "friction_rate": _v(p_row, "weekly_friction_rate"),
            "nps":           _v(p_row, "weekly_avg_nps"),
            "escalation":    _v(p_row, "weekly_channel_escalation_rate"),
            "resolution":    _v(p_row, "weekly_resolution_rate"),
            "duration":      _v(p_row, "weekly_avg_episode_duration"),
        }
        with st.spinner("Generating forecast analysis..."):
            story = generate_kpi_story(week_data, prev_data, len(fired), _ENV_PATH)
        st.session_state["kpi_story"]      = story
        st.session_state["kpi_story_week"] = sel_week

    if "kpi_story" in st.session_state:
        story      = st.session_state["kpi_story"]
        story_week = st.session_state.get("kpi_story_week", "")
        st.markdown(f"""
<div style="
  background:linear-gradient(135deg, rgba(83,74,183,0.12), rgba(77,166,255,0.08));
  border:1px solid rgba(138,92,246,0.3);
  border-left:3px solid #8A5CF6;
  border-radius:10px;
  padding:20px 24px;
  margin-top:8px;
">
  <div style="font-size:10px; letter-spacing:2px; color:#8A5CF6;
              text-transform:uppercase; margin-bottom:10px;">
    ⚡ AI FORECAST BRIEFING — {story_week}
  </div>
  <div style="font-size:14px; line-height:1.8; color:#C8D8F0; font-style:italic;">
    {story}
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:8px; font-size:10px; color:#334455;">
    * Friction rate and escalation rate alerts reflect ARIMA mean-reversion from partial final week.
    Resolution rate improvement alert is genuine upward trend.
</div>
""", unsafe_allow_html=True)
