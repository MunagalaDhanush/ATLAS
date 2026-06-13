"""
ATLAS — Executive Dashboard (Home)
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st

from utils.atlas_style import (
    inject_css, live_badge, atlas_hero_header,
    section_header, alert_banner,
    hotspot_card, generate_hotspot_headline,
    render_sidebar_footer, render_sidebar_guide,
)
from utils.db import get_kpi_alerts, get_kpi_weekly, get_friction_hotspots, get_journey_stats
from utils.charts import kpi_multi_line
from utils.ai import generate_week_story

_ENV_PATH = _APP_DIR.parents[1] / ".env"

st.set_page_config(
    page_title="ATLAS — Executive Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
st.markdown(live_badge(), unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding:16px 0 8px 0; text-align:center;">
    <div style="font-size:22px; font-weight:800; color:#F0F4FF; letter-spacing:2px;">ATLAS</div>
    <div style="font-size:9px; color:#334455; letter-spacing:2px; text-transform:uppercase; margin-top:2px;">
        Analytics Platform
    </div>
</div>
""", unsafe_allow_html=True)
    st.markdown("---")
    render_sidebar_footer()
render_sidebar_guide()

# ── Hero header ────────────────────────────────────────────────────────────────
atlas_hero_header()

# ── Load data ──────────────────────────────────────────────────────────────────
stats  = get_journey_stats()
alerts = get_kpi_alerts()
kpi_df = get_kpi_weekly()
hots   = get_friction_hotspots()

if not kpi_df.empty and not pd.api.types.is_datetime64_any_dtype(kpi_df["week_start"]):
    kpi_df["week_start"] = pd.to_datetime(kpi_df["week_start"])

fired   = alerts[alerts["alert_fired"] == True]
n_fired = len(fired)

# ── Alert banner ───────────────────────────────────────────────────────────────
if n_fired > 0:
    names   = fired["kpi_name"].str.replace("weekly_", "").str.replace("_", " ").tolist()
    summary = " | ".join(
        f"{n}: {row['pct_change']:+.1f}%"
        for n, (_, row) in zip(names, fired.iterrows())
    )
    st.markdown(alert_banner(n_fired, summary), unsafe_allow_html=True)

with st.expander("📖 What is a forecast alert?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">A forecast alert fires when a KPI's ARIMA model predicts a change of more than 10%</strong>
from the current value to next week. ARIMA (AutoRegressive Integrated Moving Average) is a
statistical model that learns the pattern of a metric over 28 weeks and extrapolates it forward.
<br><br>
<strong style="color:#F0F4FF;">Why it matters:</strong> Alerts that fire on deteriorating metrics — like rising
friction rate or escalating channel contacts — give operations teams a 7-day window to intervene
before customers start experiencing worse service. Even a 1-week head start on resource planning
or process fixes can meaningfully reduce impact.
<br><br>
<em style="color:#556680;">Technical note: each KPI is tested for stationarity using the
Augmented Dickey-Fuller test before ARIMA fitting. Non-stationary series are differenced (d=1).</em>
</div>
""", unsafe_allow_html=True)

# ── KPI metric cards (native st.metric + colored delta line) ───────────────────
st.markdown(section_header("Key Performance Indicators", margin_top="8px"),
            unsafe_allow_html=True)

def _safe_last(col: str) -> float:
    s = kpi_df[col].dropna()
    return float(s.iloc[-1]) if len(s) > 0 else 0.0

def _safe_delta(col: str) -> float | None:
    s = kpi_df[col].dropna()
    return (float(s.iloc[-1]) - float(s.iloc[-2])) if len(s) >= 2 else None

def _delta_line(col: str, lower_is_better: bool = False, scale: float = 1.0,
                unit: str = "pp") -> None:
    d = _safe_delta(col)
    if d is None or pd.isna(d):
        return
    is_good  = (d < 0) if lower_is_better else (d > 0)
    color    = "#5DCAA5" if is_good else "#E05555"
    arrow    = "▼" if d < 0 else "▲"
    label    = "improving" if is_good else "deteriorating"
    st.markdown(
        f'<p style="font-size:11px; color:{color}; margin-top:-12px; padding-left:2px;">'
        f'{arrow} {abs(d * scale):.3f}{unit} — {label}</p>',
        unsafe_allow_html=True,
    )

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Friction Rate", f"{_safe_last('weekly_friction_rate') * 100:.2f}%")
    _delta_line("weekly_friction_rate", lower_is_better=True, scale=100, unit="pp")
with c2:
    st.metric("NPS Score", f"{_safe_last('weekly_avg_nps'):.2f}")
    _delta_line("weekly_avg_nps", lower_is_better=False, scale=1.0, unit=" pts")
with c3:
    st.metric("Escalation Rate", f"{_safe_last('weekly_channel_escalation_rate') * 100:.2f}%")
    _delta_line("weekly_channel_escalation_rate", lower_is_better=True, scale=100, unit="pp")
with c4:
    st.metric("Resolution Rate", f"{_safe_last('weekly_resolution_rate') * 100:.1f}%")
    _delta_line("weekly_resolution_rate", lower_is_better=False, scale=100, unit="pp")

with st.expander("📖 What do these numbers mean?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">Friction Rate (2.2%)</strong> means that out of every 100 customer
service episodes, about 2 required the customer to contact the bank through more than one channel,
make multiple attempts, or wait more than 48 hours for resolution. While 2.2% sounds small, this
represents hundreds of customers per week experiencing unnecessary difficulty.
<br><br>
<strong style="color:#F0F4FF;">NPS Score</strong> (Net Promoter Score, 0–10) measures how likely
customers are to recommend the bank. A score above 7 is generally considered healthy. A declining
NPS trend is an early warning signal of customer dissatisfaction.
<br><br>
<strong style="color:#F0F4FF;">Why it matters:</strong> Research shows customers who experience
friction are 4× more likely to consider switching banks within 90 days. Reducing friction rate by
even 0.5 percentage points can meaningfully impact retention.
<br><br>
<details style="margin-top:8px;">
<summary style="color:#4DA6FF; cursor:pointer; font-size:12px;">Technical detail</summary>
<div style="margin-top:8px; font-size:11px; color:#556680; line-height:1.6;">
Friction Rate = friction episodes / total episodes over the selected week.
A friction episode is one where ≥1 of 4 rules fired: multi-channel escalation,
unresolved after 48h, high contact frequency (≥3 contacts), or negative NPS survey.
Episode windows use a 72-hour gap threshold via vectorized pandas shift+cumsum.
</div>
</details>
</div>
""", unsafe_allow_html=True)

