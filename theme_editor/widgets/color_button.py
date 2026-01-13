# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Tuple
from PyQt6.QtWidgets import QPushButton, QColorDialog
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

class ColorButton(QPushButton):
    """Button that shows a color preview and opens color picker."""
    
    color_changed = pyqtSignal(tuple)  # RGBA tuple
    
    def __init__(self, color: Tuple[int, int, int, int] = (255, 255, 255, 255), parent=None):
        super().__init__(parent)
        self._color = color
        self.setMinimumWidth(60)
        self.setMaximumHeight(24)
        self._update_style()
        self.clicked.connect(self._pick_color)
    
    @property
    def color(self) -> Tuple[int, int, int, int]:
        return self._color
    
    @color.setter
    def color(self, value: Tuple[int, int, int, int]) -> None:
        self._color = value
        self._update_style()
    
    def _update_style(self) -> None:
        """Update button background to show color and adjust text color for readability."""
        r, g, b, a = self._color
        
        # Calculate luminance to determine if black or white text is more readable
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        text_color = "#000000" if luminance > 128 else "#ffffff"
        
        self.setStyleSheet(
            f"ColorButton {{ "
            f"  background-color: rgba({r}, {g}, {b}, {a}); "
            f"  color: {text_color}; "
            f"  border: 1px solid #888; "
            f"  border-radius: 2px; "
            f"  font-weight: bold; "
            f"}} "
            f"ColorButton:hover {{ "
            f"  border: 1px solid #aaa; "
            f"}}"
        )
        self.setText(f"{r},{g},{b},{a}")
    
    def _pick_color(self) -> None:
        """Open color picker dialog."""
        initial = QColor(*self._color)
        color = QColorDialog.getColor(
            initial,
            self,
            "Select Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue(), color.alpha())
            self._update_style()
            self.color_changed.emit(self._color)
