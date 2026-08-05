"""Provider usage collectors — pull real LLM spend and tokens where an API
exists. Every claim below is backed by the provider's own docs (docUrl on
each result), verified 2026-08-05.

Truth table:
  OpenRouter  YES  GET /api/v1/activity (daily usd+tokens; provisioning key)
                   fallback GET /api/v1/auth/key (lifetime usd; any key)
  Anthropic   YES  Admin key: /v1/organizations/usage_report/messages
                   (tokens) + /v1/organizations/cost_report (CENTS)
  OpenAI      YES  Admin key: /v1/organization/usage/completions (tokens)
                   + /v1/organization/costs (USD)
  xAI         YES  Management key + team id:
                   POST management-api.x.ai/v1/billing/teams/{id}/usage
  Copilot     YES  GitHub PAT: /users/{login}/settings/billing/usage
  Gemini      NO   ai.google.dev/gemini-api/docs/billing documents ONLY the
                   AI Studio dashboard + Cloud Billing console — no REST
                   usage endpoint exists
  DeepSeek    NO   api-docs.deepseek.com lists 5 endpoints total; only
                   /user/balance touches money — we track spend as balance
                   deltas between refreshes

States: ok (real numbers) · unsupported (proven no API, or credential type
can't reach it — note says which) · error (call failed; message shown).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    from . import store
except ImportError:  # loaded outside package context
    import store  # type: ignore

DOCS = {
    "openrouter": "https://openrouter.ai/docs/api/api-reference/analytics/get-user-activity",
    "anthropic": "https://platform.claude.com/docs/en/api/usage-cost-api",
    "openai": "https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage",
    "xai": "https://docs.x.ai/developers/rest-api-reference/management/billing",
    "copilot": "https://docs.github.com/en/rest/billing/usage",
    "gemini": "https://ai.google.dev/gemini-api/docs/billing",
    "deepseek": "https://api-docs.deepseek.com/api/get-user-balance",
}


def _request(url: str, headers: dict, body: dict | None = None,
             timeout: int = 30) -> dict | list:
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"HTTP {exc.code}: {detail}")


def _get_json(url: str, headers: dict, timeout: int = 30):
    return _request(url, headers, None, timeout)


def _month_start() -> datetime:
    return datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)


def _sum_tokens(obj) -> int:
    """Leniently sum every *_tokens numeric field in a result object."""
    total = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and "token" in k.lower():
                total += int(v)
            elif isinstance(v, (dict, list)):
                total += _sum_tokens(v)
    elif isinstance(obj, list):
        for it in obj:
            total += _sum_tokens(it)
    return total


# ---------------------------------------------------------------------------

def collect_openrouter() -> dict:
    key = store.get_key("OPENROUTER_API_KEY")
    if not key:
        return {"provider": "OpenRouter", "state": "nokey"}
    hdrs = {"Authorization": f"Bearer {key}"}
    # daily activity first (usd + tokens, last 30 completed days) — needs a
    # provisioning/management key, so fall back to lifetime key usage
    try:
        data = _get_json("https://openrouter.ai/api/v1/activity", hdrs)
        rows = data.get("data") if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            usd = sum(float(r.get("usage") or 0) for r in rows
                      if isinstance(r, dict))
            tokens = sum(
                int(r.get("prompt_tokens") or 0)
                + int(r.get("completion_tokens") or 0)
                + int(r.get("reasoning_tokens") or 0)
                for r in rows if isinstance(r, dict))
            return {"provider": "OpenRouter", "state": "ok",
                    "costUsd": round(usd, 2), "tokens": tokens,
                    "period": "last 30 days",
                    "docUrl": DOCS["openrouter"]}
    except Exception:  # noqa: BLE001 — fall through to auth/key
        pass
    try:
        data = _get_json("https://openrouter.ai/api/v1/auth/key", hdrs)
        d = data.get("data") or {}
        return {"provider": "OpenRouter", "state": "ok",
                "costUsd": round(float(d.get("usage") or 0.0), 2),
                "period": "lifetime on this key",
                "note": "daily activity needs a provisioning key; this is "
                        "the key's lifetime spend",
                "docUrl": DOCS["openrouter"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "OpenRouter", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["openrouter"]}


def collect_anthropic() -> dict:
    admin = store.get_key("ANTHROPIC_ADMIN_KEY")
    if not admin:
        if store.get_key("ANTHROPIC_API_KEY"):
            return {"provider": "Anthropic", "state": "unsupported",
                    "note": "usage/cost reports exist but need an Admin API "
                            "key (sk-ant-admin…, Console → Settings) — add "
                            "it as ANTHROPIC_ADMIN_KEY. Unavailable for "
                            "individual (non-organization) accounts.",
                    "docUrl": DOCS["anthropic"]}
        return {"provider": "Anthropic", "state": "nokey"}
    hdrs = {"x-api-key": admin, "anthropic-version": "2023-06-01"}
    start = _month_start().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cost = _get_json(
            "https://api.anthropic.com/v1/organizations/cost_report"
            f"?starting_at={start}", hdrs)
        cents = 0.0
        for bucket in cost.get("data") or []:
            for r in bucket.get("results") or []:
                cents += float(r.get("amount") or 0.0)
        usage_ = _get_json(
            "https://api.anthropic.com/v1/organizations/usage_report/"
            f"messages?starting_at={start}&bucket_width=1d&limit=31", hdrs)
        tokens = _sum_tokens(usage_.get("data"))
        return {"provider": "Anthropic", "state": "ok",
                # cost_report reports lowest units (cents)
                "costUsd": round(cents / 100.0, 2), "tokens": tokens,
                "period": "this month", "docUrl": DOCS["anthropic"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "Anthropic", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["anthropic"]}


def collect_openai() -> dict:
    admin = store.get_key("OPENAI_ADMIN_KEY")
    if not admin:
        if store.get_key("OPENAI_API_KEY"):
            return {"provider": "OpenAI", "state": "unsupported",
                    "note": "usage/cost APIs exist but need an org admin "
                            "key — add it as OPENAI_ADMIN_KEY",
                    "docUrl": DOCS["openai"]}
        return {"provider": "OpenAI", "state": "nokey"}
    hdrs = {"Authorization": f"Bearer {admin}"}
    start = int(_month_start().timestamp())
    try:
        costs = _get_json(
            "https://api.openai.com/v1/organization/costs"
            f"?start_time={start}&limit=31", hdrs)
        usd = 0.0
        for bucket in costs.get("data") or []:
            for r in bucket.get("results") or []:
                usd += float((r.get("amount") or {}).get("value") or 0.0)
        usage_ = _get_json(
            "https://api.openai.com/v1/organization/usage/completions"
            f"?start_time={start}&bucket_width=1d&limit=31", hdrs)
        tokens = _sum_tokens(usage_.get("data"))
        return {"provider": "OpenAI", "state": "ok",
                "costUsd": round(usd, 2), "tokens": tokens,
                "period": "this month", "docUrl": DOCS["openai"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "OpenAI", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["openai"]}


def collect_xai() -> dict:
    mkey = store.get_key("XAI_MANAGEMENT_KEY")
    team = store.get_key("XAI_TEAM_ID")
    if not mkey or not team:
        if store.get_key("XAI_API_KEY") or mkey or team:
            return {"provider": "xAI / Grok", "state": "unsupported",
                    "note": "usage API exists (Management API) — add BOTH "
                            "XAI_MANAGEMENT_KEY (Console → Settings → "
                            "Management Keys) and XAI_TEAM_ID to pull it",
                    "docUrl": DOCS["xai"]}
        return {"provider": "xAI / Grok", "state": "nokey"}
    try:
        start = _month_start()
        data = _request(
            f"https://management-api.x.ai/v1/billing/teams/{team}/usage",
            {"Authorization": f"Bearer {mkey}"},
            {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "to": datetime.now(timezone.utc)
                 .strftime("%Y-%m-%dT%H:%M:%SZ")},
            timeout=45)
        cents = 0.0
        tokens = _sum_tokens(data)
        blob = json.dumps(data)
        # lenient: sum any cost-ish numeric fields the aggregate returns
        def walk(o):
            nonlocal cents
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (int, float)) and any(
                            t in k.lower() for t in
                            ("cost", "amount", "usd", "cents")):
                        cents += float(v)
                    elif isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(o, list):
                for it in o:
                    walk(it)
        walk(data)
        usd = cents / 100.0 if "cent" in blob.lower() else cents
        return {"provider": "xAI / Grok", "state": "ok",
                "costUsd": round(usd, 2), "tokens": tokens,
                "period": "this month", "docUrl": DOCS["xai"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "xAI / Grok", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["xai"]}


def collect_copilot() -> dict:
    tok = store.get_key("GITHUB_TOKEN") or store.get_key("GH_TOKEN")
    if not tok:
        return {"provider": "GitHub Copilot", "state": "nokey"}
    hdrs = {"Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "value-dashboard/1.0"}
    try:
        me = _get_json("https://api.github.com/user", hdrs)
        login = me.get("login")
        rep = _get_json(
            f"https://api.github.com/users/{login}/settings/billing/usage",
            hdrs)
        usd = 0.0
        for it in rep.get("usageItems") or rep.get("usage_items") or []:
            prod = str(it.get("product") or "").lower()
            if "copilot" in prod:
                usd += float(it.get("netAmount") or it.get("net_amount")
                             or 0.0)
        return {"provider": "GitHub Copilot", "state": "ok",
                "costUsd": round(usd, 2), "period": "current billing period",
                "docUrl": DOCS["copilot"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "GitHub Copilot", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["copilot"]}


def collect_gemini() -> dict:
    if not store.get_key("GEMINI_API_KEY"):
        return {"provider": "Gemini", "state": "nokey"}
    return {"provider": "Gemini", "state": "unsupported",
            "note": "PROVEN no REST usage endpoint — Google's billing doc "
                    "offers only the AI Studio dashboard and the Cloud "
                    "Billing console; use the manual override",
            "docUrl": DOCS["gemini"]}


def collect_deepseek() -> dict:
    key = store.get_key("DEEPSEEK_API_KEY")
    if not key:
        return {"provider": "DeepSeek", "state": "nokey"}
    try:
        data = _get_json("https://api.deepseek.com/user/balance",
                         {"Authorization": f"Bearer {key}"})
        bal = None
        for b in data.get("balance_infos") or []:
            if b.get("currency") == "USD":
                bal = float(b.get("total_balance") or 0)
        if bal is None and (data.get("balance_infos") or []):
            bal = float(data["balance_infos"][0].get("total_balance") or 0)
        prev = store.kv_get("deepseekBalance") or {}
        spend = None
        if isinstance(prev.get("balance"), (int, float)) and bal is not None \
                and bal < prev["balance"]:
            spend = round(prev["balance"] - bal, 2)
        store.kv_set("deepseekBalance", {"balance": bal, "at": time.time()})
        return {"provider": "DeepSeek", "state": "ok",
                "costUsd": spend or 0.0,
                "period": "since last refresh (balance delta)",
                "note": "PROVEN no usage endpoint (docs list 5 endpoints; "
                        "balance only) — spend tracked as balance deltas; "
                        f"balance ${bal:,.2f}" if bal is not None else
                        "balance unavailable",
                "docUrl": DOCS["deepseek"]}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "DeepSeek", "state": "error",
                "error": str(exc)[:150], "docUrl": DOCS["deepseek"]}


def collect_all() -> dict:
    """Run every collector; normalize monthly AI cost + measured tokens."""
    results = [
        collect_openrouter(),
        collect_anthropic(),
        collect_openai(),
        collect_xai(),
        collect_copilot(),
        collect_gemini(),
        collect_deepseek(),
    ]
    # merge in providers hermes itself holds credentials for (OAuth logins
    # and pool-stored keys in auth.json) — env-var scanning alone misses
    # them entirely
    by_label = {r["provider"]: r for r in results}
    pool_notes = {
        "Anthropic": ("usage/cost API exists — needs ANTHROPIC_ADMIN_KEY "
                      "(org accounts only)", DOCS["anthropic"]),
        "OpenAI": ("usage/cost API exists — needs OPENAI_ADMIN_KEY",
                   DOCS["openai"]),
        "xAI / Grok": ("usage API exists — add XAI_MANAGEMENT_KEY + "
                       "XAI_TEAM_ID", DOCS["xai"]),
        "GitHub Copilot": ("billed usage API exists — add a GitHub token "
                           "(GITHUB_TOKEN)", DOCS["copilot"]),
        "Gemini": ("PROVEN no REST usage endpoint — dashboard/Cloud "
                   "Billing only", DOCS["gemini"]),
    }
    for cp in store.connected_providers():
        label = cp["label"]
        auth = "/".join(cp["authTypes"])
        note, doc = pool_notes.get(
            label, ("no usage API reachable with this credential — use "
                    "the manual override", None))
        existing = by_label.get(label)
        full = f"connected in hermes ({auth}) — {note}"
        if existing is None:
            entry = {"provider": label, "state": "unsupported", "note": full}
            if doc:
                entry["docUrl"] = doc
            results.append(entry)
            by_label[label] = entry
        elif existing["state"] == "nokey":
            existing["state"] = "unsupported"
            existing["note"] = full
            if doc:
                existing["docUrl"] = doc

    visible = [r for r in results if r["state"] != "nokey"]
    measured = sum(r.get("costUsd") or 0.0 for r in visible
                   if r["state"] == "ok")
    tokens = sum(int(r.get("tokens") or 0) for r in visible
                 if r["state"] == "ok")
    snapshot = {
        "at": time.time(),
        "providers": visible,
        "measuredMonthlyUsd": round(measured, 2),
        "measuredTokensMonthly": tokens,
        "unsupportedCount": sum(1 for r in visible
                                if r["state"] == "unsupported"),
    }
    store.kv_set("usageSnapshot", snapshot)
    return snapshot
