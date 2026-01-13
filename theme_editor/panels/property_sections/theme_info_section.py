# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional, Dict
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFormLayout
from theme_editor.models.element import Element, ThemeInfoElement
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.widgets.color_button import ColorButton

class ThemeInfoSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Theme Settings", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        self._buffered_widgets: Dict[str, Any] = {}
        
        # Author
        self._author_edit = QLineEdit()
        self._layout.addRow("Author:", self._author_edit)
        self._buffered_widgets["author"] = self._author_edit
        
        # Size
        self._size_combo = QComboBox()
        self._size_combo.addItems(["2.1\"", "3.5\"", "5\"", "8.8\""])
        self._layout.addRow("Display Size:", self._size_combo)
        self._buffered_widgets["display_size"] = self._size_combo
        
        # Orientation
        self._orient_combo = QComboBox()
        self._orient_combo.addItems(["landscape", "portrait"])
        self._layout.addRow("Orientation:", self._orient_combo)
        self._buffered_widgets["display_orientation"] = self._orient_combo
        
        # RGB LED
        self._rgb_btn = ColorButton()
        self._layout.addRow("RGB LED:", self._rgb_btn)
        self._buffered_widgets["display_rgb_led"] = self._rgb_btn
        
        # Actions
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #2e8b57; color: white; font-weight: bold;")
        save_btn.clicked.connect(self._save_changes)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._revert_changes)
        btn_layout.addWidget(cancel_btn)
        self._layout.addRow(btn_layout)

    def update_widgets(self, element: Element) -> None:
        if isinstance(element, ThemeInfoElement):
            self._author_edit.setText(element.author)
            self._size_combo.setCurrentText(element.display_size)
            self._orient_combo.setCurrentText(element.display_orientation)
            r, g, b = element.display_rgb_led
            self._rgb_btn.color = (r, g, b, 255)

    def _save_changes(self) -> None:
        element = self._model.get_element(self._current_element_id)
        if not element: return
        
        new_author = self._author_edit.text()
        new_size = self._size_combo.currentText()
        new_orient = self._orient_combo.currentText()
        new_rgb = (self._rgb_btn.color[0], self._rgb_btn.color[1], self._rgb_btn.color[2])
        
        if new_size != element.display_size or new_orient != element.display_orientation:
            ret = QMessageBox.warning(
                self, "Layout Change", 
                "Changing display size or orientation may require adjusting element positions. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret != QMessageBox.StandardButton.Yes: return

        if new_author != element.author: self._emit_property_changed("author", new_author)
        if new_rgb != element.display_rgb_led: self._emit_property_changed("display_rgb_led", new_rgb)
        if new_size != element.display_size: self._emit_property_changed("display_size", new_size)
        if new_orient != element.display_orientation: self._emit_property_changed("display_orientation", new_orient)

    def _revert_changes(self) -> None:
        self.update_widgets(self._model.get_element(self._current_element_id))

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        # Re-sync on store changes
        self._revert_changes()
