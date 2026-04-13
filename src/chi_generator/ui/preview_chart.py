"""Planning chart widget for sequence previews."""

from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QScatterSeries, QValueAxis
from PySide6.QtCore import QMargins, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from chi_generator.domain.models import PhaseKind, SequenceScriptBundle


class ScriptPreviewChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.chart = QChart()
        self.chart.setTheme(QChart.ChartTheme.ChartThemeDark)
        self.chart.setBackgroundVisible(False)
        self.chart.layout().setContentsMargins(10, 8, 10, 8)
        self.chart.setMargins(QMargins(12, 8, 18, 12))
        self.chart.legend().hide()

        self.axis_x = QValueAxis()
        self.axis_x.setTitleText("时间 / min")
        self.axis_left = QValueAxis()
        self.axis_left.setTitleText("电流 / A")
        self.axis_right = QValueAxis()
        self.axis_right.setTitleText("预测 SoC / %")
        for axis in (self.axis_x, self.axis_left, self.axis_right):
            axis.setLabelsColor(QColor("#aab2bf"))
            axis.setGridLineColor(QColor("#3e4451"))
            axis.setTitleBrush(QColor("#c9d1d9"))

        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_left, Qt.AlignmentFlag.AlignLeft)
        self.chart.addAxis(self.axis_right, Qt.AlignmentFlag.AlignRight)

        self.current_series = QLineSeries(self.chart)
        self.current_series.setColor(QColor("#49D3B7"))

        self.soc_series = QLineSeries(self.chart)
        self.soc_series.setColor(QColor("#F2994A"))
        pen = QPen(QColor("#F2994A"))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(2)
        self.soc_series.setPen(pen)

        self.eis_series = QScatterSeries(self.chart)
        self.eis_series.setColor(QColor("#F6C945"))
        self.eis_series.setMarkerSize(10.0)
        self.eis_series.setBorderColor(QColor("#00000000"))

        self.risk_series = QScatterSeries(self.chart)
        self.risk_series.setColor(QColor("#FF5D73"))
        self.risk_series.setMarkerSize(12.0)
        self.risk_series.setBorderColor(QColor("#00000000"))

        for series in (self.current_series, self.soc_series, self.eis_series, self.risk_series):
            self.chart.addSeries(series)
            series.attachAxis(self.axis_x)
        self.current_series.attachAxis(self.axis_left)
        self.eis_series.attachAxis(self.axis_left)
        self.risk_series.attachAxis(self.axis_left)
        self.soc_series.attachAxis(self.axis_right)

        self.view = QChartView(self.chart, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.setMinimumHeight(280)
        layout.addWidget(self.view)

    def set_preview(self, bundle: SequenceScriptBundle | None) -> None:
        self.current_series.clear()
        self.soc_series.clear()
        self.eis_series.clear()
        self.risk_series.clear()
        if bundle is None or not bundle.phase_plans:
            self.axis_x.setRange(0.0, 1.0)
            self.axis_left.setRange(-1.0, 1.0)
            self.axis_right.setRange(0.0, 100.0)
            return

        points: list[QPointF] = [QPointF(0.0, 0.0)]
        current_floor = 0.0
        current_ceil = 0.0
        for plan in bundle.phase_plans:
            start_min = plan.start_time_s / 60.0
            end_min = plan.end_time_s / 60.0
            if plan.phase_kind is PhaseKind.REST:
                points.append(QPointF(start_min, 0.0))
                points.append(QPointF(end_min, 0.0))
                continue
            current_a = float(plan.operating_current_a or 0.0)
            current_floor = min(current_floor, current_a)
            current_ceil = max(current_ceil, current_a)
            points.append(QPointF(start_min, current_a))
            points.append(QPointF(end_min, current_a))
            points.append(QPointF(end_min, 0.0))
            for marker_s in plan.eis_marker_times_s:
                target = self.risk_series if marker_s in plan.lost_eis_marker_times_s else self.eis_series
                target.append(marker_s / 60.0, current_a)
        for point in points:
            self.current_series.append(point)
        for soc_point in bundle.soc_trace:
            self.soc_series.append(soc_point.time_s / 60.0, soc_point.soc_percent)

        max_time = max(bundle.total_wall_clock_s / 60.0, 1.0)
        span = max(abs(current_floor), abs(current_ceil), 1e-6)
        self.axis_x.setRange(0.0, max_time * 1.03)
        self.axis_left.setRange(-span * 1.2, span * 1.2)
        self.axis_right.setRange(0.0, 100.0)

    def set_bundle(self, bundle) -> None:
        if isinstance(bundle, SequenceScriptBundle):
            self.set_preview(bundle)
        else:
            self.set_preview(None)


__all__ = ["ScriptPreviewChart"]
