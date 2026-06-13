"""
ATLAS Streamlit - Shared style utilities.
Inject once per page; call helpers to produce themed HTML fragments.
Pure ASCII source file - no unicode, no emoji, no special chars.
"""

import pandas as pd
import streamlit as st

# --- Global CSS (injected on every page) -------------------------------------
GLOBAL_CSS = """
<style>
/* Hide default Streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}
.stDeployButton {visibility: hidden;}
.stAppToolbar {display: none;}

/* Sidebar toggle must remain visible despite header being hidden */
[data-testid="collapsedControl"] {
    visibility: visible !important;
    opacity: 1 !important;
    display: flex !important;
    background: #0D1526 !important;
    border: 1px solid rgba(77,166,255,0.3) !important;
    border-radius: 0 8px 8px 0 !important;
}
[data-testid="collapsedControl"] button {
    visibility: visible !important;
    opacity: 1 !important;
    color: #4DA6FF !important;
}
[data-testid="collapsedControl"] svg {
    visibility: visible !important;
    fill: #4DA6FF !important;
}

/* Page background */
.stApp { background-color: #0A0F1E; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0D1526;
    border-right: 1px solid rgba(77,166,255,0.12);
}
[data-testid="stSidebar"] .stMarkdown p {
    color: #8899BB;
    font-size: 12px;
}

/* Sidebar nav links */
[data-testid="stSidebarNavLink"] {
    border-radius: 6px;
    border-left: 3px solid transparent;
    padding: 7px 12px;
    margin: 1px 0;
    transition: all 0.2s ease;
}
[data-testid="stSidebarNavLink"]:hover {
    background: rgba(77,166,255,0.06);
    border-left-color: rgba(77,166,255,0.4);
}
[data-testid="stSidebarNavLinkContainer"] [aria-current="page"] {
    background: rgba(77,166,255,0.10) !important;
    border-left: 3px solid #4DA6FF !important;
}
[data-testid="stSidebarNavLink"] p {
    color: #8899BB !important;
    font-size: 13px !important;
}
[data-testid="stSidebarNavLinkContainer"] [aria-current="page"] p {
    color: #F0F4FF !important;
    font-weight: 600 !important;
}

/* All text */
.stMarkdown, .stText, p, span, label { color: #8899BB; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #0D1526;
    border: 1px solid rgba(77,166,255,0.15);
    border-radius: 10px;
    padding: 16px;
}
[data-testid="stMetricValue"] {
    color: #F0F4FF;
    font-size: 28px;
    font-weight: 700;
}
[data-testid="stMetricLabel"] {
    color: #556680;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    background: #0D1526;
    border: 1px solid rgba(77,166,255,0.12);
    border-radius: 8px;
}

/* Buttons */
.stButton > button {
    background: rgba(77,166,255,0.08);
    border: 1px solid rgba(77,166,255,0.3);
    color: #4DA6FF;
    border-radius: 6px;
    font-size: 12px;
    letter-spacing: 0.5px;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: rgba(77,166,255,0.15);
    border-color: #4DA6FF;
}

/* Selectbox / multiselect */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #0D1526;
    border-color: rgba(77,166,255,0.2);
    color: #F0F4FF;
}

/* Slider */
[data-testid="stSlider"] > div { color: #4DA6FF; }

/* Headings */
h1, h2, h3 { color: #F0F4FF !important; font-weight: 600; }

/* Divider */
hr { border-color: rgba(77,166,255,0.1) !important; }

/* Plotly transparent bg */
.js-plotly-plot .plotly, .js-plotly-plot .plotly .bg {
    background: transparent !important;
}

/* Hover card glow */
.atlas-card {
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}
.atlas-card:hover {
    border-color: #4DA6FF !important;
    box-shadow: 0 0 18px rgba(77,166,255,0.12);
}

/* Live badge pulse animation */
@keyframes pulse-live {
    0%   { box-shadow: 0 0 0 0 rgba(93,202,165,0.6); }
    70%  { box-shadow: 0 0 0 7px rgba(93,202,165,0); }
    100% { box-shadow: 0 0 0 0 rgba(93,202,165,0); }
}
@keyframes pulse-amber {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.35; }
}

/* Tab styling */
[data-testid="stTabs"] button {
    color: #8899BB;
    font-size: 12px;
    letter-spacing: 0.5px;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #4DA6FF;
    border-bottom: 2px solid #4DA6FF;
}
</style>
"""

