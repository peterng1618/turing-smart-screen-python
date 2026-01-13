# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from PyQt6.QtCore import QCoreApplication
from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.canvas.preview_canvas import PreviewCanvas
from theme_editor.panels.layer_panel import LayerPanel
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
    
    canvas = PreviewCanvas(state, model, undo_stack)
    layers = LayerPanel(state, model, undo_stack)
    props = PropertiesPanel(state, model, undo_stack)
    
    # Add widgets to qtbot for memory management and processing
    qtbot.addWidget(canvas)
    qtbot.addWidget(layers)
    qtbot.addWidget(props)
    
    return state, canvas, layers, props

def test_selection_propagation_from_canvas(setup_editor, qtbot):
    state, canvas, layers, props = setup_editor
    
    # Add real elements to state first
    from theme_editor.models.element import RectangleElement
    e1 = RectangleElement(x=10, y=10, width=50, height=50)
    e1.id = "elem_1"
    e2 = RectangleElement(x=100, y=100, width=30, height=30)
    e2.id = "elem_2"
    
    state._elements["elem_1"] = e1
    state._elements["elem_2"] = e2
    state._root_ids.append("elem_1")
    state._root_ids.append("elem_2")
    
    # Mock ids
    test_ids = ["elem_1", "elem_2"]
    
    # Simulate canvas selection
    state.set_selection(test_ids, source='canvas')
    
    assert state.selection == test_ids
    # Properties panel should show properties of the first ID
    assert props._current_element_id == "elem_1"

def test_selection_no_recursion(setup_editor):
    state, canvas, layers, props = setup_editor
    
    call_counts = {'state': 0, 'canvas': 0, 'layers': 0}
    
    def on_state_changed(ids): call_counts['state'] += 1
    # Note: PreviewCanvas and LayerPanel don't emit selection_changed 
    # when receiving it from the store in our new design (due to guards 
    # or just only updating store on USER action).
    
    state.selection_changed.connect(on_state_changed)
    
    # Set selection
    state.set_selection(["id1"])
    
    # Selection should only change once in the store
    assert call_counts['state'] == 1
