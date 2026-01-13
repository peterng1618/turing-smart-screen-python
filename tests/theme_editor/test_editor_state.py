# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QUndoStack
from theme_editor.models.editor_state import EditorState

@pytest.fixture
def app():
    """Ensure a QCoreApplication exists for signals."""
    yield QCoreApplication.instance() or QCoreApplication([])

@pytest.fixture
def state(app):
    return EditorState()

def test_initial_selection_empty(state):
    assert state.selection == []

def test_set_selection(state):
    # Mock signal listener
    results = []
    state.selection_changed.connect(lambda ids: results.append(ids))
    
    state.set_selection(["id1", "id2"])
    
    assert state.selection == ["id1", "id2"]
    assert len(results) == 1
    assert results[0] == ["id1", "id2"]

def test_selection_no_duplicate_signals(state):
    results = []
    state.selection_changed.connect(lambda ids: results.append(ids))
    
    state.set_selection(["id1"])
    state.set_selection(["id1"]) # Same selection
    
    assert len(results) == 1

def test_hover_state(state):
    results = []
    state.hover_changed.connect(lambda eid: results.append(eid))
    
    state.set_hover("element_1")
    assert state.hovered_id == "element_1"
    
    state.set_hover("element_1") # No change
    assert len(results) == 1
    
    state.set_hover("") # Clear hover
    assert state.hovered_id == ""
    assert len(results) == 2

def test_undo_stack_modified_signal(state):
    results = []
    state.document_modified.connect(lambda dirty: results.append(dirty))
    
    # Simulate stack clean change
    state.undo_stack.setClean() # Should trigger signal if it wasn't clean, 
    # but stack is clean by default usually.
    
    # In practice, we'd push a command.
    from PyQt6.QtGui import QUndoCommand
    class DummyCommand(QUndoCommand):
        def redo(self): pass
        def undo(self): pass
        
    state.undo_stack.push(DummyCommand())
    assert not state.undo_stack.isClean()
    assert True in results
