"""
ATLAS Streamlit — AI story generation via Groq.
Each function accepts the env_path so callers at different depths pass the right .env.
"""

from __future__ import annotations
from pathlib import Path


def _safe(v, default=0.0) -> float:
    import math
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def generate_week_story(week_data: dict, prev_data: dict, env_path: Path) -> str:
    """3-sentence executive briefing for a selected KPI week."""
    import os
    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv(dotenv_path=env_path, override=False)
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return "GROQ_API_KEY not found in .env — configure credentials and try again."

    prompt = f"""You are a senior banking analyst presenting weekly data to a C-suite executive.

Week: {week_data['week']}
Friction Rate: {week_data['friction_rate']:.2%} (prev: {prev_data['friction_rate']:.2%})
NPS Score: {week_data['nps']:.1f} (prev: {prev_data['nps']:.1f})
Channel Escalation Rate: {week_data['escalation']:.2%} (prev: {prev_data['escalation']:.2%})
Resolution Rate: {week_data['resolution']:.2%} (prev: {prev_data['resolution']:.2%})
Avg Episode Duration: {week_data['duration']:.1f}h (prev: {prev_data['duration']:.1f}h)

Write a 3-sentence executive briefing for this week's data:
- Sentence 1: What changed most significantly this week vs prior week
- Sentence 2: What this likely means for the business (customer experience impact)
- Sentence 3: One specific recommended action for operations or product teams

Tone: Direct, confident, data-driven. No bullet points. Plain paragraph only.
Maximum 80 words total."""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Story generation failed: {exc}"


def generate_kpi_story(week_data: dict, prev_data: dict,
                       n_alerts: int, env_path: Path) -> str:
    """3-sentence ARIMA/forecast-focused briefing for the KPI Monitor page."""
    import os
    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv(dotenv_path=env_path, override=False)
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return "GROQ_API_KEY not found in .env — configure credentials and try again."

    prompt = f"""You are a quantitative risk analyst reviewing ARIMA-generated KPI forecasts for a bank.

Week: {week_data['week']}
Current friction rate: {week_data['friction_rate']:.2%} | Prior: {prev_data['friction_rate']:.2%}
Current NPS: {week_data['nps']:.1f} | Prior: {prev_data['nps']:.1f}
Escalation rate: {week_data['escalation']:.2%} | Prior: {prev_data['escalation']:.2%}
Resolution rate: {week_data['resolution']:.2%} | Prior: {prev_data['resolution']:.2%}
Active KPI alerts (ARIMA threshold breaches): {n_alerts}

Write a 3-sentence forecast briefing:
- Sentence 1: Which KPI movement this week is most significant for the forecast
- Sentence 2: What the ARIMA alert pattern implies for the next 2-4 weeks
- Sentence 3: One preventive action to avoid forecast deterioration

Tone: Analytical, precise, risk-aware. No bullet points. Plain paragraph only.
Maximum 80 words total."""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Story generation failed: {exc}"


def generate_segment_recommendation(
    product: str,
    region: str,
    channel: str,
    n_customers: int,
    avg_friction: float,
    unresolved_rate: float,
    avg_sentiment: float,
    top_theme: str,
) -> str:
    """3-paragraph operations recommendation for a specific friction segment."""
    import os
    from dotenv import load_dotenv
    from groq import Groq

    _env = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(dotenv_path=_env, override=False)
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return "GROQ_API_KEY not found in .env — configure credentials and try again."

    prompt = f"""You are a senior banking operations analyst.

A data analyst has filtered customer journey data and found this segment:
- Product: {product}
- Region: {region}
- Contact channel: {channel}
- Customers affected: {n_customers}
- Average friction score: {avg_friction:.1f}/100
- Unresolved rate: {unresolved_rate:.0f}%
- Average customer sentiment: {avg_sentiment:.2f} (-1=very negative, +1=very positive)
- Most common issue theme: {top_theme}

Write a specific, actionable recommendation for operations leadership.
Structure your response as exactly 3 short paragraphs:

Paragraph 1 (2 sentences): What this data is telling us about these customers and why it is urgent or not urgent.

Paragraph 2 (2 sentences): The single most impactful action the operations or product team should take in the next 30 days to reduce friction in this segment.

Paragraph 3 (1 sentence): How to measure whether the action worked.

Be specific to the product, region and channel.
No bullet points. No headers. Plain paragraphs only.
Maximum 120 words total."""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Recommendation generation failed: {exc}"
