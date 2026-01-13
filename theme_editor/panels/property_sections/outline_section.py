# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from typing import Any, Optional
from PyQt6.QtWidgets import QCheckBox, QSpinBox, QComboBox, QLineEdit, QFrame
from theme_editor.models.element import Element, Outline
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.widgets.color_button import ColorButton

class OutlineSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Outline", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Enable toggle
        self._enabled_check = QCheckBox("Enable Outline")
        self._enabled_check.toggled.connect(self._on_outline_enabled_toggled)
        self._layout.addRow(self._enabled_check)
        self._widgets["enabled"] = self._enabled_check
        
        # Width
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 100)
        self._width_spin.valueChanged.connect(lambda v: self._on_outline_property_changed("width", v))
        self._layout.addRow("  Width:", self._width_spin)
        self._widgets["outline_width"] = self._width_spin
        
        # Color
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(lambda v: self._on_outline_property_changed("color", v))
        self._layout.addRow("  Color:", self._color_btn)
        self._widgets["outline_color"] = self._color_btn
        
        # Cap style
        self._cap_combo = QComboBox()
        self._cap_combo.addItems(["butt", "round", "square"])
        self._cap_combo.currentTextChanged.connect(lambda v: self._on_outline_property_changed("cap", v))
        self._layout.addRow("  Cap:", self._cap_combo)
        self._widgets["outline_cap"] = self._cap_combo
        
        # Dash array
        self._dash_edit = QLineEdit()
        self._dash_edit.setPlaceholderText("e.g. 5, 2")
        self._dash_edit.textEdited.connect(self._on_dash_changed)
        self._layout.addRow("  Dash Pattern:", self._dash_edit)
        self._widgets["outline_dash"] = self._dash_edit
        
    def update_widgets(self, element: Element) -> None:
        has_outline = hasattr(element, "outline") and element.outline is not None
        self._enabled_check.setChecked(has_outline)
        
        if has_outline and element.outline:
            self._width_spin.show(); self._width_spin.setEnabled(True)
            self._color_btn.show(); self._color_btn.setEnabled(True)
            self._cap_combo.show(); self._cap_combo.setEnabled(True)
            self._dash_edit.show(); self._dash_edit.setEnabled(True)
            
            self._width_spin.setValue(element.outline.width)
            self._color_btn.color = element.outline.color
            self._cap_combo.setCurrentText(element.outline.cap)
            
            dash = element.outline.dash_array
            self._dash_edit.setText(", ".join(map(str, dash)) if dash else "")
        else:
            self._width_spin.hide()
            self._color_btn.hide()
            self._cap_combo.hide()
            self._dash_edit.hide()

    def _on_outline_enabled_toggled(self, checked: bool) -> None:
        if self._updating or not self._current_element_id: return
        element = self._model.get_element(self._current_element_id)
        if not element: return
        
        if checked:
            new_outline = Outline(width=1, color=(255, 255, 255, 255), cap="butt")
            self._emit_property_changed("outline", new_outline)
        else:
            self._emit_property_changed("outline", None)
            
    def _on_outline_property_changed(self, prop_name: str, value: Any) -> None:
        if self._updating or not self._current_element_id: return
        element = self._model.get_element(self._current_element_id)
        if not (hasattr(element, "outline") and element.outline): return
        
        new_outline = copy.copy(element.outline)
        setattr(new_outline, prop_name, value)
        self._emit_property_changed("outline", new_outline)
        
    def _on_dash_changed(self, text: str) -> None:
        if self._updating or not self._current_element_id: return
        element = self._model.get_element(self._current_element_id)
        if not (hasattr(element, "outline") and element.outline): return
        
        new_dash = None
        try:
            if text.strip():
                new_dash = [float(d.strip()) for d in text.split(",") if d.strip()]
        except ValueError: return
        
        new_outline = copy.copy(element.outline)
        new_outline.dash_array = new_dash
        self._emit_property_changed("outline", new_outline)
        
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        # If the whole outline object changed
        if prop_name == "outline":
            self.update_widgets(self._model.get_element(self._current_element_id))
