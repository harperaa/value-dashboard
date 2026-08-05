"""Dashboard plugin — backend API routes.

Mounted at /api/plugins/value-dashboard/. AI ROI widget: provider usage
collection, the 8-step ai-saves methodology, Company-Context-derived
parameters.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except Exception:  # allows unit tests without dashboard dependencies
    class APIRouter:  # type: ignore
        def get(self, *a, **k):
            return lambda fn: fn

        def post(self, *a, **k):
            return lambda fn: fn

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code

    class BaseModel:  # type: ignore
        pass

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_PKG = "hermes_plugin_pkg_value_dashboard"

if _PKG not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _PKG, str(_PLUGIN_ROOT / "__init__.py"),
        submodule_search_locations=[str(_PLUGIN_ROOT)])
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_PKG] = _mod
    _spec.loader.exec_module(_mod)

store = importlib.import_module(f"{_PKG}.store")
usage = importlib.import_module(f"{_PKG}.usage")
roi = importlib.import_module(f"{_PKG}.roi")

router = APIRouter()


def _public_state() -> dict:
    snapshot = store.kv_get("usageSnapshot") or {}
    measured = float(snapshot.get("measuredMonthlyUsd") or 0.0)
    tokens = int(snapshot.get("measuredTokensMonthly") or 0)
    return {
        "usage": snapshot,
        "roi": roi.compute(measured_monthly_usd=measured,
                           measured_tokens_monthly=tokens),
        "keys": store.env_keys(),
        "hasCompanyContext": bool(roi._company_context_text().strip()),
    }


@router.get("/state")
def state():
    return _public_state()


@router.post("/refresh")
def refresh():
    try:
        usage.collect_all()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:200])
    return {"ok": True, "state": _public_state()}


@router.post("/derive")
def derive():
    try:
        roi.derive_params()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:300])
    return {"ok": True, "state": _public_state()}


class ParamsBody(BaseModel):
    employees: int | None = None
    salaryMonthly: float | None = None
    hoursPerWeek: float | None = None
    weeksPerMonth: float | None = None
    automationPct: float | None = None
    aiMonthlyManualUsd: float | None = None
    implementationUsd: float | None = None
    taskLabel: str | None = None
    hoursBasis: str | None = None


@router.post("/params")
def params(body: ParamsBody):
    updates = {k: v for k, v in body.__dict__.items() if v is not None}
    if updates:
        updates["source"] = "manual"
        roi.save_params(updates)
    return {"ok": True, "state": _public_state()}
