"""value-dashboard storage — a small kv sqlite for settings, derived ROI
parameters, and collected usage snapshots."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def _home() -> Path:
    val = (os.environ.get("HERMES_HOME") or "").strip()
    return Path(val).expanduser() if val else Path.home() / ".hermes"


def data_dir() -> Path:
    d = _home() / "plugins-data" / "value-dashboard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "data.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL);")
    return conn


def kv_get(key: str):
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM kv WHERE key=?",
                           (key,)).fetchone()
        return json.loads(row["value"]) if row else None
    finally:
        conn.close()


def kv_set(key: str, value) -> None:
    conn = connect()
    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO kv (key, value) "
                         "VALUES (?,?)", (key, json.dumps(value)))
    finally:
        conn.close()


def env_keys() -> dict:
    """Provider-key presence (never values) from env + ~/.hermes/.env."""
    names = ("OPENROUTER_API_KEY", "ANTHROPIC_ADMIN_KEY", "ANTHROPIC_API_KEY",
             "OPENAI_ADMIN_KEY", "OPENAI_API_KEY", "XAI_API_KEY",
             "GEMINI_API_KEY", "DEEPSEEK_API_KEY")
    found = {}
    file_vals = {}
    try:
        for line in (_home() / ".env").read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                file_vals[k.strip()] = v.strip()
    except OSError:
        pass
    for n in names:
        found[n] = bool((os.environ.get(n) or "").strip()
                        or file_vals.get(n))
    return found


def get_key(env_var: str) -> str:
    v = (os.environ.get(env_var) or "").strip()
    if v:
        return v
    try:
        for line in (_home() / ".env").read_text().splitlines():
            if line.strip().startswith(env_var + "="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


_PROVIDER_LABELS = {
    "anthropic": "Anthropic", "openai": "OpenAI", "xai": "xAI / Grok",
    "xai-oauth": "xAI / Grok", "gemini": "Gemini", "google": "Gemini",
    "deepseek": "DeepSeek", "openrouter": "OpenRouter",
    "copilot": "GitHub Copilot", "groq": "Groq", "mistral": "Mistral",
    "nous": "Nous Portal",
}


def connected_providers() -> list[dict]:
    """LLM credentials hermes itself holds (auth.json credential_pool) —
    OAuth logins and pool-stored API keys alike. Names and auth types only,
    never secrets."""
    out = []
    try:
        d = json.loads((_home() / "auth.json").read_text())
        pool = d.get("credential_pool") or {}
        for prov, entries in pool.items():
            entries = [e for e in (entries or []) if isinstance(e, dict)]
            if not entries:
                continue
            kinds = sorted({str(e.get("auth_type") or "").strip()
                            for e in entries if e.get("auth_type")})
            out.append({
                "provider": prov,
                "label": _PROVIDER_LABELS.get(
                    prov, _PROVIDER_LABELS.get(
                        prov.replace("-oauth", ""), prov)),
                "authTypes": kinds or ["unknown"],
            })
    except Exception:
        pass
    return out
