# SPDX-License-Identifier: GPL-3.0-or-later
"""
Editor State Store for Theme Editor v2.

The EditorState is the single source of truth for:
- Persistent theme data (the document)
- Ephemeral UI state (selection, hover, tools)
- Undo/Redo history
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack

from theme_editor.models.element import Element

logger = logging.getLogger(__name__)

class EditorState(QObject):
    """
    Central store for all Theme Editor state.
    
    This class implements the 'Store' pattern, where all components 
    observe this state and all modifications go through here (usually via commands).
    """
    
    # Signals for state changes
    selection_changed = pyqtSignal(list)  # list of element_ids
    hover_changed = pyqtSignal(str)       # element_id or empty string
    document_modified = pyqtSignal(bool)   # is_dirty
    
    # Model-level signals (moved from ThemeModel)
    element_added = pyqtSignal(str)  # element_id
    element_removed = pyqtSignal(str)  # element_id
    element_changed = pyqtSignal(str, str, object)  # element_id, property_name, new_value
    element_moved = pyqtSignal(str, int, int)  # element_id, new_x, new_y
    guides_changed = pyqtSignal()
    theme_loaded = pyqtSignal()
    
    def __init__(self, undo_stack: Optional[QUndoStack] = None, parent=None):
        """
        Initialize the editor state.
        
        Args:
            undo_stack: Optional existing undo stack. If None, a new one is created.
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self._undo_stack = undo_stack or QUndoStack(self)
        self._undo_stack.cleanChanged.connect(self._on_undo_clean_changed)
        
        # --- Persistent Document Data ---
        self._elements: Dict[str, Element] = {}
        self._root_ids: List[str] = []  # Top-level element IDs in order
        
        # Display settings
        self._display_size = "5\""
        self._display_orientation = "landscape"
        self._display_rgb_led = (255, 255, 255)
        
        # Background
        self._background_type = "image"  # "image" or "video"
        self._background_path = "background.png"
        self._background_x = 0
        self._background_y = 0
        self._background_width = 800
        self._background_height = 480
        self._video_config: Dict[str, Any] = {}
        
        # Theme metadata
        self._theme_name = ""
        self._theme_folder: Optional[Path] = None
        self._author = ""
        
        # Guides (for editor only)
        self._guides_h: List[int] = []
        self._guides_v: List[int] = []
        
        # --- Ephemeral UI State ---
        self._selected_ids: Set[str] = set()
        self._hovered_id: str = ""
        self._active_tool: str = "select"
        
        logger.info("EditorState initialized")

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # --- Properties for persistent data ---
    
    @property
    def display_size(self) -> str: return self._display_size
    @display_size.setter
    def display_size(self, value: str): self._display_size = value
    
    @property
    def display_orientation(self) -> str: return self._display_orientation
    @display_orientation.setter
    def display_orientation(self, value: str): self._display_orientation = value

    @property
    def display_width(self) -> int:
        """Get display width based on size and orientation."""
        sizes = {
            '2.1"': (480, 480),
            '3.5"': (320, 480),
            '5"': (480, 800),
            '8.8"': (480, 1920),
        }
        w, h = sizes.get(self._display_size, (480, 800))
        return w if self._display_orientation == "portrait" else h

    @property
    def display_height(self) -> int:
        """Get display height based on size and orientation."""
        sizes = {
            '2.1"': (480, 480),
            '3.5"': (320, 480),
            '5"': (480, 800),
            '8.8"': (480, 1920),
        }
        w, h = sizes.get(self._display_size, (480, 800))
        return h if self._display_orientation == "portrait" else w
    
    @property
    def display_rgb_led(self) -> tuple: return self._display_rgb_led
    @display_rgb_led.setter
    def display_rgb_led(self, value: tuple): self._display_rgb_led = value
    
    @property
    def background_type(self) -> str: return self._background_type
    @background_type.setter
    def background_type(self, value: str): self._background_type = value
    
    @property
    def background_path(self) -> str: return self._background_path
    @background_path.setter
    def background_path(self, value: str): self._background_path = value
    
    @property
    def background_x(self) -> int: return self._background_x
    @background_x.setter
    def background_x(self, v: int): self._background_x = v
    
    @property
    def background_y(self) -> int: return self._background_y
    @background_y.setter
    def background_y(self, v: int): self._background_y = v
    
    @property
    def background_width(self) -> int: return self._background_width
    @background_width.setter
    def background_width(self, v: int): self._background_width = v
    
    @property
    def background_height(self) -> int: return self._background_height
    @background_height.setter
    def background_height(self, v: int): self._background_height = v

    @property
    def background_rect(self) -> tuple:
        return (self._background_x, self._background_y, self._background_width, self._background_height)
    
    def set_background_rect(self, x, y, w, h):
        self._background_x, self._background_y, self._background_width, self._background_height = x, y, w, h

    @property
    def video_config(self) -> Dict[str, Any]: return self._video_config
    
    @property
    def theme_name(self) -> str: return self._theme_name
    @theme_name.setter
    def theme_name(self, value: str): self._theme_name = value
    
    @property
    def theme_folder(self) -> Optional[Path]: return self._theme_folder
    @theme_folder.setter
    def theme_folder(self, value: Optional[Path]): self._theme_folder = value
    
    @property
    def author(self) -> str: return self._author
    @author.setter
    def author(self, value: str): self._author = value
    
    @property
    def selection(self) -> List[str]:
        """Returns the current selection as a list of IDs."""
        return sorted(list(self._selected_ids))
    
    @property
    def guides_h(self) -> List[int]:
        """Horizontal guide positions."""
        return self._guides_h
        
    @property
    def guides_v(self) -> List[int]:
        """Vertical guide positions."""
        return self._guides_v

    def set_selection(self, element_ids: List[str], source: Optional[str] = None) -> None:
        """
        Update the current selection.
        
        Args:
            element_ids: List of element IDs to select
            source: Optional string identify the source of the change for logging
        """
        new_selection = set(element_ids)
        if self._selected_ids == new_selection:
            return
            
        self._selected_ids = new_selection
        logger.debug(f"Selection updated from {source}: {self.selection}")
        self.selection_changed.emit(self.selection)

    @property
    def hovered_id(self) -> str:
        return self._hovered_id

    def set_hover(self, element_id: str) -> None:
        """Update the currently hovered element."""
        if self._hovered_id == element_id:
            return
        self._hovered_id = element_id
        self.hover_changed.emit(element_id)

    def _on_undo_clean_changed(self, is_clean: bool) -> None:
        """Handle undo stack clean state changes."""
        self.document_modified.emit(not is_clean)

    # --- Element Management Methods (To be expanded) ---
    # These will eventually replace direct ThemeModel manipulation
    
    def get_element(self, element_id: str) -> Optional[Element]:
        return self._elements.get(element_id)

    def add_element(self, element: Element, parent_id: Optional[str] = None, index: int = -1) -> None:
        """Add an element to the document and manage internal mapping."""
        # Implementation details will move here from ThemeModel in Phase 2
        self._elements[element.id] = element
        if parent_id:
            parent = self.get_element(parent_id)
            if parent:
                if index < 0:
                    parent.add_child(element)
                else:
                    parent.insert_child(index, element)
        else:
            if index < 0:
                self._root_ids.append(element.id)
            else:
                self._root_ids.insert(index, element.id)
        
        # Signal will be emitted by the command that calls this
