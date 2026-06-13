#!/usr/bin/env python3
"""
ATLAS Phase 1 — Synthetic Data Generation
Generates 5 banking interaction CSVs for analytics pipeline development.

Friction population (15% of customers): appear in 2+ channels within 72 h.
  - 40% of friction customers share the same product across all their channels.
  - NPS skews 0-5 for friction, 6-10 for non-friction.
"""

import os
import uuid
import random
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

# ── Config ─────────────────────────────────────────────────────────────────────
NUM_CUSTOMERS  = 10_000
FRICTION_RATE  = 0.15
SAME_PROD_RATE = 0.40   # within friction population
WINDOW_HOURS   = 72

PRODUCTS = ["checking", "savings", "credit_card", "mortgage", "auto_loan"]
ISSUES   = ["declined_transaction", "balance_inquiry", "fraud_dispute",
            "payment_failed", "account_locked"]
REGIONS  = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
CHANNELS = ["call_center", "branch", "online", "mobile"]

CHANNEL_TARGETS = {
    "call_center": 9_500,
    "branch":      8_200,
    "online":     11_000,
    "mobile":     10_300,
}

END_DATE   = datetime.now().replace(microsecond=0)
START_DATE = END_DATE - timedelta(days=182)

_ROOT      = Path(__file__).resolve().parent   # ATLAS root
OUTPUT_DIR = _ROOT / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Text Pools ─────────────────────────────────────────────────────────────────
CALL_TEMPLATES = [
    "Customer {name} called about {issue} on their {product} account. "
    "A charge of ${amount:.2f} was in dispute. Agent {agent} {outcome}.",

    "Inbound from {name} regarding {product} {issue}. Customer had contacted us "
    "{times} times previously with no resolution. Agent {agent} {outcome}.",

    "{name} from the {region} region reported {issue} persisting for {days} days on "
    "their {product}. Agent {agent} {outcome}.",

    "Fraud concern raised by {name}: {issue} of ${amount:.2f} on {product}. "
    "Identity verification completed. Agent {agent} {outcome}.",

    "{name} requested escalation after unresolved {issue} on {product} account. "
    "Third contact this month. Agent {agent} {outcome}.",
]
CALL_OUTCOMES = [
    "resolved the issue by waiving the applicable fee",
    "escalated the case to the fraud department for review",
    "was unable to resolve on this call and escalated to a supervisor",
    "issued a provisional credit pending formal investigation",
    "confirmed the transaction as legitimate and closed the ticket",
    "scheduled a follow-up branch appointment for in-person resolution",
    "reset account credentials and re-verified customer identity",
]

VISIT_PURPOSES = [
    "account_opening", "dispute_resolution", "loan_inquiry",
    "card_replacement", "wire_transfer", "general_inquiry",
]
BANKER_TEMPLATES = [
    "Customer {name} visited branch for {purpose} on {product} account. {outcome}",
    "{name} presented government-issued ID and requested {purpose} for {product}. {outcome}",
    "Walk-in: {name} raised concern about {issue} affecting {product} account. {outcome}",
    "Scheduled appointment with {name} re: {product} {purpose}. "
    "Customer appeared {sentiment}. {outcome}",
]
BRANCH_OUTCOMES = [
    "Issue resolved in-branch; supporting documents filed.",
    "Referred to dedicated loan officer for further assessment.",
    "Replacement card ordered; estimated 5-7 business days for delivery.",
    "Account notes updated; customer departed satisfied.",
    "Could not resolve at branch level; escalated to back-office team.",
    "Branch manager intervened and offered a one-time courtesy fee waiver.",
]
SENTIMENTS = ["frustrated", "anxious", "calm", "upset", "confused", "relieved"]

PAGE_NAMES = {
    "checking":    ["account-summary", "transfer-funds", "bill-pay", "statement-download"],
    "savings":     ["savings-overview", "interest-calculator", "goal-tracker", "transfer-funds"],
    "credit_card": ["card-activity", "payment-center", "rewards-portal", "dispute-charge"],
    "mortgage":    ["mortgage-dashboard", "payment-schedule", "refinance-calc", "escrow-account"],
    "auto_loan":   ["loan-summary", "payment-portal", "payoff-calculator", "auto-insurance"],
}
FEATURE_NAMES = {
    "checking":    ["mobile-deposit", "balance-check", "push-notifications", "zelle-transfer"],
    "savings":     ["round-up-savings", "goal-tracker", "interest-view", "auto-transfer"],
    "credit_card": ["card-controls", "rewards-redemption", "payment-submit", "fraud-alert"],
    "mortgage":    ["payment-submission", "amortization-view", "document-upload", "rate-lock"],
    "auto_loan":   ["payment-submit", "loan-balance", "autopay-setup", "payoff-request"],
}

