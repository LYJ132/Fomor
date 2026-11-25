"""Prompt loading and rendering.

Prompt templates live in ``references/`` at the repository root, not inside the
Python package: they are static, human-readable reference material (stage
contracts and JSON shapes), and are kept next to the other references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "references"

TASK_FILES = {
    "system": "00-system.md",
    "aggregate": "01-aggregate.md",
    "understand": "02-understand.md",
    "opportunity": "03-opportunity.md",
    "explore": "04-explore.md",
    "discovery": "05-discovery.md",
    "feedback": "06-feedback.md",
}


def _render(template: str, variables: dict[str, Any]) -> str:
    for key, value in variables.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        template = template.replace("{{" + key + "}}", value)
    return template


def load_system() -> str:
    return (REFERENCE_DIR / TASK_FILES["system"]).read_text(encoding="utf-8")


def build_prompt(task: str, variables: dict[str, Any]) -> str:
    if task == "system" or task not in TASK_FILES:
        raise KeyError(f"unknown prompt task: {task}")
    template = (REFERENCE_DIR / TASK_FILES[task]).read_text(encoding="utf-8")
    return load_system() + "\n\n---\n\n" + _render(template, variables)


def describe_tasks() -> list[str]:
    return sorted(name for name in TASK_FILES if name != "system")