# ── Mini stats row ─────────────────────────────────────────────────────────────
st.markdown(section_header("Platform Summary"), unsafe_allow_html=True)
s1, s2, s3, s4 = st.columns(4)
s1.metric("Total Episodes",      f"{int(stats['total_episodes']):,}")
s2.metric("Friction Episodes",   f"{int(stats['friction_episodes']):,}",
          f"{stats['friction_episodes'] / stats['total_episodes'] * 100:.1f}% of total")
s3.metric("Unique Customers",    f"{int(stats['unique_customers']):,}")
s4.metric("Avg Friction Duration", f"{stats['avg_friction_duration']:.1f}h")

# ── 28-week chart with axis controls ──────────────────────────────────────────
st.markdown(section_header("28-Week KPI Trend"), unsafe_allow_html=True)

st.markdown("""
<div style="background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-radius:8px; padding:10px 16px; margin-bottom:10px;">
  <span style="font-size:10px; color:#4DA6FF; letter-spacing:1.5px;
               text-transform:uppercase; font-weight:700;">Chart Controls</span>
</div>
""", unsafe_allow_html=True)

ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
with ctrl1:
    week_range = st.slider(
        "Week range", min_value=1, max_value=max(len(kpi_df), 1),
        value=(1, len(kpi_df)), key="week_range_slider",
    )
with ctrl2:
    y_metrics = st.multiselect(
        "Metrics to show",
        options=["Friction Rate", "NPS Score", "Escalation Rate", "Resolution Rate"],
        default=["Friction Rate", "NPS Score"],
        key="metric_select",
    )
with ctrl3:
    chart_style = st.selectbox("Style", options=["Line", "Area", "Bar"], key="chart_style")

filtered_kpi = kpi_df.iloc[week_range[0] - 1 : week_range[1]]
if y_metrics and not filtered_kpi.empty:
    st.plotly_chart(kpi_multi_line(filtered_kpi, y_metrics, chart_style),
                    use_container_width=True)
else:
    st.markdown(
        '<div style="color:#556680; text-align:center; padding:40px 0;">Select at least one metric.</div>',
        unsafe_allow_html=True,
    )

# ── AI Storytelling panel ──────────────────────────────────────────────────────
st.markdown(section_header("AI Weekly Briefing"), unsafe_allow_html=True)

