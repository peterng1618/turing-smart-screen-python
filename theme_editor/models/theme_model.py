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
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData,
    pyqtSignal
)
from PyQt6.QtGui import QUndoStack

from theme_editor.models.element import (
    Element, ElementType, create_element,
    TriangleElement, BackgroundImageElement, BackgroundVideoElement, ThemeInfoElement
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
            # Qt.ItemFlag.ItemIsUserCheckable |  # Removed as per UI requirement
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
        
        # Determine target parent
        if parent.isValid():
            target_parent_id = parent.internalPointer()
        else:
            target_parent_id = None
            
        # If row is -1, it means drop on the parent itself (append)
        # But wait, QAbstractItemModel docs say row is -1 if dropped on parent.
        if row == -1:
            if target_parent_id:
                # Append to end of children
                target_element = self._elements.get(target_parent_id)
                if target_element:
                    row = len(target_element.children)
            else:
                # Append to end of root
                row = len(self._root_ids)
                
        # Handle reordering via Undo Stack
        from theme_editor.commands.undo_commands import ReorderElementCommand
        
        # We process moves sequentially.
        # Note: If we move multiple items, pushed commands create multiple undo steps
        # unless we wrap them in a macro.
        
        if len(element_ids) > 1:
            self._undo_stack.beginMacro("Reorder Layers")
            
        current_row = row
        for eid in element_ids:
            # Calculate current index for this element to create the command
            # The command logic takes (element_id, old_index, new_index)
            # But wait, ReorderElementCommand expects indices within the SAME parent?
            # Or does it handle reparenting?
            # Looking at ReorderElementCommand: 
            # It takes old_index, new_index. BUT it assumes parent is the SAME?
            # 'ReorderElementCommand' implementation shows:
            # self._model.get_element(self._element_id) ...
            # it uses internal methods to remove and insert.
            # But wait, the current Reorder implementation in undo_commands.py 
            # assumes modifying the element's CURRENT parent's children list.
            # It does NOT handle changing parents.
            # We implemented 'reorder_element' in 'ThemeModel' which supports reparenting.
            # But the 'ReorderElementCommand' class I read in undo_commands.py (lines 203+) 
            # uses '_reorder' helper which just removes/inserts in current list.
            # It does NOT support changing parent_id.
            
            # Correction: We need a 'ReparentElementCommand' or update 'ReorderElementCommand'
            # to support target_parent.
            # Actually, drag and drop OFTEN changes parents (grouping).
            # So I should implement a better command or use 'reorder_element' inside the command.
            
            # Let's assume we update ReorderElementCommand to call model.reorder_element
            # taking (element_id, target_parent_id, target_row).
            # That matches the method signature we added to ThemeModel.
            
            # I will push a command that calls 'model.reorder_element'.
            # I need to update 'ReorderElementCommand' structure first?
            # Yes, existing command is too simple.
            
            # For now, let's assume I WILL update ReorderElementCommand shortly.
            # I'll create the command call assuming the new signature.
            
            self._undo_stack.push(ReorderElementCommand(
                self, eid, target_parent_id, current_row
            ))
            current_row += 1
            
        if len(element_ids) > 1:
            self._undo_stack.endMacro()
        
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
    
    def duplicate_element(self, element_id: str) -> Optional[str]:
        """
        Duplicate an element and its children.
        
        Args:
            element_id: ID of element to duplicate
            
        Returns:
            ID of new element, or None if failed
        """
        source = self._elements.get(element_id)
        if not source:
            return None
            
        # 1. Deep copy the element structure
        import copy
        new_element = copy.deepcopy(source)
        
        # 2. Assign new IDs recursively
        # We need to map old IDs to new IDs to fix parent/child relationships
        id_map = {}
        
        def _reassign_ids(elem):
            import uuid
            old_id = elem.id
            new_id = str(uuid.uuid4())
            elem.id = new_id
            id_map[old_id] = new_id
            
            # Recurse for children
            if hasattr(elem, 'children'):
                # We iterate over a copy because we'll replace the list content
                # But wait, deepcopy already copied the list. 
                # The children IN the list are strings (IDs).
                pass
            
            return new_id

        # Pass 1: Assign new IDs and build map
        # We need to traverse the *new* structure. 
        # Since deepcopy copied the objects, we can modify them in place.
        # But we need to traverse recursively.
        
        # Helper to traverse object graph
        def _traverse_and_remap(elem):
            import uuid
            old_id = elem.id # deepcopy kept the old ID
            new_id = str(uuid.uuid4())
            elem.id = new_id
            
            # Register in model
            # But wait, we can't register yet/here easily if we want to be clean.
            # Let's just fix up IDs first.
            
            # Process children
            if hasattr(elem, 'children'):
                new_children_ids = []
                # Retrieve children objects? No, deepcopy didn't copy children if they are just ID strings in a list.
                # The 'children' attribute is a list of Strings.
                # So deepcopy gave us a new LIST of the SAME Strings.
                # We need to find the source objects for those children, deep copy them too?
                # Ah, 'children' in Element is list[str]. 
                # So deepcopy(source) only copied the source element, NOT its children elements (which are separate objects in self._elements).
                pass
        
        # Re-think: deepcopy(source) is shallow regarding the tree if children are just IDs.
        # We need to manually deep copy the tree.
        
        def _clone_tree(src_elem) -> Element:
            # Clone attributes
            import copy
            new_elem = copy.deepcopy(src_elem)
            
            # Generate new ID
            import uuid
            new_elem.id = str(uuid.uuid4())
            
            # Clear children list (it contains old IDs)
            if hasattr(new_elem, 'children'):
                new_elem.children = []
                
                # Clone children recursively
                if hasattr(src_elem, 'children'):
                    for child_id in src_elem.children:
                        child_src = self._elements.get(child_id)
                        if child_src:
                            child_clone = _clone_tree(child_src)
                            child_clone.parent_id = new_elem.id
                            new_elem.children.append(child_clone.id)
                            # Store in temp dict until we are ready to add to model
                            cloned_elements[child_clone.id] = child_clone
            
            return new_elem

        cloned_elements = {} # To hold all new objects
        new_root = _clone_tree(source)
        cloned_elements[new_root.id] = new_root
        
        # 3. Add to model
        # Modify name to indicate copy
        new_root.name = f"{new_root.name} (Copy)"
        
        # Determine insertion point (after original)
        parent_id = source.parent_id
        index = -1
        
        if parent_id:
            parent = self._elements.get(parent_id)
            if parent and source.id in parent.children:
                index = parent.children.index(source.id) + 1
        else:
            if source.id in self._root_ids:
                index = self._root_ids.index(source.id) + 1
        
        # Bulk add to _elements dict
        self._elements.update(cloned_elements)
        
        # Signal the addition of the root (and children implicit?)
        # Standard add_element expects to handle insertion logic.
        # Let's use add_element for the root, but we need to ensure children are handled.
        # Since we manually added children to the new_root.children list and self._elements,
        # we just need to hook new_root into the parent.
        
        if parent_id:
            parent_elem = self._elements.get(parent_id)
            parent_index = self._get_index_for_element(parent_id)
            
            self.beginInsertRows(parent_model_index, index, index)
            parent_elem.children.insert(index, new_root.id)
            self.endInsertRows()
        else:
            self.beginInsertRows(QModelIndex(), index, index)
            self._root_ids.insert(index, new_root.id)
            self.endInsertRows()
            
        # We should emit element_added for all new elements so views/guides can update
        for cid, _ in cloned_elements.items():
            self.element_added.emit(cid)
            
        return new_root.id

    def reorder_element(self, element_id: str, target_parent_id: Optional[str], row: int) -> bool:
        """
        Move an element to a new position in the tree.
        
        Args:
            element_id: ID of element to move
            target_parent_id: New parent ID (None for root)
            row: Target row index (desired final index in the list)
            
        Returns:
            True if moved
        """
        element = self._elements.get(element_id)
        if not element:
            return False
            
        # 1. Remove from old location
        old_parent_id = element.parent_id
        
        # Prevent moving into itself
        if target_parent_id == element_id:
            return False
            
        # Prevent moving into a descendant
        if target_parent_id:
            descendants = self.get_all_children_ids(element_id)
            if target_parent_id in descendants:
                return False
        
        if old_parent_id:
            old_parent = self._elements.get(old_parent_id)
            if not old_parent or element_id not in old_parent.children:
                return False
            
            old_row = old_parent.children.index(element_id)
            source_parent_index = self._get_index_for_element(old_parent_id)
        else:
            if element_id not in self._root_ids:
                return False
            old_row = self._root_ids.index(element_id)
            source_parent_index = QModelIndex()
        
        # Calculate destination for Qt beginMoveRows
        
        dest_list_len = 0
        if target_parent_id:
            target_parent = self._elements.get(target_parent_id)
            if not target_parent:
                return False
            dest_parent_index = self._get_index_for_element(target_parent_id)
            dest_list_len = len(target_parent.children)
        else:
            target_parent = None
            dest_parent_index = QModelIndex()
            dest_list_len = len(self._root_ids)

        # Qt Signal Row Calculation
        qt_dest_row = row
        if old_parent_id == target_parent_id:
            # Moving within same list
            if row > old_row:
                # If target is after source, Qt expects index+1 (insertion point if not removed)
                qt_dest_row = row + 1
        
        # Clamp qt_dest_row for safety with beginMoveRows
        # Note: Qt allows appending, so index == rowCount is valid
        # Logic above handles standard cases.
        
        if not self.beginMoveRows(source_parent_index, old_row, old_row, dest_parent_index, qt_dest_row):
             return False
             
        # Execute Move on Data
        if old_parent_id:
            self._elements[old_parent_id].children.pop(old_row)
        else:
            self._root_ids.pop(old_row)
            
        # Insert at desired final index
        # Since we popped, indices shifted. 
        # But list.insert(i, x) inserts before i. 
        # If we want final index 'row', we just insert at 'row'.
        
        if target_parent_id:
            # Bounds check for list insertion
            if row > len(target_parent.children):
                target_parent.children.append(element_id)
            else:
                target_parent.children.insert(row, element_id)
        else:
            if row > len(self._root_ids):
                self._root_ids.append(element_id)
            else:
                self._root_ids.insert(row, element_id)
            
        element.parent_id = target_parent_id
        
        self.endMoveRows()
        return True

    def remove_element_tree(self, root_id: str) -> None:
        """
        Remove an element and its entire subtree from the model structure (UI),
        but keep the objects alive if referenced elsewhere (like by UndoCommand).
        """
        self.remove_element(root_id)

    def restore_element_tree(
        self, 
        element_map: Dict[str, Element], 
        root_id: str, 
        parent_id: Optional[str], 
        index: int
    ) -> None:
        """
        Restore a previously removed tree of elements.
        
        Args:
            element_map: Dict of all elements in the tree (id -> Element)
            root_id: ID of the root of the tree to re-attach
            parent_id: ID of the parent to attach to
            index: Index to insert at
        """
        if not element_map or not root_id:
            return

        # 1. Restore all elements to the internal dict
        self._elements.update(element_map)
        
        # 2. Re-attach root to hierarchy
        root_element = self._elements.get(root_id)
        if not root_element:
            return
            
        # Determine parent index and list
        if parent_id:
            parent = self._elements.get(parent_id)
            if not parent:
                # Parent gone? Fallback to root
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
        
        self.beginInsertRows(parent_model_index, insert_row, insert_row)
        
        # We assume child-parent links inside the tree are preserved in 'element_map' objects
        # We only need to link the root
        root_element.parent_id = parent_id
        
        if parent_id:
            parent = self._elements.get(parent_id)
            if index < 0:
                parent.children.append(root_id)
            else:
                parent.children.insert(index, root_id)
        else:
            current_list.insert(insert_row, root_id)
            
        self.endInsertRows()
        
        # Emit added signals for everything
        for eid in element_map:
            self.element_added.emit(eid)

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
        
        # Helper to recursively get children of a group as a flat list of dicts
        def _get_group_children_recursive(group_element, target_list):
             if hasattr(group_element, 'children'):
                for child_id in group_element.children:
                    child = self._elements.get(child_id)
                    if child:
                        if child.element_type == ElementType.GROUP:
                             _get_group_children_recursive(child, target_list)
                        else:
                             target_list.append(child.to_dict())

        # Collect elements from root
        for elem_id in self._root_ids:
            element = self._elements.get(elem_id)
            if not element:
                continue
            
            # Skip special singletons (handled above)
            if element.element_type in (ElementType.BACKGROUND_IMAGE, ElementType.BACKGROUND_VIDEO, ElementType.THEME_INFO):
                continue
                
            # Check for legacy named groups "UI Elements" and "Dynamic Elements"
            # We preserve their content into the respective flat lists for compatibility
            if element.name == "UI Elements" and element.element_type == ElementType.GROUP:
                _get_group_children_recursive(element, data["ui_elements"])
                continue
            elif element.name == "Dynamic Elements" and element.element_type == ElementType.GROUP:
                _get_group_children_recursive(element, data["dynamic_elements"])
                continue
            
            # Identify where this root element belongs based on type
            is_dynamic = element.element_type in (
                ElementType.DYNAMIC_TEXT, 
                ElementType.GRAPH, 
                ElementType.RADIAL, 
                ElementType.LINE_GRAPH
            )
            
            if is_dynamic:
                data["dynamic_elements"].append(element.to_dict())
            else:
                # Groups (other than special ones), Shapes, Text, etc. -> UI Elements
                # If it's a generic group, we might want to recurse or just save it as a group?
                # The v2 format seems to support flat lists. 
                # If the element is a Group, we should probably save its children too?
                # Current Element.to_dict (we assume) saves its properties. 
                # But does it save children?
                # If the editor supports groups in the YAML, we can just append it.
                # If the editor expects flat lists (which the previous code implies by flattening named groups),
                # then we should probably flatten generic groups too OR just append them if the loader handles them.
                # Given 'ui_elements' is a list, let's append the element itself.
                # If it's a group, the loader needs to handle it.
                # However, looking at the previous specific handling of "UI Elements" group, 
                # it suggests the YAML format expects a flat list of items, NOT a hierarchy.
                # BUT, ThemeModel supports hierarchy.
                # Let's assume for now we just save the root element. 
                # If it is a group, its to_dict might need to include children IDs or data?
                # Actually, standard V2 format usually flattens everything into ui_elements.
                # Let's verify if GroupElement.to_dict includes children data.
                # Since we can't see Element.to_dict, let's look at how we loaded.
                # Loader: iterates lists, adds to parent.
                # So if we save a Group object in the list, does it contain children?
                # If not, we lose the children.
                # Safe bet: Flatten everything into the list, UNLESS the format supports nesting.
                # The previous code flattened "UI Elements" group.
                # Let's recursively flatten groups for now to be safe and compatible with the apparent "flat list" expectation of the YAML structure shown in yaml_io.py.
                
                if element.element_type == ElementType.GROUP:
                     _get_group_children_recursive(element, data["ui_elements"])
                else:
                     data["ui_elements"].append(element.to_dict())
        
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

    def duplicate_element(self, element_id: str) -> Optional[str]:
        """
        Duplicate an element and its children.
        
        Args:
            element_id: ID of element to duplicate
            
        Returns:
            ID of the new element, or None if failed
        """
        element = self.get_element(element_id)
        if not element:
            return None
            
        # Helper to recursively copy
        def copy_recursive(elem: Element, parent_id: Optional[str]) -> Element:
            import copy
            
            # Manual copy of properties
            props = elem.__dict__.copy()
            # Remove identity fields
            props.pop('id', None)
            props.pop('parent_id', None)
            props.pop('children', None)
            
            # Deep copy mutable properties
            props = copy.deepcopy(props)
            
            new_elem = create_element(elem.element_type, **props)
            
            # Add to model
            self.add_element(new_elem, parent_id)
            
            # Recurse children
            for child_id in elem.children:
                child = self.get_element(child_id)
                if child:
                    copy_recursive(child, new_elem.id)
                    
            return new_elem

        # Duplicate
        new_root = copy_recursive(element, element.parent_id)
        
        # Append " (Copy)" to the root name to differentiate
        if hasattr(new_root, 'name'):
            new_root.name = f"{new_root.name} (Copy)"
        
        self.layoutChanged.emit()
        return new_root.id

    def remove_element_tree(self, root_id: str) -> Dict[str, Element]:
        """
        Remove an element and all its descendants, returning them as a map.
        
        Args:
            root_id: ID of the root element to remove
            
        Returns:
            Dictionary mapping element IDs to Element objects
        """
        removed_map = {}
        
        # Helper to collect and remove
        def collect_remove(eid: str):
            elem = self._elements.get(eid)
            if not elem:
                return
            
            # Recurse first
            children_copy = list(elem.children)
            for child_id in children_copy:
                collect_remove(child_id)
            
            # Remove from model dict
            if eid in self._elements:
                removed_map[eid] = self._elements.pop(eid)
                
        # Main remove logic
        if root_id not in self._elements:
            return {}
            
        root = self._elements[root_id]
        
        # Detach from parent
        if root.parent_id:
            parent = self._elements.get(root.parent_id)
            if parent and root_id in parent.children:
                parent.children.remove(root_id)
        elif root_id in self._root_ids:
            self._root_ids.remove(root_id)
            
        # Collect and remove all from _elements
        collect_remove(root_id)
        
        self.layoutChanged.emit()
        self.element_removed.emit(root_id)
        
        return removed_map

    def restore_element_tree(self, element_map: Dict[str, Element], root_id: str, parent_id: Optional[str], index: int) -> None:
        """
        Restore a previously removed tree of elements.
        
        Args:
            element_map: Dictionary of {id: Element} to restore
            root_id: ID of the root element in the map
            parent_id: ID of the parent to attach to
            index: Index to insert at (in parent's children or root list)
        """
        if not element_map or root_id not in element_map:
            return
            
        # Put all elements back into dict
        self._elements.update(element_map)
        
        # Re-attach root to parent
        root = element_map[root_id]
        root.parent_id = parent_id
        
        if parent_id:
            parent = self._elements.get(parent_id)
            if parent:
                if index >= 0 and index <= len(parent.children):
                    parent.children.insert(index, root_id)
                else:
                    parent.children.append(root_id)
        else:
            if index >= 0 and index <= len(self._root_ids):
                self._root_ids.insert(index, root_id)
            else:
                self._root_ids.append(root_id)
                
        self.layoutChanged.emit()
        self.element_added.emit(root_id)
