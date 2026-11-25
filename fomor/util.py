"""Small shared helpers."""

from __future__ import annotations

import datetime as _dt
import uuid


def now() -> _dt.datetime:
    return _dt.datetime.now().astimezone()


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def today_str() -> str:
    return now().strftime("%Y-%m-%d")


def new_id(prefix: str) -> str:
    return f"{prefix}_{now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"


def parse_iso(value: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(value)


def truncate(text: str, limit: int = 40) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"
