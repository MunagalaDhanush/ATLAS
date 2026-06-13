"""
ATLAS — Segment Explorer
Find customers who need help: parameterized queries with drill-in support from Home.
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st

from utils.atlas_style import (
    inject_css, live_badge, atlas_page_header, section_header,
    sentiment_chip, channel_pills, friction_bar, render_sidebar_guide,
)
from utils.db import run_segment_query
from utils.ai import generate_segment_recommendation

st.set_page_config(page_title="ATLAS — Segment Explorer", page_icon="🔍",
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
atlas_page_header("Segment Explorer", "Filter 37,296 journeys by product, region, channel and severity")

# ── Pre-populate widget state from drill-in session_state ─────────────────────
_PRODUCTS = ["(any)", "checking", "savings", "credit_card", "mortgage", "auto_loan"]
_REGIONS  = ["(any)", "Northeast", "Southeast", "Midwest", "Southwest", "West"]
_CHANNELS = ["(any)", "call", "branch", "online", "mobile"]

for preset_key, widget_key, options in [
    ("preset_product", "seg_product", _PRODUCTS),
    ("preset_region",  "seg_region",  _REGIONS),
    ("preset_channel", "seg_channel", _CHANNELS),
]:
    if preset_key in st.session_state and widget_key not in st.session_state:
        val = st.session_state[preset_key]
        if val in options:
            st.session_state[widget_key] = val
        del st.session_state[preset_key]

# ── Filter controls ────────────────────────────────────────────────────────────
st.markdown(section_header("Who are you looking for?", margin_top="4px"), unsafe_allow_html=True)

qc1, qc2, qc3 = st.columns(3)
with qc1:
    product = st.selectbox("Which product?", _PRODUCTS, key="seg_product")
with qc2:
    region = st.selectbox("Which region?", _REGIONS, key="seg_region")
with qc3:
    channel = st.selectbox("Where did they contact us?", _CHANNELS, key="seg_channel")

# Severity radio replacing slider
severity = st.radio(
    "How frustrated are these customers?",
    options=[
        "All customers with friction (any level)",
        "Somewhat frustrated (score ≥ 30)",
        "Very frustrated (score ≥ 50)",
        "Critical — needs immediate action (score ≥ 70)",
    ],
    index=0,
    key="seg_severity",
    horizontal=True,
)

_SEVERITY_MAP = {
    "All customers with friction (any level)":        0,
    "Somewhat frustrated (score ≥ 30)":               30,
    "Very frustrated (score ≥ 50)":                   50,
    "Critical — needs immediate action (score ≥ 70)": 70,
}
threshold = _SEVERITY_MAP[severity]

if threshold > 0:
    st.caption(f"Showing customers with friction score ≥ {threshold} / 100")

# SQL preview
where_parts = ["is_friction_episode = true"]
if product != "(any)":
    where_parts.append(f"product = '{product}'")
if region != "(any)":
    where_parts.append(f"region = '{region}'")
if channel != "(any)":
    where_parts.append(f"channel = '{channel}'")
if threshold > 0:
    where_parts.append(f"friction_score ≥ {threshold}")

st.markdown(f"""
<div style="background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-radius:6px; padding:10px 16px; margin-bottom:16px;
            font-size:11px; color:#556680; font-family:monospace;">
  WHERE {" AND ".join(where_parts)} &nbsp;&nbsp;LIMIT 500
