
import unittest
from PyQt6.QtGui import QUndoStack

from theme_editor.models.editor_state import EditorState
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import ElementType, ThemeInfoElement

class TestThemeMetadata(unittest.TestCase):
    def setUp(self):
        self.undo_stack = QUndoStack()
        self.state = EditorState(self.undo_stack)
        self.model = ThemeModel(self.state)

    def test_create_new_theme_structure(self):
        """Verify new theme creation has Theme Info and Background layers as roots."""
        self.model.create_new("Test Theme")
        
        roots = self.model.get_root_elements()
        self.assertGreaterEqual(len(roots), 4) # Info, BG Video, BG Image, UI...
        
        # Check order
        self.assertEqual(roots[0].element_type, ElementType.THEME_INFO, "First element should be Theme Info")
        
        # We don't strictly enforce BG Video/Image order relative to each other as long as they are before UI
        # But per code: Info, BG Video, BG Image, UI, Dynamic
        self.assertEqual(roots[1].element_type, ElementType.BACKGROUND_VIDEO)
        self.assertEqual(roots[2].element_type, ElementType.BACKGROUND_IMAGE)
        self.assertEqual(roots[3].element_type, ElementType.GROUP) 
        self.assertEqual(roots[3].name, "UI Elements")
        
        # Verify Theme Info properties
        info = roots[0]
        self.assertIsInstance(info, ThemeInfoElement)
        self.assertEqual(info.display_size, "5\"") # Default in create_new
        self.assertTrue(info.locked)

    def test_metadata_persistence(self):
        """Verify metadata is saved to dict and loaded back."""
        # Setup
        self.model.create_new("Persistence Test")
        info = self.model.get_root_elements()[0]
        
        # Modify
        info.author = "@tester"
        info.display_size = "8.8\""
        
        # Save
        data = self.model.to_data()
        
        # Verify saved data structure (should be at root)
        self.assertEqual(data.get("author"), "@tester")
        self.assertEqual(data.get("display", {}).get("DISPLAY_SIZE"), "8.8\"")
        
        # Verify ThemeInfo is NOT in ui_elements list
        ui_elements = data.get("ui_elements", [])
        types = [e.get("type") for e in ui_elements]
        self.assertNotIn("theme_info", types)
        
        # Load back
        new_state = EditorState(QUndoStack())
        new_model = ThemeModel(new_state)
        new_model.load_from_data(data)
        
        new_roots = new_model.get_root_elements()
        new_info = new_roots[0]
        
        self.assertEqual(new_info.author, "@tester")
        self.assertEqual(new_info.display_size, "8.8\"")
        self.assertEqual(new_model._display_size, "8.8\"") # Check model sync
        
    def test_background_layer_roots_on_load(self):
        """Verify that loading data correctly places backgrounds at root."""
        data = {
            "author": "@test",
            "display": {},
            "static_images": {
                "BACKGROUND": { "PATH": "bg.png" }
            },
            "ui_elements": [
                {"type": "rectangle", "id": "rect1"}
            ],
            "dynamic_elements": []
        }
        
        self.model.load_from_data(data)
        
        roots = self.model.get_root_elements()
        # Expect: ThemeInfo, BG Video, BG Image, UI, Dynamic
        self.assertEqual(roots[0].element_type, ElementType.THEME_INFO)
        self.assertEqual(roots[1].element_type, ElementType.BACKGROUND_VIDEO) 
        self.assertEqual(roots[2].element_type, ElementType.BACKGROUND_IMAGE)
        
        # Check BG Image properties
        bg_img = roots[2]
        self.assertEqual(bg_img.path, "bg.png")
        self.assertIsNone(bg_img.parent_id)
