# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSpinBox
from theme_editor.models.element import Element, TriangleElement, LineElement
from theme_editor.panels.property_sections.base import PropertySection

class TransformSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Transform", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Position
        pos_layout = QHBoxLayout()
        self._x_spin = QSpinBox()
        self._x_spin.setRange(-9999, 9999)
        self._x_spin.valueChanged.connect(lambda v: self._emit_property_changed("x", v))
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(self._x_spin)
        self._widgets["x"] = self._x_spin
        
        self._y_spin = QSpinBox()
        self._y_spin.setRange(-9999, 9999)
        self._y_spin.valueChanged.connect(lambda v: self._emit_property_changed("y", v))
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(self._y_spin)
        self._widgets["y"] = self._y_spin
        
        self._layout.addRow("Position:", pos_layout)
        
        # Size (Simplified for basic demonstration)
        size_layout = QHBoxLayout()
        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 9999)
        self._w_spin.valueChanged.connect(lambda v: self._emit_property_changed("width", v))
        size_layout.addWidget(QLabel("W:"))
        size_layout.addWidget(self._w_spin)
        self._widgets["width"] = self._w_spin
        
        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 9999)
        self._h_spin.valueChanged.connect(lambda v: self._emit_property_changed("height", v))
        size_layout.addWidget(QLabel("H:"))
        size_layout.addWidget(self._h_spin)
        self._widgets["height"] = self._h_spin
        
        self._layout.addRow("Size:", size_layout)
        
    def update_widgets(self, element: Element) -> None:
        self._x_spin.setValue(element.x)
        self._y_spin.setValue(element.y)
        
        if hasattr(element, "width"):
            self._w_spin.setValue(element.width)
            self._w_spin.setEnabled(True)
        else:
            self._w_spin.setEnabled(False)
            
        if hasattr(element, "height"):
            self._h_spin.setValue(element.height)
            self._h_spin.setEnabled(True)
        else:
            self._h_spin.setEnabled(False)
            
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "x": self._x_spin.setValue(int(value))
        elif prop_name == "y": self._y_spin.setValue(int(value))
        elif prop_name == "width": self._w_spin.setValue(int(value))
        elif prop_name == "height": self._h_spin.setValue(int(value))