</div>
""", unsafe_allow_html=True)

run = st.button("🔍 Find these customers", type="primary")

if run:
    with st.spinner("Querying DuckDB..."):
        df = run_segment_query(
            product=product if product != "(any)" else None,
            region=region   if region  != "(any)" else None,
            channel=channel if channel != "(any)" else None,
            min_friction_score=float(threshold) if threshold > 0 else None,
        )
    st.session_state["seg_results"] = df

df = st.session_state.get("seg_results")

if df is None:
    st.markdown("""
    <div style="background:rgba(77,166,255,0.04); border:1px solid rgba(77,166,255,0.12);
                border-radius:8px; padding:40px; text-align:center; margin-top:16px;">
        <div style="font-size:13px; color:#556680; margin-bottom:8px;">
            Set your filters above and click <strong style="color:#4DA6FF;">Find these customers</strong>.
        </div>
        <div style="font-size:11px; color:#334455;">
            Results show friction episodes — customers who contacted the bank more than once,
            waited over 48h, or expressed dissatisfaction.
        </div>
    </div>
    """, unsafe_allow_html=True)

elif len(df) == 0:
    sel_str_parts = []
    if product != "(any)": sel_str_parts.append(product.replace("_", " "))
    if region  != "(any)": sel_str_parts.append(region)
    if channel != "(any)": sel_str_parts.append(channel)
    sel_str = " + ".join(sel_str_parts) if sel_str_parts else "all filters"

    st.markdown(f"""
    <div style="background:rgba(93,202,165,0.04); border:1px solid rgba(93,202,165,0.2);
                border-radius:8px; padding:24px; text-align:center; margin-top:16px;">
        <div style="font-size:14px; color:#5DCAA5; font-weight:600; margin-bottom:6px;">
            ✓ No friction customers found
        </div>
        <div style="font-size:12px; color:#556680;">
            No customers matching <strong style="color:#F0F4FF;">{sel_str}</strong>
            with {f"friction score ≥ {threshold}" if threshold > 0 else "any friction level"}
            were found in the dataset. This is a good sign for that segment.
        </div>
    </div>
    """, unsafe_allow_html=True)

else:
    # ── Plain-English results summary ──────────────────────────────────────────
    n_results     = len(df)
    avg_score     = df["friction_score"].mean()
    unres_col     = "eventually_resolved"
    unresolved_n  = int((df[unres_col] == False).sum()) if unres_col in df.columns else 0
    unres_pct     = (unresolved_n / n_results * 100) if n_results > 0 else 0.0
    avg_sent      = df["sentiment_score"].dropna().mean() if "sentiment_score" in df.columns else 0.0
    high_urg      = int((df["urgency_level"] == "high").sum()) if "urgency_level" in df.columns else 0

    severity_label = (
        "critical" if threshold >= 70 else
        "very frustrated" if threshold >= 50 else
        "frustrated" if threshold >= 30 else
        "friction"
    )

    seg_desc_parts = []
    if product != "(any)": seg_desc_parts.append(product.replace("_", " "))
    if region  != "(any)": seg_desc_parts.append(region)
    if channel != "(any)": seg_desc_parts.append(f"via {channel}")
    seg_desc = " · ".join(seg_desc_parts) if seg_desc_parts else "all segments"

    st.markdown(f"""
