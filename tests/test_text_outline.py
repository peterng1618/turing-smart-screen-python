
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock QApplication
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QUndoStack
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import create_element, ElementType
from theme_editor.panels.properties_panel import PropertiesPanel

class TestTextOutline(unittest.TestCase):
    def setUp(self):
        self.undo_stack = QUndoStack()
        self.model = ThemeModel(self.undo_stack)
        self.model.create_new("TestTheme")
        self.panel = PropertiesPanel(self.model, self.undo_stack)

    def test_text_outline_property(self):
        """Test adding outline to TextElement."""
        # 1. Create Text
        text_elem = create_element(ElementType.TEXT, name="MyText", text="Hello")
        self.model.add_element(text_elem)
        
        self.assertIsNone(text_elem.outline)
        
        # 2. Select in Panel
        self.panel.show_properties(text_elem.id)
        
        # 3. Enable Outline via Panel
        # Simulate widget states
        if "outline_width" in self.panel._widgets:
            self.panel._widgets["outline_width"].setValue(3)
        if "outline_cap" in self.panel._widgets:
            self.panel._widgets["outline_cap"].setCurrentText("round")
            
        self.panel._on_outline_enabled_toggled(True)
        
        # 4. Verify Model Update
        self.assertIsNotNone(text_elem.outline)
        self.assertEqual(text_elem.outline.width, 3)
        self.assertEqual(text_elem.outline.cap, "round")
        
        # 5. Verify Serialization
        data = text_elem.to_dict()
        self.assertIn("outline", data)
        self.assertEqual(data["outline"]["width"], 3)
        self.assertEqual(data["outline"]["cap"], "round")
        
    def test_dynamic_text_outline_property(self):
        """Test adding outline to DynamicTextElement."""
        dyn_elem = create_element(ElementType.DYNAMIC_TEXT, name="DynText", text="{cpu}")
        self.model.add_element(dyn_elem)
        
        self.assertIsNone(dyn_elem.outline)
        
        self.panel.show_properties(dyn_elem.id)
        
        # Enable Outline
        self.panel._on_outline_enabled_toggled(True)
        
        self.assertIsNotNone(dyn_elem.outline)
        
        # Verify Serialization
        data = dyn_elem.to_dict()
        self.assertIn("outline", data)

if __name__ == "__main__":
    unittest.main()
