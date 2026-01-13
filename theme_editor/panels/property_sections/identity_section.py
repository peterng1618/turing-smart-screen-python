# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional
from PyQt6.QtWidgets import QLineEdit, QLabel
from theme_editor.models.element import Element
from theme_editor.panels.property_sections.base import PropertySection

class IdentitySection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Identity", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(lambda v: self._emit_property_changed("name", v))
        self._layout.addRow("Name:", self._name_edit)
        self._widgets["name"] = self._name_edit
        
        self._type_label = QLabel()
        self._type_label.setStyleSheet("color: #aaa;")
        self._layout.addRow("Type:", self._type_label)
        
    def update_widgets(self, element: Element) -> None:
        self._name_edit.setText(element.name)
        self._type_label.setText(element.element_type.name.title())
        
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "name":
            self._name_edit.setText(str(value))
