
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock QApplication if needed, or ensure it's created
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QUndoStack
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import create_element, ElementType

class TestThemeSave(unittest.TestCase):
    def setUp(self):
        self.undo_stack = QUndoStack()
        self.model = ThemeModel(self.undo_stack)
        self.model.create_new("TestTheme")

    def test_save_root_elements(self):
        """Test that elements added to the root are correctly saved."""
        
        # Add a root-level Rectangle
        rect = create_element(ElementType.RECTANGLE, name="Root Rect", x=100, y=100, width=50, height=50)
        self.model.add_element(rect)
        
        # Add a root-level Dynamic Text
        dyn_text = create_element(ElementType.DYNAMIC_TEXT, name="Root Dyn", text="{cpu.usage}", x=200, y=200)
        self.model.add_element(dyn_text)
        
        # Convert to data
        data = self.model.to_data()
        
        # Verify UI Elements
        ui_elements = data.get("ui_elements", [])
        found_rect = any(e.get("name") == "Root Rect" for e in ui_elements)
        self.assertTrue(found_rect, "Root Rectangle should be present in 'ui_elements'")
        
        # Verify Dynamic Elements
        dyn_elements = data.get("dynamic_elements", [])
        found_dyn = any(e.get("name") == "Root Dyn" for e in dyn_elements)
        self.assertTrue(found_dyn, "Root Dynamic Text should be present in 'dynamic_elements'")

    def test_save_nested_groups(self):
        """Test that elements inside groups are saved (flattened or preserved)."""
        # Create a group
        group = create_element(ElementType.GROUP, name="Test Group")
        self.model.add_element(group)
        
        # Add child to group
        child_rect = create_element(ElementType.RECTANGLE, name="Child Rect")
        self.model.add_element(child_rect, parent_id=group.id)
        
        # Convert to data
        data = self.model.to_data()
        ui_elements = data.get("ui_elements", [])
        
        # Depending on implementation choice (recursive flattening or nested), check presence.
        # Current implementation: recursive flattening for 'UI Elements'/'Dynamic Elements' legacy groups,
        # AND recursive flattening for general groups in the new logic.
        
        found_child = any(e.get("name") == "Child Rect" for e in ui_elements)
        self.assertTrue(found_child, "Child element inside group should be found (flattened)")

if __name__ == "__main__":
    unittest.main()
