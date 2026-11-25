"""Filesystem layout for Fomor.

User data lives in ``~/.fomor`` by default.  The repository only contains
code, prompts and Trae package files, so upgrading the plugin can never
overwrite long-term memory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FomorPaths:
    root: Path

    @classmethod
    def resolve(cls, home: str | os.PathLike[str] | None = None) -> "FomorPaths":
        if home:
            root = Path(home).expanduser()
        else:
            root = Path(os.environ.get("FOMOR_HOME", "~/.fomor")).expanduser()
        return cls(root=root)

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    @property
    def topics_dir(self) -> Path:
        return self.root / "topics"

    @property
    def discoveries_dir(self) -> Path:
        return self.root / "discoveries"

    @property
    def pending_dir(self) -> Path:
        return self.discoveries_dir / "pending"

    @property
    def promoted_dir(self) -> Path:
        return self.discoveries_dir / "promoted"

    @property
    def tombstones_dir(self) -> Path:
        return self.root / "tombstones"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def state_file(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def runs_file(self) -> Path:
        return self.runtime_dir / "runs.json"

    @property
    def lock_file(self) -> Path:
        return self.runtime_dir / "analyze.lock"

    @property
    def catchup_lock_file(self) -> Path:
        return self.runtime_dir / "catchup.lock"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def backup_dir(self) -> Path:
        return self.root / "backup"

    def ensure(self) -> "FomorPaths":
        for path in (
            self.config_dir,
            self.events_dir,
            self.topics_dir,
            self.pending_dir,
            self.promoted_dir,
            self.tombstones_dir,
            self.reports_dir,
            self.runtime_dir,
            self.logs_dir,
            self.backup_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        return self

    def event_file(self, day: str) -> Path:
        return self.events_dir / f"{day}.jsonl"
