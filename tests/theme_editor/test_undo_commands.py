# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for theme_editor.commands.undo_commands module.
"""

import pytest

from PyQt6.QtGui import QUndoStack

from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import ElementType, create_element
from theme_editor.commands.undo_commands import (
    MoveElementCommand,
    ChangePropertyCommand,
    AddElementCommand,
    DeleteElementCommand,
    ReorderElementCommand,
    GroupElementsCommand,
    UngroupElementsCommand,
)


@pytest.fixture
def undo_stack():
    """Create a real undo stack."""
    return QUndoStack()


@pytest.fixture
def editor_state(undo_stack):
    """Create a real editor state."""
    return EditorState(undo_stack)


@pytest.fixture
def model(editor_state):
    """Create a fresh theme model."""
    return ThemeModel(editor_state)


class TestMoveElementCommand:
    """Tests for MoveElementCommand."""
    
    def test_redo_moves_element(self, model, undo_stack):
        """Test that redo moves element to new position."""
        elem = create_element(ElementType.RECTANGLE, x=0, y=0)
        model.add_element(elem)
        
        cmd = MoveElementCommand(model, elem.id, 0, 0, 100, 200)
        undo_stack.push(cmd)
        
        assert elem.x == 100
        assert elem.y == 200
    
    def test_undo_restores_position(self, model, undo_stack):
        """Test that undo restores original position."""
        elem = create_element(ElementType.RECTANGLE, x=50, y=75)
        model.add_element(elem)
        
        cmd = MoveElementCommand(model, elem.id, 50, 75, 200, 300)
        undo_stack.push(cmd)
        
        assert elem.x == 200
        assert elem.y == 300
        
        undo_stack.undo()
        
        assert elem.x == 50
        assert elem.y == 75
    
    def test_merge_consecutive_moves(self, model, undo_stack):
        """Test that consecutive moves of same element are merged."""
        elem = create_element(ElementType.RECTANGLE, x=0, y=0)
        model.add_element(elem)
        
        cmd1 = MoveElementCommand(model, elem.id, 0, 0, 10, 10)
        undo_stack.push(cmd1)
        
        cmd2 = MoveElementCommand(model, elem.id, 10, 10, 20, 20)
        undo_stack.push(cmd2)
        
        cmd3 = MoveElementCommand(model, elem.id, 20, 20, 30, 30)
        undo_stack.push(cmd3)
        
        # All moves should be merged, so undo once should go back to 0,0
        undo_stack.undo()
        assert elem.x == 0
        assert elem.y == 0
    
    def test_no_merge_different_elements(self, model, undo_stack):
        """Test that moves of different elements are not merged."""
        elem1 = create_element(ElementType.RECTANGLE, x=0, y=0)
        elem2 = create_element(ElementType.CIRCLE, x=0, y=0)
        model.add_element(elem1)
        model.add_element(elem2)
        
        cmd1 = MoveElementCommand(model, elem1.id, 0, 0, 100, 100)
        undo_stack.push(cmd1)
        
        cmd2 = MoveElementCommand(model, elem2.id, 0, 0, 200, 200)
        undo_stack.push(cmd2)
        
        # Two separate undos should be needed
        undo_stack.undo()  # Undo elem2 move
        assert elem2.x == 0
        assert elem1.x == 100
        
        undo_stack.undo()  # Undo elem1 move
        assert elem1.x == 0


class TestChangePropertyCommand:
    """Tests for ChangePropertyCommand."""
    
    def test_redo_changes_property(self, model, undo_stack):
        """Test that redo changes property value."""
        elem = create_element(ElementType.RECTANGLE, name="old_name")
        model.add_element(elem)
        
        cmd = ChangePropertyCommand(model, elem.id, "name", "old_name", "new_name")
        undo_stack.push(cmd)
        
        assert elem.name == "new_name"
    
    def test_undo_restores_property(self, model, undo_stack):
        """Test that undo restores original property value."""
        elem = create_element(ElementType.RECTANGLE)
        elem.opacity = 1.0
        model.add_element(elem)
        
        cmd = ChangePropertyCommand(model, elem.id, "opacity", 1.0, 0.5)
        undo_stack.push(cmd)
        
        assert elem.opacity == 0.5
        
        undo_stack.undo()
        
        assert elem.opacity == 1.0
    
    def test_command_text(self, model, undo_stack):
        """Test that command has appropriate text."""
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        cmd = ChangePropertyCommand(model, elem.id, "color", None, (255, 0, 0, 255))
        
        assert "color" in cmd.text()


class TestAddElementCommand:
    """Tests for AddElementCommand."""
    
    def test_redo_adds_element(self, model, undo_stack):
        """Test that redo adds new element."""
        assert model.rowCount() == 0
        
        cmd = AddElementCommand(model, ElementType.RECTANGLE)
        undo_stack.push(cmd)
        
        assert model.rowCount() == 1
    
    def test_undo_removes_element(self, model, undo_stack):
        """Test that undo removes the added element."""
        cmd = AddElementCommand(model, ElementType.RECTANGLE)
        undo_stack.push(cmd)
        
        assert model.rowCount() == 1
        
        undo_stack.undo()
        
        assert model.rowCount() == 0
    
    def test_redo_after_undo_re_adds_element(self, model, undo_stack):
        """Test that redo after undo re-adds the same element."""
        cmd = AddElementCommand(model, ElementType.RECTANGLE)
        undo_stack.push(cmd)
        
        elem_id = cmd._element_id
        
        undo_stack.undo()
        undo_stack.redo()
        
        # Element should be re-added with same ID
        assert model.get_element(elem_id) is not None
    
    def test_add_with_parent(self, model, undo_stack):
        """Test adding element with parent."""
        parent = create_element(ElementType.GROUP)
        model.add_element(parent)
        
        cmd = AddElementCommand(
            model,
            ElementType.RECTANGLE,
            parent_id=parent.id
        )
        undo_stack.push(cmd)
        
        elem = model.get_element(cmd._element_id)
        assert elem.parent_id == parent.id
        assert cmd._element_id in parent.children
    
    def test_add_with_properties(self, model, undo_stack):
        """Test adding element with custom properties."""
        cmd = AddElementCommand(
            model,
            ElementType.TEXT,
            properties={"x": 100, "y": 200, "text": "Hello"}
        )
        undo_stack.push(cmd)
        
        elem = model.get_element(cmd._element_id)
        assert elem.x == 100
        assert elem.y == 200
        assert elem.text == "Hello"


class TestDeleteElementCommand:
    """Tests for DeleteElementCommand."""
    
    def test_redo_deletes_element(self, model, undo_stack):
        """Test that redo deletes element."""
        elem = create_element(ElementType.RECTANGLE, name="to_delete")
        model.add_element(elem)
        
        assert model.rowCount() == 1
        
        cmd = DeleteElementCommand(model, elem.id)
        undo_stack.push(cmd)
        
        assert model.rowCount() == 0
        assert model.get_element(elem.id) is None
    
    def test_undo_restores_element(self, model, undo_stack):
        """Test that undo restores deleted element."""
        elem = create_element(ElementType.RECTANGLE, name="restored")
        elem.x = 50
        elem.y = 100
        model.add_element(elem)
        elem_id = elem.id
        
        cmd = DeleteElementCommand(model, elem_id)
        undo_stack.push(cmd)
        
        undo_stack.undo()
        
        restored = model.get_element(elem_id)
        assert restored is not None
        assert restored.name == "restored"
        assert restored.x == 50
        assert restored.y == 100
    
    def test_delete_preserves_parent_relationship(self, model, undo_stack):
        """Test that delete preserves parent-child relationship for undo."""
        parent = create_element(ElementType.GROUP, name="parent")
        model.add_element(parent)
        
        child = create_element(ElementType.RECTANGLE, name="child")
        model.add_element(child, parent_id=parent.id)
        
        cmd = DeleteElementCommand(model, child.id)
        undo_stack.push(cmd)
        
        # Child should be removed from parent
        assert child.id not in parent.children
        
        undo_stack.undo()
        
        # Child should be back in parent
        assert child.id in parent.children



class TestReorderElementCommand:
    """Tests for ReorderElementCommand."""
    
    def test_redo_reorders_element(self, model, undo_stack):
        """Test that redo moves element to new position."""
        elem1 = create_element(ElementType.RECTANGLE, name="first")
        elem2 = create_element(ElementType.CIRCLE, name="second")
        elem3 = create_element(ElementType.TEXT, name="third")
        
        model.add_element(elem1)
        model.add_element(elem2)
        model.add_element(elem3)
        
        # Move elem3 to index 0 (parent=None for root)
        cmd = ReorderElementCommand(model, elem3.id, None, 0)
        undo_stack.push(cmd)
        
        # elem3 should now be first
        roots = model.get_root_elements()
        assert roots[0].id == elem3.id
    
    def test_undo_restores_order(self, model, undo_stack):
        """Test that undo restores original order."""
        elem1 = create_element(ElementType.RECTANGLE, name="first")
        elem2 = create_element(ElementType.CIRCLE, name="second")
        
        model.add_element(elem1)
        model.add_element(elem2)
        
        # Move elem2 to index 0
        cmd = ReorderElementCommand(model, elem2.id, None, 0)
        undo_stack.push(cmd)
        
        undo_stack.undo()
        
        roots = model.get_root_elements()
        assert roots[0].id == elem1.id
        assert roots[1].id == elem2.id


class TestDuplicateElementCommand:
    """Tests for DuplicateElementCommand."""
    
    def test_redo_duplicates_element(self, model, undo_stack):
        """Test that redo duplicates an element."""
        from theme_editor.commands.undo_commands import DuplicateElementCommand
        
        elem = create_element(ElementType.RECTANGLE, name="Original")
        model.add_element(elem)
        original_count = model.rowCount()
        
        cmd = DuplicateElementCommand(model, elem.id)
        undo_stack.push(cmd)
        
        # Should have one more element
        assert model.rowCount() == original_count + 1
        
        # New element should be a copy
        roots = model.get_root_elements()
        new_elem = roots[1] # Assumes appended/inserted after
        assert new_elem.id != elem.id
        assert new_elem.name == "Original (Copy)"
    
    def test_undo_removes_duplicate(self, model, undo_stack):
        """Test that undo removes the duplicated element."""
        from theme_editor.commands.undo_commands import DuplicateElementCommand
        
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        original_count = model.rowCount()
        
        cmd = DuplicateElementCommand(model, elem.id)
        undo_stack.push(cmd)
        
        assert model.rowCount() == original_count + 1
        
        undo_stack.undo()
        
        assert model.rowCount() == original_count
    
    def test_redo_restores_tree(self, model, undo_stack):
        """Test that redo consistently restores the same duplicated tree."""
        from theme_editor.commands.undo_commands import DuplicateElementCommand
        
        # Create a hierarchy: Group -> Child
        group = create_element(ElementType.GROUP, name="Group")
        model.add_element(group)
        
        child = create_element(ElementType.RECTANGLE, name="Child")
        model.add_element(child, parent_id=group.id)
        
        # Duplicate the group
        cmd = DuplicateElementCommand(model, group.id)
        undo_stack.push(cmd)
        
        # Find the new group
        roots = model.get_root_elements()
        assert len(roots) == 2
        new_group = roots[1]
        
        # Sanity check new structure
        assert len(new_group.children) == 1
        new_child_id = new_group.children[0]
        
        undo_stack.undo()
        undo_stack.redo()
        
        # Check if we got the same objects/IDs back
        roots_after = model.get_root_elements()
        assert len(roots_after) == 2
        restored_group = roots_after[1]
        
        assert restored_group.id == new_group.id
        assert restored_group.children[0] == new_child_id


class TestGroupElementsCommand:
    """Tests for GroupElementsCommand."""
    
    def test_redo_groups_elements(self, model, undo_stack):
        """Test that redo creates group containing elements."""
        elem1 = create_element(ElementType.RECTANGLE)
        elem2 = create_element(ElementType.CIRCLE)
        model.add_element(elem1)
        model.add_element(elem2)
        
        cmd = GroupElementsCommand(model, [elem1.id, elem2.id], "My Group")
        undo_stack.push(cmd)
        
        # Elements should now have a parent
        assert elem1.parent_id is not None
        assert elem2.parent_id is not None
        assert elem1.parent_id == elem2.parent_id
        
        # The group should exist
        group = model.get_element(elem1.parent_id)
        assert group is not None
        assert group.name == "My Group"
        assert group.element_type == ElementType.GROUP
    
    def test_undo_ungroups_elements(self, model, undo_stack):
        """Test that undo restores elements to original state."""
        elem1 = create_element(ElementType.RECTANGLE)
        elem2 = create_element(ElementType.CIRCLE)
        model.add_element(elem1)
        model.add_element(elem2)
        
        original_count = model.rowCount()
        
        cmd = GroupElementsCommand(model, [elem1.id, elem2.id])
        undo_stack.push(cmd)
        
        undo_stack.undo()
        
        # Elements should be back at root level
        assert elem1.parent_id is None
        assert elem2.parent_id is None
        assert model.rowCount() == original_count


class TestUngroupElementsCommand:
    """Tests for UngroupElementsCommand."""
    
    def test_redo_ungroups_elements(self, model, undo_stack):
        """Test that redo moves children out of group."""
        # Create a group with children
        group = create_element(ElementType.GROUP, name="group")
        model.add_element(group)
        
        child1 = create_element(ElementType.RECTANGLE)
        child2 = create_element(ElementType.CIRCLE)
        model.add_element(child1, parent_id=group.id)
        model.add_element(child2, parent_id=group.id)
        
        cmd = UngroupElementsCommand(model, group.id)
        undo_stack.push(cmd)
        
        # Children should be at root level now
        assert child1.parent_id is None or child1.parent_id == group.parent_id
        assert child2.parent_id is None or child2.parent_id == group.parent_id
        
        # Group should be removed
        assert model.get_element(group.id) is None
    
    def test_undo_recreates_group(self, model, undo_stack):
        """Test that undo recreates the group with children."""
        group = create_element(ElementType.GROUP, name="restored_group")
        model.add_element(group)
        group_id = group.id
        
        child = create_element(ElementType.RECTANGLE)
        model.add_element(child, parent_id=group.id)
        child_id = child.id
        
        cmd = UngroupElementsCommand(model, group.id)
        undo_stack.push(cmd)
        
        undo_stack.undo()
        
        # Group should be back
        restored_group = model.get_element(group_id)
        assert restored_group is not None
        assert restored_group.name == "restored_group"
        
        # Child should be back in group's children list
        assert child_id in restored_group.children
