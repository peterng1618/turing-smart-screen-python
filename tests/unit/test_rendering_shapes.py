import unittest
from PIL import Image
from library.rendering.shapes import draw_rectangle, draw_ellipse, draw_line

class TestRenderingShapes(unittest.TestCase):
    def test_draw_rectangle(self):
        canvas = Image.new('RGB', (20, 20), (255, 255, 255))
        draw_rectangle(canvas, (0, 0, 20, 20), fill=(255, 0, 0))
        self.assertEqual(canvas.getpixel((10, 10)), (255, 0, 0))

    def test_draw_ellipse(self):
        canvas = Image.new('RGB', (20, 20), (255, 255, 255))
        draw_ellipse(canvas, (0, 0, 20, 20), fill=(0, 255, 0))
        self.assertEqual(canvas.getpixel((10, 10)), (0, 255, 0))

    def test_draw_line(self):
        canvas = Image.new('RGB', (20, 20), (255, 255, 255))
        draw_line(canvas, [(0, 0), (19, 19)], fill=(0, 0, 255))
        self.assertEqual(canvas.getpixel((0, 0)), (0, 0, 255))

if __name__ == '__main__':
    unittest.main()
