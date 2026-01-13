
import pytest
from PyQt6.QtWidgets import QMainWindow
from unittest.mock import MagicMock, patch

# Import after mocking potential heavy imports if necessary, 
# but for smoke tests we usually want to test real initialization.
from theme_editor.main_window import MainWindow

@pytest.fixture
def mock_settings(monkeypatch):
    """Mock QSettings to prevent reading/writing real registry/config."""
    from PyQt6.QtCore import QSettings
    
    mock_instance = MagicMock(spec=QSettings)
    mock_instance.value.return_value = None
    
    def mock_constructor(*args, **kwargs):
        return mock_instance
        
    monkeypatch.setattr("PyQt6.QtCore.QSettings", mock_constructor)
    return mock_instance

def test_main_window_init(qapp, mock_settings):
    """
    Smoke test: Verify MainWindow initializes without error.
    """
    # Create window
    window = MainWindow(debug=True)
    
    # Check basic properties
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "Theme Editor v2"
    
    # Check key widgets exist
    assert hasattr(window, "_canvas")
    assert hasattr(window, "_theme_model")
    assert hasattr(window, "_tool_panel")
    assert hasattr(window, "_properties_panel")
    assert hasattr(window, "_layer_panel")
    
    # Close
    window.close()

def test_new_theme_action(qapp, mock_settings):
    """Verify 'New Theme' action basics."""
    window = MainWindow()
    
    # We need to mock the message box if there are unsaved changes, 
    # but initially it should be clean.
    assert window._undo_stack.isClean()
    
    # Trigger new theme
    with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_msg:
        window.action_new.trigger()
        
        # It shouldn't prompt as it's clean
        mock_msg.assert_not_called()
        
    assert window._theme_model.rowCount() == 0
    window.close()