MOBILE_TEMPLATES = [
    "App crashed while trying to {action} for my {product}. "
    "This is the {times}th time this week.",
    "Persistent error when I try to {action}. "
    "My {product} payment may now be late because of this.",
    "The {feature} feature is completely broken. I need to {action} urgently.",
    "Cannot access my {product} — app keeps freezing on the {feature} screen.",
    "{action} failed again without explanation. Very frustrated with this app.",
]
MOBILE_ACTIONS = [
    "submit a payment", "check my balance", "transfer funds",
    "view my statement", "set up autopay", "dispute a charge",
]

NPS_FRICTION_TEMPLATES = [
    "I have called {times} times about the same {issue} on my {product} "
    "and it is still not fixed.",
    "Very disappointed. My {product} {issue} has gone unresolved for {days} days.",
    "I was bounced between {times} departments and my problem was never addressed.",
    "I would not recommend this bank after this {issue} experience on my {product}.",
    "Waiting {days} days for a {issue} resolution is completely unacceptable.",
]
NPS_POSITIVE_TEMPLATES = [
    "Very satisfied — my {product} setup was smooth and completed quickly.",
    "The representative resolved my {issue} on the first call. Great service.",
    "Excellent overall experience with {product}. Exactly what I needed.",
    "Smooth process from start to finish. Proactive communication was appreciated.",
    "Outstanding service. I have already recommended this bank to friends and family.",
]

# Probabilities for NPS scores 0-10
NPS_FRICTION_PROBS = [0.12, 0.15, 0.14, 0.13, 0.12, 0.10, 0.08, 0.07, 0.05, 0.03, 0.01]
NPS_POSITIVE_PROBS = [0.01, 0.01, 0.01, 0.02, 0.02, 0.03, 0.08, 0.12, 0.18, 0.22, 0.30]

# CSAT score weights (1-5)
CSAT_FRICTION_W  = [35, 30, 20, 10, 5]
CSAT_POSITIVE_W  = [5,  8,  17, 30, 40]

# ── Helpers ────────────────────────────────────────────────────────────────────
def rand_ts() -> datetime:
    delta = (END_DATE - START_DATE).total_seconds()
    return START_DATE + timedelta(seconds=random.uniform(0, delta))

def fric_ts(anchor: datetime) -> datetime:
    return anchor + timedelta(hours=random.uniform(0, WINDOW_HOURS - 0.01))

def uid() -> str:
    return str(uuid.uuid4())

def fmt(s: str) -> str:
    return s.replace("_", " ")

def call_text(name: str, issue: str, product: str, region: str) -> str:
    return random.choice(CALL_TEMPLATES).format(
        name=name, issue=fmt(issue), product=fmt(product),
        amount=round(random.uniform(20, 4_000), 2),
        agent=fake.first_name(), region=region,
        days=random.randint(1, 30), times=random.randint(2, 7),
        outcome=random.choice(CALL_OUTCOMES),
    )

def branch_text(name: str, purpose: str, product: str, issue: str) -> str:
    return random.choice(BANKER_TEMPLATES).format(
        name=name, purpose=fmt(purpose), product=fmt(product),
        issue=fmt(issue), sentiment=random.choice(SENTIMENTS),
        outcome=random.choice(BRANCH_OUTCOMES),
    )

def mobile_text(product: str) -> str:
    return random.choice(MOBILE_TEMPLATES).format(
        product=fmt(product),
        feature=random.choice(FEATURE_NAMES[product]),
        action=random.choice(MOBILE_ACTIONS),
        times=random.randint(2, 8),
    )

def nps_text(is_friction: bool, issue: str, product: str) -> str:
    if is_friction:
        return random.choice(NPS_FRICTION_TEMPLATES).format(
            times=random.randint(2, 6), issue=fmt(issue),
            product=fmt(product), days=random.randint(3, 45),
        )
    return random.choice(NPS_POSITIVE_TEMPLATES).format(
        issue=fmt(issue), product=fmt(product),
    )

