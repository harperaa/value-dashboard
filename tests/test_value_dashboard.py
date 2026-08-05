"""value-dashboard tests — ROI math, x-factor, params, usage collectors."""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

PKG = "value_dashboard_test_pkg"
ROOT = Path(__file__).resolve().parent.parent

if PKG not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PKG, str(ROOT / "__init__.py"),
        submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = mod
    spec.loader.exec_module(mod)

store = importlib.import_module(f"{PKG}.store")
usage = importlib.import_module(f"{PKG}.usage")
roi = importlib.import_module(f"{PKG}.roi")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for var in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                "ANTHROPIC_ADMIN_KEY", "OPENAI_API_KEY", "OPENAI_ADMIN_KEY",
                "XAI_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_roi_matches_the_ai_saves_example(home):
    """The calculator's own base scenario: 5 people x $5,500, 30 h/wk,
    weeks 5 -> 600 h/mo at $60/h (team cost $35,750), 65% automation,
    AI $900/mo, setup $3,000 -> Year-1 ROI 1,921%."""
    out = roi.compute(params={
        "employees": 5, "salaryMonthly": 5500, "hoursPerWeek": 30,
        "weeksPerMonth": 4, "automationPct": 65,
        "aiMonthlyManualUsd": 900, "implementationUsd": 3000,
        "supervisionPct": 0,     # the site's formula has no review deduction
        "taskLabel": "Customer support", "source": "manual",
    }, measured_monthly_usd=0.0)
    steps = {s["n"]: s["value"] for s in out["steps"]}
    assert steps[1] == 35750.0                    # 5 x 5500 x 1.3
    assert steps[2] == 600.0                      # 5 x 30 x 4
    assert steps[3] == pytest.approx(59.58, abs=0.01)
    assert steps[4] == 390.0                      # 600 x 65%
    assert steps[5] == pytest.approx(23237.5, abs=1)   # site shows $23,238
    assert steps[6] == pytest.approx(22337.5, abs=1)
    assert out["roiPct"] == pytest.approx(1921, abs=10)  # site: 1,921%
    # x-factor conversion: 1,900% -> 20x
    assert out["xFactor"] == pytest.approx(out["roiPct"] / 100 + 1, abs=0.1)


def test_x_factor_examples(home):
    out = roi.compute(params={**roi.DEFAULT_PARAMS,
                              "aiMonthlyManualUsd": 100},
                      measured_monthly_usd=0.0)
    assert out["xFactor"] == pytest.approx(out["roiPct"] / 100 + 1, abs=0.1)


def test_roi_without_ai_cost_returns_note_not_infinity(home):
    out = roi.compute(params={**roi.DEFAULT_PARAMS,
                              "aiMonthlyManualUsd": 0,
                              "implementationUsd": 0},
                      measured_monthly_usd=0.0)
    assert out["roiPct"] is None and out["xFactor"] is None
    assert "manual monthly spend" in out["roiNote"]


def test_params_clamped_and_persisted(home):
    p = roi.save_params({"employees": 0, "automationPct": 99,
                         "hoursPerWeek": 200, "salaryMonthly": -5})
    assert p["employees"] == 1
    assert p["automationPct"] == 85.0
    assert p["hoursPerWeek"] == 80.0
    assert p["salaryMonthly"] == 0.0
    assert roi.get_params()["automationPct"] == 85.0


def test_blended_rate_is_documented_mean(home):
    assert roi.BLENDED_RATE == pytest.approx(
        (75 + 95 + 60) / 3, abs=0.01)
    # the default salary lands back on the blended loaded rate at 160 h
    loaded = roi.DEFAULT_PARAMS["salaryMonthly"] * 1.3 / 160
    assert loaded == pytest.approx(roi.BLENDED_RATE, abs=0.5)


