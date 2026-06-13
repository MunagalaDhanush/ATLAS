"""
ATLAS — LLM Insights
Theme distribution, channel sentiment, friction vs non-friction comparison
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP_DIR))

import streamlit as st
from utils.atlas_style import (
    inject_css, live_badge, atlas_page_header, section_header,
    sentiment_chip, channel_pills, render_sidebar_guide,
)
from utils.db import get_llm_theme_summary, get_channel_sentiment, get_llm_insights
from utils.charts import (
    theme_sentiment_combo,
    sentiment_channel_bar, unresolved_channel_bar,
)

st.set_page_config(page_title="ATLAS — LLM Insights", page_icon="🧠",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()
st.markdown(live_badge(), unsafe_allow_html=True)
render_sidebar_guide()
atlas_page_header("LLM Insights", "AI analysis of 500 customer interactions via Groq")

with st.expander("📖 How does AI analyze these customer comments?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">Each event in this page was processed by Groq's llama-3.1-8b-instant model</strong>
running a structured extraction prompt. For each customer service interaction, the model was asked to return:
<br><br>
<ul style="margin:0 0 12px 16px; padding:0; line-height:2.0;">
  <li><strong style="color:#F0F4FF;">Theme</strong> — one of 8 predefined categories (e.g. <em>app_issue</em>, <em>payment_dispute</em>, <em>account_access</em>)</li>
  <li><strong style="color:#F0F4FF;">Sentiment score</strong> — a float from −1.0 (very negative) to +1.0 (very positive)</li>
  <li><strong style="color:#F0F4FF;">Urgency level</strong> — high / medium / low based on language cues</li>
  <li><strong style="color:#F0F4FF;">Key phrase</strong> — the most important verbatim phrase from the interaction</li>
  <li><strong style="color:#F0F4FF;">Unresolved issue</strong> — true/false flag based on phrases like "still waiting" or "not fixed"</li>
</ul>
The model was prompted to return valid JSON only. Results were validated and stored in
<code style="color:#AFA9EC; background:#0D1526; padding:1px 5px; border-radius:3px;">analytics.llm_insights</code>.
500 events were processed to keep within API rate limits during the portfolio demo build.
<br><br>
<em style="color:#556680; font-size:12px;">All GROQ_API_KEY credentials are stored in <code>.env</code> — never hardcoded.</em>
</div>
""", unsafe_allow_html=True)

themes   = get_llm_theme_summary()
ch_sent  = get_channel_sentiment()
insights = get_llm_insights()

# ── Theme summary cards ────────────────────────────────────────────────────────
st.markdown(section_header("Theme Overview"), unsafe_allow_html=True)
cols = st.columns(min(4, len(themes)))
for i, (_, row) in enumerate(themes.head(4).iterrows()):
    with cols[i % 4]:
        sent  = float(row["avg_sentiment_score"])
        unres = float(row.get("unresolved_rate", 0))
        count = int(row["event_count"])
        color = "#E05555" if sent < -0.3 else "#5DCAA5" if sent > 0.3 else "#F0A500"
        st.markdown(f"""
        <div class="atlas-card" style="
            background:#0D1526; border:1px solid rgba(77,166,255,0.12);
            border-top:2px solid {color}; border-radius:10px;
            padding:14px 16px; margin-bottom:8px;
        ">
            <div style="font-size:11px; font-weight:700; color:#F0F4FF; text-transform:capitalize; margin-bottom:6px;">
                {row['theme'].replace('_',' ')}
            </div>
            <div style="font-size:22px; font-weight:800; color:#F0F4FF;">{count}</div>
            <div style="font-size:10px; color:#556680; margin-top:4px; letter-spacing:0.5px;">events</div>
            <div style="margin-top:8px; display:flex; justify-content:space-between;">
                <div>
                    <div style="font-size:9px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Sentiment</div>
                    <div style="margin-top:2px;">{sentiment_chip(sent)}</div>
                </div>
                <div>
                    <div style="font-size:9px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Unresolved</div>
                    <div style="font-size:12px; font-weight:700; color:{'#E05555' if unres>0.7 else '#F0A500' if unres>0.3 else '#5DCAA5'}; margin-top:2px;">
                        {unres*100:.0f}%
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with st.expander("📖 What do these theme categories mean?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
The 8 themes were defined before LLM processing to ensure consistency. The model classified
each event into exactly one theme:
<br><br>
<ul style="margin:0 0 8px 16px; padding:0; line-height:2.0;">
  <li><strong style="color:#F0F4FF;">app_issue</strong> — mobile app crashes, login failures, feature bugs</li>
  <li><strong style="color:#F0F4FF;">payment_dispute</strong> — incorrect charges, fraud disputes, payment failures</li>
  <li><strong style="color:#F0F4FF;">account_access</strong> — lockouts, password resets, authentication problems</li>
  <li><strong style="color:#F0F4FF;">loan_inquiry</strong> — questions about mortgage, auto loan, or credit rates</li>
  <li><strong style="color:#F0F4FF;">transfer_issue</strong> — failed or delayed transfers, wire problems</li>
  <li><strong style="color:#F0F4FF;">card_issue</strong> — debit/credit card not working, replacement requests</li>
  <li><strong style="color:#F0F4FF;">statement_error</strong> — incorrect statements, missing transactions</li>
  <li><strong style="color:#F0F4FF;">general_inquiry</strong> — product questions, eligibility, and other topics</li>
</ul>
</div>
""", unsafe_allow_html=True)

