"""Adapters that bridge the GUI to the domain service."""

from __future__ import annotations

from dataclasses import dataclass

from opeis_master.domain.services import ScriptGenerationService

from .models import PreviewArtifact, ScriptFormState
from .validation import evaluate_local_validation


@dataclass(slots=True)
class DomainValidationPreviewAdapter:
    """GUI backend that reuses the current domain validator."""

    validator_service: ScriptGenerationService

    def preview(self, state: ScriptFormState) -> PreviewArtifact:
        validation = evaluate_local_validation(state)
        status = "可以生成脚本" if validation.can_generate else "存在错误，脚本未生成"
        commented = self._build_placeholder_script(state, verbose=True)
        minimal = self._build_placeholder_script(state, verbose=False)
        return PreviewArtifact(
            commented_script=commented,
            minimal_script=minimal,
            validation=validation,
            summary=status,
            preview_ready=validation.can_generate,
        )

    def _build_placeholder_script(self, state: ScriptFormState, *, verbose: bool) -> str:
        lines = [
            "# Script generation backend is not connected yet.",
            f"# workflow={state.workflow.value}",
            f"# technique={state.technique.value}",
            f"# output_variant={state.output_variant.value}",
        ]
        if verbose:
            lines.extend(
                [
                    f"# eh={state.eh_v}",
                    f"# el={state.el_v}",
                    f"# cl={state.cl}",
                    f"# fh={state.imp_fh_hz}",
                    f"# fl={state.imp_fl_hz}",
                    f"# points_per_decade={state.points_per_decade}",
                ]
            )
        return "\n".join(lines)

