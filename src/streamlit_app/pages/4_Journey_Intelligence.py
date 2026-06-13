"""
ATLAS — Journey Intelligence
Episode stats, channel sequences, region breakdown
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP_DIR))

import streamlit as st
from utils.atlas_style import (
    inject_css, live_badge, atlas_page_header, section_header,
    channel_pills, render_sidebar_guide,
)
from utils.db import (
    get_customer_journeys, get_journey_stats,
    get_top_sequences, get_friction_by_region,
)
from utils.charts import (
    friction_vs_duration_scatter, sequence_bar, friction_by_region_bar,
)

st.set_page_config(page_title="ATLAS — Journey Intelligence", page_icon="🗺️",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()
st.markdown(live_badge(), unsafe_allow_html=True)
render_sidebar_guide()
atlas_page_header("Journey Intelligence", "Customer movement across channels")

stats = get_journey_stats()
seqs  = get_top_sequences()
regs  = get_friction_by_region()

# ── Top-level metrics ──────────────────────────────────────────────────────────
st.markdown(section_header("Episode Overview", margin_top="4px"), unsafe_allow_html=True)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Episodes", f"{int(stats['total_episodes']):,}")
m2.metric("Friction Episodes", f"{int(stats['friction_episodes']):,}")
m3.metric("Friction Rate", f"{stats['friction_episodes']/stats['total_episodes']*100:.1f}%")
m4.metric("Avg Friction Duration", f"{stats['avg_friction_duration']:.1f}h")
m5.metric("Unique Customers", f"{int(stats['unique_customers']):,}")

with st.expander("📖 How are customer episodes defined?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
An <strong style="color:#F0F4FF;">episode</strong> is a single continuous service interaction
grouped by customer and time. Two contacts from the same customer are merged into one episode if
they occur within a <strong style="color:#F0F4FF;">72-hour gap</strong> of each other. If the gap
exceeds 72 hours, a new episode begins.<br><br>
<strong style="color:#F0F4FF;">An episode is flagged as "friction" if at least one of these four rules fires:</strong>
<ul style="margin:8px 0 8px 16px; padding:0; line-height:2.0;">
  <li>The customer contacted the bank through more than one channel (multi-channel escalation)</li>
  <li>The episode was open for more than 48 hours without resolution (unresolved timeout)</li>
  <li>The customer made 3 or more contacts in a single episode (high frequency)</li>
  <li>The customer's NPS survey response was below the threshold (negative NPS)</li>
</ul>
The episode window logic uses vectorized pandas <code style="color:#AFA9EC; background:#0D1526;
padding:1px 4px; border-radius:3px;">shift + cumsum</code> over sorted customer contact timestamps
to efficiently assign episode IDs at scale across 37,296 rows.
</div>
""", unsafe_allow_html=True)

# ── Region breakdown ───────────────────────────────────────────────────────────
st.markdown(section_header("Friction by Region"), unsafe_allow_html=True)
rc1, rc2 = st.columns([2, 1])
with rc1:
    st.plotly_chart(friction_by_region_bar(regs), use_container_width=True)