# ── Theme + sentiment combo chart ──────────────────────────────────────────────
st.markdown(section_header("Theme Volume & Sentiment"), unsafe_allow_html=True)
st.plotly_chart(theme_sentiment_combo(themes), use_container_width=True)

# ── Channel analysis ───────────────────────────────────────────────────────────
st.markdown(section_header("Channel Analysis"), unsafe_allow_html=True)
cc1, cc2 = st.columns(2)
with cc1:
    st.plotly_chart(sentiment_channel_bar(ch_sent), use_container_width=True)
with cc2:
    st.plotly_chart(unresolved_channel_bar(ch_sent), use_container_width=True)

with st.expander("📖 What does 'unresolved rate by channel' mean?", expanded=False):
    st.markdown("""
<div style="font-size:13px; color:#C8D8F0; line-height:1.8; padding:8px 0;">
<strong style="color:#F0F4FF;">Unresolved rate by channel</strong> is the share of LLM-analyzed events
where the AI flagged the interaction as still having an open issue at the end of the recorded interaction.
The LLM detects phrases like "still waiting", "no one got back to me", "the problem persists", or
"I've called three times" as signals of an unresolved state.<br><br>
<strong style="color:#F0F4FF;">Why channel matters:</strong> A high unresolved rate on mobile
is more alarming than on branch, because mobile customers have fewer escalation paths available —
they can't simply walk into a branch the next day. A mobile unresolved event is more likely to
result in silent churn.
</div>
""", unsafe_allow_html=True)

# ── Mobile alert spotlight ─────────────────────────────────────────────────────
mobile = ch_sent[ch_sent["channel"] == "mobile"]
if not mobile.empty:
    mob_sent  = float(mobile["avg_sentiment"].iloc[0])
    mob_unres = float(mobile["unresolved_rate"].iloc[0])
    st.markdown(section_header("Mobile Channel Spotlight"), unsafe_allow_html=True)
    st.markdown(f"""
    <div style="
        background:rgba(224,85,85,0.05); border:1px solid rgba(224,85,85,0.25);
        border-radius:8px; padding:16px 20px;
    ">
        <div style="font-size:12px; font-weight:700; color:#E05555; letter-spacing:0.8px; margin-bottom:8px;">
            WORST PERFORMING CHANNEL
        </div>
        <div style="display:flex; gap:32px; flex-wrap:wrap;">
            <div>
                <div style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Avg Sentiment</div>
                <div style="font-size:28px; font-weight:800; color:#E05555;">{mob_sent:.3f}</div>
            </div>
            <div>
                <div style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px;">Unresolved Rate</div>
                <div style="font-size:28px; font-weight:800; color:#E05555;">{mob_unres*100:.0f}%</div>
            </div>
            <div style="flex:1; min-width:200px;">
                <div style="font-size:10px; color:#556680; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px;">Key Finding</div>
                <div style="font-size:12px; color:#8899BB; line-height:1.5;">
                    Mobile channel has the lowest sentiment score across all LLM-analysed events
                    and 100% unresolved rate, making it the highest-risk channel for customer churn.
                    The app_issue theme dominates with -0.814 avg sentiment.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Sample LLM events ──────────────────────────────────────────────────────────
st.markdown(section_header("Sample LLM-Extracted Events"), unsafe_allow_html=True)
urgency_filter = st.selectbox("Filter by Urgency", ["All", "high", "medium", "low"])
sample = insights.copy()
if urgency_filter != "All":
    sample = sample[sample["urgency_level"] == urgency_filter]

for _, row in sample.head(8).iterrows():
    urg   = str(row.get("urgency_level", ""))
    theme = str(row.get("theme", ""))
    sent  = float(row.get("sentiment_score", 0)) if str(row.get("sentiment_score", "")) != "nan" else None
    ch    = str(row.get("channel", ""))
    phrase= str(row.get("key_phrase", ""))
    # unresolved_issue = True means NOT resolved
    unresolved_flag = bool(row.get("unresolved_issue", False))
    resolved = not unresolved_flag

    urg_color = "#E05555" if urg == "high" else "#F0A500" if urg == "medium" else "#5DCAA5"

    st.markdown(f"""
    <div class="atlas-card" style="
        background:#0D1526; border:1px solid rgba(77,166,255,0.12);
        border-radius:8px; padding:12px 16px; margin-bottom:6px;
        display:flex; gap:12px; align-items:flex-start;
    ">
        <div style="
            background:{urg_color}18; border:1px solid {urg_color}44;
            color:{urg_color}; font-size:9px; font-weight:700;
            padding:3px 8px; border-radius:4px; letter-spacing:1px;
            text-transform:uppercase; flex-shrink:0; margin-top:2px;
        ">{urg}</div>
        <div style="flex:1; min-width:0;">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px; flex-wrap:wrap;">
                <span style="color:#F0F4FF; font-weight:600; font-size:12px; text-transform:capitalize;">
                    {theme.replace('_',' ')}
                </span>
                {channel_pills(ch)}
                {sentiment_chip(sent)}
                <span style="font-size:10px; color:{'#5DCAA5' if resolved else '#E05555'};">
                    {'✓ Resolved' if resolved else '✗ Unresolved'}
                </span>
            </div>
            <div style="color:#556680; font-size:11px; font-style:italic;">"{phrase}"</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
