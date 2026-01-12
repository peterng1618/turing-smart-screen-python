
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QUndoStack
from theme_editor.panels.properties_panel import PropertiesPanel
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import create_element, ElementType, Outline

# Create dummy app
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

def test_prop_panel_outline():
    undo_stack = QUndoStack()
    model = ThemeModel(undo_stack)
    model.create_new("TestTheme")
    
    # 1. Add Rectangle
    rect = create_element(ElementType.RECTANGLE, name="TestRect", x=10, y=10)
    model.add_element(rect)
    
    # 2. Setup Panel
    panel = PropertiesPanel(model, undo_stack)
    
    # 3. Select Element
    panel.show_properties(rect.id)
    
    # Verify initial state
    print(f"Initial Outline: {rect.outline}")
    
    # 4. Simulate Checking "Outline" GroupBox
    # Find the widget. The panel stores 'outline_width' etc in _widgets, 
    # but the GroupBox itself is not in _widgets, it's just in the layout.
    # However, we can call the handler directly to simulate the toggle.
    # self._on_outline_enabled_toggled(True)
    
    print("Simulating Enable Outline...")
    panel._on_outline_enabled_toggled(True)
    
    print(f"Outline after enable: {rect.outline}")
    
    if rect.outline is None:
        print("FAILURE: Outline is None after enabling via panel!")
        return

    # 5. Simulate Change Properties
    # Change width via widget simulation? or call handler.
    # The handlers read from widgets. So we must set widget values first.
    
    # Set Widgets
    if "outline_width" in panel._widgets:
        panel._widgets["outline_width"].setValue(10)
    
    # Trigger Change
    print("Simulating Change Width to 10...")
    panel._on_outline_property_changed("width", 10)
    
    print(f"Outline Width: {rect.outline.width}")
    
    if rect.outline.width != 10:
         print(f"FAILURE: Width mismatch. Expected 10, got {rect.outline.width}")
    else:
         print("SUCCESS: Width updated correctly.")

    # 6. Check Save Data
    data = rect.to_dict()
    if "outline" in data and data["outline"]["width"] == 10:
        print("SUCCESS: Outline saved in to_dict.")
    else:
        print(f"FAILURE: Outline missing or incorrect in to_dict: {data.get('outline')}")

if __name__ == "__main__":
    test_prop_panel_outline()
