import pytest
from PyQt6.QtGui import QUndoStack
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import ElementType, create_element

@pytest.fixture
def theme_model():
    stack = QUndoStack()
    model = ThemeModel(stack)
    return model

def test_duplicate_element(theme_model):
    # Setup: Create Parent -> Child
    parent_id = theme_model.add_element(create_element(ElementType.RECTANGLE, name="Parent"))
    child_id = theme_model.add_element(create_element(ElementType.TEXT, name="Child"), parent_id)
    
    # Duplicate Parent
    new_parent_id = theme_model.duplicate_element(parent_id)
    assert new_parent_id is not None
    assert new_parent_id != parent_id
    
    # Verify structure
    new_parent = theme_model.get_element(new_parent_id)
    assert new_parent.name == "Parent"
    assert len(new_parent.children) == 1
    
    new_child_id = new_parent.children[0]
    assert new_child_id != child_id
    
    new_child = theme_model.get_element(new_child_id)
    assert new_child.name == "Child"
    assert new_child.parent_id == new_parent_id

def test_remove_restore_element_tree(theme_model):
    # Setup
    parent_id = theme_model.add_element(create_element(ElementType.RECTANGLE, name="Parent"))
    child_id = theme_model.add_element(create_element(ElementType.TEXT, name="Child"), parent_id)
    
    # Remove Tree
    removed_map = theme_model.remove_element_tree(parent_id)
    
    assert parent_id not in theme_model._elements
    assert child_id not in theme_model._elements
    assert len(removed_map) == 2
    assert removed_map[parent_id].name == "Parent"
    assert removed_map[child_id].name == "Child"
    
    # Restore Tree
    theme_model.restore_element_tree(removed_map, parent_id, None, -1)
    
    assert parent_id in theme_model._elements
    assert child_id in theme_model._elements
    
    restored_parent = theme_model.get_element(parent_id)
    assert restored_parent.children == [child_id]
