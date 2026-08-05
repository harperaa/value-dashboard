"""AI ROI — the transparent 8-step methodology from ai-saves.com/en,
parameterized from the AICVC Roadmap's Company Context.

The 8 steps (quoted from the calculator's own FAQ):
  1) Team cost   = employees x salary x 1.3 (payroll burden)
  2) Hours/month = employees x hours/week x weeks/month
  3) Hourly rate = (1) / (2)
  4) Automated   = (2) x automation %
  5) Gross       = (4) x (3)
  6) Net         = (5) - AI monthly cost
  7) Payback     = implementation cost / net monthly savings
  8) Year-1 ROI  = annual net benefit / (12 x AI monthly + implementation)

x-factor conversion (the user-facing headline): ROI% -> multiple of money
returned per dollar in — 1,900% ROI means every dollar came back as $20,
so x = ROI/100 + 1.

Standard blended rate when no salary is known: analysis $75/hr,
engineering $95/hr, marketing $60/hr -> blend $76.67/hr (typical US
mid-market consulting/employee loaded ranges).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

try:
    from . import store
except ImportError:  # loaded outside package context
    import store  # type: ignore

logger = logging.getLogger(__name__)

PLUGIN_ID = "value-dashboard"

STANDARD_RATES = {"analysis": 75.0, "engineering": 95.0, "marketing": 60.0}
# Token -> labor model (used when measured token counts exist):
# LLM output tokens ~0.75 words each; a human produces polished
# analysis/engineering/marketing work at ~600 words/hour; and only a
# conservative share of generated tokens actually displaces human work
# (drafts, retries, and thinking tokens don't count) — 35%.
WORDS_PER_TOKEN = 0.75
HUMAN_WORDS_PER_HOUR = 600.0
TOKEN_UTILIZATION = 0.35
# Token Economy anchors (meaningfultech.com "The Token Economy — what a
# $100,000 employee really costs"): a fully-burdened $135k knowledge
# worker produces ~1.17M output tokens/yr (7-10M total throughput), which
# prices human output at $25-40 per MILLION tokens once adjusted to the
# 2-4 actually-productive hours per day. We use the range as a displayed
# cross-check on the words-based hours model, and its verification-burden
# finding (~4.3 h/week, >10% of work time) as the default supervision
# deduction — AI output someone must review isn't free labor.
HUMAN_COST_PER_MTOK_LOW = 25.0
HUMAN_COST_PER_MTOK_HIGH = 40.0
DEFAULT_SUPERVISION_PCT = 10.0
BLENDED_RATE = round(sum(STANDARD_RATES.values()) / len(STANDARD_RATES), 2)
PAYROLL_BURDEN = 1.30
# ai-saves.com automation medians by task type
AUTOMATION_SHARES = {"support": 0.65, "content": 0.55,
                     "analytics": 0.50, "search": 0.70}

DEFAULT_PARAMS = {
    "employees": 1,
    # blended rate expressed as a monthly gross salary so step 1's x1.3
    # burden lands back on the blended loaded rate at 160 h/mo:
    # 76.67 x 160 / 1.3 = 9436
    "salaryMonthly": 9436,
    "hoursPerWeek": 20,
    "weeksPerMonth": 4,
    "automationPct": 55,          # content/marketing median — creator work
    "aiMonthlyManualUsd": 0,      # adds to measured provider usage
    "implementationUsd": 0,       # mentees build inside the platform
    "taskLabel": "AI-assisted business building (blended)",
    "hoursBasis": "auto",         # auto | assumptions | tokens
    "supervisionPct": DEFAULT_SUPERVISION_PCT,   # % of automated hours a
    # human spends reviewing AI output (Token Economy: >10% of work time)
    "source": "defaults",
}


def get_params() -> dict:
    saved = store.kv_get("roiParams")
    p = dict(DEFAULT_PARAMS)
    if isinstance(saved, dict):
        p.update({k: saved[k] for k in saved if k in DEFAULT_PARAMS
                  or k in ("derivedNote", "derivedAt")})
    return p


def save_params(updates: dict) -> dict:
    p = get_params()
    for k, v in (updates or {}).items():
        if k in ("employees",):
            p[k] = max(1, int(v))
        elif k in ("salaryMonthly", "aiMonthlyManualUsd", "implementationUsd"):
            p[k] = max(0.0, float(v))
        elif k in ("hoursPerWeek",):
            p[k] = min(80.0, max(0.5, float(v)))
        elif k in ("weeksPerMonth",):
            p[k] = min(5.0, max(1.0, float(v)))
        elif k in ("automationPct",):
            p[k] = min(85.0, max(5.0, float(v)))
        elif k in ("supervisionPct",):
            p[k] = min(50.0, max(0.0, float(v)))
        elif k in ("hoursBasis",):
            p[k] = v if v in ("auto", "assumptions", "tokens") else "auto"
        elif k in ("taskLabel", "source", "derivedNote"):
            p[k] = str(v)[:300]
    store.kv_set("roiParams", p)
    return p


def token_hours(tokens_monthly: int) -> float:
    """Measured tokens -> human-equivalent hours of produced work."""
    return (tokens_monthly * WORDS_PER_TOKEN / HUMAN_WORDS_PER_HOUR
            * TOKEN_UTILIZATION)


def compute(params: Optional[dict] = None,
            measured_monthly_usd: float = 0.0,
            measured_tokens_monthly: int = 0) -> dict:
    """Run the 8 steps; every intermediate is returned for the
    step-by-step panel. When measured tokens exist (hoursBasis auto or
    tokens), automated hours come from the token->labor model instead of
    the hours x automation%% assumption."""
    p = params or get_params()
    employees = max(1, int(p["employees"]))
    salary = float(p["salaryMonthly"])
    hpw = float(p["hoursPerWeek"])
    wpm = float(p["weeksPerMonth"])
    auto = float(p["automationPct"]) / 100.0
    ai_monthly = round(float(measured_monthly_usd)
                       + float(p.get("aiMonthlyManualUsd") or 0.0), 2)
    impl = float(p.get("implementationUsd") or 0.0)

    team_cost = employees * salary * PAYROLL_BURDEN                  # 1
    hours_month = employees * hpw * wpm                              # 2
    hourly_rate = team_cost / hours_month if hours_month else 0.0    # 3
    tok_hours_raw = token_hours(int(measured_tokens_monthly or 0))
    # FTE sanity cap (Token Economy: agents burn far more tokens than the
    # human throughput they replace) — you can't save more hours than the
    # task actually takes
    tok_hours = min(tok_hours_raw, hours_month)
    basis = p.get("hoursBasis", "auto")
    use_tokens = (basis == "tokens"
                  or (basis == "auto" and tok_hours > 0))
    assumption_hours = hours_month * auto
    automated_hours = tok_hours if use_tokens else assumption_hours  # 4
    gross_monthly = automated_hours * hourly_rate                    # 5
    supervision_pct = float(p.get("supervisionPct",
                                  DEFAULT_SUPERVISION_PCT)) / 100.0
    supervision_usd = automated_hours * supervision_pct * hourly_rate
    net_monthly = gross_monthly - ai_monthly - supervision_usd       # 6
    payback_months = (impl / net_monthly) if net_monthly > 0 else None  # 7
    annual_net = net_monthly * 12 - impl
    denominator = 12 * ai_monthly + impl                             # 8
    roi_pct = (annual_net / denominator * 100.0) if denominator > 0 else None
    x_factor = (roi_pct / 100.0 + 1.0) if roi_pct is not None else None

    return {
        "params": p,
        "aiMonthlyUsd": ai_monthly,
        "steps": [
            {"n": 1, "label": "Team cost (x1.3 payroll burden)",
             "formula": f"{employees} x ${salary:,.0f} x {PAYROLL_BURDEN}",
             "value": round(team_cost, 2), "unit": "$/mo"},
            {"n": 2, "label": "Hours on the task",
             "formula": f"{employees} x {hpw:g} h/wk x {wpm:g} wk",
             "value": round(hours_month, 1), "unit": "h/mo"},
            {"n": 3, "label": "Effective hourly rate",
             "formula": "step 1 / step 2",
             "value": round(hourly_rate, 2), "unit": "$/h"},
            {"n": 4,
             "label": ("Automated hours (from measured tokens)"
                       if use_tokens else
                       f"Automated hours ({auto * 100:.0f}%)"),
             "formula": (f"{int(measured_tokens_monthly):,} tokens x "
                         f"{WORDS_PER_TOKEN} words x 1/"
                         f"{HUMAN_WORDS_PER_HOUR:.0f} words-per-hour x "
                         f"{TOKEN_UTILIZATION:.0%} utilization"
                         if use_tokens else
                         f"step 2 x {auto * 100:.0f}%"),
             "value": round(automated_hours, 1), "unit": "h/mo"},
            {"n": 5, "label": "Gross savings",
             "formula": "step 4 x step 3",
             "value": round(gross_monthly, 2), "unit": "$/mo"},
            {"n": 6,
             "label": "Net savings (minus AI cost and supervision)",
             "formula": (f"step 5 - ${ai_monthly:,.2f} AI - "
                         f"${supervision_usd:,.2f} review time "
                         f"({supervision_pct:.0%} of automated hours — "
                         "the Token Economy verification burden)"),
             "value": round(net_monthly, 2), "unit": "$/mo"},
            {"n": 7, "label": "Payback",
             "formula": f"${impl:,.0f} / step 6",
             "value": (round(payback_months, 2)
                       if payback_months is not None else 0.0),
             "unit": "months"},
            {"n": 8, "label": "First-year ROI",
             "formula": f"(step 6 x 12 - ${impl:,.0f}) / "
                        f"(12 x ${ai_monthly:,.2f} + ${impl:,.0f})",
             "value": round(roi_pct, 1) if roi_pct is not None else None,
             "unit": "%"},
        ],
        "hoursBasis": "tokens" if use_tokens else "assumptions",
        "supervisionUsd": round(supervision_usd, 2),
        "tokenHoursCapped": tok_hours_raw > hours_month,
        "tokenAnchor": ({
            "lowUsd": round(measured_tokens_monthly / 1e6
                            * HUMAN_COST_PER_MTOK_LOW, 2),
            "highUsd": round(measured_tokens_monthly / 1e6
                             * HUMAN_COST_PER_MTOK_HIGH, 2),
        } if measured_tokens_monthly else None),
        "tokenHoursMonthly": round(tok_hours, 1),
        "assumptionHoursMonthly": round(assumption_hours, 1),
        "measuredTokensMonthly": int(measured_tokens_monthly or 0),
        "netMonthlyUsd": round(net_monthly, 2),
        "annualNetUsd": round(annual_net, 2),
        "roiPct": round(roi_pct, 1) if roi_pct is not None else None,
        "xFactor": round(x_factor, 1) if x_factor is not None else None,
        "roiNote": (None if roi_pct is not None else
                    "AI cost is $0 this period — every automated hour is "
                    "pure upside, so a ratio isn't meaningful yet. Add a "
                    "manual monthly spend or connect a usage-reporting "
                    "provider."),
        "computedAt": time.time(),
    }


# ---------------------------------------------------------------------------
# Parameter derivation from the AICVC Roadmap's Company Context
# ---------------------------------------------------------------------------

def _company_context_text() -> str:
    path = store._home() / "plugins-data" / "ai-cyber-value-creator" / \
        "company-context.md"
    try:
        return path.read_text()[:6000]
    except OSError:
        return ""


_DERIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "employees": {"type": "integer",
                      "description": "people regularly doing AI-automatable work here (1 for a solo creator)"},
        "salaryMonthly": {"type": "number",
                          "description": "gross monthly value of one such person's time in USD; use the blended analysis/engineering/marketing rate if unstated"},
        "hoursPerWeek": {"type": "number",
                         "description": "hours/week each spends on work the AI now assists"},
        "automationPct": {"type": "number",
                          "description": "realistic automation share 5-85, using the ai-saves medians: support 65, content 55, analytics 50, search 70"},
        "taskLabel": {"type": "string",
                      "description": "one line naming the automated work"},
        "note": {"type": "string",
                 "description": "1-2 sentences on how the context informed these numbers"},
    },
    "required": ["employees", "salaryMonthly", "hoursPerWeek",
                 "automationPct", "taskLabel", "note"],
}


def derive_params() -> dict:
    """Ask the host LLM to parameterize the ROI model from everything we
    know about the user (Company Context). Falls back to defaults."""
    ctx = _company_context_text()
    if not ctx.strip():
        p = save_params({**DEFAULT_PARAMS, "source": "defaults",
                         "derivedNote": "No Company Context found on the "
                         "Roadmap yet — using standard blended rates "
                         f"(analysis ${STANDARD_RATES['analysis']:.0f} / "
                         f"engineering ${STANDARD_RATES['engineering']:.0f} /"
                         f" marketing ${STANDARD_RATES['marketing']:.0f}"
                         f" -> ${BLENDED_RATE}/h)."})
        return p

    from agent.plugin_llm import PluginLlm
    res = PluginLlm(plugin_id=PLUGIN_ID).complete_structured(
        instructions=(
            "Parameterize an AI-ROI model from a company context document. "
            "Be conservative and realistic. Where the context is silent, "
            f"use the standard blended rate (${BLENDED_RATE}/h = "
            f"${BLENDED_RATE * 160 / 1.3:,.0f}/mo gross at 160h) and the "
            "ai-saves automation medians."),
        input=[{"type": "text", "text": "COMPANY CONTEXT:\n" + ctx}],
        json_schema=_DERIVE_SCHEMA,
        schema_name="roi_params",
        temperature=0.2,
        max_tokens=800,
        timeout=120,
        purpose="value-dashboard-roi-params",
    )
    parsed = getattr(res, "parsed", None)
    if parsed is None:
        raw = getattr(res, "text", "") or ""
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else None
    if not isinstance(parsed, dict):
        raise RuntimeError("could not derive parameters — try again")
    return save_params({
        "employees": parsed.get("employees", 1),
        "salaryMonthly": parsed.get("salaryMonthly",
                                    DEFAULT_PARAMS["salaryMonthly"]),
        "hoursPerWeek": parsed.get("hoursPerWeek",
                                   DEFAULT_PARAMS["hoursPerWeek"]),
        "automationPct": parsed.get("automationPct",
                                    DEFAULT_PARAMS["automationPct"]),
        "taskLabel": parsed.get("taskLabel", DEFAULT_PARAMS["taskLabel"]),
        "source": "company-context",
        "derivedNote": parsed.get("note", ""),
    })