# --- Inject CSS --------------------------------------------------------------
def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# --- Animated live badge -----------------------------------------------------
def live_badge() -> str:
    return """
    <div style="
        position:fixed; top:14px; right:20px; z-index:9999;
        display:flex; align-items:center; gap:7px;
        background:rgba(13,21,38,0.92);
        border:1px solid rgba(77,166,255,0.22);
        border-radius:20px; padding:5px 13px;
        backdrop-filter:blur(10px);
    ">
        <span style="
            width:8px; height:8px; border-radius:50%;
            background:#5DCAA5; display:inline-block;
            animation: pulse-live 2s infinite;
        "></span>
        <span style="color:#5DCAA5; font-size:10px; font-weight:700; letter-spacing:1.8px;">LIVE</span>
    </div>
    """


# --- Section header (uppercase label) ----------------------------------------
def section_header(text: str, margin_top: str = "28px") -> str:
    return f"""
    <div style="
        font-size:10px; font-weight:700; letter-spacing:1.8px;
        text-transform:uppercase; color:#4DA6FF;
        margin-top:{margin_top}; margin-bottom:12px;
        padding-bottom:6px;
        border-bottom:1px solid rgba(77,166,255,0.12);
    ">{text}</div>
    """


# --- KPI card with top-accent stripe -----------------------------------------
def kpi_card(label: str, value: str, delta=None,
             accent: str = "#4DA6FF", lower_is_better: bool = False) -> str:
    delta_html = ""
    if delta is not None:
        is_positive = delta > 0
        is_good = (not lower_is_better and is_positive) or (lower_is_better and not is_positive)
        delta_color = "#5DCAA5" if is_good else "#E05555"
        arrow = "^" if is_positive else "v"
        delta_html = f"""
        <div style="margin-top:6px; font-size:11px; color:{delta_color}; font-weight:600;">
            {arrow} {abs(delta):.4f}
        </div>
        """
    return f"""
    <div class="atlas-card" style="
        background:#0D1526;
        border:1px solid rgba(77,166,255,0.15);
        border-top:2px solid {accent};
        border-radius:10px; padding:18px 20px;
        margin-bottom:4px;
    ">
        <div style="font-size:10px; font-weight:600; letter-spacing:1.4px;
                    text-transform:uppercase; color:#556680; margin-bottom:10px;">
            {label}
        </div>
        <div style="font-size:28px; font-weight:700; color:#F0F4FF; line-height:1.1;">
            {value}
        </div>
        {delta_html}
    </div>
    """


# --- Alert banner (pulsing amber) --------------------------------------------
def alert_banner(n_alerts: int, summary: str = "") -> str:
    return f"""
    <div style="
        background:rgba(240,165,0,0.08);
        border:1px solid rgba(240,165,0,0.4);
        border-radius:8px; padding:12px 18px;
        margin-bottom:20px;
        display:flex; align-items:center; gap:12px;
    ">
        <span style="
            font-size:18px; color:#F0A500;
            animation: pulse-amber 1.5s infinite;
            display:inline-block;
        ">[!]</span>
        <div>
            <div style="color:#F0A500; font-size:12px; font-weight:700; letter-spacing:0.8px;">
                KPI ALERT - {n_alerts} metric(s) outside forecast threshold
            </div>
            {f'<div style="color:#AA7800; font-size:11px; margin-top:3px;">{summary}</div>' if summary else ""}
        </div>
    </div>
    """


# --- Priority score circular badge -------------------------------------------
def priority_badge(score: float) -> str:
    color = "#E05555" if score > 60 else "#F0A500" if score > 40 else "#5DCAA5"
    bg    = "rgba(224,85,85,0.12)" if score > 60 else "rgba(240,165,0,0.12)" if score > 40 else "rgba(93,202,165,0.12)"
    return f"""
    <div style="
        width:54px; height:54px; border-radius:50%;
        border:2.5px solid {color}; background:{bg};
        display:flex; align-items:center; justify-content:center;
        color:{color}; font-size:15px; font-weight:700;
        flex-shrink:0;
    ">{score:.0f}</div>
    """


