"""
ATLAS — Friction Hotspots
75 segments ranked by priority score
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st
from utils.atlas_style import (
    inject_css, live_badge, atlas_page_header, section_header,
    hotspot_card, generate_hotspot_headline, render_sidebar_guide,
)
from utils.db import get_friction_hotspots
from utils.charts import priority_bar

st.set_page_config(page_title="ATLAS — Friction Hotspots", page_icon="🔥",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()
st.markdown(live_badge(), unsafe_allow_html=True)
render_sidebar_guide()
st.markdown("""
<div style="margin-bottom:12px;">
  <a href="/" target="_self" style="
    display:inline-flex; align-items:center; gap:6px;
    font-size:12px; color:#4DA6FF; text-decoration:none;
    padding:5px 12px; border:1px solid rgba(77,166,255,0.3);
    border-radius:6px; background:rgba(77,166,255,0.05);
  ">&larr; Back to Executive Dashboard</a>
</div>
""", unsafe_allow_html=True)
atlas_page_header("Friction Hotspots", "Ranked by priority score across 75 segments")

hots = get_friction_hotspots()

# ── What are priority hotspots? ────────────────────────────────────────────────
st.markdown("""
<div style="background:rgba(77,166,255,0.06); border:1px solid rgba(77,166,255,0.2);
            border-left:3px solid #4DA6FF; border-radius:10px; padding:18px 22px; margin-bottom:24px;">
  <div style="font-size:10px; letter-spacing:2px; color:#4DA6FF;
              text-transform:uppercase; margin-bottom:10px; font-weight:700;">
    What are Priority Hotspots?
  </div>
  <div style="font-size:13px; color:#C8D8F0; line-height:1.8;">
    A <strong style="color:#F0F4FF;">Priority Hotspot</strong> is a specific combination of
    <strong style="color:#F0F4FF;">product × region × channel</strong> where customers are experiencing
    disproportionately high friction. Each hotspot is scored 0–100 using a weighted formula:
  </div>
  <div style="display:flex; gap:12px; margin-top:14px; flex-wrap:wrap;">
    <div style="background:#0D1526; border-radius:8px; padding:10px 14px; flex:1; min-width:140px;">
      <div style="color:#E05555; font-size:18px; font-weight:800; margin-bottom:2px;">35%</div>
      <div style="color:#F0F4FF; font-size:11px; font-weight:600;">Friction score</div>
      <div style="color:#556680; font-size:10px; margin-top:2px;">How severe are the interactions?</div>
    </div>
    <div style="background:#0D1526; border-radius:8px; padding:10px 14px; flex:1; min-width:140px;">
      <div style="color:#F0A500; font-size:18px; font-weight:800; margin-bottom:2px;">35%</div>
      <div style="color:#F0F4FF; font-size:11px; font-weight:600;">Unresolved rate</div>
      <div style="color:#556680; font-size:10px; margin-top:2px;">How often do issues go unresolved?</div>
    </div>
    <div style="background:#0D1526; border-radius:8px; padding:10px 14px; flex:1; min-width:140px;">
      <div style="color:#AFA9EC; font-size:18px; font-weight:800; margin-bottom:2px;">20%</div>
      <div style="color:#F0F4FF; font-size:11px; font-weight:600;">Customer sentiment</div>
      <div style="color:#556680; font-size:10px; margin-top:2px;">How frustrated do customers sound?</div>
    </div>
    <div style="background:#0D1526; border-radius:8px; padding:10px 14px; flex:1; min-width:140px;">
      <div style="color:#4DA6FF; font-size:18px; font-weight:800; margin-bottom:2px;">10%</div>
      <div style="color:#F0F4FF; font-size:11px; font-weight:600;">Episode duration</div>
      <div style="color:#556680; font-size:10px; margin-top:2px;">How long do problems take to close?</div>
    </div>
  </div>
  <div style="font-size:11px; color:#556680; margin-top:12px;">
    🔴 Score ≥ 65 = Critical &nbsp; 🟡 Score 45–64 = Elevated &nbsp; 🔵 Score &lt; 45 = Monitor
  </div>
</div>
""", unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────────────
st.markdown(section_header("Filters", margin_top="4px"), unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)

with fc1:
    products = ["All"] + sorted(hots["product_involved"].unique().tolist())
    sel_product = st.selectbox("Product", products)
with fc2:
    regions = ["All"] + sorted(hots["region"].unique().tolist())
    sel_region = st.selectbox("Region", regions)
with fc3:
    channels = ["All"] + sorted(hots["dominant_channel"].unique().tolist())
    sel_channel = st.selectbox("Channel", channels)
with fc4:
    min_score = st.slider("Min Priority Score", 0, 80, 0, step=5)

filtered = hots.copy()
if sel_product != "All":
    filtered = filtered[filtered["product_involved"] == sel_product]
if sel_region != "All":
    filtered = filtered[filtered["region"] == sel_region]
if sel_channel != "All":
    filtered = filtered[filtered["dominant_channel"] == sel_channel]
filtered = filtered[filtered["priority_score"] >= min_score]

st.markdown(f"""
<div style="font-size:11px; color:#556680; margin-bottom:12px;">
    Showing <strong style="color:#F0F4FF;">{len(filtered)}</strong> of 75 segments
</div>
""", unsafe_allow_html=True)

# ── Priority bar chart ─────────────────────────────────────────────────────────
st.markdown(section_header("Priority Score Chart"), unsafe_allow_html=True)
st.plotly_chart(priority_bar(filtered, top_n=min(20, len(filtered))),
                use_container_width=True)

with st.expander("📖 How is the Priority Score calculated?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
The priority score normalises each component to a 0–100 scale within the set of 75 hotspot segments,
then applies the weighted formula: <strong style="color:#F0F4FF;">0.35 × friction + 0.35 × unresolved
+ 0.20 × (1 − sentiment_norm) + 0.10 × duration</strong>.<br><br>
Because all components are normalised to the same scale before weighting, a segment that is
slightly bad on all four dimensions can outscore one that is extreme on a single dimension.
This design avoids the "one bad metric" false-alarm problem.
</div>
""", unsafe_allow_html=True)

