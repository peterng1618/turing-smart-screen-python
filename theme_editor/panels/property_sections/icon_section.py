# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional
from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout
from theme_editor.models.element import Element, IconElement
from theme_editor.panels.property_sections.base import PropertySection

class IconSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Icon Source", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        
        # URL input
        url_label = QLabel("FontAwesome URL:")
        url_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self._layout.addWidget(url_label)
        
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://fontawesome.com/icons/laptop-code?f=classic&s=solid")
        self._url_edit.textChanged.connect(lambda v: self._emit_property_changed("icon", v))
        self._layout.addWidget(self._url_edit)
        self._widgets["icon"] = self._url_edit
        
        # Help text
        help_label = QLabel("Browse icons at fontawesome.com and paste the URL here.")
        help_label.setStyleSheet("color: #999; font-size: 9px;")
        help_label.setWordWrap(True)
        self._layout.addWidget(help_label)
        
    def update_widgets(self, element: Element) -> None:
        if isinstance(element, IconSection) or hasattr(element, "icon"):
            self._url_edit.setText(getattr(element, "icon", "") or "")

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "icon":
            self._url_edit.setText(str(value))