# ── Customer Pool ──────────────────────────────────────────────────────────────
def build_customers() -> pd.DataFrame:
    n_fric = int(NUM_CUSTOMERS * FRICTION_RATE)

    is_fric = [True] * n_fric + [False] * (NUM_CUSTOMERS - n_fric)
    random.shuffle(is_fric)

    fric_idx = [i for i, f in enumerate(is_fric) if f]
    same_prod_set = set(random.sample(fric_idx, int(n_fric * SAME_PROD_RATE)))

    records = []
    for i in range(NUM_CUSTOMERS):
        is_f = is_fric[i]
        records.append({
            "customer_id":       uid(),
            "is_friction":       is_f,
            "same_product":      i in same_prod_set,
            "region":            random.choice(REGIONS),
            "primary_product":   random.choice(PRODUCTS),
            "anchor_ts":         rand_ts() if is_f else None,
            "friction_channels": random.sample(CHANNELS, k=random.randint(2, 3)) if is_f else [],
        })
    return pd.DataFrame(records)

def _prod(cust) -> str:
    """Product for a friction customer: fixed if same_product flag is set, else random."""
    return cust["primary_product"] if cust["same_product"] else random.choice(PRODUCTS)

# ── Channel Generators ─────────────────────────────────────────────────────────
def gen_call_center(customers: pd.DataFrame) -> pd.DataFrame:
    rows = []

    fric = customers[customers["friction_channels"].apply(lambda x: "call_center" in x)]
    for _, c in fric.iterrows():
        prod, issue = _prod(c), random.choice(ISSUES)
        rows.append({
            "customer_id":           c["customer_id"],
            "call_id":               uid(),
            "call_timestamp":        fric_ts(c["anchor_ts"]),
            "call_duration_seconds": random.randint(45, 1_800),
            "ivr_resolution":        random.random() < 0.30,
            "agent_resolution":      random.random() < 0.55,
            "product_involved":      prod,
            "issue_category":        issue,
            "transcript_text":       call_text(fake.name(), issue, prod, c["region"]),
            "region":                c["region"],
        })

    needed = CHANNEL_TARGETS["call_center"] - len(rows)
    fill = customers[~customers["is_friction"]].sample(n=needed, replace=True, random_state=1)
    for _, c in fill.iterrows():
        prod, issue = random.choice(PRODUCTS), random.choice(ISSUES)
        rows.append({
            "customer_id":           c["customer_id"],
            "call_id":               uid(),
            "call_timestamp":        rand_ts(),
            "call_duration_seconds": random.randint(45, 1_800),
            "ivr_resolution":        random.random() < 0.40,
            "agent_resolution":      random.random() < 0.70,
            "product_involved":      prod,
            "issue_category":        issue,
            "transcript_text":       call_text(fake.name(), issue, prod, c["region"]),
            "region":                c["region"],
        })

    df = pd.DataFrame(rows)
    df["call_timestamp"] = pd.to_datetime(df["call_timestamp"])
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def gen_branch_visits(customers: pd.DataFrame) -> pd.DataFrame:
    rows = []

    fric = customers[customers["friction_channels"].apply(lambda x: "branch" in x)]
    for _, c in fric.iterrows():
        prod, issue = _prod(c), random.choice(ISSUES)
        purpose = random.choice(VISIT_PURPOSES)
        rows.append({
            "customer_id":    c["customer_id"],
            "visit_id":       uid(),
            "visit_timestamp": fric_ts(c["anchor_ts"]),
            "branch_id":      f"BR-{random.randint(1000, 9999)}",
            "visit_purpose":  purpose,
            "product_involved": prod,
            "resolved_flag":  random.random() < 0.55,
            "banker_notes":   branch_text(fake.name(), purpose, prod, issue),
            "region":         c["region"],
        })

    needed = CHANNEL_TARGETS["branch"] - len(rows)
    fill = customers[~customers["is_friction"]].sample(n=needed, replace=True, random_state=2)
    for _, c in fill.iterrows():
        prod, issue = random.choice(PRODUCTS), random.choice(ISSUES)
        purpose = random.choice(VISIT_PURPOSES)
        rows.append({
            "customer_id":    c["customer_id"],
            "visit_id":       uid(),
            "visit_timestamp": rand_ts(),
            "branch_id":      f"BR-{random.randint(1000, 9999)}",
            "visit_purpose":  purpose,
            "product_involved": prod,
            "resolved_flag":  random.random() < 0.75,
            "banker_notes":   branch_text(fake.name(), purpose, prod, issue),
            "region":         c["region"],
        })

    df = pd.DataFrame(rows)
    df["visit_timestamp"] = pd.to_datetime(df["visit_timestamp"])
    return df.sample(frac=1, random_state=43).reset_index(drop=True)


