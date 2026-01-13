# SPDX-License-Identifier: GPL-3.0-or-later
"""
Properties Panel for Theme Editor v2.

Provides a property editor for the currently selected element with:
- Auto-generated form based on element type
- Type-appropriate widgets (spinbox, color picker, font selector, etc.)
- Real-time property updates with undo support
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QUndoStack

from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    Element, TriangleElement
)
from theme_editor.panels.property_sections.registry import get_sections_for_element_type
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.widgets.color_button import ColorButton

logger = logging.getLogger(__name__)





class PropertiesPanel(QWidget):
    """
    Panel for viewing and editing properties of selected elements.
    
    Dynamically generates property widgets based on element type.
    """
    
    property_changed = pyqtSignal(str, str, object)  # element_id, property_name, value
    
    def __init__(
        self,
        editor_state: EditorState,
        theme_model: ThemeModel,
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setMinimumWidth(320)
        
        self._editor_state = editor_state
        self._model = theme_model
        self._undo_stack = undo_stack
        self._current_element_id: Optional[str] = None
        self._sections: List[PropertySection] = []
        self._widgets: Dict[str, QWidget] = {}
        self._updating = False  # Prevent feedback loops
        self._aspect_ratio: float = 1.0  # Aspect ratio for W/H lock
        self._aspect_locked: bool = True  # W/H linked by default
        
        self._setup_ui()
        
        # Connect to Store
        self._editor_state.element_changed.connect(self._on_model_element_changed)
        self._editor_state.selection_changed.connect(self._on_store_selection_changed)
    
    def _on_model_element_changed(self, element_id: str, prop_name: str, value: Any) -> None:
        """Handle element changes from model (e.g. from canvas or undo)."""
        if element_id != self._current_element_id or self._updating:
            return
        
        # When points change for triangles, we also need to update the virtual W/H
        if prop_name in ("x1", "y1", "x2", "y2", "x3", "y3"):
            element = self._model.get_element(element_id)
            if isinstance(element, TriangleElement):
                xs = [element.x1, element.x2, element.x3]
                ys = [element.y1, element.y2, element.y3]
                self.update_property("width", max(xs) - min(xs))
                self.update_property("height", max(ys) - min(ys))
        
        if prop_name == "_insert_sensor":
            self._insert_sensor_into_focused_widget(value)
            return

        # self.update_property(prop_name, value)
        for section in self._sections:
            section.update_single_property(prop_name, value)

    def _on_store_selection_changed(self, element_ids: List[str]) -> None:
        """Handle selection changes from the central store."""
        if not element_ids:
            self.clear()
        else:
            # For now, properties panel only supports single selection (show first)
            self.show_properties(element_ids[0])
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Placeholder label
        self._placeholder = QLabel("Select an element to edit properties")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #aaa;")
        self._content_layout.addWidget(self._placeholder)
        
        scroll.setWidget(self._content)
        layout.addWidget(scroll)
    
    def clear(self) -> None:
        """Clear all property widgets."""
        # Remove all widgets except placeholder
        try:
            while self._content_layout.count() > 1:
                item = self._content_layout.takeAt(1)
                if item.widget():
                    item.widget().hide()
                    # We don't delete them yet if we want to reuse? 
                    # Actually, for the POC, deleting is safer but reg-based re-use is better.
                    # For now, let's stick to deleting like before but for modular sections.
                    item.widget().deleteLater()
            
            self._sections.clear()
            self._widgets.clear()
            self._current_element_id = None
            self._placeholder.show()
        except Exception as e:
            # Log error but don't crash
            logger.error(f"Error clearing properties panel: {e}")
    
    def show_properties(self, element_id: str) -> None:
        """
        Show properties for the specified element using the modular registry.
        """
        element = self._model.get_element(element_id)
        if not element:
            self.clear()
            return
        
        # Clear existing widgets
        self.clear()
        self._placeholder.hide()
        self._current_element_id = element_id
        
        # Get sections for this element type
        section_classes = get_sections_for_element_type(element.element_type)
        
        for section_class in section_classes:
            section = section_class(self._editor_state, self._model, self)
            section.property_changed.connect(
                lambda name, val: self._on_property_changed(name, val)
            )
            section.set_element(element_id)
            self._content_layout.addWidget(section)
            self._sections.append(section)
            
            # Map widgets for the global update_property method (compatibility)
            # This is a bit of a hack during transition
            for name, widget in section._widgets.items():
                self._widgets[name] = widget
        
        # Stretch at bottom
        self._content_layout.addStretch()
    def _insert_sensor_into_focused_widget(self, placeholder: str) -> None:
        """Insert a sensor placeholder into the text field if it exists."""
        if "text" in self._widgets:
            text_edit = self._widgets["text"]
            if isinstance(text_edit, QLineEdit):
                current = text_edit.text()
                # Insert at cursor position or end
                cursor_pos = text_edit.cursorPosition()
                new_text = current[:cursor_pos] + placeholder + current[cursor_pos:]
                text_edit.setText(new_text)
                text_edit.setCursorPosition(cursor_pos + len(placeholder))
                text_edit.setFocus()

    def _on_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle property value change and push to undo stack."""
        if self._updating or not self._current_element_id:
            return
            
        element = self._model.get_element(self._current_element_id)
        if not element:
            return
            
        # Get old value for undo
        old_value = getattr(element, prop_name, None)
        if old_value == value:
            return
            
        from theme_editor.commands.undo_commands import ChangePropertyCommand
        cmd = ChangePropertyCommand(
            self._model, self._current_element_id, prop_name, old_value, value
        )
        self._undo_stack.push(cmd)
    
    def update_property(self, prop_name: str, value: Any) -> None:
        """
        Update a property widget value (called when model changes externally).
        
        Args:
            prop_name: Property name
            value: New value
        """
        widget = self._widgets.get(prop_name)
        if not widget:
            return
        
        self._updating = True
        try:
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QSpinBox):
                clamped_val = int(max(-2147483648, min(2147483647, int(value))))
                widget.setValue(clamped_val)
            elif isinstance(widget, QDoubleSpinBox):
                clamped_val = float(max(-1000000, min(1000000, float(value))))
                widget.setValue(clamped_val)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, ColorButton):
                widget.color = value
        finally:
            self._updating = False
