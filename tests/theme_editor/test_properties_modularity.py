# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from PyQt6.QtCore import QCoreApplication
from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import RectangleElement
from theme_editor.panels.properties_panel import PropertiesPanel
from PyQt6.QtGui import QUndoStack

@pytest.fixture
def app():
    return QCoreApplication.instance() or QCoreApplication([])

@pytest.fixture
def setup_editor(qtbot):
    state = EditorState()
    model = ThemeModel(state)
    undo_stack = state.undo_stack
    
    props = PropertiesPanel(state, model, undo_stack)
    qtbot.addWidget(props)
    
    return state, model, props

def test_modular_sections_loaded(setup_editor, qtbot):
    state, model, props = setup_editor
    
    # Add element
    e1 = RectangleElement(name="Box 1")
    e1.id = "rect_1"
    state._elements["rect_1"] = e1
    state._root_ids.append("rect_1")
    
    # Select element
    state.set_selection(["rect_1"])
    
    # Verify sections loaded
    # IdentitySection and TransformSection should be there by default
    assert len(props._sections) >= 2
    assert props._current_element_id == "rect_1"
    
    # Verify identity section widget value
    name_widget = props._widgets.get("name")
    assert name_widget is not None
    assert name_widget.text() == "Box 1"

def test_modular_section_update_from_store(setup_editor, qtbot):
    state, model, props = setup_editor
    
    e1 = RectangleElement(name="Old Name")
    e1.id = "rect_1"
    state._elements["rect_1"] = e1
    state._root_ids.append("rect_1")
    
    state.set_selection(["rect_1"])
    
    # Update property in store/model
    state.element_changed.emit("rect_1", "name", "New Name")
    
    # Widget should update
    assert props._widgets["name"].text() == "New Name"
