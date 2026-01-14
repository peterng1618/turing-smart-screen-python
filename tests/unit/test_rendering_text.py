import unittest
from PIL import Image, ImageFont
from library.rendering.text import draw_text, get_text_bbox
import os

class TestRenderingText(unittest.TestCase):
    def setUp(self):
        self.canvas = Image.new('RGB', (100, 100), (255, 255, 255))
        # Use a system font or a bundled one if available. 
        # For tests, we'll try to find a font or use default.
        self.font_path = "res/fonts/roboto/Roboto-Regular.ttf"
        if not os.path.exists(self.font_path):
             self.font = ImageFont.load_default()
        else:
             self.font = ImageFont.truetype(self.font_path, 16)

    def test_draw_text(self):
        draw_text(self.canvas, "Hello", (0, 0), self.font, (0, 0, 0, 255))
        # Check if some pixels are not white anymore
        pixels = list(self.canvas.getdata())
        self.assertTrue(any(p != (255, 255, 255) for p in pixels), "Canvas should have some non-white pixels after drawing text")

    def test_get_text_bbox(self):
        bbox = get_text_bbox("Test", self.font, (10, 10))
        self.assertEqual(len(bbox), 4)
        self.assertTrue(bbox[2] > bbox[0])
        self.assertTrue(bbox[3] > bbox[1])

if __name__ == '__main__':
    unittest.main()
