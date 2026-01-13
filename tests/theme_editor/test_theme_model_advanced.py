# SPDX-License-Identifier: GPL-3.0-or-later
"""
Advanced unit tests for theme_editor.models.theme_model module.
Focuses on deep copy (duplication) and reordering logic.
"""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtGui import QUndoStack
from PyQt6.QtCore import Qt

from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    ElementType, create_element
)

@pytest.fixture
def undo_stack():
    return MagicMock(spec=QUndoStack)

@pytest.fixture
def editor_state(undo_stack):
    return EditorState(undo_stack)

@pytest.fixture
def model(editor_state):
    m = ThemeModel(editor_state)
    m.create_new("test_advanced")
    return m

class TestAdvancedOperations:
    
    def test_duplicate_element_deep_copy(self, model):
        """Test that duplication creates a deep copy with new IDs."""
        # Create hierarchy: Group -> [Rect, Group -> [Circle]]
        root_group = create_element(ElementType.GROUP, name="Original Group")
        model.add_element(root_group)
        
        rect = create_element(ElementType.RECTANGLE, name="Original Rect")
        model.add_element(rect, parent_id=root_group.id)
        
        sub_group = create_element(ElementType.GROUP, name="Original SubGroup")
        model.add_element(sub_group, parent_id=root_group.id)
        
        circle = create_element(ElementType.CIRCLE, name="Original Circle")
        model.add_element(circle, parent_id=sub_group.id)
        
        # Duplicate Root
        new_id = model.duplicate_element(root_group.id)
        assert new_id is not None
        assert new_id != root_group.id
        
        new_group = model.get_element(new_id)
        assert new_group.name == "Original Group (Copy)"
        assert len(new_group.children) == 2
        
        # Verify children IDs are different
        new_child_ids = new_group.children
        for cid in new_child_ids:
            assert cid not in root_group.children
            # Recursively check
            child = model.get_element(cid)
            if child.element_type == ElementType.GROUP:
                assert child.name == "Original SubGroup" # Name kept (only root gets (Copy)?)
                # Actually my implementation recursively copies but only renames ROOT.
                assert len(child.children) == 1
                grandchild_id = child.children[0]
                grandchild = model.get_element(grandchild_id)
                assert grandchild.id != circle.id
                assert grandchild.name == "Original Circle"

    def test_reorder_element_same_parent(self, model):
        """Test reordering within same parent."""
        # Setup: Root -> [A, B, C]
        root = create_element(ElementType.GROUP, name="Root")
        model.add_element(root)
        
        a = create_element(ElementType.RECTANGLE, name="A")
        b = create_element(ElementType.RECTANGLE, name="B")
        c = create_element(ElementType.RECTANGLE, name="C")
        
        model.add_element(a, parent_id=root.id)
        model.add_element(b, parent_id=root.id)
        model.add_element(c, parent_id=root.id)
        
        assert root.children == [a.id, b.id, c.id]
        
        # Move A to end (index 2)
        # Note: In Qt semantics, if we move down, logic handles shifting.
        # My implementation: insert_row logic.
        success = model.reorder_element(a.id, root.id, 2)
        assert success
        
        # Expected: B, C, A (A at index 2)
        # New logic treats 'row' as the desired final index.
        # pop(0) -> [B, C]
        # insert(2) -> [B, C, A]
        
        parent = model.get_element(root.id)
        assert parent.children == [b.id, c.id, a.id]

    def test_reorder_element_change_parent(self, model):
        """Test moving element to different parent."""
        g1 = create_element(ElementType.GROUP, name="G1")
        g2 = create_element(ElementType.GROUP, name="G2")
        model.add_element(g1)
        model.add_element(g2)
        
        elem = create_element(ElementType.RECTANGLE, name="Elem")
        model.add_element(elem, parent_id=g1.id)
        
        assert elem.id in g1.children
        assert elem.parent_id == g1.id
        
        # Move Elem to G2 at index 0
        success = model.reorder_element(elem.id, g2.id, 0)
        assert success
        
        assert elem.id not in g1.children
        assert elem.id in g2.children
        assert elem.parent_id == g2.id
