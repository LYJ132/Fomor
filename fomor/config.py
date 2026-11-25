"""Configuration defaults and loading."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .paths import FomorPaths
from .utils import atomic_write_json, read_json

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "timezone": "Asia/Shanghai",
    "schedule": {
        "hour": 3,
        "minute": 0,
        # A run is considered due when it is older than the 03:00 cutoff.
        # The SessionStart catch-up uses this value to avoid running twice.
        "catch_up_after_hours": 20,
    },
    "retention": {
        "event_days": 8,
        "feedback_days": 7,
        "tombstone_days": 90,
        "dedupe_days": 2,
    },
    "llm": {
        "mode": "mock",  # mock | traecli | openai
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "FOMOR_LLM_API_KEY",
        "temperature": 0.3,
        "timeout": 180,
        "traecli": "traecli",
    },
    "analysis": {
        "max_events_per_run": 200,
        "max_topics_per_run": 3,
        "min_events_for_discovery": 1,
    },
    "scoring": {
        "explore_threshold": 3.5,
        "watch_threshold": 2.0,
    },
    "feedback": {
        "strong_similarity": 0.18,
        "weak_similarity": 0.06,
    },
    "search": {
        "provider": "none",
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(paths: FomorPaths) -> dict[str, Any]:
    user_config = read_json(paths.settings_file, default={}) or {}
    return _merge(DEFAULT_CONFIG, user_config)


def save_config(paths: FomorPaths, config: dict[str, Any]) -> None:
    atomic_write_json(paths.settings_file, config)


def ensure_initialized(paths: FomorPaths) -> dict[str, Any]:
    paths.ensure()
    config = load_config(paths)
    if not paths.settings_file.exists():
        save_config(paths, config)
    return config
