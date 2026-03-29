"""Preset document persistence for the workstep editor."""

from __future__ import annotations

import json
from pathlib import Path

from chi_generator.ui.models import GuiState, RecentPresetDocument, SequencePresetDocument, WorkspaceMode


PRESET_EXTENSION = ".chi-preset"
MAX_RECENT_PRESETS = 8


class PresetService:
    def __init__(self, recent_file: Path | None = None) -> None:
        self.recent_file = recent_file or self.default_recent_file()

    @staticmethod
    def default_recent_file() -> Path:
        base = Path.cwd() / ".chi-generator"
        base.mkdir(parents=True, exist_ok=True)
        return base / "recent-presets.json"

    def save_state(self, path: Path, state: GuiState) -> Path:
        path = self._normalize_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = SequencePresetDocument(workspace_mode=state.workspace_mode, state=state)
        path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        self.mark_recent(path)
        return path

    def load_state(self, path: Path) -> GuiState:
        document = SequencePresetDocument.model_validate_json(path.read_text(encoding="utf-8"))
        self.mark_recent(path)
        return document.state.model_copy(update={"workspace_mode": WorkspaceMode(document.workspace_mode)})

    def list_recent(self) -> list[Path]:
        if not self.recent_file.exists():
            return []
        try:
            document = RecentPresetDocument.model_validate_json(self.recent_file.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [Path(item) for item in document.recent_files if Path(item).exists()]

    def mark_recent(self, path: Path) -> None:
        path = path.resolve()
        recents = [path, *[item.resolve() for item in self.list_recent() if item.resolve() != path]]
        document = RecentPresetDocument(recent_files=[str(item) for item in recents[:MAX_RECENT_PRESETS]])
        self.recent_file.parent.mkdir(parents=True, exist_ok=True)
        self.recent_file.write_text(document.model_dump_json(indent=2), encoding="utf-8")

    def _normalize_path(self, path: Path) -> Path:
        if path.suffix.lower() != PRESET_EXTENSION:
            return path.with_suffix(PRESET_EXTENSION)
        return path


__all__ = ["MAX_RECENT_PRESETS", "PRESET_EXTENSION", "PresetService"]
