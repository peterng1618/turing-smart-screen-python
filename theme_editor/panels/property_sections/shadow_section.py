# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from typing import Any, Optional
from PyQt6.QtWidgets import QCheckBox, QSpinBox, QHBoxLayout, QLabel
from theme_editor.models.element import Element, Shadow
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.widgets.color_button import ColorButton

class ShadowSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Shadow", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Enable toggle
        self._enabled_check = QCheckBox("Enable Shadow")
        self._enabled_check.toggled.connect(self._on_shadow_enabled_toggled)
        self._layout.addRow(self._enabled_check)
        self._widgets["enabled"] = self._enabled_check
        
        # Color
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(lambda v: self._on_shadow_property_changed("color", v))
        self._layout.addRow("  Color:", self._color_btn)
        self._widgets["shadow_color"] = self._color_btn
        
        # Blur
        self._blur_spin = QSpinBox()
        self._blur_spin.setRange(0, 100)
        self._blur_spin.valueChanged.connect(lambda v: self._on_shadow_property_changed("blur", v))
        self._layout.addRow("  Blur:", self._blur_spin)
        self._widgets["shadow_blur"] = self._blur_spin
        
        # Offsets
        offset_layout = QHBoxLayout()
        self._offset_x_spin = QSpinBox()
        self._offset_x_spin.setRange(-100, 100)
        self._offset_x_spin.valueChanged.connect(lambda v: self._on_shadow_property_changed("offset_x", v))
        offset_layout.addWidget(QLabel("X:"))
        offset_layout.addWidget(self._offset_x_spin)
        self._widgets["shadow_offset_x"] = self._offset_x_spin
        
        self._offset_y_spin = QSpinBox()
        self._offset_y_spin.setRange(-100, 100)
        self._offset_y_spin.valueChanged.connect(lambda v: self._on_shadow_property_changed("offset_y", v))
        offset_layout.addWidget(QLabel("Y:"))
        offset_layout.addWidget(self._offset_y_spin)
        self._widgets["shadow_offset_y"] = self._offset_y_spin
        
        self._layout.addRow("  Offset:", offset_layout)
        
    def update_widgets(self, element: Element) -> None:
        has_shadow = hasattr(element, "shadow") and element.shadow is not None
        self._enabled_check.setChecked(has_shadow)
        
        if has_shadow and element.shadow:
            self._color_btn.show(); self._color_btn.setEnabled(True)
            self._blur_spin.show(); self._blur_spin.setEnabled(True)
            self._offset_x_spin.show(); self._offset_x_spin.setEnabled(True)
            self._offset_y_spin.show(); self._offset_y_spin.setEnabled(True)
            
            self._color_btn.color = element.shadow.color
            self._blur_spin.setValue(int(element.shadow.blur))
            self._offset_x_spin.setValue(int(element.shadow.offset_x))
            self._offset_y_spin.setValue(int(element.shadow.offset_y))
        else:
            self._color_btn.hide()
            self._blur_spin.hide()
            self._offset_x_spin.hide()
            self._offset_y_spin.hide()

    def _on_shadow_enabled_toggled(self, checked: bool) -> None:
        if self._updating or not self._current_element_id: return
        element = self._model.get_element(self._current_element_id)
        if not element: return
        
        if checked:
            new_shadow = Shadow(color=(0, 0, 0, 150), blur=5, offset_x=2, offset_y=2)
            self._emit_property_changed("shadow", new_shadow)
        else:
            self._emit_property_changed("shadow", None)
            
    def _on_shadow_property_changed(self, prop_name: str, value: Any) -> None:
        if self._updating or not self._current_element_id: return
        element = self._model.get_element(self._current_element_id)
        if not (hasattr(element, "shadow") and element.shadow): return
        
        new_shadow = copy.copy(element.shadow)
        setattr(new_shadow, prop_name, value)
        self._emit_property_changed("shadow", new_shadow)
        
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "shadow":
            self.update_widgets(self._model.get_element(self._current_element_id))
        elif prop_name == "shadow.color": self._color_btn.color = value
        elif prop_name == "shadow.blur": self._blur_spin.setValue(int(value))
        elif prop_name == "shadow.offset_x": self._offset_x_spin.setValue(int(value))
        elif prop_name == "shadow.offset_y": self._offset_y_spin.setValue(int(value))
