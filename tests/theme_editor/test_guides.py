import pytest
from PyQt6.QtGui import QUndoStack
from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel

def test_guides_properties():
    """Test that guides properties are correctly exposed and proxied."""
    state = EditorState()
    model = ThemeModel(state)
    
    # Check initial empty state
    assert model.guides_h == []
    assert model.guides_v == []
    
    # Check that they proxy to internal state
    state._guides_h = [10, 20]
    state._guides_v = [30, 40]
    
    assert model.guides_h == [10, 20]
    assert model.guides_v == [30, 40]

def test_set_guides_undo_redo():
    """Test that set_guides works with undo/redo."""
    state = EditorState()
    model = ThemeModel(state)
    stack = model._undo_stack
    
    # Signal tracking
    signal_emitted = 0
    def on_guides_changed():
        nonlocal signal_emitted
        signal_emitted += 1
    
    model.guides_changed.connect(on_guides_changed)
    
    # Perform change
    model.set_guides([100], [200])
    
    assert model.guides_h == [100]
    assert model.guides_v == [200]
    assert signal_emitted == 1
    
    # Undo
    stack.undo()
    assert model.guides_h == []
    assert model.guides_v == []
    assert signal_emitted == 2
    
    # Redo
    stack.redo()
    assert model.guides_h == [100]
    assert model.guides_v == [200]
    assert signal_emitted == 3
