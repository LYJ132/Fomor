"""Configuration and data directory layout.

All runtime data lives under a single home directory (``FOMOR_HOME`` or
``./data``).  Layout follows the PRD (section 9.3):

    <home>/config/settings.json
    <home>/config/preferences.json
    <home>/events/YYYY-MM-DD.json
    <home>/topics/topic_*.json
    <home>/discoveries/discovery_*.json
    <home>/runtime/tasks.json
    <home>/runtime/scheduler.json
    <home>/logs/
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

DEFAULT_SETTINGS: dict = {
    "timezone": "Asia/Shanghai",
    "analysis_hour": 3,
    "retention_hours": 48,
    "llm": {
        # Set "mock" to false and export FOMOR_LLM_API_KEY to use a real model.
        "mock": True,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "FOMOR_LLM_API_KEY",
        "temperature": 0.3,
        "timeout": 120,
    },
    "search": {"provider": "none"},
    "scoring": {
        "explore_threshold": 3.5,
        "watch_threshold": 2.0,
    },
    "topic": {"dormant_days": 30, "archive_days": 90},
    "report": {"output": "report.html"},
}


def home(root: str | Path | None = None) -> Path:
    if root:
        return Path(root).expanduser()
    env = os.environ.get("FOMOR_HOME")
    return Path(env).expanduser() if env else Path.cwd() / "data"


def paths(root: str | Path | None = None) -> dict[str, Path]:
    base = home(root)
    return {
        "root": base,
        "config": base / "config",
        "events": base / "events",
        "topics": base / "topics",
        "discoveries": base / "discoveries",
        "runtime": base / "runtime",
        "logs": base / "logs",
        "settings": base / "config" / "settings.json",
        "preferences": base / "config" / "preferences.json",
        "tasks": base / "runtime" / "tasks.json",
        "scheduler": base / "runtime" / "scheduler.json",
    }


def ensure_dirs(root: str | Path | None = None) -> dict[str, Path]:
    p = paths(root)
    for key in ("config", "events", "topics", "discoveries", "runtime", "logs"):
        p[key].mkdir(parents=True, exist_ok=True)
    return p


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(root: str | Path | None = None) -> dict:
    p = ensure_dirs(root)
    if not p["settings"].exists():
        save_settings(DEFAULT_SETTINGS, root)
        return copy.deepcopy(DEFAULT_SETTINGS)
    with open(p["settings"], encoding="utf-8") as f:
        user = json.load(f)
    return _deep_merge(DEFAULT_SETTINGS, user)


def save_settings(settings: dict, root: str | Path | None = None) -> None:
    p = ensure_dirs(root)
    tmp = p["settings"].with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p["settings"])


def load_preferences(root: str | Path | None = None) -> dict:
    p = ensure_dirs(root)
    if not p["preferences"].exists():
        return {"global": {"likes": [], "dislikes": []}, "updated_at": None}
    with open(p["preferences"], encoding="utf-8") as f:
        return json.load(f)