def test_openrouter_collector_normalizes(home, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

    def fake_get(url, headers, timeout=30):
        assert "openrouter.ai/api/v1/auth/key" in url
        assert headers["Authorization"] == "Bearer or-key"
        return {"data": {"usage": 42.5, "limit": None}}

    monkeypatch.setattr(usage, "_get_json", fake_get)
    out = usage.collect_openrouter()
    assert out["state"] == "ok" and out["costUsd"] == 42.5


def test_collect_all_states_and_snapshot(home, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("XAI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")   # non-admin -> unsupported

    def fake_get(url, headers, timeout=30):
        return {"data": {"usage": 10.0}}

    monkeypatch.setattr(usage, "_get_json", fake_get)
    snap = usage.collect_all()
    states = {p["provider"]: p["state"] for p in snap["providers"]}
    assert states["OpenRouter"] == "ok"
    assert states["xAI / Grok"] == "unsupported"
    assert states["Anthropic"] == "unsupported"
    assert "Gemini" not in states                  # no key -> hidden
    assert snap["measuredMonthlyUsd"] == 10.0
    assert store.kv_get("usageSnapshot")["measuredMonthlyUsd"] == 10.0


def test_derive_params_defaults_without_context(home):
    p = roi.derive_params()
    assert p["source"] == "defaults"
    assert "blended" in p["derivedNote"].lower() or \
        "Company Context" in p["derivedNote"]


def test_derive_params_from_context(home, monkeypatch):
    ctx_dir = home / "plugins-data" / "ai-cyber-value-creator"
    ctx_dir.mkdir(parents=True)
    (ctx_dir / "company-context.md").write_text(
        "# Company\nSolo consultant, AI security audits, ~25 h/wk billable.")

    class FakeRes:
        parsed = {"employees": 1, "salaryMonthly": 12000,
                  "hoursPerWeek": 25, "automationPct": 50,
                  "taskLabel": "AI security audits",
                  "note": "solo consultant at premium rates"}

    class FakeLlm:
        def complete_structured(self, **kw):
            return FakeRes()

    import types
    fake_mod = types.ModuleType("agent.plugin_llm")
    fake_mod.PluginLlm = lambda plugin_id: FakeLlm()
    fake_agent = types.ModuleType("agent")
    fake_agent.plugin_llm = fake_mod
    monkeypatch.setitem(sys.modules, "agent", fake_agent)
    monkeypatch.setitem(sys.modules, "agent.plugin_llm", fake_mod)

    p = roi.derive_params()
    assert p["source"] == "company-context"
    assert p["salaryMonthly"] == 12000
    assert p["taskLabel"] == "AI security audits"


def test_hermes_credential_pool_counts_as_connected(home, monkeypatch):
    import json as _json
    (home / "auth.json").write_text(_json.dumps({
        "version": 1,
        "credential_pool": {
            "anthropic": [{"id": "c1", "auth_type": "api_key",
                           "label": "work key", "priority": 1}],
            "xai-oauth": [{"id": "c2", "auth_type": "oauth",
                           "label": "grok login", "priority": 1,
                           "access_token": "SECRET"}],
            "empty-provider": [],
        },
    }))
    conns = store.connected_providers()
    by = {c["provider"]: c for c in conns}
    assert by["anthropic"]["label"] == "Anthropic"
    assert by["anthropic"]["authTypes"] == ["api_key"]
    assert by["xai-oauth"]["label"] == "xAI / Grok"
    assert "empty-provider" not in by
    # secrets never leak through
    assert "SECRET" not in _json.dumps(conns)

    snap = usage.collect_all()
    states = {p["provider"]: p for p in snap["providers"]}
    assert states["Anthropic"]["state"] == "unsupported"
    assert "connected in hermes (api_key)" in states["Anthropic"]["note"]
    assert states["xAI / Grok"]["state"] == "unsupported"
    assert "oauth" in states["xAI / Grok"]["note"]


def test_token_labor_model(home):
    # 1M output-ish tokens -> 0.75M words -> 1250 h raw -> 437.5 h at 35%
    assert roi.token_hours(1_000_000) == pytest.approx(437.5, abs=0.1)
    out = roi.compute(params={**roi.DEFAULT_PARAMS,
                              "aiMonthlyManualUsd": 500},
                      measured_tokens_monthly=1_000_000)
    assert out["hoursBasis"] == "tokens"
    step4 = [s for s in out["steps"] if s["n"] == 4][0]
    # FTE cap: 437.5 raw hours bound by the task's 80 h/mo
    assert step4["value"] == pytest.approx(80.0, abs=0.1)
    assert out["tokenHoursCapped"] is True
    assert "tokens" in step4["formula"]
    # uncapped: a smaller batch stays under the cap
    small = roi.compute(params={**roi.DEFAULT_PARAMS,
                                "aiMonthlyManualUsd": 500},
                        measured_tokens_monthly=100_000)
    s4 = [x for x in small["steps"] if x["n"] == 4][0]
    assert s4["value"] == pytest.approx(43.75, abs=0.1)
    assert small["tokenHoursCapped"] is False
    # explicit assumptions basis ignores tokens
    out2 = roi.compute(params={**roi.DEFAULT_PARAMS,
                               "hoursBasis": "assumptions",
                               "aiMonthlyManualUsd": 500},
                       measured_tokens_monthly=1_000_000)
    assert out2["hoursBasis"] == "assumptions"
    assert out2["assumptionHoursMonthly"] == 80.0 * 0.55


def test_anthropic_cost_is_cents(home, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "sk-ant-admin01-x")

    def fake_get(url, headers, timeout=30):
        if "cost_report" in url:
            return {"data": [{"results": [{"amount": 12345.0}]}]}
        return {"data": [{"results": [
            {"uncached_input_tokens": 1000, "output_tokens": 500}]}]}

    monkeypatch.setattr(usage, "_get_json", fake_get)
    out = usage.collect_anthropic()
    assert out["state"] == "ok"
    assert out["costUsd"] == 123.45          # cents -> dollars
    assert out["tokens"] == 1500


def test_proven_unsupported_carry_doc_links(home, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("XAI_API_KEY", "x")   # api key alone: unsupported
    g = usage.collect_gemini()
    assert g["state"] == "unsupported" and "PROVEN" in g["note"]
    assert g["docUrl"].startswith("https://ai.google.dev")
    x = usage.collect_xai()
    assert x["state"] == "unsupported" and "Management" in x["note"]
    assert x["docUrl"].startswith("https://docs.x.ai")


def test_token_economy_concepts(home):
    # supervision deduction: 10% of automated hours at the effective rate
    out = roi.compute(params={**roi.DEFAULT_PARAMS,
                              "hoursBasis": "assumptions",
                              "aiMonthlyManualUsd": 100},
                      measured_tokens_monthly=0)
    hours = out["assumptionHoursMonthly"]           # 80 x 55% = 44
    rate = [s for s in out["steps"] if s["n"] == 3][0]["value"]
    assert out["supervisionUsd"] == pytest.approx(hours * 0.10 * rate, abs=1)
    step6 = [s for s in out["steps"] if s["n"] == 6][0]
    assert "supervision" in step6["label"].lower() or \
        "review" in step6["formula"]

    # FTE cap: token hours can never exceed the task's total hours
    big = roi.compute(params={**roi.DEFAULT_PARAMS,
                              "aiMonthlyManualUsd": 100},
                      measured_tokens_monthly=50_000_000)
    assert big["tokenHoursMonthly"] == 80.0         # capped at hours_month
    assert big["tokenHoursCapped"] is True

    # per-token human-cost anchor: $25-40 per million tokens
    assert big["tokenAnchor"]["lowUsd"] == pytest.approx(50 * 25, abs=1)
    assert big["tokenAnchor"]["highUsd"] == pytest.approx(50 * 40, abs=1)

    # supervision clamps 0-50
    p = roi.save_params({"supervisionPct": 99})
    assert p["supervisionPct"] == 50.0
