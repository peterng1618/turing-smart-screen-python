# SPDX-License-Identifier: GPL-3.0-or-later
"""
Undo Commands for Theme Editor v2.

Provides QUndoCommand subclasses for all reversible operations:
- Move element
- Resize element
- Change property
- Add element
- Delete element
- Reorder layers
- Group/Ungroup
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtGui import QUndoCommand

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import Element, ElementType, create_element

logger = logging.getLogger(__name__)


class MoveElementCommand(QUndoCommand):
    """Command for moving an element."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        old_x: int,
        old_y: int,
        new_x: int,
        new_y: int,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Move Element", parent)
        
        self._model = model
        self._element_id = element_id
        self._old_x = old_x
        self._old_y = old_y
        self._new_x = new_x
        self._new_y = new_y
    
    def undo(self) -> None:
        self._model.move_element(self._element_id, self._old_x, self._old_y)
    
    def redo(self) -> None:
        self._model.move_element(self._element_id, self._new_x, self._new_y)
    
    def mergeWith(self, other: QUndoCommand) -> bool:
        """Merge consecutive moves of the same element."""
        if not isinstance(other, MoveElementCommand):
            return False
        if other._element_id != self._element_id:
            return False
        
        self._new_x = other._new_x
        self._new_y = other._new_y
        return True
    
    def id(self) -> int:
        """Return command ID for merging."""
        return 1


class ChangePropertyCommand(QUndoCommand):
    """Command for changing an element property."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        property_name: str,
        old_value: Any,
        new_value: Any,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__(f"Change {property_name}", parent)
        
        self._model = model
        self._element_id = element_id
        self._property_name = property_name
        self._old_value = old_value
        self._new_value = new_value
    
    def undo(self) -> None:
        self._model.set_element_property(
            self._element_id, self._property_name, self._old_value
        )
    
    def redo(self) -> None:
        self._model.set_element_property(
            self._element_id, self._property_name, self._new_value
        )


class ChangePropertiesCommand(QUndoCommand):
    """Command for changing multiple element properties atomically."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        text: str = "Change Properties",
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__(text, parent)
        self._model = model
        self._element_id = element_id
        self._old_values = old_values
        self._new_values = new_values
    
    def undo(self) -> None:
        for prop, val in self._old_values.items():
            self._model.set_element_property(self._element_id, prop, val)
    
    def redo(self) -> None:
        for prop, val in self._new_values.items():
            self._model.set_element_property(self._element_id, prop, val)


class AddElementCommand(QUndoCommand):
    """Command for adding a new element."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_type: ElementType,
        parent_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__(f"Add {element_type.name}", parent)
        
        self._model = model
        self._element_type = element_type
        self._parent_id = parent_id
        self._properties = properties or {}
        self._element: Optional[Element] = None
        self._element_id: Optional[str] = None
    
    def undo(self) -> None:
        if self._element_id:
            self._model.remove_element(self._element_id)
    
    def redo(self) -> None:
        if self._element:
            # Re-add existing element
            self._model.add_element(self._element, self._parent_id)
        else:
            # Create new element
            self._element = create_element(self._element_type, **self._properties)
            self._element_id = self._model.add_element(self._element, self._parent_id)


class DeleteElementCommand(QUndoCommand):
    """Command for deleting an element."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        parent: Optional[QUndoCommand] = None
    ):
        element = model.get_element(element_id)
        name = element.name if element else element_id
        super().__init__(f"Delete {name}", parent)
        
        self._model = model
        self._element_id = element_id
        self._element: Optional[Element] = None
        self._parent_id: Optional[str] = None
        self._index: int = -1
    
    def undo(self) -> None:
        if self._element:
            self._model.add_element(self._element, self._parent_id, self._index)
    
    def redo(self) -> None:
        element = self._model.get_element(self._element_id)
        if element:
            self._element = element
            self._parent_id = element.parent_id
            
            # Remember position for undo
            if self._parent_id:
                parent = self._model.get_element(self._parent_id)
                if parent and self._element_id in parent.children:
                    self._index = parent.children.index(self._element_id)
            else:
                if self._element_id in self._model._root_ids:
                    self._index = self._model._root_ids.index(self._element_id)
            
            self._model.remove_element(self._element_id)