# --- Friction score inline bar -----------------------------------------------
def friction_bar(score: float, max_score: float = 100) -> str:
    pct  = min(score / max_score * 100, 100)
    color = "#E05555" if score > 65 else "#F0A500" if score > 45 else "#4DA6FF"
    return f"""
    <div style="display:flex; align-items:center; gap:8px;">
        <div style="
            flex:1; height:5px; border-radius:3px;
            background:rgba(77,166,255,0.1); overflow:hidden;
        ">
            <div style="width:{pct:.0f}%; height:100%; background:{color}; border-radius:3px;"></div>
        </div>
        <span style="
            font-size:12px; font-weight:700;
            color:{color}; min-width:32px; text-align:right;
        ">{score:.0f}</span>
    </div>
    """


# --- Sentiment colored value --------------------------------------------------
def sentiment_chip(value) -> str:
    if value is None:
        return '<span style="color:#445566; font-size:12px;">n/a</span>'
    color = "#E05555" if value < -0.3 else "#5DCAA5" if value > 0.3 else "#8899BB"
    sign  = "+" if value >= 0 else ""
    return f'<span style="color:{color}; font-weight:700; font-size:12px;">{sign}{value:.2f}</span>'


# --- Channel sequence connected pills ----------------------------------------
_CHANNEL_COLORS = {
    "call":   ("#4DA6FF", "rgba(77,166,255,0.12)"),
    "branch": ("#5DCAA5", "rgba(93,202,165,0.12)"),
    "online": ("#AFA9EC", "rgba(83,74,183,0.15)"),
    "mobile": ("#F0A500", "rgba(240,165,0,0.12)"),
    "survey": ("#8899BB", "rgba(136,153,187,0.1)"),
}

def channel_pills(sequence: str) -> str:
    channels = [c.strip() for c in sequence.replace("||", " > ").split(">") if c.strip()]
    parts = []
    for i, ch in enumerate(channels[:4]):
        fg, bg = _CHANNEL_COLORS.get(ch.lower(), ("#8899BB", "rgba(136,153,187,0.1)"))
        radius = "4px 0 0 4px" if i == 0 else ("0 4px 4px 0" if i == len(channels)-1 else "0")
        margin = "0 0 0 -1px" if i > 0 else "0"
        parts.append(
            f'<span style="'
            f'background:{bg}; border:1px solid {fg}44; color:{fg};'
            f'font-size:10px; font-weight:600; padding:2px 8px;'
            f'border-radius:{radius}; margin:{margin}; '
            f'white-space:nowrap; display:inline-block;">{ch}</span>'
        )
    if len(channels) > 4:
        parts.append(f'<span style="color:#556680; font-size:10px;"> +{len(channels)-4}</span>')
    return "".join(parts)


# --- Generic themed card wrapper ---------------------------------------------
def card(content: str, padding: str = "18px 20px", extra_style: str = "") -> str:
    return f"""
    <div class="atlas-card" style="
        background:#0D1526;
        border:1px solid rgba(77,166,255,0.15);
        border-radius:10px; padding:{padding};
        {extra_style}
    ">{content}</div>
    """


