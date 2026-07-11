"""Script preview and guarded copy controls."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import PlainTextEdit, PrimaryPushButton, PushButton

from .widgets import ScriptEditor, SummaryPanel, fixed_font_family


class ScriptOutputPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._copy_feedback_timer = QTimer(self)
        self._copy_feedback_timer.setSingleShot(True)
        self._copy_feedback_timer.setInterval(1200)
        self._copy_feedback_timer.timeout.connect(self._reset_copy_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        self.summary_label = SummaryPanel(self)
        self.summary_label.setPlainText("等待预览生成")
        self.summary_label.setObjectName("summaryPanel")
        root.addWidget(self.summary_label, 0)
        self.editor_title = QLabel("极简脚本", self)
        self.editor_title.setObjectName("panelLabel")
        root.addWidget(self.editor_title)
        self.minimal_editor = ScriptEditor()
        self.minimal_editor.setReadOnly(True)
        self.minimal_editor.setLineWrapMode(PlainTextEdit.LineWrapMode.NoWrap)
        font = self.minimal_editor.font()
        font.setFamily(fixed_font_family())
        self.minimal_editor.setFont(font)
        self.minimal_editor.setMinimumHeight(260)
        root.addWidget(self.minimal_editor, 1)
        button_row = QHBoxLayout()
        self.confirm_risk_button = PushButton(self)
        self.confirm_risk_button.setText("我已确认高风险，允许复制")
        self.confirm_risk_button.setVisible(False)
        button_row.addWidget(self.confirm_risk_button)
        self.copy_minimal_button = PrimaryPushButton(self)
        self.copy_minimal_button.setText("复制极简脚本")
        self.copy_minimal_button.clicked.connect(self._handle_copy_minimal)
        button_row.addWidget(self.copy_minimal_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

    def _set_editor_text(self, editor: PlainTextEdit, text: str) -> None:
        if editor.toPlainText() == text:
            return
        vertical_value = editor.verticalScrollBar().value()
        horizontal_value = editor.horizontalScrollBar().value()
        editor.setPlainText(text)
        editor.verticalScrollBar().setValue(vertical_value)
        editor.horizontalScrollBar().setValue(horizontal_value)

    def _handle_copy_minimal(self) -> None:
        text = self.minimal_editor.toPlainText()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self.copy_minimal_button.setText("已复制")
        self._copy_feedback_timer.start()

    def _reset_copy_button(self) -> None:
        self.copy_minimal_button.setText("复制极简脚本")

    def set_scripts(
        self,
        commented: str,
        minimal: str,
        summary: str,
        can_copy: bool,
        *,
        requires_confirmation: bool = False,
        confirmed: bool = False,
    ) -> None:
        del commented
        self._set_editor_text(self.minimal_editor, minimal)
        self.summary_label.setText(summary)
        has_script = bool(minimal.strip())
        confirmation_pending = can_copy and has_script and requires_confirmation and not confirmed
        self.confirm_risk_button.setVisible(confirmation_pending)
        copy_enabled = can_copy and has_script and not confirmation_pending
        self.copy_minimal_button.setEnabled(copy_enabled)
        if not copy_enabled:
            self._reset_copy_button()


__all__ = ["ScriptOutputPanel"]

