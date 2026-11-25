"""Load the single-file CLI as an importable module for tests."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fomor"
_loader = importlib.machinery.SourceFileLoader("fomor", str(SCRIPT))
_spec = importlib.util.spec_from_loader("fomor", _loader)
fomor = importlib.util.module_from_spec(_spec)
sys.modules["fomor"] = fomor
_loader.exec_module(fomor)

# The implementation is one file; expose its sections under the old module
# names so tests read naturally (`from fomor.store import append_event`).
for _name in ("utils", "paths", "config", "store", "prompts", "llm", "feedback", "scheduler", "pipeline", "cli"):
    sys.modules[f"fomor.{_name}"] = fomor