def gen_online_events(customers: pd.DataFrame) -> pd.DataFrame:
    EVENT_TYPES = ["page_view", "error_page", "form_abandon", "chat_initiated", "logout_frustration"]
    rows = []

    fric = customers[customers["friction_channels"].apply(lambda x: "online" in x)]
    for _, c in fric.iterrows():
        prod  = _prod(c)
        etype = random.choice(EVENT_TYPES)
        rows.append({
            "customer_id":    c["customer_id"],
            "session_id":     uid(),
            "event_timestamp": fric_ts(c["anchor_ts"]),
            "event_type":     etype,
            "page_name":      random.choice(PAGE_NAMES[prod]),
            "product_involved": prod,
            "session_resolved": random.random() < 0.35,
            "region":         c["region"],
        })

    needed = CHANNEL_TARGETS["online"] - len(rows)
    fill = customers[~customers["is_friction"]].sample(n=needed, replace=True, random_state=3)
    for _, c in fill.iterrows():
        prod  = random.choice(PRODUCTS)
        etype = random.choice(EVENT_TYPES)
        rows.append({
            "customer_id":    c["customer_id"],
            "session_id":     uid(),
            "event_timestamp": rand_ts(),
            "event_type":     etype,
            "page_name":      random.choice(PAGE_NAMES[prod]),
            "product_involved": prod,
            "session_resolved": random.random() < 0.65,
            "region":         c["region"],
        })

    df = pd.DataFrame(rows)
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    return df.sample(frac=1, random_state=44).reset_index(drop=True)


def gen_mobile_events(customers: pd.DataFrame) -> pd.DataFrame:
    EVENT_TYPES = ["app_crash", "feature_error", "in_app_feedback", "chat_initiated", "force_close"]
    rows = []

    fric = customers[customers["friction_channels"].apply(lambda x: "mobile" in x)]
    for _, c in fric.iterrows():
        prod  = _prod(c)
        etype = random.choice(EVENT_TYPES)
        rows.append({
            "customer_id":    c["customer_id"],
            "event_id":       uid(),
            "event_timestamp": fric_ts(c["anchor_ts"]),
            "event_type":     etype,
            "feature_name":   random.choice(FEATURE_NAMES[prod]),
            "product_involved": prod,
            "feedback_text":  mobile_text(prod),
            "resolved_flag":  random.random() < 0.40,
            "region":         c["region"],
        })

    needed = CHANNEL_TARGETS["mobile"] - len(rows)
    fill = customers[~customers["is_friction"]].sample(n=needed, replace=True, random_state=4)
    for _, c in fill.iterrows():
        prod  = random.choice(PRODUCTS)
        etype = random.choice(EVENT_TYPES)
        rows.append({
            "customer_id":    c["customer_id"],
            "event_id":       uid(),
            "event_timestamp": rand_ts(),
            "event_type":     etype,
            "feature_name":   random.choice(FEATURE_NAMES[prod]),
            "product_involved": prod,
            "feedback_text":  mobile_text(prod),
            "resolved_flag":  random.random() < 0.62,
            "region":         c["region"],
        })

    df = pd.DataFrame(rows)
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    return df.sample(frac=1, random_state=45).reset_index(drop=True)