with rc2:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    for _, row in regs.iterrows():
        rate  = float(row["friction_rate"])
        color = "#E05555" if rate > 0.025 else "#F0A500" if rate > 0.02 else "#4DA6FF"
        st.markdown(f"""
        <div style="
            background:#0D1526; border:1px solid rgba(77,166,255,0.10);
            border-radius:6px; padding:10px 14px; margin-bottom:6px;
            display:flex; justify-content:space-between; align-items:center;
        ">
            <span style="color:#F0F4FF; font-size:12px; font-weight:600;">{row['region']}</span>
            <div style="text-align:right;">
                <div style="color:{color}; font-weight:700; font-size:13px;">{rate*100:.2f}%</div>
                <div style="color:#556680; font-size:10px;">{int(row['friction_episodes'])} friction</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── Channel sequences ──────────────────────────────────────────────────────────
st.markdown(section_header("Top Channel Sequences by Friction Rate"), unsafe_allow_html=True)
sc1, sc2 = st.columns([3, 2])
with sc1:
    st.plotly_chart(sequence_bar(seqs), use_container_width=True)
with sc2:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    for _, row in seqs.head(8).iterrows():
        rate = float(row["friction_rate"])
        st.markdown(f"""
        <div style="
            background:#0D1526; border:1px solid rgba(77,166,255,0.10);
            border-radius:6px; padding:9px 12px; margin-bottom:5px;
            display:flex; justify-content:space-between; align-items:center;
        ">
            <div>{channel_pills(str(row['channel_sequence']))}</div>
            <div style="text-align:right; flex-shrink:0; margin-left:12px;">
                <span style="color:{'#E05555' if rate>0.5 else '#F0A500' if rate>0.3 else '#4DA6FF'};
                             font-weight:700; font-size:12px;">{rate*100:.1f}%</span>
                <span style="color:#556680; font-size:10px; margin-left:6px;">{int(row['episode_count'])} ep</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

with st.expander("📖 What does a channel sequence like 'online → mobile' mean?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
A <strong style="color:#F0F4FF;">channel sequence</strong> records the order of channels a customer
contacted during a single episode — separated by arrows (→). It captures the customer's journey
from their first contact to their last.<br><br>
<strong style="color:#F0F4FF;">online → mobile</strong> means the customer started by contacting
support through the online portal, then escalated to the mobile app. This is the highest-friction
sequence (66.3% friction rate) because it usually indicates the online portal failed to resolve
the issue and the customer sought a second path.<br><br>
<strong style="color:#F0F4FF;">Why this matters operationally:</strong>
<ul style="margin:8px 0 8px 16px; padding:0; line-height:2.0;">
  <li>High-friction sequences point to <em>channel handoff failures</em> — the first channel didn't resolve the issue</li>
  <li>Sequences with 3+ channels (e.g. online → mobile → call) represent customers who had to try 3 paths before getting help</li>
  <li>Targeting the most common high-friction sequences for process fixes gives the highest ROI on operations spend</li>
</ul>
The sequence strings are built by sorting contacts within an episode by timestamp, then joining the
channel names with <code style="color:#AFA9EC; background:#0D1526; padding:1px 4px;
border-radius:3px;">" → "</code> using a pandas groupby + transform.
</div>
""", unsafe_allow_html=True)

# ── Scatter: friction vs duration ──────────────────────────────────────────────
st.markdown(section_header("Friction Score vs Episode Duration"), unsafe_allow_html=True)
journeys = get_customer_journeys()
st.plotly_chart(friction_vs_duration_scatter(journeys), use_container_width=True)
st.markdown("""
<div style="font-size:10px; color:#334455;">
    Red = friction episode · Blue = non-friction · 1,500-row sample for performance
</div>
""", unsafe_allow_html=True)

# ── Friction rule breakdown ────────────────────────────────────────────────────
st.markdown(section_header("Key Friction Findings"), unsafe_allow_html=True)

findings = [
    ("online → mobile", "66.3%", "Highest friction sequence — customers who start online and escalate to mobile", "#E05555"),
    ("branch → call",   "57.8%", "Second-highest — branch-initiated journeys escalating to call center", "#F0A500"),
    ("mobile → online", "52.8%", "Third — mobile app failures driving customers to online portal", "#F0A500"),
    ("Southeast",       "2.3%",  "Highest friction region across all 5 US regions", "#4DA6FF"),
]
fc1, fc2 = st.columns(2)
for i, (label, value, desc, color) in enumerate(findings):
    col = fc1 if i % 2 == 0 else fc2
    with col:
        st.markdown(f"""
        <div class="atlas-card" style="
            background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-left:3px solid {color}; border-radius:8px;
            padding:14px 16px; margin-bottom:8px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div style="font-size:12px; font-weight:700; color:#F0F4FF;">{label}</div>
                <div style="font-size:20px; font-weight:800; color:{color};">{value}</div>
            </div>
            <div style="font-size:11px; color:#556680; margin-top:4px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
