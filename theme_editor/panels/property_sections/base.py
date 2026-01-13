# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Any, Dict, Optional
from PyQt6.QtWidgets import QWidget, QGroupBox, QFormLayout
from PyQt6.QtCore import pyqtSignal
from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import Element

class PropertySection(QGroupBox):
    """
    Base class for a modular section in the Properties Panel.
    Each section is a QGroupBox containing a form with widgets for specific properties.
    """
    
    # Signals
    property_changed = pyqtSignal(str, object)  # property_name, new_value
    
    def __init__(self, title: str, editor_state: EditorState, theme_model: ThemeModel, parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self._editor_state = editor_state
        self._model = theme_model
        self._current_element_id: Optional[str] = None
        self._updating = False
        self._widgets: Dict[str, QWidget] = {}
        
        self._layout = QFormLayout(self)
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Override this to add widgets to the section."""
        pass
        
    def set_element(self, element_id: str) -> None:
        """Update section widgets with values from the given element."""
        self._current_element_id = element_id
        element = self._model.get_element(element_id)
        if element:
            self._updating = True
            try:
                self.update_widgets(element)
            finally:
                self._updating = False
        self.show()
        
    def update_widgets(self, element: Element) -> None:
        """Override this to sync widgets with element data."""
        pass
        
    def update_single_property(self, prop_name: str, value: Any) -> None:
        """Update a single widget if it's managed by this section."""
        if self._updating:
            return
            
        self._updating = True
        try:
            self._on_store_property_changed(prop_name, value)
        finally:
            self._updating = False
                
    def _on_store_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle property changes coming from the store/model."""
        pass
        
    def _emit_property_changed(self, prop_name: str, value: Any) -> None:
        """Emit signal and potentially update store directly if needed."""
        if not self._updating:
            self.property_changed.emit(prop_name, value)