class ReorderElementCommand(QUndoCommand):
    """Command for reordering elements within their parent."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        old_index: int,
        new_index: int,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Reorder Element", parent)
        
        self._model = model
        self._element_id = element_id
        self._old_index = old_index
        self._new_index = new_index
    
    def undo(self) -> None:
        self._reorder(self._new_index, self._old_index)
    
    def redo(self) -> None:
        self._reorder(self._old_index, self._new_index)
    
    def _reorder(self, from_idx: int, to_idx: int) -> None:
        """Move element from one index to another."""
        element = self._model.get_element(self._element_id)
        if not element:
            return
        
        if element.parent_id:
            parent = self._model.get_element(element.parent_id)
            if parent:
                parent.children.remove(self._element_id)
                parent.children.insert(to_idx, self._element_id)
        else:
            self._model._root_ids.remove(self._element_id)
            self._model._root_ids.insert(to_idx, self._element_id)
        
        self._model.layoutChanged.emit()


class GroupElementsCommand(QUndoCommand):
    """Command for grouping multiple elements."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_ids: List[str],
        group_name: str = "Group",
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__(f"Group {len(element_ids)} elements", parent)
        
        self._model = model
        self._element_ids = element_ids
        self._group_name = group_name
        self._group: Optional[Element] = None
        self._original_parents: Dict[str, Optional[str]] = {}
        self._original_indices: Dict[str, int] = {}
    
    def undo(self) -> None:
        if not self._group:
            return
        
        # Move elements back to their original parents
        for elem_id in self._element_ids:
            element = self._model.get_element(elem_id)
            if element:
                # Remove from group
                if elem_id in self._group.children:
                    self._group.children.remove(elem_id)
                
                # Restore original parent
                original_parent = self._original_parents.get(elem_id)
                original_index = self._original_indices.get(elem_id, -1)
                
                element.parent_id = original_parent
                
                if original_parent:
                    parent = self._model.get_element(original_parent)
                    if parent:
                        parent.children.insert(original_index, elem_id)
                else:
                    self._model._root_ids.insert(original_index, elem_id)
        
        # Remove the group
        self._model.remove_element(self._group.id)
        self._model.layoutChanged.emit()
    
    def redo(self) -> None:
        # Create group if not exists
        if not self._group:
            self._group = create_element(ElementType.GROUP, name=self._group_name)
        
        # Remember original parents and indices
        for elem_id in self._element_ids:
            element = self._model.get_element(elem_id)
            if element:
                self._original_parents[elem_id] = element.parent_id
                
                if element.parent_id:
                    parent = self._model.get_element(element.parent_id)
                    if parent and elem_id in parent.children:
                        self._original_indices[elem_id] = parent.children.index(elem_id)
                        parent.children.remove(elem_id)
                else:
                    if elem_id in self._model._root_ids:
                        self._original_indices[elem_id] = self._model._root_ids.index(elem_id)
                        self._model._root_ids.remove(elem_id)
                
                element.parent_id = self._group.id
                self._group.children.append(elem_id)
        
        # Add the group
        self._model.add_element(self._group)
        self._model.layoutChanged.emit()


class UngroupElementsCommand(QUndoCommand):
    """Command for ungrouping elements."""
    
    def __init__(
        self,
        model: ThemeModel,
        group_id: str,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Ungroup", parent)
        
        self._model = model
        self._group_id = group_id
        self._group: Optional[Element] = None
        self._group_parent_id: Optional[str] = None
        self._group_index: int = -1
    
    def undo(self) -> None:
        if not self._group:
            return
        
        # Re-add the group
        self._model.add_element(self._group, self._group_parent_id, self._group_index)
        
        # Move elements back into the group
        for child_id in list(self._group.children):
            element = self._model.get_element(child_id)
            if element:
                # Remove from current parent
                if element.parent_id:
                    parent = self._model.get_element(element.parent_id)
                    if parent and child_id in parent.children:
                        parent.children.remove(child_id)
                else:
                    if child_id in self._model._root_ids:
                        self._model._root_ids.remove(child_id)
                
                element.parent_id = self._group.id
        
        self._model.layoutChanged.emit()
    
    def redo(self) -> None:
        group = self._model.get_element(self._group_id)
        if not group:
            return
        
        self._group = group
        self._group_parent_id = group.parent_id
        
        # Remember group position
        if group.parent_id:
            parent = self._model.get_element(group.parent_id)
            if parent and self._group_id in parent.children:
                self._group_index = parent.children.index(self._group_id)
        else:
            if self._group_id in self._model._root_ids:
                self._group_index = self._model._root_ids.index(self._group_id)
        
        # Move children to group's parent
        parent_id = group.parent_id
        for child_id in list(group.children):
            element = self._model.get_element(child_id)
            if element:
                element.parent_id = parent_id
                
                if parent_id:
                    parent = self._model.get_element(parent_id)
                    if parent:
                        parent.children.append(child_id)
                else:
                    self._model._root_ids.append(child_id)
        
        # Remove the group
        self._model.remove_element(self._group_id)
        self._model.layoutChanged.emit()