# --- Hotspot card (full card for one segment) ---------------------------------
def hotspot_card(row) -> str:
    score    = float(row["priority_score"])
    fr_score = float(row["avg_friction_score"])
    unres    = float(row["unresolved_rate"])

    _theme_raw = row["top_theme"]
    theme = str(_theme_raw) if not pd.isna(_theme_raw) else "-"

    _sent_raw = row["avg_sentiment"]
    sent  = float(_sent_raw) if not pd.isna(_sent_raw) else None

    _cust_raw = row["affected_customers"]
    n_cust = int(_cust_raw) if not pd.isna(_cust_raw) else 0

    badge = priority_badge(score)
    bar   = friction_bar(fr_score)
    schip = sentiment_chip(sent)
    pills = channel_pills(str(row["dominant_channel"]))

    unres_color = "#E05555" if unres > 0.7 else "#F0A500" if unres > 0.4 else "#5DCAA5"
    product_label = str(row["product_involved"]).replace("_", " ").title()

    return (
        '<div class="atlas-card" style="'
        "background:#0D1526;"
        "border:1px solid rgba(77,166,255,0.15);"
        "border-radius:10px; padding:16px 18px;"
        'margin-bottom:10px; display:flex; gap:16px; align-items:flex-start;">'
        + badge
        + '<div style="flex:1; min-width:0;">'
        '<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px; flex-wrap:wrap;">'
        f'<span style="color:#F0F4FF; font-weight:700; font-size:14px;">{product_label}</span>'
        f'<span style="color:#4DA6FF; font-size:12px;"> - {row["region"]}</span>'
        + pills
        + "</div>"
        '<div style="margin-bottom:8px;">' + bar + "</div>"
        '<div style="display:flex; gap:16px; flex-wrap:wrap;">'
        '<div><span style="font-size:10px; color:#556680; letter-spacing:1px; text-transform:uppercase;">Customers</span>'
        f'<span style="color:#F0F4FF; font-weight:700; font-size:13px; margin-left:6px;">{n_cust:,}</span></div>'
        '<div><span style="font-size:10px; color:#556680; letter-spacing:1px; text-transform:uppercase;">Unresolved</span>'
        f'<span style="color:{unres_color}; font-weight:700; font-size:13px; margin-left:6px;">{unres*100:.0f}%</span></div>'
        '<div><span style="font-size:10px; color:#556680; letter-spacing:1px; text-transform:uppercase;">Sentiment</span>'
        f'<span style="margin-left:6px;">{schip}</span></div>'
        '<div><span style="font-size:10px; color:#556680; letter-spacing:1px; text-transform:uppercase;">Theme</span>'
        f'<span style="color:#AFA9EC; font-size:11px; margin-left:6px;">{theme}</span></div>'
        "</div></div></div>"
    )


# --- ATLAS hero header (rendered at the top of every page) -------------------
def atlas_hero_header() -> None:
    st.markdown("""
<div style="text-align:center; padding:32px 0 24px; position:relative;">
  <div style="
    font-size:52px; font-weight:800; letter-spacing:6px;
    color:#F0F4FF; text-transform:uppercase;
    position:relative; display:inline-block;
    text-shadow:
      0 0 40px rgba(138,92,246,0.8),
      0 0 80px rgba(138,92,246,0.4),
      0 0 120px rgba(77,166,255,0.3);
    animation: atlas-glow 3s ease-in-out infinite alternate;
  ">ATLAS</div>
  <div style="
    font-size:11px; letter-spacing:4px; color:#4DA6FF;
    text-transform:uppercase; margin-top:6px; opacity:0.8;
  ">Automated Transaction &amp; Lifecycle Analytics System</div>
  <div style="
    width:120px; height:1px;
    background:linear-gradient(90deg, transparent, #8A5CF6, #4DA6FF, transparent);
    margin:16px auto 0;
  "></div>
  <style>
    @keyframes atlas-glow {
      from { text-shadow: 0 0 40px rgba(138,92,246,0.8), 0 0 80px rgba(138,92,246,0.4), 0 0 120px rgba(77,166,255,0.3); }
      to   { text-shadow: 0 0 60px rgba(138,92,246,1.0), 0 0 120px rgba(138,92,246,0.6), 0 0 200px rgba(77,166,255,0.5); }
    }
  </style>
</div>
""", unsafe_allow_html=True)


