# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any, Optional
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QComboBox, QLineEdit, QPushButton, QFileDialog
from theme_editor.models.element import Element
from theme_editor.panels.property_sections.base import PropertySection

class TypographySection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Typography", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Text
        self._text_label = QLabel("Text:")
        self._text_edit = QLineEdit()
        self._text_edit.textChanged.connect(lambda v: self._emit_property_changed("text", v))
        self._layout.addRow(self._text_label, self._text_edit)
        self._widgets["text"] = self._text_edit
        
        # Font
        font_layout = QHBoxLayout()
        self._font_label = QLabel()
        self._font_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self._font_label.setWordWrap(True)
        
        font_btn = QPushButton("...")
        font_btn.setFixedWidth(32)
        font_btn.clicked.connect(self._pick_font)
        
        font_layout.addWidget(self._font_label, 1)
        font_layout.addWidget(font_btn)
        self._layout.addRow("Font:", font_layout)
        
        # Size
        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 1000)
        self._size_spin.valueChanged.connect(lambda v: self._emit_property_changed("font_size", v))
        self._layout.addRow("Size:", self._size_spin)
        self._widgets["font_size"] = self._size_spin
        
        # Align
        self._align_combo = QComboBox()
        self._align_combo.addItems(["left", "center", "right"])
        self._align_combo.currentTextChanged.connect(lambda v: self._emit_property_changed("align", v))
        self._layout.addRow("Align:", self._align_combo)
        self._widgets["align"] = self._align_combo
        
        # Anchor
        self._anchor_combo = QComboBox()
        self._anchor_combo.addItems(["lt", "lm", "lb", "mt", "mm", "mb", "rt", "rm", "rb"])
        self._anchor_combo.currentTextChanged.connect(lambda v: self._emit_property_changed("anchor", v))
        self._layout.addRow("Anchor:", self._anchor_combo)
        self._widgets["anchor"] = self._anchor_combo
        
    def update_widgets(self, element: Element) -> None:
        # Text
        if hasattr(element, "text"):
            self._text_label.show()
            self._text_edit.show()
            self._text_edit.setText(element.text)
        else:
            self._text_label.hide()
            self._text_edit.hide()
            
        # Font
        if hasattr(element, "font"):
            self._font_label.setText(element.font)
            self._font_label.setToolTip(element.font)
            
        # Size
        if hasattr(element, "font_size"):
            self._size_spin.setValue(int(element.font_size))
            
        # Align
        if hasattr(element, "align"):
            self._align_combo.setCurrentText(element.align)
            
        # Anchor
        if hasattr(element, "anchor"):
            self._anchor_combo.setCurrentText(element.anchor)
            
    def _pick_font(self) -> None:
        """Open font picker dialog browsing res/fonts folder."""
        # Get res/fonts directory relative to this file
        # theme_editor/panels/property_sections/typography_section.py
        # -> theme_editor/res/fonts
        fonts_dir = Path(__file__).parent.parent.parent / "res" / "fonts"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Font",
            str(fonts_dir),
            "Font Files (*.ttf *.otf);;All Files (*)"
        )
        
        if file_path:
            # Convert to relative path from res/fonts
            try:
                rel_path = Path(file_path).relative_to(fonts_dir)
                font_path = str(rel_path).replace("\\", "/")
            except ValueError:
                # File not under res/fonts, use absolute path
                font_path = file_path
            
            self._emit_property_changed("font", font_path)
            self._font_label.setText(font_path)

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "text": self._text_edit.setText(str(value))
        elif prop_name == "font": self._font_label.setText(str(value))
        elif prop_name == "font_size": self._size_spin.setValue(int(value))
        elif prop_name == "align": self._align_combo.setCurrentText(str(value))
        elif prop_name == "anchor": self._anchor_combo.setCurrentText(str(value))
