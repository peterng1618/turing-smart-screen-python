import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time
from PIL import Image

# Ensure we can import library
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock problematic modules before they are imported by stats
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()

# Mock display mod
mock_display_mod = MagicMock()
sys.modules['library.display'] = mock_display_mod

# Mock config mod
mock_config_mod = MagicMock()
sys.modules['library.config'] = mock_config_mod
mock_config_mod.FONTS_DIR = "/tmp/fonts/"
mock_config_mod.STATS_VALUES = {}
mock_config_mod.STATS_RAW = {}
mock_config_mod.THEME_DATA = {}
mock_config_mod.CONFIG_DATA = {
    "config": {
        "HW_SENSORS": "STUB",
        "ETH": "",
        "WLO": "",
        "CPU_FAN": "AUTO",
        "PING": "127.0.0.1"
    }
}

# Now we can safely import stats
from library import stats

class TestDynamicText(unittest.TestCase):
    def setUp(self):
        stats.DynamicText.last_updates = {}
        mock_config_mod.STATS_VALUES = {
            "CPU_PERCENTAGE": " 15%",
            "CPU_PERCENTAGE_RAW": " 15",
            "GPU_PERCENTAGE": " 42%",
            "GPU_PERCENTAGE_RAW": " 42"
        }
        mock_config_mod.STATS_RAW = {
            "CPU_PERCENTAGE": 15.5,
            "GPU_PERCENTAGE": 42.1
        }
        mock_config_mod.THEME_DATA = {
            "PATH": "/tmp/theme/",
            "dynamic_text": {
                "TEST_VAL": {
                    "SHOW": True,
                    "TEXT": "CPU: {CPU_PERCENTAGE:u} | GPU: {GPU_PERCENTAGE:nu} | RAW: {CPU_PERCENTAGE:r}",
                    "X": 10,
                    "Y": 10,
                    "FONT": "test.ttf",
                    "FONT_SIZE": 12,
                    "angle": 5,
                    "opacity": 0.5,
                    "shadow": {"color": "black", "blur": 2}
                }
            }
        }

    def test_dynamic_text_substitution(self):
        mock_lcd = MagicMock()
        mock_display_mod.display.lcd = mock_lcd
        
        stats.DynamicText.stats()
        
        # We check if DisplayPILImage was called
        mock_lcd.DisplayPILImage.assert_called_once()
        args, kwargs = mock_lcd.DisplayPILImage.call_args
        # Image is first arg
        img = args[0]
        self.assertIsInstance(img, Image.Image)
        # Coordinates are 2nd and 3rd or as kwargs? 
        # DisplayPILImage(img, left, top)
        # In my code: display.lcd.DisplayPILImage(final_styled_img, int(final_x), int(final_y))

    def test_dynamic_text_missing_sensor(self):
        mock_lcd = MagicMock()
        mock_display_mod.display.lcd = mock_lcd
        
        mock_config_mod.THEME_DATA["dynamic_text"]["TEST_VAL"]["TEXT"] = "Val: {MISSING_SENSOR}"
        
        # Reset last_updates for clean test
        stats.DynamicText.last_updates = {}
        
        stats.DynamicText.stats()
        
        # mock_lcd.DisplayText replaced by DisplayPILImage
        mock_lcd.DisplayPILImage.assert_called_once()
    
    def test_dynamic_text_interval(self):
        mock_lcd = MagicMock()
        mock_display_mod.display.lcd = mock_lcd
        
        # Reset last_updates
        stats.DynamicText.last_updates = {}
        
        # Setup element with 10s interval
        mock_config_mod.THEME_DATA["dynamic_text"]["TEST_VAL"]["INTERVAL"] = 10
        
        # First call should render
        stats.DynamicText.stats()
        self.assertEqual(mock_lcd.DisplayPILImage.call_count, 1)
        
        # Second call immediately after should NOT render
        stats.DynamicText.stats()
        self.assertEqual(mock_lcd.DisplayPILImage.call_count, 1)
        
        # Mock time forward
        with patch('time.time', return_value=time.time() + 11):
            stats.DynamicText.stats()
            self.assertEqual(mock_lcd.DisplayPILImage.call_count, 2)

if __name__ == '__main__':
    unittest.main()
