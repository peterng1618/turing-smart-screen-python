# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional, List, Tuple
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, 
    QVBoxLayout, QScrollArea, QWidget, QPushButton
)
from PyQt6.QtCore import Qt
from theme_editor.models.element import Element, DynamicTextElement
from theme_editor.panels.property_sections.base import PropertySection

class SensorSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Dynamic Settings", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Interval
        interval_layout = QHBoxLayout()
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.1, 60.0)
        self._interval_spin.setSingleStep(0.5)
        self._interval_spin.setSuffix(" sec")
        self._interval_spin.valueChanged.connect(lambda v: self._emit_property_changed("interval", v))
        interval_layout.addWidget(self._interval_spin, 1)
        self._layout.addRow("Refresh:", interval_layout)
        self._widgets["interval"] = self._interval_spin
        
        # Force Static
        self._force_static_check = QCheckBox("Force Static Width/Height")
        self._force_static_check.setToolTip("If checked, width/height are fixed and won't auto-resize to fit text content.")
        self._force_static_check.toggled.connect(lambda v: self._emit_property_changed("force_static", v))
        self._layout.addRow(self._force_static_check)
        self._widgets["force_static"] = self._force_static_check
        
        # Sensor Picker
        self._layout.addRow(QLabel("Insert Sensor:"))
        
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setMaximumHeight(180)
        
        self._sensors_container = QWidget()
        self._sensors_layout = QVBoxLayout(self._sensors_container)
        self._sensors_layout.setContentsMargins(2, 2, 2, 2)
        self._sensors_layout.setSpacing(4)
        
        self._setup_sensor_list()
        
        self._scroll_area.setWidget(self._sensors_container)
        self._layout.addRow(self._scroll_area)

    def _setup_sensor_list(self) -> None:
        sensor_configs = [
            ("CPU", [("CPU.PERCENTAGE", "Load", ["u", "nu", "r"]), ("CPU.TEMPERATURE", "Temp", ["u", "nu", "r"])]),
            ("GPU", [("GPU.PERCENTAGE", "Load", ["u", "nu", "r"]), ("GPU.TEMPERATURE", "Temp", ["u", "nu", "r"])]),
            ("RAM", [("MEMORY.VIRTUAL.PERCENTAGE", "Virt%", ["u", "nu", "r"]), ("MEMORY.VIRTUAL.USED", "Used", ["u", "nu", "r"])]),
            ("Net", [("NET.DOWNLOAD.RATE", "Down", ["u", "nu", "r"]), ("NET.UPLOAD.RATE", "Up", ["u", "nu", "r"])]),
            ("Date", [("DATE.DAY", "Day", ["short", "medium", "long", "full"]), ("DATE.HOUR", "Time", ["short", "medium", "long", "full"])]),
            ("Sys", [("UPTIME", "Uptime", ["FORMATTED", "SECONDS"]), ("WEATHER.TEMPERATURE", "Weather", ["u", "nu"])]),
        ]
        
        for category, items in sensor_configs:
            cat_label = QLabel(category)
            cat_label.setStyleSheet("font-weight: bold; color: #AAA; font-size: 9px; margin-top: 4px;")
            self._sensors_layout.addWidget(cat_label)
            
            for sensor_id, label, flags in items:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                for flag in flags:
                    btn = QPushButton(flag)
                    btn.setFixedSize(35, 18)
                    btn.setStyleSheet("font-size: 8px;")
                    btn.clicked.connect(self._make_insert_handler(sensor_id, flag))
                    row.addWidget(btn)
                row.addStretch()
                self._sensors_layout.addLayout(row)
        
        self._sensors_layout.addStretch()

    def _make_insert_handler(self, sensor_id: str, flag: str):
        return lambda: self._editor_state.element_changed.emit(self._current_element_id, "_insert_sensor", f"{{{sensor_id}:{flag}}}")

    def update_widgets(self, element: Element) -> None:
        if isinstance(element, DynamicTextElement):
            self._interval_spin.setValue(element.interval)
            self._force_static_check.setChecked(getattr(element, "force_static", False))

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "interval": self._interval_spin.setValue(float(value))
        elif prop_name == "force_static": self._force_static_check.setChecked(bool(value))
