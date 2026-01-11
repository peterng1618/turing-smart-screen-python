# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for theme_editor.models.theme_model module.
"""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtGui import QUndoStack
from PyQt6.QtCore import Qt

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    Element, ElementType, create_element,
    RectangleElement, TextElement, GroupElement
)


@pytest.fixture
def undo_stack():
    """Create a mock undo stack."""
    return MagicMock(spec=QUndoStack)


@pytest.fixture
def model(undo_stack):
    """Create a fresh theme model."""
    return ThemeModel(undo_stack)


class TestThemeModelBasics:
    """Basic tests for ThemeModel."""
    
    def test_init(self, model):
        """Test model initialization."""
        assert model.rowCount() == 0
        assert model.display_width > 0
        assert model.display_height > 0
    
    def test_display_dimensions_landscape(self, undo_stack):
        """Test display dimensions for landscape orientation."""
        model = ThemeModel(undo_stack)
        model._display_size = '5"'
        model._display_orientation = "landscape"
        
        assert model.display_width == 800
        assert model.display_height == 480
    
    def test_display_dimensions_portrait(self, undo_stack):
        """Test display dimensions for portrait orientation."""
        model = ThemeModel(undo_stack)
        model._display_size = '5"'
        model._display_orientation = "portrait"
        
        assert model.display_width == 480
        assert model.display_height == 800


class TestElementOperations:
    """Tests for element add/remove/get operations."""
    
    def test_add_element_root(self, model):
        """Test adding element at root level."""
        elem = create_element(ElementType.RECTANGLE, name="test_rect")
        elem_id = model.add_element(elem)
        
        assert elem_id == elem.id
        assert model.rowCount() == 1
        assert model.get_element(elem_id) is elem
    
    def test_add_element_to_parent(self, model):
        """Test adding element to a parent."""
        parent = create_element(ElementType.GROUP, name="parent_group")
        model.add_element(parent)
        
        child = create_element(ElementType.RECTANGLE, name="child_rect")
        model.add_element(child, parent_id=parent.id)
        
        assert child.parent_id == parent.id
        assert child.id in parent.children
    
    def test_remove_element(self, model):
        """Test removing element."""
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        assert model.rowCount() == 1
        
        removed = model.remove_element(elem.id)
        
        assert removed is elem
        assert model.rowCount() == 0
        assert model.get_element(elem.id) is None
    
    def test_remove_nonexistent(self, model):
        """Test removing non-existent element."""
        result = model.remove_element("fake_id")
        assert result is None
    
    def test_get_all_elements(self, model):
        """Test getting all elements."""
        elem1 = create_element(ElementType.RECTANGLE)
        elem2 = create_element(ElementType.CIRCLE)
        elem3 = create_element(ElementType.TEXT)
        
        model.add_element(elem1)
        model.add_element(elem2)
        model.add_element(elem3)
        
        all_elements = model.get_all_elements()
        
        assert len(all_elements) == 3
        assert elem1 in all_elements
        assert elem2 in all_elements
        assert elem3 in all_elements
    
    def test_get_root_elements(self, model):
        """Test getting root elements only."""
        parent = create_element(ElementType.GROUP)
        child = create_element(ElementType.RECTANGLE)
        sibling = create_element(ElementType.CIRCLE)
        
        model.add_element(parent)
        model.add_element(child, parent_id=parent.id)
        model.add_element(sibling)
        
        roots = model.get_root_elements()
        
        assert len(roots) == 2
        assert parent in roots
        assert sibling in roots
        assert child not in roots


class TestPropertyOperations:
    """Tests for element property operations."""
    
    def test_set_element_property(self, model):
        """Test setting element property."""
        elem = create_element(ElementType.RECTANGLE, x=0, y=0)
        model.add_element(elem)
        
        result = model.set_element_property(elem.id, "x", 100)
        
        assert result is True
        assert elem.x == 100
    
    def test_set_nonexistent_property(self, model):
        """Test setting non-existent property."""
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        result = model.set_element_property(elem.id, "fake_prop", 123)
        
        assert result is False
    
    def test_move_element(self, model):
        """Test moving element."""
        elem = create_element(ElementType.RECTANGLE, x=0, y=0)
        model.add_element(elem)
        
        result = model.move_element(elem.id, 50, 100)
        
        assert result is True
        assert elem.x == 50
        assert elem.y == 100


class TestModelViewInterface:
    """Tests for QAbstractItemModel interface."""
    
    def test_row_count_root(self, model):
        """Test rowCount at root level."""
        assert model.rowCount() == 0
        
        for i in range(3):
            model.add_element(create_element(ElementType.RECTANGLE))
        
        assert model.rowCount() == 3
    
    def test_row_count_children(self, model):
        """Test rowCount for children."""
        parent = create_element(ElementType.GROUP)
        model.add_element(parent)
        
        parent_index = model.index(0, 0)
        assert model.rowCount(parent_index) == 0
        
        model.add_element(create_element(ElementType.RECTANGLE), parent_id=parent.id)
        model.add_element(create_element(ElementType.CIRCLE), parent_id=parent.id)
        
        assert model.rowCount(parent_index) == 2
    
    def test_column_count(self, model):
        """Test columnCount is always 1."""
        assert model.columnCount() == 1
    
    def test_data_display_role(self, model):
        """Test data with DisplayRole."""
        elem = create_element(ElementType.RECTANGLE, name="my_rect")
        model.add_element(elem)
        
        index = model.index(0, 0)
        name = model.data(index, Qt.ItemDataRole.DisplayRole)
        
        assert name == "my_rect"
    
    def test_data_element_id_role(self, model):
        """Test data with ElementIdRole."""
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        index = model.index(0, 0)
        elem_id = model.data(index, ThemeModel.ElementIdRole)
        
        assert elem_id == elem.id
    
    def test_data_visible_role(self, model):
        """Test data with VisibleRole."""
        elem = create_element(ElementType.RECTANGLE)
        elem.visible = False
        model.add_element(elem)
        
        index = model.index(0, 0)
        visible = model.data(index, ThemeModel.VisibleRole)
        
        assert visible is False
    
    def test_set_data_edit_role(self, model):
        """Test setData with EditRole (rename)."""
        elem = create_element(ElementType.RECTANGLE, name="old_name")
        model.add_element(elem)
        
        index = model.index(0, 0)
        result = model.setData(index, "new_name", Qt.ItemDataRole.EditRole)
        
        assert result is True
        assert elem.name == "new_name"
    
    def test_flags(self, model):
        """Test item flags."""
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        index = model.index(0, 0)
        flags = model.flags(index)
        
        assert flags & Qt.ItemFlag.ItemIsEnabled
        assert flags & Qt.ItemFlag.ItemIsSelectable
        assert flags & Qt.ItemFlag.ItemIsEditable
        assert flags & Qt.ItemFlag.ItemIsDragEnabled


class TestThemeOperations:
    """Tests for theme-level operations."""
    
    def test_clear(self, model):
        """Test clearing the model."""
        model.add_element(create_element(ElementType.RECTANGLE))
        model.add_element(create_element(ElementType.CIRCLE))
        
        assert model.rowCount() == 2
        
        model.clear()
        
        assert model.rowCount() == 0
        assert len(model.get_all_elements()) == 0
    
    def test_create_new(self, model):
        """Test creating new theme with default structure."""
        model.create_new("test_theme")
        
        # Should have 3 root groups: Background, UI Elements, Dynamic Elements
        assert model.rowCount() == 3
        
        roots = model.get_root_elements()
        names = [elem.name for elem in roots]
        
        assert "Background" in names
        assert "UI Elements" in names
        assert "Dynamic Elements" in names
    
    def test_to_data(self, model):
        """Test converting model to dict."""
        model.create_new("test_theme")
        
        # Add a test element
        ui_group = None
        for elem in model.get_root_elements():
            if elem.name == "UI Elements":
                ui_group = elem
                break
        
        rect = create_element(ElementType.RECTANGLE, x=10, y=20)
        model.add_element(rect, parent_id=ui_group.id)
        
        data = model.to_data()
        
        assert "display" in data
        assert "background" in data
        assert "ui_elements" in data
        assert "dynamic_elements" in data
        assert len(data["ui_elements"]) == 1


class TestSignals:
    """Tests for model signals."""
    
    def test_element_added_signal(self, model):
        """Test element_added signal is emitted."""
        handler = MagicMock()
        model.element_added.connect(handler)
        
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        
        handler.assert_called_once_with(elem.id)
    
    def test_element_removed_signal(self, model):
        """Test element_removed signal is emitted."""
        handler = MagicMock()
        model.element_removed.connect(handler)
        
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        model.remove_element(elem.id)
        
        handler.assert_called_once_with(elem.id)
    
    def test_element_changed_signal(self, model):
        """Test element_changed signal is emitted."""
        handler = MagicMock()
        model.element_changed.connect(handler)
        
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        model.set_element_property(elem.id, "x", 100)
        
        handler.assert_called_with(elem.id, "x", 100)
    
    def test_element_moved_signal(self, model):
        """Test element_moved signal is emitted."""
        handler = MagicMock()
        model.element_moved.connect(handler)
        
        elem = create_element(ElementType.RECTANGLE)
        model.add_element(elem)
        model.move_element(elem.id, 50, 75)
        
        handler.assert_called_with(elem.id, 50, 75)
