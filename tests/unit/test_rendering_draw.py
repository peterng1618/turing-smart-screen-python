import unittest
import os
from PIL import Image, ImageFont
from library.rendering import draw

class TestRenderingDraw(unittest.TestCase):
    def setUp(self):
        self.canvas = Image.new('RGBA', (100, 100), (255, 255, 255, 255))
        self.font_path = "./res/fonts/roboto/Roboto-Regular.ttf"
        if not os.path.exists(self.font_path):
             # Fallback for CI or different environments if needed
             self.font = ImageFont.load_default()
        else:
             self.font = ImageFont.truetype(self.font_path, 20)

    def test_resolve_color(self):
        # String formats
        self.assertEqual(draw.resolve_color("255, 0, 0"), (255, 0, 0, 255))
        self.assertEqual(draw.resolve_color("0, 255, 0, 128"), (0, 255, 0, 128))
        self.assertEqual(draw.resolve_color("white"), (255, 255, 255, 255))
        self.assertEqual(draw.resolve_color("#FF0000"), (255, 0, 0, 255))
        
        # Tuple formats
        self.assertEqual(draw.resolve_color((255, 255, 0)), (255, 255, 0, 255))
        self.assertEqual(draw.resolve_color((1, 2, 3, 4)), (1, 2, 3, 4))
        
        # Override alpha
        self.assertEqual(draw.resolve_color("white", override_alpha=128), (255, 255, 255, 128))
        self.assertEqual(draw.resolve_color("white", override_alpha=0.5), (255, 255, 255, 127))

    def test_composite_background_color(self):
        bg = draw.composite_background(50, 50, (255, 0, 0, 255))
        self.assertEqual(bg.size, (50, 50))
        self.assertEqual(bg.getpixel((0, 0)), (255, 0, 0, 255))

    def test_composite_background_image(self):
        full_bg = Image.new('RGBA', (200, 200), (0, 255, 0, 255))
        bg = draw.composite_background(50, 50, (0, 0, 0, 0), background_image=full_bg, crop_xy=(10, 10))
        self.assertEqual(bg.size, (50, 50))
        self.assertEqual(bg.getpixel((0, 0)), (0, 255, 0, 255))

    def test_draw_text(self):
        bbox = draw.text(self.canvas, "Hello", (10, 10), self.font, (0, 0, 0, 255))
        self.assertTrue(bbox[2] > 0)
        self.assertTrue(bbox[3] > 0)
        # Check center of rendered text block (roughly)
        px, py = bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2
        pixel = self.canvas.getpixel((px, py))
        self.assertNotEqual(pixel, (255, 255, 255, 255))

    def test_draw_progress_bar(self):
        # 80px width, 50% = 40px filled. Starts at x=10.
        # Should be filled from 10 to 49.
        draw.progress_bar(self.canvas, (10, 10, 80, 20), 50, bar_color=(255, 0, 0, 255))
        # Check at x=30 (well inside the 10-49 range)
        pixel = self.canvas.getpixel((30, 20))
        self.assertEqual(pixel, (255, 0, 0, 255))

    def test_draw_radial_progress_bar(self):
        # xc=50, yc=50, radius=40. 0-180 degrees (clockwise) is the bottom half.
        draw.radial_progress_bar(self.canvas, (50, 50, 40), 10, 50, bar_color=(0, 255, 0, 255))
        # Top half should stay white
        self.assertEqual(self.canvas.getpixel((50, 15)), (255, 255, 255, 255))
        # Bottom half should be bar color
        self.assertEqual(self.canvas.getpixel((50, 85)), (0, 255, 0, 255))

if __name__ == '__main__':
    unittest.main()
