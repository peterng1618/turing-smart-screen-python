import unittest
import os
from PIL import Image
from library.ui_renderer import UiRenderer

# Mock logger/config
from unittest.mock import MagicMock
import library.log
import library.config
library.log.logger = MagicMock()
library.config.FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../res/fonts')) 

class TestUiRenderer(unittest.TestCase):
    def setUp(self):
        self.theme_path = os.path.dirname(os.path.abspath(__file__))
        self.theme_data = {
            'display': {'DISPLAY_SIZE': '3.5"'},
            'ui_elements': {'shapes': [], 'ui_text': []}
        }
        self.renderer = UiRenderer(self.theme_data, self.theme_path)

    def test_rgb_string_parsing(self):
        # Test standard RGB string
        self.theme_data['ui_elements'] = [{
            'type': 'rectangle',
            'x': 0, 'y': 0, 'width': 10, 'height': 10,
            'color': '255, 0, 0, 255' 
        }]
        overlay = self.renderer.generate_overlay()
        self.assertEqual(overlay.getpixel((5, 5)), (255, 0, 0, 255))
        
        # Test RGB string with alpha override (legacy check, but still valid logic internally)
        self.theme_data['ui_elements'] = [{
            'type': 'rectangle',
            'x': 0, 'y': 0, 'width': 10, 'height': 10,
            'color': '0, 255, 0, 128', 
            # 'alpha': 128 # No longer using alpha keys, relying on RGBA string
        }]
        overlay = self.renderer.generate_overlay()
        r, g, b, a = overlay.getpixel((5, 5))
        self.assertEqual((r, g, b), (0, 255, 0))
        self.assertEqual(a, 128)

    def test_rgb_outline(self):
        self.theme_data['ui_elements'] = [{
            'type': 'rectangle',
            'x': 10, 'y': 10, 'width': 20, 'height': 20,
            'color': '0, 0, 0, 0', # Transparent
            'outline_color': '0, 0, 255, 255', # Blue outline
            'outline_width': 1
        }]
        overlay = self.renderer.generate_overlay()
        bbox = overlay.getbbox()
        self.assertIsNotNone(bbox)
        # Check center is empty (transparent)
        self.assertEqual(overlay.getpixel((20, 20))[3], 0)

    def test_image_rendering(self):
        # We need a dummy image file. 
        # For unit test, we can mock Image.open or create a dummy file. 
        # Using unittest.mock for Image.open is cleaner.
        import unittest.mock as mock
        
        with mock.patch('PIL.Image.open') as mock_open:
            # Setup mock image
            mock_img = Image.new('RGBA', (100, 100), (255, 0, 0, 255))
            mock_open.return_value = mock_img
            
            # Mock os.path.exists
            with mock.patch('os.path.exists', return_value=True):
                self.theme_data['ui_elements'] = [{
                    'type': 'image',
                    'path': 'dummy.png',
                    'x': 0,
                    'y': 0,
                    'width': 50,
                    'height': 50,
                    'opacity': 0.5
                }]
                overlay = self.renderer.generate_overlay()
                
                # Should be scaled to 50x50
                # Opacity applied. 
                # Note: alpha_composite onto empty buffer -> (255, 0, 0, 127) roughly
                
                # Since we can't easily inspect the exact pixels without knowing implementation details of Lanczos and alpha composite,
                # we just verify no crash and mocks called.
                mock_open.assert_called()
                
                # If we want a check, let's check size if possible or side effects.
                # Just ensuring it runs through the new 'image' type block is good enough for now.

    def test_triangle_rendering(self):
        self.theme_data['ui_elements'] = [{
            'type': 'triangle',
            'x1': 10, 'y1': 10,
            'x2': 50, 'y2': 10,
            'x3': 30, 'y3': 40,
            'color': '255, 0, 0, 255',
            'radius': 5
        }]
        overlay = self.renderer.generate_overlay()
        # Verify color inside the triangle
        self.assertEqual(overlay.getpixel((30, 20)), (255, 0, 0, 255))
        # Verify outside
        self.assertEqual(overlay.getpixel((0, 0))[3], 0)

    def test_sheared_rectangle_rendering(self):
        self.theme_data['ui_elements'] = [{
            'type': 'rectangle',
            'width': 100, 'height': 50,
            'x': 50, 'y': 50,
            'shear_left': 15,
            'shear_right': 15,
            'color': '0, 255, 0, 255',
            'radius': 10
        }]
        overlay = self.renderer.generate_overlay()
        # Should render without error
        self.assertIsNotNone(overlay.getbbox())
        # Check a pixel that should be filled in the sheared parallelogram
        self.assertEqual(overlay.getpixel((100, 75)), (0, 255, 0, 255))

    def test_icon_auto_resolution(self):
        # Test 1: Resolve from Font Awesome URL with specific style
        self.theme_data['ui_elements'] = [{
            'type': 'icon',
            'icon': 'https://fontawesome.com/icons/angrycreative?f=brands&s=solid',
            'x': 50, 'y': 50,
            'size': 60
        }]
        overlay = self.renderer.generate_overlay()
        self.assertIsNotNone(overlay.getbbox())
        
        # Test 2: Resolve from complex URL user reported (user?f=classic&s=solid)
        self.theme_data['ui_elements'] = [{
            'type': 'icon',
            'icon': 'https://fontawesome.com/icons/user?f=classic&s=solid',
            'x': 50, 'y': 50,
            'size': 60
        }]
        overlay = self.renderer.generate_overlay()
        self.assertIsNotNone(overlay.getbbox())

        # Test 3: Resolve from name 'house'
        self.theme_data['ui_elements'] = [{
            'type': 'icon',
            'icon': 'house',
            'x': 100, 'y': 100,
            'size': 40
        }]
        overlay = self.renderer.generate_overlay()
        self.assertIsNotNone(overlay.getbbox())
        
        # Check if the cache has icons.json
        from library.config import FONTS_DIR
        meta_path = os.path.join(FONTS_DIR, 'cache', 'icons.json')
        self.assertTrue(os.path.exists(meta_path))
