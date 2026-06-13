"""
ATLAS Phase 4 — Groq Client
Reusable LLM extraction layer. Sends banking interaction text to Groq
and returns structured JSON with theme, sentiment, urgency, and key phrase.

Usage:
    from groq_client import extract_insight
    result = extract_insight(text, event_id="evt-123")
"""

import os
import json
import time
import re
import logging
from pathlib import Path

from groq import Groq, RateLimitError, APIConnectionError, APIStatusError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL       = "llama-3.1-8b-instant"
MAX_RETRIES = 3
MAX_CHARS   = 1_500   # cap text before sending to avoid token waste

VALID_THEMES  = {
    "declined_transaction", "fraud_dispute", "payment_failed",
    "account_locked", "balance_inquiry", "poor_service",
    "wait_time", "app_issue", "other",
}
VALID_URGENCY = {"low", "medium", "high", "critical"}

SYSTEM_PROMPT = """\
You are a banking customer experience analyst.
Analyse the customer interaction text provided by the user and extract key insights.

Return ONLY a valid JSON object — no markdown, no code fences, no explanation.
Exact required structure:
{
  "theme": "<one of: declined_transaction | fraud_dispute | payment_failed | account_locked | balance_inquiry | poor_service | wait_time | app_issue | other>",
  "sentiment_score": <float -1.0 to 1.0>,
  "unresolved_issue": <true or false>,
  "urgency_level": "<one of: low | medium | high | critical>",
  "key_phrase": "<single most important phrase from the text, max 8 words>"
}

Scoring guides:
  sentiment_score : -1.0 = furious / very distressed, 0.0 = neutral, 1.0 = very satisfied
  urgency_level   : low = minor inconvenience, medium = standard friction,
                    high = significant financial impact, critical = fraud / account locked\
"""

# ── Groq client (lazy singleton) ──────────────────────────────────────────────
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


# ── JSON helpers ───────────────────────────────────────────────────────────────
def _parse_json(raw: str) -> dict | None:
    """Strip markdown fences then parse; fall back to regex extraction."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Last resort: pull first {...} block from the string
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _validate(data: dict) -> dict:
    """Coerce / clamp fields into expected types and value ranges."""
    # theme
    if not isinstance(data.get("theme"), str) or data["theme"] not in VALID_THEMES:
        data["theme"] = "other"

    # sentiment_score
    try:
        data["sentiment_score"] = max(-1.0, min(1.0, float(data["sentiment_score"])))
    except (TypeError, ValueError):
        data["sentiment_score"] = 0.0

    # unresolved_issue
    val = data.get("unresolved_issue")
    if isinstance(val, bool):
        pass
    elif isinstance(val, str):
        data["unresolved_issue"] = val.lower() in ("true", "yes", "1")
    else:
        data["unresolved_issue"] = bool(val)

    # urgency_level
    if not isinstance(data.get("urgency_level"), str) or data["urgency_level"] not in VALID_URGENCY:
        data["urgency_level"] = "medium"

    # key_phrase
    if not isinstance(data.get("key_phrase"), str):
        data["key_phrase"] = ""
    else:
        # Trim to 8 words
        words = data["key_phrase"].split()
        data["key_phrase"] = " ".join(words[:8])

    return data


# ── Public API ─────────────────────────────────────────────────────────────────
def extract_insight(text: str, event_id: str = "") -> dict | None:
    """
    Send *text* to Groq and return a validated insight dict, or None on failure.
    Retries up to MAX_RETRIES times on rate-limit errors with exponential backoff.
    """
    truncated = text[:MAX_CHARS]

    for attempt in range(MAX_RETRIES):
        try:
            response = _get_client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": truncated},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300,
            )
            raw = response.choices[0].message.content
            data = _parse_json(raw)

            if data is None:
                log.warning(f"[{event_id}] JSON parse failed — raw: {raw[:120]!r}")
                return None

            data = _validate(data)
            log.info(
                f"[{event_id}] theme={data['theme']:<22} "
                f"sentiment={data['sentiment_score']:+.2f}  "
                f"urgency={data['urgency_level']}"
            )
            return data

        except RateLimitError:
            wait = 2 ** (attempt + 1)   # 2s, 4s, 8s
            log.warning(
                f"[{event_id}] Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Backing off {wait}s..."
            )
            time.sleep(wait)

        except (APIConnectionError, APIStatusError) as e:
            log.error(f"[{event_id}] API error ({type(e).__name__}): {e}")
            return None

        except Exception as e:
            log.error(f"[{event_id}] Unexpected error: {type(e).__name__}: {e}")
            return None

    log.error(f"[{event_id}] Max retries reached — skipping.")
    return None


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = (
        "Customer called about a declined transaction on their credit card. "
        "A charge of $234.50 at a grocery store was blocked without warning. "
        "Customer is frustrated — this is the third occurrence this month. "
        "Agent escalated to the fraud department; issue remains unresolved."
    )

    print(f"Model : {MODEL}")
    print(f"Text  : {sample[:80]}...")
    print()

    result = extract_insight(sample, event_id="TEST-001")

    if result:
        print("\nExtracted insight:")
        print(json.dumps(result, indent=2))
    else:
        print("Extraction failed — check GROQ_API_KEY and model availability.")
