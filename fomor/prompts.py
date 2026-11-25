"""Prompt loading and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).parent / "prompts"


def _render(template: str, variables: dict[str, Any]) -> str:
    for key, value in variables.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        template = template.replace("{{" + key + "}}", value)
    return template


def load_system() -> str:
    return (PROMPT_DIR / "system.md").read_text(encoding="utf-8")


def build_prompt(task: str, variables: dict[str, Any]) -> str:
    template = (PROMPT_DIR / f"{task}.md").read_text(encoding="utf-8")
    return load_system() + "\n\n---\n\n" + _render(template, variables)


def describe_tasks() -> list[str]:
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md") if path.stem != "system")