# --- Sidebar platform stats --------------------------------------------------
def render_sidebar_footer(total_eps: int = 37296, friction_pct: float = 2.2,
                          high_sev: int = 340, llm_events: int = 500) -> None:
    st.sidebar.markdown(f"""
    <div style="margin-top:24px; padding-top:16px; border-top:1px solid rgba(77,166,255,0.1);">
        <div style="font-size:10px; letter-spacing:1.5px; color:#4DA6FF; text-transform:uppercase; margin-bottom:10px;">Platform Stats</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div style="background:rgba(77,166,255,0.05); border-radius:6px; padding:8px; border:1px solid rgba(77,166,255,0.08);">
                <div style="font-size:16px; font-weight:700; color:#F0F4FF;">{total_eps:,}</div>
                <div style="font-size:9px; color:#4DA6FF; letter-spacing:1px; text-transform:uppercase;">Episodes</div>
            </div>
            <div style="background:rgba(240,165,0,0.05); border-radius:6px; padding:8px; border:1px solid rgba(240,165,0,0.1);">
                <div style="font-size:16px; font-weight:700; color:#F0A500;">{friction_pct}%</div>
                <div style="font-size:9px; color:#8899BB; letter-spacing:1px; text-transform:uppercase;">Friction</div>
            </div>
            <div style="background:rgba(224,85,85,0.05); border-radius:6px; padding:8px; border:1px solid rgba(224,85,85,0.1);">
                <div style="font-size:16px; font-weight:700; color:#E05555;">{high_sev}</div>
                <div style="font-size:9px; color:#8899BB; letter-spacing:1px; text-transform:uppercase;">High Sev</div>
            </div>
            <div style="background:rgba(83,74,183,0.05); border-radius:6px; padding:8px; border:1px solid rgba(83,74,183,0.15);">
                <div style="font-size:16px; font-weight:700; color:#AFA9EC;">{llm_events}</div>
                <div style="font-size:9px; color:#8899BB; letter-spacing:1px; text-transform:uppercase;">LLM Events</div>
            </div>
        </div>
        <div style="margin-top:14px; font-size:10px; color:#334455; text-align:center;">
            ATLAS v1.0 - DuckDB - Groq
        </div>
    </div>
    """, unsafe_allow_html=True)


# --- Sidebar quick-guide (call on every page) --------------------------------
def render_sidebar_guide() -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
<div style="font-size:11px; color:#556680; padding:0 8px;">
  <div style="color:#4DA6FF; font-size:10px; letter-spacing:1.5px;
    text-transform:uppercase; margin-bottom:8px;">Quick guide</div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">Home</strong> -
    Overall health of customer experience
  </div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">KPI Monitor</strong> -
    Track trends and get forecasts
  </div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">Friction Hotspots</strong> -
    Where customers struggle most
  </div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">LLM Insights</strong> -
    AI analysis of customer feedback
  </div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">Journey Intelligence</strong> -
    How customers move across channels
  </div>
  <div style="margin-bottom:6px;">
    <strong style="color:#8899BB;">Segment Explorer</strong> -
    Find specific customer groups
  </div>
</div>
""", unsafe_allow_html=True)


# --- Compact page header with ATLAS branding (used on inner pages) -----------
def atlas_page_header(page_title: str, page_subtitle: str = "") -> None:
    sub_html = (
        f'<div style="font-size:11px; color:#556680; margin-top:2px;">{page_subtitle}</div>'
        if page_subtitle else ""
    )
    st.markdown(f"""
<div style="
  display:flex; align-items:center; gap:20px;
  padding:16px 0 24px;
  border-bottom:1px solid rgba(77,166,255,0.1);
  margin-bottom:24px;
">
  <div style="
    font-size:22px; font-weight:800; letter-spacing:3px; color:#F0F4FF;
    text-shadow:0 0 20px rgba(138,92,246,0.6), 0 0 40px rgba(138,92,246,0.3);
  ">ATLAS</div>
  <div style="width:1px; height:32px; background:rgba(77,166,255,0.3);"></div>
  <div>
    <div style="font-size:16px; font-weight:600; color:#F0F4FF;">{page_title}</div>
    {sub_html}
  </div>
</div>
""", unsafe_allow_html=True)


# --- Plain-English hotspot headline ------------------------------------------
def generate_hotspot_headline(row) -> tuple:
    product = str(row.get("product_involved", "")).replace("_", " ").title()
    channel = str(row.get("dominant_channel", "")).title()
    region = str(row.get("region", ""))
    score = float(row.get("priority_score", 0))
    unres = float(row.get("unresolved_rate", 0))
    sentiment = row.get("avg_sentiment", None)

    if score >= 65:
        urgency = "[CRITICAL]"
    elif score >= 45:
        urgency = "[ELEVATED]"
    else:
        urgency = "[MONITOR]"

    unres_pct = f"{unres * 100:.0f}%"
    headline = f"{urgency} {product} customers in {region} via {channel}"
    subline = f"{unres_pct} of issues go unresolved"

    if sentiment is not None:
        try:
            s = float(sentiment)
            if s < -0.5:
                subline += " - customers are very frustrated"
            elif s < -0.2:
                subline += " - customers are moderately frustrated"
        except (ValueError, TypeError):
            pass

    return headline, subline