if not kpi_df.empty:
    week_options = kpi_df["week_start"].dt.strftime("%Y-%m-%d").tolist()
    default_week = week_options[-2] if len(week_options) >= 2 else week_options[-1]

    selected_week = st.select_slider(
        "Select a week to get AI analysis",
        options=week_options,
        value=default_week,
        key="home_week_selector",
    )

    if st.button("⚡ Generate AI story for this week", key="story_btn"):
        idx      = week_options.index(selected_week)
        prev_idx = max(0, idx - 1)
        w_row    = kpi_df.iloc[idx]
        p_row    = kpi_df.iloc[prev_idx]

        def _v(r, col):
            v = r[col]
            return 0.0 if pd.isna(v) else float(v)

        week_data = dict(week=selected_week,
                         friction_rate=_v(w_row, "weekly_friction_rate"),
                         nps=_v(w_row, "weekly_avg_nps"),
                         escalation=_v(w_row, "weekly_channel_escalation_rate"),
                         resolution=_v(w_row, "weekly_resolution_rate"),
                         duration=_v(w_row, "weekly_avg_episode_duration"))
        prev_data = dict(week=week_options[prev_idx],
                         friction_rate=_v(p_row, "weekly_friction_rate"),
                         nps=_v(p_row, "weekly_avg_nps"),
                         escalation=_v(p_row, "weekly_channel_escalation_rate"),
                         resolution=_v(p_row, "weekly_resolution_rate"),
                         duration=_v(p_row, "weekly_avg_episode_duration"))
        with st.spinner("Analyzing week..."):
            story = generate_week_story(week_data, prev_data, _ENV_PATH)
        st.session_state["home_story"]      = story
        st.session_state["home_story_week"] = selected_week

    if "home_story" in st.session_state:
        story_week = st.session_state.get("home_story_week", "")
        st.markdown(f"""
<div style="background:linear-gradient(135deg,rgba(83,74,183,0.12),rgba(77,166,255,0.08));
            border:1px solid rgba(138,92,246,0.3); border-left:3px solid #8A5CF6;
            border-radius:10px; padding:20px 24px; margin-top:8px;">
  <div style="font-size:10px; letter-spacing:2px; color:#8A5CF6;
              text-transform:uppercase; margin-bottom:10px;">
    ⚡ AI WEEKLY BRIEFING — {story_week}
  </div>
  <div style="font-size:14px; line-height:1.8; color:#C8D8F0; font-style:italic;">
    {st.session_state["home_story"]}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Top 5 hotspot cards + drill buttons ───────────────────────────────────────
st.markdown(section_header("Top 5 Priority Hotspots"), unsafe_allow_html=True)

st.markdown("""
<div style="background:rgba(77,166,255,0.06); border:1px solid rgba(77,166,255,0.2);
            border-left:3px solid #4DA6FF; border-radius:10px; padding:16px 20px; margin-bottom:20px;">
  <div style="font-size:10px; letter-spacing:2px; color:#4DA6FF;
              text-transform:uppercase; margin-bottom:8px;">What are Priority Hotspots?</div>
  <div style="font-size:13px; color:#C8D8F0; line-height:1.7;">
    A <strong style="color:#F0F4FF;">Priority Hotspot</strong> is a specific combination of product,
    region, and channel where customers are experiencing the most difficulty. Each hotspot is ranked
    by a <strong style="color:#F0F4FF;">Priority Score</strong> (0–100) that combines four signals:
    how many channels the customer had to contact, how often issues went unresolved, how negative
    the customer sentiment was, and how long issues took to resolve.
    <strong style="color:#F0A500;">Higher score = more urgent attention needed.</strong>
  </div>
  <div style="font-size:11px; color:#556680; margin-top:8px;">
    💡 Click "Drill into this segment →" on any hotspot to see the specific customers affected.
  </div>
</div>
""", unsafe_allow_html=True)

for i, (_, row) in enumerate(hots.head(5).iterrows()):
    headline, subline = generate_hotspot_headline(row)
    st.markdown(f"""
<div style="margin-bottom:6px;">
  <div style="font-size:13px; font-weight:600; color:#F0F4FF;">{headline}</div>
  <div style="font-size:11px; color:#8899BB; margin-top:3px;">{subline}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown(hotspot_card(row), unsafe_allow_html=True)
    if st.button("Drill into segment →", key=f"drill_{i}"):
        st.session_state["preset_product"] = row["product_involved"]
        st.session_state["preset_region"]  = row["region"]
        st.session_state["preset_channel"] = row["dominant_channel"]
        st.switch_page("pages/5_Segment_Explorer.py")
    st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:12px; font-size:10px; color:#334455; text-align:right;">
    Navigate via the sidebar to explore KPIs, hotspots, LLM insights, journeys, and segment queries.
</div>
""", unsafe_allow_html=True)
