from __future__ import annotations

import json
from pathlib import Path

from chi_generator.ui.presets import PresetFileService


def test_old_preset_is_migrated_to_reference_basis_fields() -> None:
    artifact_dir = Path.cwd() / ".pytest-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    preset_path = artifact_dir / "legacy-reference-basis.chi-preset"
    recent_path = artifact_dir / "recent-presets.json"
    preset_path.write_text(
        json.dumps(
            {
                "version": 3,
                "workspace_mode": "sequence",
                "state": {
                    "workspace_mode": "sequence",
                    "scheme_name": "demo",
                    "file_prefix": "CHI",
                    "export_dir": "",
                    "active_material_mg": "1",
                    "theoretical_capacity_mah_mg": "865",
                    "phases": [],
                    "workflow_items": [],
                    "use_open_circuit_init_e": True,
                    "init_e_v": "3.2",
                    "high_frequency_hz": "100000",
                    "low_frequency_hz": "0.01",
                    "amplitude_v": "0.005",
                    "quiet_time_s": "2",
                    "pulse_relaxation_mode": "rest",
                    "pulse_relaxation_time_s": "60",
                    "pulse_relaxation_current_mode": "rate",
                    "pulse_relaxation_rate_c": "0.02",
                    "pulse_relaxation_current_a": "0.00002",
                    "pulse_current_mode": "rate",
                    "pulse_current_rate_c": "1",
                    "pulse_current_a": "0.001",
                    "pulse_duration_s": "5",
                    "pulse_count": "1",
                    "pulse_sample_interval_s": "0.001",
                    "pulse_upper_voltage_v": "4",
                    "pulse_lower_voltage_v": "-1",
                    "pulse_pre_wait_s": "0",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = PresetFileService(recent_store_path=recent_path).load_preset(preset_path)

    assert state.current_basis_mode.value == "material"
    assert state.reference_rate_c == "1"
    assert state.reference_current_a == "0.000865"
