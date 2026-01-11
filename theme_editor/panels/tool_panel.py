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
    
    # Signals for element creation
    add_element_requested = pyqtSignal(object)  # ElementType or (sensor_type, variant)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
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
            btn.setStyleSheet("""
                QToolButton { 
                    text-align: left; 
                    padding: 2px 4px;
                    height: 26px;
                    border: 1px solid #444; 
                    border-radius: 4px;
                    background: rgba(255, 255, 255, 0.05);
                }
                QToolButton:hover { 
                    background: rgba(255, 255, 255, 0.15);
                    border: 1px solid #666; 
                }
                QToolButton::text {
                    text-align: left;
                }
            """)
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
            btn.setStyleSheet("""
                QToolButton { 
                    text-align: left; 
                    padding: 2px 14px 2px 4px; 
                    height: 26px;
                    border: 1px solid #444; 
                    border-radius: 4px;
                    background: rgba(255, 255, 255, 0.05);
                }
                QToolButton:hover { 
                    background: rgba(255, 255, 255, 0.15);
                    border: 1px solid #666; 
                }
                QToolButton::menu-indicator {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    right: 4px;
                    width: 8px;
                }
            """)
            
            menu = QMenu(self)
            
            for v_label, v_id in [("Text", "TEXT"), ("Graph", "GRAPH"), ("Radial", "RADIAL"), ("Line Graph", "LINE_GRAPH")]:
                if v_id != "TEXT" and sensor_id in ["DATE", "WEATHER", "UPTIME"]:
                    continue
                act = menu.addAction(v_label)
                act.triggered.connect(make_emit_handler(sensor_id, v_id))
            
            btn.setMenu(menu)
            grid.addWidget(btn, i // 2, i % 2)
            
        return group