<div style="background:rgba(77,166,255,0.06); border:1px solid rgba(77,166,255,0.2);
            border-left:3px solid #4DA6FF; border-radius:10px;
            padding:18px 22px; margin-bottom:20px;">
  <div style="font-size:10px; letter-spacing:2px; color:#4DA6FF;
              text-transform:uppercase; margin-bottom:8px; font-weight:700;">
    What the results tell us
  </div>
  <div style="font-size:14px; color:#F0F4FF; font-weight:600; margin-bottom:8px;">
    Found {n_results:,} {severity_label} customers
    {f"— {seg_desc}" if seg_desc_parts else ""}
  </div>
  <div style="font-size:13px; color:#C8D8F0; line-height:1.8;">
    These customers have an average friction score of <strong style="color:#F0A500;">{avg_score:.1f}/100</strong>.
    <strong style="color:#E05555;">{unres_pct:.0f}% ({unresolved_n:,} customers)</strong> left without
    their issue resolved — they are most at risk of churn or repeat contact.
    {"<strong style='color:#E05555;'>" + str(high_urg) + " high-urgency events</strong> suggest immediate intervention is needed." if high_urg > 0 else ""}
    {"Average customer sentiment is <strong style='color:#E05555;'>negative (" + f"{avg_sent:.2f})</strong> — these customers are frustrated." if avg_sent < -0.2 else
    "Average customer sentiment is <strong style='color:#F0A500;'>neutral (" + f"{avg_sent:.2f})</strong>." if avg_sent < 0.2 else
    "Average customer sentiment is <strong style='color:#5DCAA5;'>positive (" + f"{avg_sent:.2f})</strong> despite friction."}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Summary metrics ────────────────────────────────────────────────────────
    st.markdown(section_header("Query Results"), unsafe_allow_html=True)
    sr1, sr2, sr3, sr4 = st.columns(4)
    sr1.metric("Matching Customers", f"{n_results:,}")
    sr2.metric("Avg Friction Score", f"{avg_score:.1f}")
    sr3.metric("Unresolved Rate", f"{unres_pct:.1f}%")
    sr4.metric("Avg Sentiment", f"{avg_sent:.3f}")

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_cards, tab_table = st.tabs(["Customer Cards", "Data Table"])

    with tab_cards:
        for _, row in df.head(20).iterrows():
            fr_score = float(row["friction_score"])
            ch       = str(row.get("dominant_channel", row.get("channel", "")))
            seq      = str(row.get("channel_sequence", ""))
            theme    = str(row.get("theme", "—"))
            _sv      = row.get("sentiment_score")
            sent     = float(_sv) if _sv is not None and not pd.isna(_sv) else None
            resolved = bool(row.get("eventually_resolved", False))
            urg      = str(row.get("urgency_level", ""))

            urg_color = "#E05555" if urg == "high" else "#F0A500" if urg == "medium" else "#5DCAA5"
            pill_seq  = seq if seq and seq != "nan" else ch

            urg_badge = ""
            if urg and urg != "nan":
                urg_badge = (
                    f'<span style="background:{urg_color}18; border:1px solid {urg_color}44;'
                    f' color:{urg_color}; font-size:9px; font-weight:700; padding:2px 7px;'
                    f' border-radius:4px; letter-spacing:1px; text-transform:uppercase;">{urg}</span>'
                )
            res_color = "#5DCAA5" if resolved else "#E05555"
            res_label = "✓ Resolved" if resolved else "✗ Unresolved"
            product_label = str(row.get("product_involved", "")).replace("_", " ").title()

            st.markdown(
                '<div class="atlas-card" style="'
                "background:#0D1526; border:1px solid rgba(77,166,255,0.12);"
                'border-radius:8px; padding:14px 16px; margin-bottom:7px;">'
                '<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">'
                '<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">'
                f'<span style="color:#F0F4FF; font-weight:700; font-size:13px;">{product_label}</span>'
                f'<span style="color:#4DA6FF; font-size:11px;">· {row.get("region","")}</span>'
                + channel_pills(pill_seq)
                + "</div>"
                '<div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">'
                + urg_badge
                + f'<span style="font-size:10px; color:{res_color};">{res_label}</span>'
                "</div></div>"
                '<div style="margin-bottom:8px;">' + friction_bar(fr_score) + "</div>"
                '<div style="display:flex; gap:16px; flex-wrap:wrap;">'
                '<div><span style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Theme</span>'
                f'<span style="color:#AFA9EC; font-size:11px; margin-left:6px; text-transform:capitalize;">{theme.replace("_"," ")}</span></div>'
                '<div><span style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Sentiment</span>'
                f'<span style="margin-left:6px;">{sentiment_chip(sent)}</span></div>'
                '<div><span style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Duration</span>'
                f'<span style="color:#F0F4FF; font-size:11px; font-weight:600; margin-left:6px;">{float(row.get("episode_duration_hours", 0)):.1f}h</span></div>'
                "</div></div>",
                unsafe_allow_html=True,
            )

        if len(df) > 20:
            st.markdown(
                f'<div style="color:#556680; font-size:11px; text-align:center; margin-top:8px;">'
                f"Showing 20 of {len(df)} customers — use the Data Table tab to see all results</div>",
                unsafe_allow_html=True,
            )

    with tab_table:
        display_cols = [
            "customer_id", "product_involved", "region", "dominant_channel",
            "friction_score", "eventually_resolved", "episode_duration_hours",
            "theme", "sentiment_score", "urgency_level",
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].rename(columns={
                "customer_id":            "Customer ID",
                "product_involved":       "Product",
                "dominant_channel":       "Channel",
                "friction_score":         "Friction",
                "eventually_resolved":    "Resolved",
                "episode_duration_hours": "Duration (h)",
                "sentiment_score":        "Sentiment",
                "urgency_level":          "Urgency",
            }).style.format({
                "Friction":    "{:.1f}",
                "Sentiment":   "{:.3f}",
                "Duration (h)":"{:.1f}",
            }),
            use_container_width=True, hide_index=True,
        )
        csv = df[available].to_csv(index=False)
        st.download_button(
            "Download CSV", csv,
            file_name="atlas_segment_query.csv", mime="text/csv",
        )

    # ── AI recommendation panel ────────────────────────────────────────────────
    st.markdown(section_header("AI Operations Recommendation"), unsafe_allow_html=True)
    top_theme_val = (
        df["theme"].mode().iloc[0]
        if "theme" in df.columns and not df["theme"].dropna().empty
        else "unknown"
    )
    avg_sent_val = df["sentiment_score"].dropna().mean() if "sentiment_score" in df.columns else 0.0
    unres_rate_val = (
        (df["eventually_resolved"] == False).sum() / len(df) * 100
        if "eventually_resolved" in df.columns else 0.0
    )
    avg_fr_val = df["friction_score"].mean() if "friction_score" in df.columns else 0.0

    st.markdown(f"""
<div style="background:rgba(138,92,246,0.06); border:1px solid rgba(138,92,246,0.2);
            border-left:3px solid #8A5CF6; border-radius:10px;
            padding:16px 20px; margin-bottom:16px;">
  <div style="font-size:10px; letter-spacing:2px; color:#8A5CF6;
              text-transform:uppercase; margin-bottom:8px; font-weight:700;">
    Segment summary passed to AI
  </div>
  <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:12px; color:#8899BB;">
    <span>Product: <strong style="color:#F0F4FF;">{product.replace("_"," ") if product != "(any)" else "All"}</strong></span>
    <span>Region: <strong style="color:#F0F4FF;">{region if region != "(any)" else "All"}</strong></span>
    <span>Channel: <strong style="color:#F0F4FF;">{channel if channel != "(any)" else "All"}</strong></span>
    <span>Customers: <strong style="color:#F0F4FF;">{n_results:,}</strong></span>
    <span>Avg friction: <strong style="color:#F0A500;">{avg_fr_val:.1f}/100</strong></span>
    <span>Unresolved: <strong style="color:#E05555;">{unres_rate_val:.0f}%</strong></span>
    <span>Top theme: <strong style="color:#AFA9EC;">{str(top_theme_val).replace("_"," ")}</strong></span>
  </div>
</div>
""", unsafe_allow_html=True)

    if st.button("Generate recommendation", key="seg_ai_btn", type="primary"):
        with st.spinner("Generating operations recommendation..."):
            rec = generate_segment_recommendation(
                product=product if product != "(any)" else "all products",
                region=region if region != "(any)" else "all regions",
                channel=channel if channel != "(any)" else "all channels",
                n_customers=n_results,
                avg_friction=avg_fr_val,
                unresolved_rate=unres_rate_val,
                avg_sentiment=avg_sent_val,
                top_theme=str(top_theme_val).replace("_", " "),
            )
        st.session_state["seg_ai_rec"] = rec

    if "seg_ai_rec" in st.session_state:
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
              text-transform:uppercase; margin-bottom:12px;">
    AI Operations Recommendation
  </div>
  <div style="font-size:13px; line-height:1.9; color:#C8D8F0;">
    {st.session_state["seg_ai_rec"].replace(chr(10)+chr(10), '</div><div style="font-size:13px; line-height:1.9; color:#C8D8F0; margin-top:12px;">')}
  </div>
</div>
""", unsafe_allow_html=True)
