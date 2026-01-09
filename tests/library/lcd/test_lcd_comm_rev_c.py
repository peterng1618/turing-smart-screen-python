import unittest
from unittest.mock import Mock

from library.lcd.lcd_comm_rev_c import LcdCommRevC, Orientation, SubRevision

from .serial_mock import new_testing_serial
from .sample_image import generate_sample_image


class MockedLcdCommRevC(LcdCommRevC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mocking initialization that usually happens in _hello()
        self.sub_revision = SubRevision.REV_5INCH
        self.rom_version = 87

    def openSerial(self):
        self.lcd_serial = new_testing_serial()

    def expect_golden(self, tc: unittest.TestCase, fn: str):
        self.lcd_serial.expect_golden(tc, fn)

sample_img_portrait = generate_sample_image(480, 800)
sample_img_landscape = generate_sample_image(800, 480)

class TestLcdCommRevC(unittest.TestCase):
    def test_set_brightness(self):
        lcd = MockedLcdCommRevC()
        lcd.SetBrightness()

        lcd.expect_golden(self, "rev_c_set_brightness")

    # display_pil_image_<orientation> : display a full-screen image

    def test_display_pil_image_portrait(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.PORTRAIT)
        lcd.DisplayPILImage(sample_img_portrait)

        lcd.expect_golden(self, "rev_c_display_pil_image_portrait")

    def test_display_pil_image_landscape(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.LANDSCAPE)
        lcd.DisplayPILImage(sample_img_landscape)

        lcd.expect_golden(self, "rev_c_display_pil_image_landscape")

    def test_display_pil_image_reverse_portrait(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.REVERSE_PORTRAIT)
        lcd.DisplayPILImage(sample_img_portrait)

        lcd.expect_golden(self, "rev_c_display_pil_image_reverse_portrait")

    def test_display_pil_image_reverse_landscape(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.REVERSE_LANDSCAPE)
        lcd.DisplayPILImage(sample_img_landscape)

        lcd.expect_golden(self, "rev_c_display_pil_image_reverse_landscape")

    # display_pil_image_patch_<orientation> : display a less-than-full-screen image at a given location

    def test_display_pil_image_patch_portrait(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.PORTRAIT)
        lcd.DisplayPILImage(sample_img_portrait, x=10, y=20, image_width=100, image_height=200)

        lcd.expect_golden(self, "rev_c_display_pil_image_patch_portrait")

    def test_display_pil_image_patch_landscape(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.LANDSCAPE)
        lcd.DisplayPILImage(sample_img_landscape, x=10, y=20, image_width=100, image_height=200)

        lcd.expect_golden(self, "rev_c_display_pil_image_patch_landscape")

    def test_display_pil_image_patch_reverse_portrait(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.REVERSE_PORTRAIT)
        lcd.DisplayPILImage(sample_img_portrait, x=10, y=20, image_width=100, image_height=200)

        lcd.expect_golden(self, "rev_c_display_pil_image_patch_reverse_portrait")

    def test_display_pil_image_patch_reverse_landscape(self):
        lcd = MockedLcdCommRevC()
        lcd.SetOrientation(orientation=Orientation.REVERSE_LANDSCAPE)
        lcd.DisplayPILImage(sample_img_landscape, x=10, y=20, image_width=100, image_height=200)

        lcd.expect_golden(self, "rev_c_display_pil_image_patch_reverse_landscape")


class TestLcdCommRevCVideo(unittest.TestCase):
    def test_start_video(self):
        lcd = MockedLcdCommRevC()
        # Mock sub_revision to REV_5INCH to ensure video commands are enabled (though they don't strictly check it yet except overlay)
        lcd.sub_revision = SubRevision.REV_5INCH
        
        # Mock GetFileSize to return a valid size so StartVideo proceeds
        lcd.GetFileSize = Mock(return_value=123456)
        
        lcd.StartVideo("/mnt/SDCARD/video/test.mp4")
        lcd.expect_golden(self, "rev_c_video_start")

    def test_stop_video(self):
        lcd = MockedLcdCommRevC()
        lcd.StopVideo()
        lcd.expect_golden(self, "rev_c_video_stop")

    def test_delete_file(self):
        lcd = MockedLcdCommRevC()
        lcd.DeleteFile("/mnt/SDCARD/video/old.mp4")
        lcd.expect_golden(self, "rev_c_video_delete_file")

    def test_initialize_video_overlay(self):
        lcd = MockedLcdCommRevC()
        lcd.sub_revision = SubRevision.REV_5INCH
        lcd.InitializeVideoOverlay()
        lcd.expect_golden(self, "rev_c_video_init_overlay")

