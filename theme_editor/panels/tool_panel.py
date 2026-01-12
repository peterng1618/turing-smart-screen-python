# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tool Panel for Theme Editor v2.
Provides a categorization of creation tools in a dockable panel.
"""

import logging
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QToolButton, 
    QLabel, QGroupBox, QMenu, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction

from theme_editor.models.element import ElementType

logger = logging.getLogger(__name__)

class ToolPanel(QWidget):
    """Panel containing categorized creation tools."""
    

    # Signals for element creation and UI control
    add_element_requested = pyqtSignal(object)  # ElementType or (sensor_type, variant)
    theme_toggle_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Central stylesheet for all tool buttons to follow palette
        self.setStyleSheet("""
            QToolButton {
                text-align: left;
                padding: 4px 8px;
                height: 30px;
                background: palette(window);
                border: 1px solid palette(mid);
                border-radius: 4px;
                color: palette(window-text);
            }
            QToolButton:hover {
                background: palette(highlight);
                color: palette(highlighted-text);
                border: 1px solid palette(highlight);
            }
            QToolButton:pressed {
                background: palette(midlight);
            }
            QToolButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 4px;
                width: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid palette(mid);
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 15px;
                color: palette(window-text);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: palette(window-text);
            }
        """)

        self.setMinimumWidth(210) # Enforce minimum workspace area
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Scroll area for many tools
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(15)

        # 1. Dynamic Elements Group
        container_layout.addWidget(self._create_group("Dynamic Elements", [
            ("🔄 Dynamic", lambda: self.add_element_requested.emit(ElementType.DYNAMIC_TEXT)),
        ]))

        # 2. Sensors Group
        container_layout.addWidget(self._create_sensor_group())

        # 3. UI Elements Group
        container_layout.addWidget(self._create_group("UI Elements", [
            ("📝 UI Text", lambda: self.add_element_requested.emit(ElementType.TEXT)),
            ("🖼️ Image", lambda: self.add_element_requested.emit(ElementType.IMAGE)),
            ("⚙️ Icon", lambda: self.add_element_requested.emit(ElementType.ICON)),
            ("🟦 Rectangle", lambda: self.add_element_requested.emit(ElementType.RECTANGLE)),
            ("📐 Triangle", lambda: self.add_element_requested.emit(ElementType.TRIANGLE)),
            ("🟡 Circle", lambda: self.add_element_requested.emit(ElementType.CIRCLE)),
            ("➖ Line", lambda: self.add_element_requested.emit(ElementType.LINE)),
        ]))

        container_layout.addStretch()

        # 4. Theme Toggle
        toggle_btn = QToolButton()
        toggle_btn.setText("🌓 Toggle theme")
        toggle_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toggle_btn.clicked.connect(self.theme_toggle_requested.emit)
        container_layout.addWidget(toggle_btn)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _create_group(self, title: str, tools: list) -> QGroupBox:
        """Create a grouped section of simple tool buttons."""
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setContentsMargins(5, 10, 5, 5)
        grid.setSpacing(5)

        for i, (label, callback) in enumerate(tools):
            btn = QToolButton()
            btn.setText(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumWidth(85)
            btn.clicked.connect(callback)
            grid.addWidget(btn, i // 2, i % 2)

        return group

    def _create_sensor_group(self) -> QGroupBox:
        """Create the sensor group with standard dropdown menus."""
        group = QGroupBox("Sensors")
        grid = QGridLayout(group)
        grid.setContentsMargins(5, 10, 5, 5)
        grid.setSpacing(6)

        sensors = [
            ("💻 CPU", "CPU"),
            ("🎮 GPU", "GPU"),
            ("💾 RAM", "MEMORY"),
            ("💽 Disk", "DISK"),
            ("🌐 Net", "NET"),
            ("📅 Date", "DATE"),
            ("☁️ Weather", "WEATHER"),
            ("⏱️ Uptime", "UPTIME"),
            ("📶 Ping", "PING")
        ]

        # Define handler factory OUTSIDE the loop to avoid closure issues
        def make_emit_handler(sensor, variant):
            def handler():
                self.add_element_requested.emit((sensor, variant))
            return handler

        for i, (label, sensor_id) in enumerate(sensors):
            btn = QToolButton()
            btn.setText(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumWidth(85)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

            menu = QMenu(self)

            for v_label, v_id in [("Text", "TEXT"), ("Graph", "GRAPH"), ("Radial", "RADIAL"), ("Line Graph", "LINE_GRAPH")]:
                if v_id != "TEXT" and sensor_id in ["DATE", "WEATHER", "UPTIME"]:
                    continue
                act = menu.addAction(v_label)
                act.triggered.connect(make_emit_handler(sensor_id, v_id))
            
            btn.setMenu(menu)
            grid.addWidget(btn, i // 2, i % 2)
            
        return group
