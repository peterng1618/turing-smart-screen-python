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
    TextElement, ImageElement, IconElement, GroupElement, DynamicTextElement,
    BackgroundImageElement, BackgroundVideoElement, ThemeInfoElement
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
    guides_changed = pyqtSignal()
    
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
        self._background_x = 0
        self._background_y = 0
        self._background_width = 800
        self._background_height = 480
        self._video_config: Dict[str, Any] = {}
        
        # Theme metadata
        self._theme_name = ""
        self._theme_path: Optional[Path] = None
        self._author = ""
        
        # Guides (for editor only)
        self._guides_h: List[int] = []
        self._guides_v: List[int] = []
    
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
            try:
                parent_id = parent.internalPointer()
                if not isinstance(parent_id, str):
                    return QModelIndex()
                parent_element = self._elements.get(parent_id)
            except Exception:
                return QModelIndex()
                
            if parent_element and 0 <= row < len(parent_element.children):
                child_id = parent_element.children[row]
                return self.createIndex(row, column, child_id)
        
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get parent index of item."""
        if not index.isValid():
            return QModelIndex()
        
        try:
            element_id = index.internalPointer()
            # In some rare cases with C++ object deletion, internalPointer might return garbage
            # causing standard python ops to fail with obscure errors like AttributeError: mro
            if not isinstance(element_id, str):
                return QModelIndex()
                
            element = self._elements.get(element_id)
        except Exception:
            # Catch AttributeError: mro or other corruption issues
            return QModelIndex()
        
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
        
        try:
            parent_id = parent.internalPointer()
            if not isinstance(parent_id, str):
                return 0
            parent_element = self._elements.get(parent_id)
        except Exception:
            return 0
            
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
        
        try:
            element_id = index.internalPointer()
            if not isinstance(element_id, str):
                return None
            element = self._elements.get(element_id)
        except Exception:
            return None
            
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
        
        try:
            element_id = index.internalPointer()
            if not isinstance(element_id, str):
                return False
            element = self._elements.get(element_id)
        except Exception:
            return False
            
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

        try:
            # Check if pointer is valid before returning flags
            element_id = index.internalPointer()
            if not isinstance(element_id, str):
                return Qt.ItemFlag.NoItemFlags
            # Just existence check
            if not self._elements.get(element_id):
                return Qt.ItemFlag.NoItemFlags
        except Exception:
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
        element_ids = []
        for idx in indexes:
            if idx.isValid():
                try:
                    eid = idx.internalPointer()
                    if isinstance(eid, str):
                        element_ids.append(eid)
                except Exception:
                    pass
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
        # Calculate insert position and parent index for Qt signals
        if parent_id:
            parent = self._elements.get(parent_id)
            if not parent:
                # Fallback to root if parent invalid
                parent_id = None
                parent_model_index = QModelIndex()
                current_list = self._root_ids
            else:
                parent_model_index = self._get_index_for_element(parent_id)
                current_list = parent.children
        else:
            parent_model_index = QModelIndex()
            current_list = self._root_ids
            
        insert_row = len(current_list) if index < 0 else index
        
        # Begin model update
        self.beginInsertRows(parent_model_index, insert_row, insert_row)
        
        self._elements[element.id] = element
        element.parent_id = parent_id
        
        if parent_id:
            # We already resolved parent above
            if index < 0:
                parent.children.append(element.id)
            else:
                parent.children.insert(index, element.id)
        else:
            if index < 0:
                self._root_ids.append(element.id)
            else:
                self._root_ids.insert(index, element.id)
        
        self.endInsertRows()
        
        # Emit custom signal for other components
        self.element_added.emit(element.id)
        
        logger.debug(f"Added element: {element.name} ({element.id})")
        return element.id
    
    def remove_element(self, element_id: str) -> Optional[Element]:
        """
        Remove an element from the model.
        
        Args:
            element_id: ID of element to remove
            
        Returns:
            Removed element, or None if not found or protected
        """
        # Check if element exists first
        element = self._elements.get(element_id)
        if not element:
            return None
        
        # Prevent removal of background layers
        if isinstance(element, (BackgroundImageElement, BackgroundVideoElement)):
            logger.debug(f"Cannot remove protected element: {element.name}")
            return None
        
        # Determine parent index and row for removal
        if element.parent_id:
            parent_elem = self._elements.get(element.parent_id)
            if parent_elem and element_id in parent_elem.children:
                row = parent_elem.children.index(element_id)
                parent_index = self._get_index_for_element(element.parent_id)
                
                self.beginRemoveRows(parent_index, row, row)
                parent_elem.children.remove(element_id)
                self.endRemoveRows()
        else:
            if element_id in self._root_ids:
                row = self._root_ids.index(element_id)
                self.beginRemoveRows(QModelIndex(), row, row)
                self._root_ids.remove(element_id)
                self.endRemoveRows()
        
        # Remove from dict
        self._elements.pop(element_id, None)
        
        # Helper to recursively remove children from dict
        # (Model rows for children are implicitly removed when parent is removed,
        # so we don't need beginRemoveRows for them, just dict cleanup)
        def _cleanup_children(elem):
            for child_id in list(elem.children):
                child = self._elements.pop(child_id, None)
                if child:
                    _cleanup_children(child)
        
        _cleanup_children(element)
        
        self.element_removed.emit(element_id)
        
        logger.debug(f"Removed element: {element.name} ({element_id})")
        return element
    
    def get_element(self, element_id: str) -> Optional[Element]:
        """Get element by ID."""
        return self._elements.get(element_id)
    
    def get_all_elements(self) -> List[Element]:
        """Get all elements in the model."""
        return list(self._elements.values())
    
    def get_all_children_ids(self, element_id: str) -> List[str]:
        """Get all child IDs of an element recursively."""
        element = self.get_element(element_id)
        if not element or not hasattr(element, 'children'):
            return []
            
        child_ids = []
        for child_id in element.children:
            child_ids.append(child_id)
            child_ids.extend(self.get_all_children_ids(child_id))
        return child_ids
    
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
        
        # Special scaling for Triangle width/height
        if isinstance(element, TriangleElement) and prop_name in ("width", "height"):
            xs = [element.x1, element.x2, element.x3]
            ys = [element.y1, element.y2, element.y3]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            old_w = max(1, max_x - min_x)
            old_h = max(1, max_y - min_y)
            
            if prop_name == "width":
                scale = value / old_w
                element.x1 = max(-20000, min(20000, int(min_x + (element.x1 - min_x) * scale)))
                element.x2 = max(-20000, min(20000, int(min_x + (element.x2 - min_x) * scale)))
                element.x3 = max(-20000, min(20000, int(min_x + (element.x3 - min_x) * scale)))
            else: # height
                scale = value / old_h
                element.y1 = max(-20000, min(20000, int(min_y + (element.y1 - min_y) * scale)))
                element.y2 = max(-20000, min(20000, int(min_y + (element.y2 - min_y) * scale)))
                element.y3 = max(-20000, min(20000, int(min_y + (element.y3 - min_y) * scale)))

            # Signal changes for all affected properties
            self.element_changed.emit(element_id, "x1", element.x1)
            self.element_changed.emit(element_id, "y1", element.y1)
            self.element_changed.emit(element_id, "x2", element.x2)
            self.element_changed.emit(element_id, "y2", element.y2)
            self.element_changed.emit(element_id, "x3", element.x3)
            self.element_changed.emit(element_id, "y3", element.y3)
            # We don't call setattr(element, prop_name) because 'width'/'height' 
            # are virtual for triangels (derived from points)
            return True

        # Clamp value if it's a coordinate or size to avoid overflow
        if prop_name in ("x", "y", "x1", "y1", "x2", "y2", "x3", "y3", "width", "height"):
            value = max(-20000, min(20000, int(value)))
        elif isinstance(value, (int, float)):
            # General safe bound for 32-bit QSpinBox compatibility
            value = max(-1000000, min(1000000, value))

        setattr(element, prop_name, value)
        self.element_changed.emit(element_id, prop_name, value)
        
        if prop_name == "name":
            index = self._get_index_for_element(element_id)
            if index.isValid():
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        
        # Sync ThemeInfo properties with model attributes
        if isinstance(element, ThemeInfoElement):
            if prop_name == "author":
                self._author = value
            elif prop_name == "display_size":
                self._display_size = value
                # Trigger layout update for canvas resize if needed
                self.element_changed.emit(element_id, "display_size", value)
            elif prop_name == "display_orientation":
                self._display_orientation = value
                self.element_changed.emit(element_id, "display_orientation", value)
            elif prop_name == "display_rgb_led":
                self._display_rgb_led = value
        
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
        self._theme_path = Path(__file__).parent.parent.parent / "res" / "themes" / name
        
        # 1. Add Theme Info (Bottom of Layer List = Index 0)
        theme_info = create_element(ElementType.THEME_INFO, name="Theme Info")
        # Set defaults
        theme_info.author = f"@{self._author}" if self._author else "@your_github_name"
        theme_info.display_size = "5\"" 
        theme_info.display_orientation = "landscape"
        theme_info.display_rgb_led = (50, 50, 50)
        # Sync model fields
        self._author = theme_info.author
        self._display_size = theme_info.display_size
        self._display_orientation = theme_info.display_orientation
        self._display_rgb_led = theme_info.display_rgb_led
        
        self.add_element(theme_info)

        # 2. Add Background layers (siblings of UI Elements now)
        bg_video = create_element(
            ElementType.BACKGROUND_VIDEO,
            name="Background Video"
        )
        self.add_element(bg_video)
        
        bg_image = create_element(
            ElementType.BACKGROUND_IMAGE,
            name="Background Image"
        )
        self.add_element(bg_image)
        
        # 3. Add UI Elements group
        ui_group = create_element(
            ElementType.GROUP,
            name="UI Elements"
        )
        self.add_element(ui_group)
        
        # 4. Add Dynamic Elements group
        dynamic_group = create_element(
            ElementType.GROUP,
            name="Dynamic Elements"
        )
        self.add_element(dynamic_group)
        
        logger.info(f"Created new theme: {name}")
    
    def load_from_data(self, data: Dict[str, Any], theme_path: Optional[Path] = None) -> None:
        """
        Load theme from parsed YAML data.
        
        Args:
            data: Theme data dictionary
            theme_path: Optional explicit path to theme directory
        """
        self.clear()
        
        if theme_path:
            self._theme_path = theme_path
            self._theme_name = theme_path.name
        elif not self._theme_path and self._theme_name:
            # Fallback path resolution
            self._theme_path = Path(__file__).parent.parent.parent / "res" / "themes" / self._theme_name
        # Load author
        self._author = data.get("author", "")
        
        # Load background info from static_images: BACKGROUND
        static_imgs = data.get("static_images", {})
        bg_info = static_imgs.get("BACKGROUND", {})
        self._background_path = bg_info.get("PATH", "background.png")
        self._background_x = bg_info.get("X", 0)
        self._background_y = bg_info.get("Y", 0)
        self._background_width = bg_info.get("WIDTH", 800)
        self._background_height = bg_info.get("HEIGHT", 480)
        
        # Load video config if present
        self._video_config = data.get("video_background", {})
        if self._video_config:
            self._background_type = "video"
        else:
            self._background_type = "image"
            
        # Load guides
        guides = data.get("editor_guides", {})
        self._guides_h = guides.get("horizontal", [])
        self._guides_v = guides.get("vertical", [])
        
        # Load display settings
        display = data.get("display", {})
        self._display_size = display.get("DISPLAY_SIZE", "5\"")
        self._display_orientation = display.get("DISPLAY_ORIENTATION", "landscape")
        led = display.get("DISPLAY_RGB_LED", "255, 255, 255")
        if isinstance(led, str):
            self._display_rgb_led = tuple(int(c.strip()) for c in led.split(","))
        else:
            self._display_rgb_led = tuple(led)
        
        # Load all elements
        # We handle nested structures (groups) by using the parent_id
        main_ui_elements = data.get("ui_elements", [])
        main_dynamic_elements = data.get("dynamic_elements", [])
        
        # 1. Add Theme Info Element (Always first)
        theme_info = create_element(ElementType.THEME_INFO, name="Theme Info")
        theme_info.author = self._author
        theme_info.display_size = self._display_size
        theme_info.display_orientation = self._display_orientation
        theme_info.display_rgb_led = self._display_rgb_led
        self.add_element(theme_info)
        
        # 2. Add Backgrounds as Roots
        bg_video_elem = create_element(ElementType.BACKGROUND_VIDEO, name="Background Video") # Renamed for clarity vs Layer List
        if self._video_config:
            bg_video_elem.source_path = self._video_config.get("SOURCE_PATH", "")
            # ... other video config mapping if needed
            bg_video_elem.enabled = self._video_config.get("ENABLE", True)
        else:
            bg_video_elem.enabled = False
        self.add_element(bg_video_elem) # Root
        
        bg_image_elem = create_element(ElementType.BACKGROUND_IMAGE, name="Background Image Layer")
        bg_image_elem.path = self._background_path
        # We don't have X, Y, WIDTH, HEIGHT on the element class yet, but it uses display size
        self.add_element(bg_image_elem) # Root
        
        # 3. Add Groups
        # Create top-level groups if not present in data
        ui_group = None
        dynamic_group = None
        
        # Check if they already exist in data
        for elem_data in main_ui_elements:
            if elem_data.get("type") == "group" and elem_data.get("name") == "UI Elements":
                ui_group = self._parse_element(elem_data)
                if ui_group:
                    self.add_element(ui_group)
                break
        
        if not ui_group:
            ui_group = create_element(ElementType.GROUP, name="UI Elements")
            self.add_element(ui_group)
            
        for elem_data in main_dynamic_elements:
            if elem_data.get("type") == "group" and elem_data.get("name") == "Dynamic Elements":
                dynamic_group = self._parse_element(elem_data)
                if dynamic_group:
                    self.add_element(dynamic_group)
                break
        
        if not dynamic_group:
            dynamic_group = create_element(ElementType.GROUP, name="Dynamic Elements")
            self.add_element(dynamic_group)
            
        # Load other elements 
        for elem_data in main_ui_elements:
            etype = elem_data.get("type")
            if etype in ["background_image", "background_video", "group", "theme_info"]:
                continue
            element = self._parse_element(elem_data)
            if element:
                self.add_element(element, parent_id=ui_group.id)
        
        # Background elements are already created and added above.

        # 3. Load remaining elements from data
        # Skipping the singletons we already handled
        handled_ids = set()
        for obj in [bg_video_elem, bg_image_elem, ui_group, dynamic_group, theme_info]:
            if obj and hasattr(obj, 'id'):
                handled_ids.add(obj.id)
        
        handled_types = {"background_video", "background_image", "theme_info"}
        
        for elem_data in main_ui_elements:
            eid = elem_data.get("id")
            etype = elem_data.get("type")
            
            # Skip handled singletons by ID or Type
            if (eid and eid in handled_ids) or etype in handled_types:
                continue
            
            if etype == "group" and elem_data.get("name") == "UI Elements":
                continue
                 
            element = self._parse_element(elem_data)
            if element:
                self.add_element(element, parent_id=ui_group.id)
            
        for elem_data in main_dynamic_elements:
            eid = elem_data.get("id")
            etype = elem_data.get("type")
            
            # Skip handled singletons
            if (eid and eid in handled_ids) or etype in handled_types:
                continue
                
            if etype == "group" and elem_data.get("name") == "Dynamic Elements":
                continue
                
            element = self._parse_element(elem_data)
            if element:
                self.add_element(element, parent_id=dynamic_group.id)
        
        self.guides_changed.emit()
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
            "graph": ElementType.GRAPH,
            "radial": ElementType.RADIAL,
            "line_graph": ElementType.LINE_GRAPH,
            "background_image": ElementType.BACKGROUND_IMAGE,
            "background_video": ElementType.BACKGROUND_VIDEO,
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
        # Find Background Elements & Theme Info
        bg_image_elem = None
        bg_video_elem = None
        theme_info_elem = None
        
        for elem in self._elements.values():
            if elem.element_type == ElementType.BACKGROUND_IMAGE:
                bg_image_elem = elem
            elif elem.element_type == ElementType.BACKGROUND_VIDEO:
                bg_video_elem = elem
            elif elem.element_type == ElementType.THEME_INFO:
                theme_info_elem = elem
        
        # Defaults
        bg_path = self._background_path
        bg_x = self._background_x
        bg_y = self._background_y
        bg_w = self._background_width
        bg_h = self._background_height
        
        # Sync from Theme Info if present
        if theme_info_elem:
            self._author = theme_info_elem.author
            self._display_size = theme_info_elem.display_size
            self._display_orientation = theme_info_elem.display_orientation
            self._display_rgb_led = theme_info_elem.display_rgb_led
        
        if bg_image_elem:
            bg_path = getattr(bg_image_elem, "path", bg_path)
            # Use element props if available
            bg_x = getattr(bg_image_elem, "x", bg_x)
            bg_y = getattr(bg_image_elem, "y", bg_y)
            # Use display dimensions as default/authoritative for background
            bg_w = self.display_width
            bg_h = self.display_height
        
        data = {
            "author": self._author,
            "display": {
                "DISPLAY_SIZE": self._display_size,
                "DISPLAY_ORIENTATION": self._display_orientation,
                "DISPLAY_RGB_LED": f"{self._display_rgb_led[0]}, {self._display_rgb_led[1]}, {self._display_rgb_led[2]}",
            },
            "static_images": {
                "BACKGROUND": {
                    "PATH": bg_path,
                    "X": bg_x,
                    "Y": bg_y,
                    "WIDTH": bg_w,
                    "HEIGHT": bg_h,
                }
            },
            "ui_elements": [],
            "dynamic_elements": [],
            "editor_guides": {
                "horizontal": self._guides_h,
                "vertical": self._guides_v,
            },
        }
        
        if bg_video_elem and getattr(bg_video_elem, "enabled", False):
            # Construct video_config from element
            data["video_background"] = {
                "ENABLE": True,
                "SOURCE_PATH": getattr(bg_video_elem, "source_path", ""),
                # ... other properties mapping
            }
        elif self._background_type == "video":
             data["video_background"] = self._video_config
        
        # Find UI Elements and Dynamic Elements groups
        for elem_id in self._root_ids:
            element = self._elements.get(elem_id)
            if not element:
                continue
            
            if element.name == "UI Elements":
                for child_id in element.children:
                    child = self._elements.get(child_id)
                    if child and child.element_type not in [ElementType.BACKGROUND_IMAGE, ElementType.BACKGROUND_VIDEO]:
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

    @property
    def theme_folder(self) -> Optional[Path]:
        """Get the current theme directory."""
        return self._theme_path

    @property
    def author(self) -> str:
        """Get the theme author."""
        return self._author
    
    @author.setter
    def author(self, value: str):
        """Set the theme author."""
        self._author = value

    # --- Guides ---
    
    @property
    def guides_h(self) -> List[int]:
        """Get horizontal guides."""
        return self._guides_h
        
    @property
    def guides_v(self) -> List[int]:
        """Get vertical guides."""
        return self._guides_v
        
    def set_guides(self, horizontal: List[int], vertical: List[int]):
        """Set guides and emit signal."""
        # Remove duplicates and sort
        self._guides_h = sorted(list(set(horizontal)))
        self._guides_v = sorted(list(set(vertical)))
        self.guides_changed.emit()
