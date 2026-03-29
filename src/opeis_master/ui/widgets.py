"""Reusable Qt widgets for the GUI."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from opeis_master.domain.models import ValidationIssue


def fixed_font_family() -> str:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    return font.family()


class Card(QFrame):
    """Simple bordered card."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        layout.addLayout(self.content_layout)


class IssueListWidget(QListWidget):
    """Validation issue list."""

    def set_issues(self, issues: list[ValidationIssue]) -> None:
        self.clear()
        if not issues:
            self.addItem(QListWidgetItem("当前没有告警。"))
            return

        for issue in issues:
            prefix = issue.severity.upper()
            item = QListWidgetItem(f"[{prefix}] {issue.field or '-'}: {issue.message}")
            if issue.severity == "error":
                item.setForeground(Qt.GlobalColor.red)
            elif issue.severity == "warning":
                item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                item.setForeground(Qt.GlobalColor.darkCyan)
            self.addItem(item)


class ScriptOutputPanel(QWidget):
    """Preview tabs and copy buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.summary_label = QLabel("等待预览。")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("summaryLabel")
        root.addWidget(self.summary_label)

        self.tabs = QTabWidget()
        self.comment_tab, self.comment_editor = self._make_editor_tab("注释版")
        self.minimal_tab, self.minimal_editor = self._make_editor_tab("极简版")
        self.tabs.addTab(self.comment_tab, "注释版")
        self.tabs.addTab(self.minimal_tab, "极简版")
        root.addWidget(self.tabs)

        button_row = QHBoxLayout()
        self.copy_comment_button = QPushButton("复制注释版")
        self.copy_minimal_button = QPushButton("复制极简版")
        self.copy_comment_button.clicked.connect(lambda: self._copy_text(self.comment_editor.toPlainText()))
        self.copy_minimal_button.clicked.connect(lambda: self._copy_text(self.minimal_editor.toPlainText()))
        button_row.addWidget(self.copy_comment_button)
        button_row.addWidget(self.copy_minimal_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

    def _make_editor_tab(self, title: str) -> tuple[QWidget, QPlainTextEdit]:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("panelLabel")
        layout.addWidget(label)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setFontFamily(fixed_font_family())
        layout.addWidget(editor)
        return tab, editor

    def _copy_text(self, text: str) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)

    def set_scripts(self, commented: str, minimal: str, summary: str, preview_ready: bool) -> None:
        self.comment_editor.setPlainText(commented)
        self.minimal_editor.setPlainText(minimal)
        self.summary_label.setText(summary)
        self.copy_comment_button.setEnabled(preview_ready and bool(commented.strip()))
        self.copy_minimal_button.setEnabled(preview_ready and bool(minimal.strip()))

