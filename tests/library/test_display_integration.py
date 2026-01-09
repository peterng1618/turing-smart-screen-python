import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import library
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from library.display import Display
from library import config

class TestDisplayIntegration(unittest.TestCase):
    @patch('library.display.LcdSimulated')
    @patch('library.ui_renderer.UiRenderer')
    def test_display_static_images_calls_renderer(self, MockUiRenderer, MockLcd):
        # Setup Mocks
        config.THEME_DATA = {
            'static_images': {},
            'ui_elements': {'shapes': [{'type': 'rectangle'}]},
            'PATH': '/tmp/theme/',
            'display': {'DISPLAY_SIZE': '3.5"'}
        }
        config.CONFIG_DATA = {
            'display': {'REVISION': 'SIMU', 'BRIGHTNESS': 100},
            'config': {'COM_PORT': 'COM1'}
        }
        
        # Mock LCD behavior
        mock_lcd_instance = MockLcd.return_value
        # Mock screen_image to be a MagicMock that we can check calls on
        mock_screen_image = MagicMock()
        mock_lcd_instance.screen_image = mock_screen_image
        
        # Mock Renderer
        mock_renderer_instance = MockUiRenderer.return_value
        mock_overlay = MagicMock()
        mock_renderer_instance.generate_overlay.return_value = mock_overlay
        
        # Initialize Display
        display = Display()
        display.lcd = mock_lcd_instance # Force our mock
        
        # Call method
        display.display_static_images()
        
        # Verify UiRenderer was initialized
        MockUiRenderer.assert_called_once()
        
        # Verify generate_overlay was called
        mock_renderer_instance.generate_overlay.assert_called_once()
        
        # Verify alpha_composite was called on the screen image with the overlay
        mock_screen_image.alpha_composite.assert_called_with(mock_overlay, (0, 0))

if __name__ == '__main__':
    unittest.main()
