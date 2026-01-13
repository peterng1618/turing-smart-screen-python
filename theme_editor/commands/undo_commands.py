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
        element_or_type: Any,  # Element or ElementType
        parent_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        parent: Optional[QUndoCommand] = None
    ):
        # Determine if we received an Element instance or ElementType
        if isinstance(element_or_type, ElementType):
            self._element_type = element_or_type
            self._element = None
        else:
            # Assume it's an Element instance
            self._element = element_or_type
            self._element_type = self._element.element_type
            
        super().__init__(f"Add {self._element_type.name}", parent)
        
        self._model = model
        self._parent_id = parent_id
        self._properties = properties or {}
        self._element_id: Optional[str] = self._element.id if self._element else None
    
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
    """Command for reordering elements (supports reparenting)."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        new_parent_id: Optional[str],
        new_row: int,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Reorder Element", parent)
        
        self._model = model
        self._element_id = element_id
        self._new_parent_id = new_parent_id
        self._new_row = new_row
        
        # Capture old state for undo
        element = model.get_element(element_id)
        self._old_parent_id = element.parent_id if element else None
        self._old_row = 0
        
        # Find old row
        if element:
            if self._old_parent_id:
                p = model.get_element(self._old_parent_id)
                if p and element_id in p.children:
                    self._old_row = p.children.index(element_id)
            else:
                if element_id in model._root_ids:
                    self._old_row = model._root_ids.index(element_id)
    
    def undo(self) -> None:
        self._model.reorder_element(self._element_id, self._old_parent_id, self._old_row)
    
    def redo(self) -> None:
        self._model.reorder_element(self._element_id, self._new_parent_id, self._new_row)


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


class DuplicateElementCommand(QUndoCommand):
    """Command for duplicating an element."""
    
    def __init__(
        self,
        model: ThemeModel,
        element_id: str,
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Duplicate Element", parent)
        
        self._model = model
        self._source_id = element_id
        self._new_element_id: Optional[str] = None
        # We need to capture the duplicated structure so Redo can restore the exact same IDs
        # if the user Undo -> Redo.
        # But ThemeModel.duplicate_element logic generates new IDs every time.
        # So we should probably let duplicate_element do the work on first Redo,
        # but capturing the result is tricky if duplicate_element doesn't support "reinstalling"
        # a specific tree with specific IDs.
        
        # Strategy: 
        # On first redo (or just execution), call duplicate_element.
        # It generates a new subtree.
        # We grab the root ID of that new subtree.
        # On Undo, we remove that root ID (just like Add).
        # On subsequent Redo, we need to re-add that subtree.
        # But wait, remove_element removes it from model but returns the Element object.
        # So we can hold onto the removed element (and its children objects derived from it)
        # However, ThemeModel.remove_element recursively removes children from dict.
        # So if we hold the root element, do we hold the whole tree?
        # ThemeModel.remove_element returns the element object.
        # But children are just ID strings in the element.children list.
        # If we remove_element(root), it removes root from _elements.
        # The recursion in remove_element also pops child objects from _elements.
        # So unless we kept a reference to them, they differ.
        # remove_element implementation: 
        # `_cleanup_children(element)` -> recursively pops from `self._elements`.
        # It doesn't return the list of removed child objects. It just drops them.
        # So standard remove_element DESTROYS the child tree structure in the sense that the objects are gone.
        # We need a `remove_element_tree` or similar that returns the full object graph?
        # Or duplicate_element should happen entirely inside Redo every time?
        # If we re-generate IDs every time on Redo, that's fine for simple duplication.
        # But if the user performed SUBSEQUENT actions on the duplicated item (e.g. Move it),
        # those subsequent undo commands reference specific IDs.
        # If we undo duplicate, then redo duplicate and get NEW IDs, the subsequent Redo actions (Move X)
        # will look for old ID X which doesn't exist.
        # CRITICAL: IDs MUST PERSIST across Undo/Redo.
        
        # Solution:
        # duplicate_element needs to accept an optional 'target_id' or we need a way
        # to inject a pre-constructed element tree.
        # `model.add_element_tree(root_element, ...)` ?
        # For now, let's implement the logic here in the Command.
        
        self._created_element_tree: Optional[Dict[str, Element]] = None
        self._root_id: Optional[str] = None
        self._parent_id: Optional[str] = None
        self._index: int = -1

    def redo(self) -> None:
        if self._root_id and self._created_element_tree:
            # Re-restore the previously created tree
            # We need a method in model to bulk-inject elements?
            # Or just iterate and add.
            # But order matters if we want to preserve hierarchy references.
            # Actually, since we have the objects with parent_id/children lists already set correctly,
            # we just need to put them back into self._elements dict.
            # And then link the root back to its parent.
            
            # We cannot access model._elements directly technically (it's protected).
            # But we are in the same package (mostly).
            # Better: add a public method `restore_element_tree` to ThemeModel.
            self._model.restore_element_tree(
                self._created_element_tree, 
                self._root_id, 
                self._parent_id, 
                self._index
            )
        else:
            # First execution
            new_id = self._model.duplicate_element(self._source_id)
            if new_id:
                self._root_id = new_id
                
                # capture context for undo/redo
                elem = self._model.get_element(new_id)
                if elem:
                    self._parent_id = elem.parent_id
                    # Find index
                    if self._parent_id:
                        p = self._model.get_element(self._parent_id)
                        if p: self._index = p.children.index(new_id)
                    else:
                        if new_id in self._model._root_ids:
                            self._index = self._model._root_ids.index(new_id)
                            
                    # Capture the whole tree of objects for subsequent Redo
                    # We can use get_all_children_ids + get_element to shallow copy the dict entries
                    all_ids = [new_id] + self._model.get_all_children_ids(new_id)
                    self._created_element_tree = {}
                    for eid in all_ids:
                        e = self._model.get_element(eid)
                        if e:
                            self._created_element_tree[eid] = e
    
    def undo(self) -> None:
        if self._root_id:
            # We use a special remove that returns the tree or we just trust our _created_element_tree snapshot?
            # If the user made changes to properties, the objects in _elements are modified.
            # If we rely on _created_element_tree (which points to those same objects), 
            # we preserve the changes if we re-add them later? 
            # Yes, because Python objects are ref-counted.
            # UNLESS subsequent commands replaced the objects.
            # Standard property changes modify attributes in place.
            # So holding the Element object is sufficient.
            
            self._model.remove_element_tree(self._root_id)


class SetGuidesCommand(QUndoCommand):
    """Command for updating editor guides."""
    
    def __init__(
        self,
        model: ThemeModel,
        h_guides: List[int],
        v_guides: List[int],
        parent: Optional[QUndoCommand] = None
    ):
        super().__init__("Set Guides", parent)
        self._model = model
        self._new_h = h_guides
        self._new_v = v_guides
        self._old_h = model.guides_h
        self._old_v = model.guides_v
        
    def undo(self) -> None:
        self._model._apply_guides(self._old_h, self._old_v)
        
    def redo(self) -> None:
        self._model._apply_guides(self._new_h, self._new_v)
