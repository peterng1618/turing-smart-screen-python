# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any, Optional
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QFileDialog, QVBoxLayout
from theme_editor.models.element import Element, ImageElement
from theme_editor.panels.property_sections.base import PropertySection

class ImageSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Image Source", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        
        # Current path
        path_layout = QHBoxLayout()
        self._path_label = QLabel()
        self._path_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self._path_label.setWordWrap(True)
        path_layout.addWidget(self._path_label, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._pick_image)
        path_layout.addWidget(browse_btn)
        
        self._layout.addLayout(path_layout)
        
    def update_widgets(self, element: Element) -> None:
        if isinstance(element, ImageElement):
            self._path_label.setText(element.path)
            self._path_label.setToolTip(element.path)
            
    def _pick_image(self) -> None:
        """Open file dialog to select an image."""
        start_dir = ""
        if hasattr(self._model, 'theme_folder') and self._model.theme_folder:
            start_dir = str(self._model.theme_folder)
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            start_dir,
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )
        
        if file_path:
            self._emit_property_changed("path", file_path)
            self._path_label.setText(file_path)
            
            # Auto-set width/height from image
            try:
                from PIL import Image
                img_path = Path(file_path)
                if img_path.exists():
                     with Image.open(img_path) as img:
                          width, height = img.size
                          self._emit_property_changed("width", width)
                          self._emit_property_changed("height", height)
            except Exception:
                pass # Silently fail auto-size

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name == "path":
            self._path_label.setText(str(value))
