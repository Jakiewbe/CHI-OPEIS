"""Preset document persistence for the GUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import GuiDraftState, SequencePresetDocument


class PresetFileService:
    def __init__(self, recent_store_path: Path | None = None) -> None:
        self.recent_store_path = recent_store_path or (Path.home() / ".chi_generator" / "recent_presets.json")

    def normalize_preset_path(self, raw_path: str | Path) -> Path:
        path = Path(raw_path).expanduser().resolve()
        if path.suffix.lower() != ".chi-preset":
            path = path.with_suffix(".chi-preset")
        return path

    def save_preset(self, path: str | Path, state: GuiDraftState) -> Path:
        resolved = self.normalize_preset_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        document = SequencePresetDocument(workspace_mode=state.workspace_mode, state=state)
        resolved.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        self.record_recent_file(resolved)
        return resolved

    def load_preset(self, path: str | Path) -> GuiDraftState:
        resolved = Path(path).expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        migrated = self._migrate_payload(payload)
        document = SequencePresetDocument.model_validate(migrated)
        self.record_recent_file(resolved)
        return document.state

    def load_recent_files(self) -> list[Path]:
        store = self.recent_store_path
        if not store.exists():
            return []
        try:
            payload = json.loads(store.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        recent_paths: list[Path] = []
        for raw_path in payload.get("recent_files", []):
            path = Path(raw_path)
            if path.exists():
                recent_paths.append(path)
        return recent_paths

    def record_recent_file(self, path: str | Path) -> None:
        resolved = Path(path).expanduser().resolve()
        recent_files = [resolved, *[item for item in self.load_recent_files() if item != resolved]]
        trimmed = recent_files[:8]
        self.recent_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.recent_store_path.write_text(
            json.dumps({"recent_files": [str(item) for item in trimmed]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _migrate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        migrated = dict(payload)
        version = int(migrated.get("version", 1))
        state = migrated.get("state")
        if not isinstance(state, dict):
            return migrated

        state = dict(state)
        if version < 4:
            state.setdefault("current_basis_mode", "material")
            state.setdefault("reference_rate_c", "1")
            state.setdefault("reference_current_a", "0.000865")
        migrated["state"] = state
        migrated["version"] = 4
        return migrated


__all__ = ["PresetFileService"]
