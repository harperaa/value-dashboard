"""Provider usage collectors — pull real LLM spend where an API exists.

Honesty policy: every provider reports one of three states —
  ok           real numbers from the provider's usage API
  unsupported  the provider has no usable programmatic usage endpoint
               (browse their console; use the manual override)
  error        a key exists but the call failed (message included)

Verified endpoints:
  OpenRouter   GET /api/v1/auth/key — key info incl. lifetime usage USD
  Anthropic    GET /v1/organizations/usage_report/messages (ADMIN key only)
  OpenAI       GET /v1/organization/costs (admin key only)
Everything else (xAI, Gemini, DeepSeek) exposes usage in the console, not
the API — those report `unsupported` and count via the manual override.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from . import store
except ImportError:  # loaded outside package context
    import store  # type: ignore


def _get_json(url: str, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"HTTP {exc.code}: {body}")


def _month_start_epoch() -> int:
    now = datetime.now(timezone.utc)
    return int(now.replace(day=1, hour=0, minute=0, second=0,
                           microsecond=0).timestamp())


def collect_openrouter() -> dict:
    key = store.get_key("OPENROUTER_API_KEY")
    if not key:
        return {"provider": "OpenRouter", "state": "nokey"}
    try:
        data = _get_json("https://openrouter.ai/api/v1/auth/key",
                         {"Authorization": f"Bearer {key}"})
        d = data.get("data") or {}
        return {"provider": "OpenRouter", "state": "ok",
                "costUsd": float(d.get("usage") or 0.0),
                "period": "lifetime on this key",
                "note": "OpenRouter reports lifetime spend per key"}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "OpenRouter", "state": "error",
                "error": str(exc)[:150]}


def collect_anthropic() -> dict:
    key = store.get_key("ANTHROPIC_ADMIN_KEY")
    if not key:
        if store.get_key("ANTHROPIC_API_KEY"):
            return {"provider": "Anthropic", "state": "unsupported",
                    "note": "usage reports need an ADMIN key "
                            "(ANTHROPIC_ADMIN_KEY) — regular API keys "
                            "can't read them"}
        return {"provider": "Anthropic", "state": "nokey"}
    try:
        start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        data = _get_json(
            "https://api.anthropic.com/v1/organizations/cost_report"
            f"?starting_at={start.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            {"x-api-key": key, "anthropic-version": "2023-06-01"})
        total = 0.0
        for bucket in data.get("data") or []:
            for r in bucket.get("results") or []:
                total += float(r.get("amount") or 0.0)
        return {"provider": "Anthropic", "state": "ok",
                "costUsd": round(total, 2), "period": "this month"}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "Anthropic", "state": "error",
                "error": str(exc)[:150]}


def collect_openai() -> dict:
    key = store.get_key("OPENAI_ADMIN_KEY")
    if not key:
        if store.get_key("OPENAI_API_KEY"):
            return {"provider": "OpenAI", "state": "unsupported",
                    "note": "org cost reports need an admin key "
                            "(OPENAI_ADMIN_KEY)"}
        return {"provider": "OpenAI", "state": "nokey"}
    try:
        data = _get_json(
            "https://api.openai.com/v1/organization/costs"
            f"?start_time={_month_start_epoch()}&limit=31",
            {"Authorization": f"Bearer {key}"})
        total = 0.0
        for bucket in data.get("data") or []:
            for r in bucket.get("results") or []:
                amt = (r.get("amount") or {})
                total += float(amt.get("value") or 0.0)
        return {"provider": "OpenAI", "state": "ok",
                "costUsd": round(total, 2), "period": "this month"}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "OpenAI", "state": "error",
                "error": str(exc)[:150]}


def _console_only(name: str, env_var: str, console: str) -> dict:
    if not store.get_key(env_var):
        return {"provider": name, "state": "nokey"}
    return {"provider": name, "state": "unsupported",
            "note": f"no usage API — check {console} and use the manual "
                    "monthly-spend override"}


def collect_all() -> dict:
    """Run every collector; normalize to an estimated monthly AI cost."""
    results = [
        collect_openrouter(),
        collect_anthropic(),
        collect_openai(),
        _console_only("xAI / Grok", "XAI_API_KEY", "console.x.ai"),
        _console_only("Gemini", "GEMINI_API_KEY",
                      "aistudio.google.com / console.cloud.google.com"),
        _console_only("DeepSeek", "DEEPSEEK_API_KEY",
                      "platform.deepseek.com"),
    ]
    visible = [r for r in results if r["state"] != "nokey"]
    measured = sum(r.get("costUsd") or 0.0 for r in visible
                   if r["state"] == "ok")
    snapshot = {
        "at": time.time(),
        "providers": visible,
        "measuredMonthlyUsd": round(measured, 2),
        "unsupportedCount": sum(1 for r in visible
                                if r["state"] == "unsupported"),
    }
    store.kv_set("usageSnapshot", snapshot)
    return snapshot
