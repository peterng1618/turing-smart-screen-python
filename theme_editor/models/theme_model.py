# SPDX-License-Identifier: GPL-3.0-or-later
"""
Theme Model for Theme Editor v2.

The ThemeModel is the central data model that holds all theme data including:
- Display settings (size, orientation, RGB LED color)
- Background configuration (image or video)
- UI elements (shapes, text, images, icons)
- Dynamic elements (sensor-bound stats)

It extends QAbstractItemModel to work seamlessly with Qt's model/view framework.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PyQt6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData,
    pyqtSignal, QByteArray
)
from PyQt6.QtGui import QUndoStack

from theme_editor.models.element import (
    Element, ElementType, create_element,
    RectangleElement, CircleElement, TriangleElement, LineElement,
    TextElement, ImageElement, IconElement, GroupElement, DynamicTextElement
)

logger = logging.getLogger(__name__)


class ThemeModel(QAbstractItemModel):
    """
    Central data model for theme data.
    
    Implements QAbstractItemModel for use with QTreeView (layer panel).
    Emits signals when data changes for canvas/property panel updates.
    """
    
    # Signals
    element_added = pyqtSignal(str)  # element_id
    element_removed = pyqtSignal(str)  # element_id
    element_changed = pyqtSignal(str, str, object)  # element_id, property_name, new_value
    element_moved = pyqtSignal(str, int, int)  # element_id, new_x, new_y
    selection_changed = pyqtSignal(list)  # list of element_ids
    
    # Custom role for element ID
    ElementIdRole = Qt.ItemDataRole.UserRole + 1
    ElementTypeRole = Qt.ItemDataRole.UserRole + 2
    VisibleRole = Qt.ItemDataRole.UserRole + 3
    LockedRole = Qt.ItemDataRole.UserRole + 4
    
    def __init__(self, undo_stack: QUndoStack, parent=None):
        """
        Initialize the theme model.
        
        Args:
            undo_stack: Undo stack for command tracking
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self._undo_stack = undo_stack
        self._elements: Dict[str, Element] = {}
        self._root_ids: List[str] = []  # Top-level element IDs in order
        
        # Display settings
        self._display_size = "5\""
        self._display_orientation = "landscape"
        self._display_rgb_led = (255, 255, 255)
        
        # Background
        self._background_type = "image"  # "image" or "video"
        self._background_path = "background.png"
        self._video_config: Dict[str, Any] = {}
        
        # Theme metadata
        self._theme_name = ""
        self._theme_path: Optional[Path] = None
        self._author = ""
    
    # --- QAbstractItemModel Implementation ---
    
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create index for item at row, column under parent."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            # Root level
            if 0 <= row < len(self._root_ids):
                element_id = self._root_ids[row]
                return self.createIndex(row, column, element_id)
        else:
            # Child level
            parent_id = parent.internalPointer()
            parent_element = self._elements.get(parent_id)
            if parent_element and 0 <= row < len(parent_element.children):
                child_id = parent_element.children[row]
                return self.createIndex(row, column, child_id)
        
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get parent index of item."""
        if not index.isValid():
            return QModelIndex()
        
        element_id = index.internalPointer()
        element = self._elements.get(element_id)
        
        if not element or not element.parent_id:
            return QModelIndex()
        
        parent_element = self._elements.get(element.parent_id)
        if not parent_element:
            return QModelIndex()
        
        # Find parent's row
        if parent_element.parent_id:
            grandparent = self._elements.get(parent_element.parent_id)
            if grandparent:
                row = grandparent.children.index(element.parent_id)
            else:
                return QModelIndex()
        else:
            row = self._root_ids.index(element.parent_id)
        
        return self.createIndex(row, 0, element.parent_id)
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of children under parent."""
        if parent.column() > 0:
            return 0
        
        if not parent.isValid():
            return len(self._root_ids)
        
        parent_id = parent.internalPointer()
        parent_element = self._elements.get(parent_id)
        if parent_element:
            return len(parent_element.children)
        
        return 0
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Always single column for tree view."""
        return 1
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Get data for item at index."""
        if not index.isValid():
            return None
        
        element_id = index.internalPointer()
        element = self._elements.get(element_id)
        if not element:
            return None
        
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return element.name or f"{element.element_type.name.lower()}"
        elif role == self.ElementIdRole:
            return element.id
        elif role == self.ElementTypeRole:
            return element.element_type
        elif role == self.VisibleRole:
            return element.visible
        elif role == self.LockedRole:
            return element.locked
        elif role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if element.visible else Qt.CheckState.Unchecked
        
        return None
    
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Set data for item at index."""
        if not index.isValid():
            return False
        
        element_id = index.internalPointer()
        element = self._elements.get(element_id)
        if not element:
            return False
        
        if role == Qt.ItemDataRole.EditRole:
            old_name = element.name
            element.name = str(value)
            self.dataChanged.emit(index, index, [role])
            self.element_changed.emit(element_id, "name", value)
            return True
        elif role == Qt.ItemDataRole.CheckStateRole:
            element.visible = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role, self.VisibleRole])
            self.element_changed.emit(element_id, "visible", element.visible)
            return True
        
        return False
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Get flags for item at index."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        flags = (
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsEditable |
            Qt.ItemFlag.ItemIsUserCheckable |
            Qt.ItemFlag.ItemIsDragEnabled |
            Qt.ItemFlag.ItemIsDropEnabled
        )
        
        return flags
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Get header data."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return "Layers"
        return None
    
    def supportedDropActions(self) -> Qt.DropAction:
        """Support move operations for reordering."""
        return Qt.DropAction.MoveAction
    
    def mimeTypes(self) -> List[str]:
        """Supported MIME types for drag/drop."""
        return ["application/x-themeeditor-element"]
    
    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        """Encode dragged items."""
        mime_data = QMimeData()
        element_ids = [idx.internalPointer() for idx in indexes if idx.isValid()]
        mime_data.setData(
            "application/x-themeeditor-element",
            ",".join(element_ids).encode()
        )
        return mime_data
    
    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex
    ) -> bool:
        """Handle dropped items."""
        if action == Qt.DropAction.IgnoreAction:
            return True
        
        if not data.hasFormat("application/x-themeeditor-element"):
            return False
        
        element_ids = data.data("application/x-themeeditor-element").data().decode().split(",")
        
        # TODO: Implement reordering via undo command
        logger.debug(f"Drop: {element_ids} at row {row}, parent {parent.internalPointer() if parent.isValid() else 'root'}")
        
        return True
    
    # --- Element Operations ---
    
    def add_element(self, element: Element, parent_id: Optional[str] = None, index: int = -1) -> str:
        """
        Add a new element to the model.
        
        Args:
            element: Element to add
            parent_id: Parent element ID, or None for root level
            index: Insert position, -1 for end
            
        Returns:
            ID of added element
        """
        self._elements[element.id] = element
        element.parent_id = parent_id
        
        if parent_id:
            parent = self._elements.get(parent_id)
            if parent:
                if index < 0:
                    parent.children.append(element.id)
                else:
                    parent.children.insert(index, element.id)
        else:
            if index < 0:
                self._root_ids.append(element.id)
            else:
                self._root_ids.insert(index, element.id)
        
        # Emit model signals
        self.layoutChanged.emit()
        self.element_added.emit(element.id)
        
        logger.debug(f"Added element: {element.name} ({element.id})")
        return element.id
    
    def remove_element(self, element_id: str) -> Optional[Element]:
        """
        Remove an element from the model.
        
        Args:
            element_id: ID of element to remove
            
        Returns:
            Removed element, or None if not found
        """
        element = self._elements.pop(element_id, None)
        if not element:
            return None
        
        # Remove from parent's children or root list
        if element.parent_id:
            parent = self._elements.get(element.parent_id)
            if parent and element_id in parent.children:
                parent.children.remove(element_id)
        else:
            if element_id in self._root_ids:
                self._root_ids.remove(element_id)
        
        # Recursively remove children
        for child_id in list(element.children):
            self.remove_element(child_id)
        
        self.layoutChanged.emit()
        self.element_removed.emit(element_id)
        
        logger.debug(f"Removed element: {element.name} ({element_id})")
        return element
    
    def get_element(self, element_id: str) -> Optional[Element]:
        """Get element by ID."""
        return self._elements.get(element_id)
    
    def get_all_elements(self) -> List[Element]:
        """Get all elements in the model."""
        return list(self._elements.values())
    
    def get_root_elements(self) -> List[Element]:
        """Get top-level elements in order."""
        return [self._elements[eid] for eid in self._root_ids if eid in self._elements]
    
    def set_element_property(self, element_id: str, prop_name: str, value: Any) -> bool:
        """
        Set a property on an element.
        
        Args:
            element_id: ID of element to modify
            prop_name: Property name
            value: New value
            
        Returns:
            True if property was set
        """
        element = self._elements.get(element_id)
        if not element:
            return False
        
        if not hasattr(element, prop_name):
            return False
        
        setattr(element, prop_name, value)
        self.element_changed.emit(element_id, prop_name, value)
        
        # Update model index if name changed
        if prop_name == "name":
            index = self._get_index_for_element(element_id)
            if index.isValid():
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        
        return True
    
    def move_element(self, element_id: str, new_x: int, new_y: int) -> bool:
        """
        Move an element to a new position.
        
        Args:
            element_id: ID of element to move
            new_x: New X coordinate
            new_y: New Y coordinate
            
        Returns:
            True if element was moved
        """
        element = self._elements.get(element_id)
        if not element:
            return False
        
        element.x = new_x
        element.y = new_y
        self.element_moved.emit(element_id, new_x, new_y)
        
        return True
    
    def _get_index_for_element(self, element_id: str) -> QModelIndex:
        """Get QModelIndex for an element."""
        element = self._elements.get(element_id)
        if not element:
            return QModelIndex()
        
        if element.parent_id:
            parent = self._elements.get(element.parent_id)
            if parent and element_id in parent.children:
                row = parent.children.index(element_id)
                return self.createIndex(row, 0, element_id)
        elif element_id in self._root_ids:
            row = self._root_ids.index(element_id)
            return self.createIndex(row, 0, element_id)
        
        return QModelIndex()
    
    # --- Theme Operations ---
    
    def clear(self) -> None:
        """Clear all elements and reset to empty state."""
        self.beginResetModel()
        self._elements.clear()
        self._root_ids.clear()
        self._theme_name = ""
        self._theme_path = None
        self._author = ""
        self.endResetModel()
        logger.debug("Model cleared")
    
    def create_new(self, name: str) -> None:
        """
        Create a new theme with default structure.
        
        Args:
            name: Name for the new theme
        """
        self.clear()
        self._theme_name = name
        
        # Add default background group
        bg_group = create_element(
            ElementType.GROUP,
            name="Background"
        )
        self.add_element(bg_group)
        
        # Add UI Elements group
        ui_group = create_element(
            ElementType.GROUP,
            name="UI Elements"
        )
        self.add_element(ui_group)
        
        # Add Dynamic Elements group
        dynamic_group = create_element(
            ElementType.GROUP,
            name="Dynamic Elements"
        )
        self.add_element(dynamic_group)
        
        logger.info(f"Created new theme: {name}")
    
    def load_from_data(self, data: Dict[str, Any]) -> None:
        """
        Load theme from parsed YAML data.
        
        Args:
            data: Theme data dictionary
        """
        self.clear()
        
        # Load display settings
        display = data.get("display", {})
        self._display_size = display.get("DISPLAY_SIZE", "5\"")
        self._display_orientation = display.get("DISPLAY_ORIENTATION", "landscape")
        led = display.get("DISPLAY_RGB_LED", "255, 255, 255")
        if isinstance(led, str):
            self._display_rgb_led = tuple(int(c.strip()) for c in led.split(","))
        else:
            self._display_rgb_led = tuple(led)
        
        # Load background
        background = data.get("background", {})
        if background:
            self._background_type = background.get("type", "image")
            self._background_path = background.get("path", "background.png")
            if self._background_type == "video":
                self._video_config = background.get("video", {})
        
        # Create Background group
        bg_group = create_element(ElementType.GROUP, name="Background")
        self.add_element(bg_group)
        
        # Load UI elements
        ui_group = create_element(ElementType.GROUP, name="UI Elements")
        self.add_element(ui_group)
        
        for elem_data in data.get("ui_elements", []):
            element = self._parse_element(elem_data)
            if element:
                self.add_element(element, parent_id=ui_group.id)
        
        # Load dynamic elements
        dynamic_group = create_element(ElementType.GROUP, name="Dynamic Elements")
        self.add_element(dynamic_group)
        
        for elem_data in data.get("dynamic_elements", []):
            element = self._parse_element(elem_data)
            if element:
                self.add_element(element, parent_id=dynamic_group.id)
        
        logger.info("Loaded theme from data")
    
    def _parse_element(self, data: Dict[str, Any]) -> Optional[Element]:
        """Parse element data dictionary into Element object."""
        elem_type = data.get("type", "").lower()
        
        type_map = {
            "rectangle": ElementType.RECTANGLE,
            "circle": ElementType.CIRCLE,
            "ellipse": ElementType.ELLIPSE,
            "triangle": ElementType.TRIANGLE,
            "line": ElementType.LINE,
            "text": ElementType.TEXT,
            "image": ElementType.IMAGE,
            "icon": ElementType.ICON,
            "group": ElementType.GROUP,
            "dynamic_text": ElementType.DYNAMIC_TEXT,
        }
        
        element_type = type_map.get(elem_type)
        if not element_type:
            logger.warning(f"Unknown element type: {elem_type}")
            return None
        
        element = create_element(element_type, **data)
        return element
    
    def to_data(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for YAML serialization.
        
        Returns:
            Theme data dictionary
        """
        data = {
            "display": {
                "DISPLAY_SIZE": self._display_size,
                "DISPLAY_ORIENTATION": self._display_orientation,
                "DISPLAY_RGB_LED": f"{self._display_rgb_led[0]}, {self._display_rgb_led[1]}, {self._display_rgb_led[2]}",
            },
            "background": {
                "type": self._background_type,
                "path": self._background_path,
            },
            "ui_elements": [],
            "dynamic_elements": [],
        }
        
        if self._background_type == "video":
            data["background"]["video"] = self._video_config
        
        # Find UI Elements and Dynamic Elements groups
        for elem_id in self._root_ids:
            element = self._elements.get(elem_id)
            if not element:
                continue
            
            if element.name == "UI Elements":
                for child_id in element.children:
                    child = self._elements.get(child_id)
                    if child:
                        data["ui_elements"].append(child.to_dict())
            elif element.name == "Dynamic Elements":
                for child_id in element.children:
                    child = self._elements.get(child_id)
                    if child:
                        data["dynamic_elements"].append(child.to_dict())
        
        return data
    
    # --- Display Settings ---
    
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
