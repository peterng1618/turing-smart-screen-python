# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox
from PyQt6.QtCore import Qt
from theme_editor.models.element import Element, RectangleElement, LineElement
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.widgets.color_button import ColorButton

class AppearanceSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Appearance", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Color
        self._color_label = QLabel("Color:")
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(lambda v: self._emit_property_changed("color", v))
        self._layout.addRow(self._color_label, self._color_btn)
        self._widgets["color"] = self._color_btn
        
        # Opacity
        opacity_layout = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        
        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setRange(0.0, 1.0)
        self._opacity_spin.setSingleStep(0.1)
        
        self._opacity_slider.valueChanged.connect(lambda v: self._opacity_spin.setValue(v / 100))
        self._opacity_spin.valueChanged.connect(lambda v: self._emit_property_changed("opacity", v))
        
        opacity_layout.addWidget(self._opacity_slider)
        opacity_layout.addWidget(self._opacity_spin)
        self._layout.addRow("Opacity:", opacity_layout)
        self._widgets["opacity"] = self._opacity_spin
        
        # Radius (Corner radius for Rectangles)
        self._radius_label = QLabel("Corner Radius:")
        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(0, 999)
        self._radius_spin.valueChanged.connect(lambda v: self._emit_property_changed("radius", v))
        self._layout.addRow(self._radius_label, self._radius_spin)
        self._widgets["radius"] = self._radius_spin
        
        # Shear (for Rectangles)
        self._shear_layout = QHBoxLayout()
        self._shear_left = QDoubleSpinBox()
        self._shear_left.setRange(-89, 89)
        self._shear_left.setSuffix("°")
        self._shear_left.valueChanged.connect(lambda v: self._emit_property_changed("shear_left", v))
        self._shear_layout.addWidget(QLabel("L:"))
        self._shear_layout.addWidget(self._shear_left)
        self._widgets["shear_left"] = self._shear_left
        
        self._shear_right = QDoubleSpinBox()
        self._shear_right.setRange(-89, 89)
        self._shear_right.setSuffix("°")
        self._shear_right.valueChanged.connect(lambda v: self._emit_property_changed("shear_right", v))
        self._shear_layout.addWidget(QLabel("R:"))
        self._shear_layout.addWidget(self._shear_right)
        self._widgets["shear_right"] = self._shear_right
        
        self._shear_label = QLabel("Shear:")
        self._layout.addRow(self._shear_label, self._shear_layout)
        
        # Line width and cap
        self._line_width_label = QLabel("Stroke Width:")
        self._line_width_spin = QSpinBox()
        self._line_width_spin.setRange(1, 100)
        self._line_width_spin.valueChanged.connect(lambda v: self._emit_property_changed("line_width", v))
        self._layout.addRow(self._line_width_label, self._line_width_spin)
        self._widgets["line_width"] = self._line_width_spin
        
        self._cap_label = QLabel("End Cap:")
        self._cap_combo = QComboBox()
        self._cap_combo.addItems(["butt", "round"])
        self._cap_combo.currentTextChanged.connect(lambda v: self._emit_property_changed("end_cap", v))
        self._layout.addRow(self._cap_label, self._cap_combo)
        self._widgets["end_cap"] = self._cap_combo
        
    def update_widgets(self, element: Element) -> None:
        # Color
        if hasattr(element, "color"):
            self._color_label.show()
            self._color_btn.show()
            self._color_btn.color = element.color
        else:
            self._color_label.hide()
            self._color_btn.hide()
            
        # Opacity
        self._opacity_spin.setValue(element.opacity)
        self._opacity_slider.setValue(int(element.opacity * 100))
        
        # Radius
        if isinstance(element, RectangleElement):
            self._radius_label.show()
            self._radius_spin.show()
            self._radius_spin.setValue(element.radius)
        else:
            self._radius_label.hide()
            self._radius_spin.hide()
            
        # Shear
        if isinstance(element, RectangleElement):
            self._shear_label.show()
            self._shear_layout.itemAt(0).widget().show() # L label
            self._shear_left.show()
            self._shear_layout.itemAt(2).widget().show() # R label
            self._shear_right.show()
            self._shear_left.setValue(element.shear_left)
            self._shear_right.setValue(element.shear_right)
        else:
            self._shear_label.hide()
            self._shear_layout.itemAt(0).widget().hide() 
            self._shear_left.hide()
            self._shear_layout.itemAt(2).widget().hide() 
            self._shear_right.hide()
            
        # Line properties
        if isinstance(element, LineElement):
            self._line_width_label.show()
            self._line_width_spin.show()
            self._line_width_spin.setValue(element.line_width)
            self._cap_label.show()
            self._cap_combo.show()
            self._cap_combo.setCurrentText(element.end_cap)
        else:
            self._line_width_label.hide()
            self._line_width_spin.hide()
            self._cap_label.hide()
            self._cap_combo.hide()
            
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "color": self._color_btn.color = value
        elif prop_name == "opacity":
            self._opacity_spin.setValue(float(value))
            self._opacity_slider.setValue(int(float(value) * 100))
        elif prop_name == "radius": self._radius_spin.setValue(int(value))
        elif prop_name == "shear_left": self._shear_left.setValue(float(value))
        elif prop_name == "shear_right": self._shear_right.setValue(float(value))
        elif prop_name == "line_width": self._line_width_spin.setValue(int(value))
        elif prop_name == "end_cap": self._cap_combo.setCurrentText(str(value))
