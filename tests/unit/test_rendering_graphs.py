import unittest
import math
from PIL import Image
from library.rendering.graphs import draw_progress_bar, draw_line_graph, draw_radial_progress_bar

class TestRenderingGraphs(unittest.TestCase):
    def test_draw_progress_bar(self):
        canvas = Image.new('RGB', (100, 20), (255, 255, 255))
        # Now uses x, y from rect
        draw_progress_bar(canvas, (10, 5, 80, 10), 50, bar_color=(255, 0, 0), bar_outline=False)
        # Check inside bar
        self.assertEqual(canvas.getpixel((10, 5)), (255, 0, 0))
        # Check outside bar
        self.assertEqual(canvas.getpixel((0, 0)), (255, 255, 255))

    def test_draw_line_graph(self):
        canvas = Image.new('RGB', (100, 50), (255, 255, 255))
        # Now uses x, y from rect
        values = [0, 50, 100]
        draw_line_graph(canvas, (10, 10, 80, 30), values, line_color=(0, 0, 255))
        pixels = list(canvas.getdata())
        self.assertTrue(any(p == (0, 0, 255) for p in pixels))

    def test_draw_radial_progress_bar(self):
        canvas = Image.new('RGB', (100, 100), (255, 255, 255))
        # Signature: canvas, center, radius, bar_width, value, ...
        draw_radial_progress_bar(canvas, (50, 50), 40, 10, 50, bar_color=(0, 255, 0))
        pixels = list(canvas.getdata())
        self.assertTrue(any(p == (0, 255, 0) for p in pixels))

if __name__ == '__main__':
    unittest.main()
