"""GUI-facing data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Iterable, Literal

Severity = Literal["error", "warning"]


@dataclass(slots=True)
class Issue:
    message: str
    field: str | None = None
    severity: Severity = "error"

    def as_html(self) -> str:
        color = "#b91c1c" if self.severity == "error" else "#b45309"
        label = "错误" if self.severity == "error" else "告警"
        field = f"<code>{escape(self.field)}</code>: " if self.field else ""
        return f"<div style='color:{color}; margin:2px 0;'>[{label}] {field}{escape(self.message)}</div>"


@dataclass(slots=True)
class ScriptBundle:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    summary: str = ""
    script: str = ""

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def all_issues(self) -> list[Issue]:
        return [*self.errors, *self.warnings]

    @classmethod
    def empty(cls) -> "ScriptBundle":
        return cls()


def normalize_result(raw: Any) -> ScriptBundle:
    if raw is None:
        return ScriptBundle.empty()
    if isinstance(raw, ScriptBundle):
        return raw
    if isinstance(raw, dict):
        return ScriptBundle(
            errors=_coerce_issues(raw.get("errors"), "error"),
            warnings=_coerce_issues(raw.get("warnings"), "warning"),
            summary=str(raw.get("summary", "") or "").strip(),
            script=str(raw.get("script", "") or "").rstrip(),
        )

    return ScriptBundle(
        errors=_coerce_issues(getattr(raw, "errors", None), "error"),
        warnings=_coerce_issues(getattr(raw, "warnings", None), "warning"),
        summary=str(getattr(raw, "summary", "") or "").strip(),
        script=str(getattr(raw, "script", "") or "").rstrip(),
    )


def _coerce_issues(raw: Any, severity: Severity) -> list[Issue]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [Issue(message=raw, severity=severity)]
    if isinstance(raw, dict):
        return [_coerce_issue(raw, severity)]
    if isinstance(raw, Iterable):
        return [_coerce_issue(item, severity) for item in raw]
    return [Issue(message=str(raw), severity=severity)]


def _coerce_issue(raw: Any, severity: Severity) -> Issue:
    if isinstance(raw, Issue):
        return raw
    if isinstance(raw, str):
        return Issue(message=raw, severity=severity)
    if isinstance(raw, dict):
        message = raw.get("message") or raw.get("text") or raw.get("detail") or ""
        field = raw.get("field")
        level = raw.get("severity") or raw.get("level") or severity
        return Issue(message=str(message), field=str(field) if field else None, severity=_normalize_severity(level))
    message = getattr(raw, "message", None) or getattr(raw, "text", None) or str(raw)
    field = getattr(raw, "field", None)
    level = getattr(raw, "severity", None) or getattr(raw, "level", None) or severity
    return Issue(message=str(message), field=str(field) if field else None, severity=_normalize_severity(level))


def _normalize_severity(value: Any) -> Severity:
    text = str(value).strip().lower()
    return "warning" if text == "warning" else "error"