# ── Segment cards ──────────────────────────────────────────────────────────────
tab_cards, tab_table = st.tabs(["Segment Cards", "Data Table"])

with tab_cards:
    st.markdown(section_header("All Segments (ranked by priority)", margin_top="8px"),
                unsafe_allow_html=True)

    if filtered.empty:
        st.markdown(
            '<div style="color:#556680; text-align:center; padding:32px;">No segments match these filters.</div>',
            unsafe_allow_html=True,
        )
    else:
        for _, row in filtered.head(30).iterrows():
            # Plain-English headline above the card
            headline, subline = generate_hotspot_headline(row)
            st.markdown(f"""
<div style="margin-bottom:6px;">
  <div style="font-size:13px; font-weight:600; color:#F0F4FF;">{headline}</div>
  <div style="font-size:11px; color:#8899BB; margin-top:3px;">{subline}</div>
</div>
""", unsafe_allow_html=True)

            # Hotspot card
            st.markdown(hotspot_card(row), unsafe_allow_html=True)

            # "Why this combination?" context panel
            product = str(row["product_involved"]).replace("_", " ").title()
            channel = str(row["dominant_channel"]).title()
            region  = str(row["region"])
            unres   = float(row["unresolved_rate"]) if not pd.isna(row["unresolved_rate"]) else 0.0
            aff_raw = row.get("affected_customers")
            affected = int(aff_raw) if aff_raw is not None and not pd.isna(aff_raw) else 0
            score    = float(row["priority_score"])
            theme_raw = row.get("top_theme", "")
            top_theme = str(theme_raw).replace("_", " ") if theme_raw and not pd.isna(theme_raw) else "unknown"
            dur_raw = row.get("avg_episode_duration")
            duration = float(dur_raw) if dur_raw is not None and not pd.isna(dur_raw) else 0.0

            why_body = (
                f"<strong style='color:#F0F4FF;'>{product}</strong> customers in "
                f"<strong style='color:#F0F4FF;'>{region}</strong> who contact the bank via "
                f"<strong style='color:#F0F4FF;'>{channel}</strong> show "
                f"<strong style='color:#F0A500;'>{unres * 100:.0f}% unresolved issues</strong> — "
                f"meaning most of them had to contact the bank again, or never got their problem fixed. "
                f"This segment affects <strong style='color:#F0F4FF;'>{affected:,} customers</strong> with "
                f"an average episode lasting <strong style='color:#F0F4FF;'>{duration:.1f} hours</strong>. "
                f"The dominant complaint theme is <em style='color:#AFA9EC;'>{top_theme}</em>. "
            )
            if score >= 65:
                why_body += (
                    "The priority score of <strong style='color:#E05555;'>"
                    f"{score:.0f}/100</strong> puts this in the <strong style='color:#E05555;'>Critical</strong> tier — "
                    "immediate operational attention is warranted."
                )
            elif score >= 45:
                why_body += (
                    "The priority score of <strong style='color:#F0A500;'>"
                    f"{score:.0f}/100</strong> puts this in the <strong style='color:#F0A500;'>Elevated</strong> tier — "
                    "flag for operations review within the next sprint."
                )
            else:
                why_body += (
                    "The priority score of <strong style='color:#4DA6FF;'>"
                    f"{score:.0f}/100</strong> puts this in the <strong style='color:#4DA6FF;'>Monitor</strong> tier — "
                    "watch for deterioration over the coming weeks."
                )

            st.markdown(f"""
<div style="background:rgba(138,92,246,0.06); border:1px solid rgba(138,92,246,0.2);
            border-left:3px solid #8A5CF6; border-radius:8px;
            padding:14px 18px; margin-top:4px; margin-bottom:24px;">
  <div style="font-size:10px; letter-spacing:1.5px; color:#8A5CF6;
              text-transform:uppercase; margin-bottom:8px; font-weight:700;">
    Why does this combination matter?
  </div>
  <div style="font-size:12px; color:#C8D8F0; line-height:1.7;">{why_body}</div>
</div>
""", unsafe_allow_html=True)

    if len(filtered) > 30:
        st.markdown(f"""
<div style="color:#556680; font-size:11px; text-align:center; margin-top:8px;">
    Showing top 30 of {len(filtered)} — apply filters or use the Data Table tab for full results
</div>
""", unsafe_allow_html=True)

with tab_table:
    display_cols = ["product_involved", "region", "dominant_channel",
                    "priority_score", "avg_friction_score", "unresolved_rate",
                    "affected_customers", "avg_sentiment", "avg_episode_duration", "top_theme"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(
        filtered[available].rename(columns={
            "product_involved":  "Product",
            "dominant_channel":  "Channel",
            "priority_score":    "Priority",
            "avg_friction_score":"Friction Score",
            "unresolved_rate":   "Unresolved %",
            "affected_customers":"Customers",
            "avg_sentiment":     "Sentiment",
            "avg_episode_duration": "Avg Duration (h)",
            "top_theme":         "Top Theme",
        }).style.format({
            "Priority":       "{:.1f}",
            "Friction Score": "{:.1f}",
            "Unresolved %":   "{:.0%}",
            "Sentiment":      "{:.3f}",
            "Avg Duration (h)": "{:.1f}",
        }),
        use_container_width=True, hide_index=True,
    )
