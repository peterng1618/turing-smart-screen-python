import unittest
import math
from PIL import Image
from library.rendering.graphs import draw_progress_bar, draw_line_graph, draw_radial_progress_bar

class TestRenderingGraphs(unittest.TestCase):
    def test_draw_progress_bar(self):
        canvas = Image.new('RGB', (100, 20), (255, 255, 255))
        draw_progress_bar(canvas, (0, 0, 100, 20), 50, bar_color=(255, 0, 0), bar_outline=False)
        # Top-left pixel (within bar) should be red
        self.assertEqual(canvas.getpixel((0, 0)), (255, 0, 0))
        # Middle-right pixel (outside 50% bar) should be white
        self.assertEqual(canvas.getpixel((75, 10)), (255, 255, 255))

    def test_draw_line_graph(self):
        canvas = Image.new('RGB', (100, 50), (255, 255, 255))
        values = [0, 50, 100]
        draw_line_graph(canvas, (0, 0, 100, 50), values, line_color=(0, 0, 255))
        pixels = list(canvas.getdata())
        self.assertTrue(any(p == (0, 0, 255) for p in pixels))

    def test_draw_radial_progress_bar(self):
        canvas = Image.new('RGB', (100, 100), (255, 255, 255))
        draw_radial_progress_bar(canvas, 50, 10, 50, bar_color=(0, 255, 0))
        pixels = list(canvas.getdata())
        self.assertTrue(any(p == (0, 255, 0) for p in pixels))

if __name__ == '__main__':
    unittest.main()
