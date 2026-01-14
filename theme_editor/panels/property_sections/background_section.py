# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Optional
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QDoubleSpinBox
from theme_editor.models.element import Element, BackgroundImageElement, BackgroundVideoElement
from theme_editor.panels.property_sections.base import PropertySection

class BackgroundSection(PropertySection):
    def __init__(self, editor_state, theme_model, parent=None):
        super().__init__("Background Settings", editor_state, theme_model, parent)
        
    def _setup_ui(self) -> None:
        # Source Row
        source_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setStyleSheet("background: #333;")
        source_layout.addWidget(self._path_edit, 1)
        
        self._browse_btn = QPushButton("...")
        self._browse_btn.setFixedWidth(32)
        self._browse_btn.clicked.connect(self._pick_source)
        source_layout.addWidget(self._browse_btn)
        self._layout.addRow("Source:", source_layout)
        
        # Video Processing Group
        self._video_group = QGroupBox("Video Processing")
        self._video_form = QFormLayout(self._video_group)
        
        self._v_enabled = QCheckBox("Video Enabled")
        self._v_enabled.toggled.connect(lambda v: self._emit_property_changed("enabled", v))
        self._video_form.addRow(self._v_enabled)
        
        self._v_start = QLineEdit()
        self._v_start.setPlaceholderText("00:00")
        self._v_start.textChanged.connect(lambda v: self._emit_property_changed("start_offset", v))
        self._video_form.addRow("Start Offset:", self._v_start)
        
        self._v_duration = QLineEdit()
        self._v_duration.setPlaceholderText("(full)")
        self._v_duration.textChanged.connect(lambda v: self._emit_property_changed("duration", v))
        self._video_form.addRow("Duration:", self._v_duration)
        
        self._v_fade = QDoubleSpinBox()
        self._v_fade.setRange(0.0, 10.0)
        self._v_fade.setSuffix(" sec")
        self._v_fade.valueChanged.connect(lambda v: self._emit_property_changed("loop_fade_duration", v))
        self._video_form.addRow("Loop Fade:", self._v_fade)
        
        self._layout.addRow(self._video_group)

    def update_widgets(self, element: Element) -> None:
        if isinstance(element, BackgroundImageElement):
            self._path_edit.setText(element.path)
            self._video_group.hide()
        elif isinstance(element, BackgroundVideoElement):
            self._path_edit.setText(element.source_path)
            self._v_enabled.setChecked(element.enabled)
            self._v_start.setText(element.start_offset)
            self._v_duration.setText(element.duration)
            self._v_fade.setValue(element.loop_fade_duration)
            self._video_group.show()

    def _pick_source(self) -> None:
        element = self._model.get_element(self._current_element_id)
        is_video = isinstance(element, BackgroundVideoElement)
        
        title = "Select Background Video" if is_video else "Select Background Image"
        filters = "Video Files (*.mp4 *.webm *.mov *.avi)" if is_video else "Image Files (*.png *.jpg *.jpeg)"
        
        file_path, _ = QFileDialog.getOpenFileName(self, title, "", f"{filters};;All Files (*)")
        if file_path:
            prop = "source_path" if is_video else "path"
            self._emit_property_changed(prop, file_path)
            self._path_edit.setText(file_path)

    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        if prop_name in ["path", "source_path"]: self._path_edit.setText(str(value))
        elif prop_name == "enabled": self._v_enabled.setChecked(bool(value))
        elif prop_name == "start_offset": self._v_start.setText(str(value))
        elif prop_name == "duration": self._v_duration.setText(str(value))
        elif prop_name == "loop_fade_duration": self._v_fade.setValue(float(value))
