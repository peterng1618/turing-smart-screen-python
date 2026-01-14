import unittest
from PIL import Image
from library.rendering.image import draw_image

class TestRenderingImage(unittest.TestCase):
    def test_draw_image(self):
        canvas = Image.new('RGB', (20, 20), (255, 255, 255))
        img = Image.new('RGB', (10, 10), (0, 0, 0))
        draw_image(canvas, img, (5, 5))
        self.assertEqual(canvas.getpixel((5, 5)), (0, 0, 0))
        self.assertEqual(canvas.getpixel((0, 0)), (255, 255, 255))

    def test_draw_image_resize(self):
        canvas = Image.new('RGB', (20, 20), (255, 255, 255))
        img = Image.new('RGB', (5, 5), (255, 0, 0))
        draw_image(canvas, img, (0, 0), size=(10, 10))
        self.assertEqual(canvas.getpixel((9, 9)), (255, 0, 0))

if __name__ == '__main__':
    unittest.main()