def gen_nps_surveys(customers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, c in customers.iterrows():
        is_f  = c["is_friction"]
        prod  = c["primary_product"]
        issue = random.choice(ISSUES)
        score = int(np.random.choice(11, p=NPS_FRICTION_PROBS if is_f else NPS_POSITIVE_PROBS))
        csat  = random.choices([1, 2, 3, 4, 5],
                               weights=CSAT_FRICTION_W if is_f else CSAT_POSITIVE_W)[0]
        ch_last = (random.choice(c["friction_channels"]) if is_f else random.choice(CHANNELS))

        if is_f:
            survey_ts = min(
                c["anchor_ts"] + timedelta(hours=random.uniform(72, 168)),
                END_DATE,
            )
        else:
            survey_ts = rand_ts()

        rows.append({
            "customer_id":           c["customer_id"],
            "survey_id":             uid(),
            "survey_timestamp":      survey_ts,
            "nps_score":             score,
            "csat_score":            csat,
            "open_response":         nps_text(is_f, issue, prod),
            "product_involved":      prod,
            "channel_of_last_contact": ch_last,
            "region":                c["region"],
        })

    df = pd.DataFrame(rows)
    df["survey_timestamp"] = pd.to_datetime(df["survey_timestamp"])
    return df

# ── Verification ───────────────────────────────────────────────────────────────
def verify(customers: pd.DataFrame, dfs: dict) -> None:
    chan_dfs = {k: v for k, v in dfs.items() if k != "nps_surveys"}
    ts_col   = {
        "call_center_logs": "call_timestamp",
        "branch_visits":    "visit_timestamp",
        "online_events":    "event_timestamp",
        "mobile_events":    "event_timestamp",
    }

    id_sets = {ch: set(df["customer_id"]) for ch, df in chan_dfs.items()}
    fric_ids = set(customers.loc[customers["is_friction"], "customer_id"])
    multi_ch = {cid for cid in fric_ids if sum(cid in s for s in id_sets.values()) >= 2}

    same_prod_ids = set(customers.loc[customers["same_product"], "customer_id"])

    nps = dfs["nps_surveys"].merge(customers[["customer_id", "is_friction"]], on="customer_id")
    fric_nps    = nps.loc[nps["is_friction"],  "nps_score"].mean()
    nonfric_nps = nps.loc[~nps["is_friction"], "nps_score"].mean()

    print("\n=== Row Counts " + "=" * 63)
    for name, df in dfs.items():
        print(f"  {name:<22} {len(df):>7,} rows")

    print(f"\n=== Friction Verification " + "=" * 53)
    print(f"  Total customers:           {NUM_CUSTOMERS:,}")
    print(f"  Flagged friction:          {len(fric_ids):,}  ({len(fric_ids)/NUM_CUSTOMERS:.1%})")
    print(f"  Multi-channel (>=2 chans): {len(multi_ch):,}  ({len(multi_ch)/NUM_CUSTOMERS:.1%})")
    print(f"  Same-product cross-chan:   {len(same_prod_ids):,}  "
          f"({len(same_prod_ids)/len(fric_ids):.1%} of friction)")

    print(f"\n=== NPS Distributions " + "=" * 57)
    print(f"  Friction avg NPS:     {fric_nps:.2f}  (target range 0-5)")
    print(f"  Non-friction avg NPS: {nonfric_nps:.2f}  (target range 6-10)")

    print(f"\n=== Sample Friction Customers (cross-channel timestamps) " + "=" * 22)
    for cid in sorted(multi_ch)[:5]:
        print(f"\n  {cid}")
        for ch, df in chan_dfs.items():
            hit = df[df["customer_id"] == cid]
            if not hit.empty:
                ts   = hit[ts_col[ch]].iloc[0]
                prod = hit["product_involved"].iloc[0]
                print(f"    {ch:<14}  {ts}   product={prod}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("ATLAS Phase 1 — Synthetic Data Generation")
    print(f"  Date range : {START_DATE.date()} to {END_DATE.date()}")
    print(f"  Customers  : {NUM_CUSTOMERS:,}")
    print(f"  Friction   : {FRICTION_RATE:.0%}  |  Same-product subset: {SAME_PROD_RATE:.0%}\n")

    customers = build_customers()

    dfs = {
        "call_center_logs": gen_call_center(customers),
        "branch_visits":    gen_branch_visits(customers),
        "online_events":    gen_online_events(customers),
        "mobile_events":    gen_mobile_events(customers),
        "nps_surveys":      gen_nps_surveys(customers),
    }

    print("Writing to data/raw/")
    for name, df in dfs.items():
        path = OUTPUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  {path}")

    verify(customers, dfs)
    print("\nDone.")


if __name__ == "__main__":
    main()
