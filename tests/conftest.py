import pytest
import sys
from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """
    Fixture to create a QApplication instance for the entire test session.
    Necessary for any GUI-related tests (QMainWindow, QWidget, signals, etc.).
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    yield app
    
    # Optional: cleanup if needed, though usually QApplication persists
