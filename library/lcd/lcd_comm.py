# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import copy
import math
import os
import platform
import queue
import sys
import threading
import time
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Tuple, List, Optional, Dict

import serial
from PIL import Image, ImageDraw, ImageFont

from library.log import logger
from library.lcd.color import Color, parse_color
import library.rendering.text as rendering_text
import library.rendering.image as rendering_image
import library.rendering.graphs as rendering_graphs
import library.rendering.effects as rendering_effects
import library.rendering.draw as rendering_draw


class Orientation(IntEnum):
    PORTRAIT = 0
    LANDSCAPE = 2
    REVERSE_PORTRAIT = 1
    REVERSE_LANDSCAPE = 3


class LcdComm(ABC):
    def __init__(self, com_port: str = "AUTO", display_width: int = 320, display_height: int = 480,
                 update_queue: Optional[queue.Queue] = None):
        self.lcd_serial = None

        # String containing absolute path to serial port e.g. "COM3", "/dev/ttyACM1" or "AUTO" for auto-discovery
        self.com_port = com_port

        # Display always start in portrait orientation by default
        self.orientation = Orientation.PORTRAIT
        # Display width in default orientation (portrait)
        self.display_width = display_width
        # Display height in default orientation (portrait)
        self.display_height = display_height

        # Queue containing the serial requests to send to the screen. An external thread should run to process requests
        # on the queue. If you want serial requests to be done in sequence, set it to None
        self.update_queue = update_queue

        # Mutex to protect the queue in case a thread want to add multiple requests (e.g. image data) that should not be
        # mixed with other requests in-between
        self.update_queue_mutex = threading.Lock()

        # Create a cache to store opened images, to avoid opening and loading from the filesystem every time
        self.image_cache = {}  # { key=path, value=PIL.Image }

        # Create a cache to store opened fonts, to avoid opening and loading from the filesystem every time
        self.font_cache: Dict[
            Tuple[str, int],  # key=(font, size)
            ImageFont.FreeTypeFont # value= a loaded freetype font
        ] = {}

    def get_width(self) -> int:
        if self.orientation == Orientation.PORTRAIT or self.orientation == Orientation.REVERSE_PORTRAIT:
            return self.display_width
        else:
            return self.display_height

    def get_height(self) -> int:
        if self.orientation == Orientation.PORTRAIT or self.orientation == Orientation.REVERSE_PORTRAIT:
            return self.display_height
        else:
            return self.display_width

    def openSerial(self):
        if self.com_port == 'AUTO':
            self.com_port = self.auto_detect_com_port()
            if not self.com_port:
                logger.error(
                    "Cannot find COM port automatically, please run Configuration again and select COM port manually")
                try:
                    sys.exit(0)
                except:  # noqa: E722
                    os._exit(0)
            else:
                logger.debug(f"Auto detected COM port: {self.com_port}")
        else:
            logger.debug(f"Static COM port: {self.com_port}")

        try:
            self.lcd_serial = serial.Serial(self.com_port, 115200, timeout=1, rtscts=True)
        except Exception as e:
            logger.error(f"Cannot open COM port {self.com_port}: {e}")
            try:
                sys.exit(0)
            except:  # noqa: E722
                os._exit(0)

    def closeSerial(self):
        if self.lcd_serial is not None:
            self.lcd_serial.close()

    def serial_write(self, data: bytes):
        assert self.lcd_serial is not None
        self.lcd_serial.write(data)

    def serial_read(self, size: int) -> bytes:
        assert self.lcd_serial is not None
        return self.lcd_serial.read(size)

    def serial_readall(self) -> bytes:
        assert self.lcd_serial is not None
        return self.lcd_serial.readall()

    def serial_flush_input(self):
        if self.lcd_serial is not None:
            self.lcd_serial.reset_input_buffer()

    def WriteData(self, byteBuffer: bytearray):
        self.WriteLine(bytes(byteBuffer))

    def SendLine(self, line: bytes):
        if self.update_queue:
            # Queue the request. Mutex is locked by caller to queue multiple lines
            self.update_queue.put((self.WriteLine, [line]))
        else:
            # If no queue for async requests: do request now
            self.WriteLine(line)

    def WriteLine(self, line: bytes):
        try:
            self.serial_write(line)
            if platform.system() == "Darwin":
                # macOS needs the serial buffer to be flushed regularly to avoid bitmap corruption on the display
                # See https://github.com/mathoudebine/turing-smart-screen-python/issues/7
                self.lcd_serial.flush()
        except serial.SerialTimeoutException:
            # We timed-out trying to write to our device, slow things down.
            logger.warning("(Write line) Too fast! Slow down!")
        except serial.SerialException:
            # Error writing data to device: close and reopen serial port, try to write again
            logger.error(
                "SerialException: Failed to send serial data to device. Closing and reopening COM port before retrying once.")
            self.closeSerial()
            time.sleep(1)
            self.openSerial()
            self.serial_write(line)

    def ReadData(self, readSize: int):
        try:
            response = self.serial_read(readSize)
            # logger.debug("Received: [{}]".format(str(response, 'utf-8')))
            return response
        except serial.SerialTimeoutException:
            # We timed-out trying to read from our device, slow things down.
            logger.warning("(Read data) Too fast! Slow down!")
        except serial.SerialException:
            # Error writing data to device: close and reopen serial port, try to read again
            logger.error(
                "SerialException: Failed to read serial data from device. Closing and reopening COM port before retrying once.")
            self.closeSerial()
            time.sleep(1)
            self.openSerial()
            return self.serial_read(readSize)

    @staticmethod
    @abstractmethod
    def auto_detect_com_port() -> Optional[str]:
        pass

    @abstractmethod
    def InitializeComm(self):
        pass

    @abstractmethod
    def Reset(self):
        pass

    @abstractmethod
    def Clear(self):
        pass

    @abstractmethod
    def ScreenOff(self):
        pass

    @abstractmethod
    def ScreenOn(self):
        pass

    @abstractmethod
    def SetBrightness(self, level: int):
        pass

    def SetBackplateLedColor(self, led_color: Tuple[int, int, int] = (255, 255, 255)):
        pass

    @abstractmethod
    def SetOrientation(self, orientation: Orientation):
        pass

    @abstractmethod
    def DisplayPILImage(
            self,
            image: Image.Image,
            x: int = 0, y: int = 0,
            image_width: int = 0,
            image_height: int = 0
    ):
        pass

    def DisplayBitmap(self, bitmap_path: str, x: int = 0, y: int = 0, width: int = 0, height: int = 0):
        image = self.open_image(bitmap_path)
        
        # Calculate target size if not specified
        target_size = (width, height) if width != 0 and height != 0 else image.size
        
        # Create a temporary canvas for potential resizing/pasting if we wanted to isolate,
        # but DisplayBitmap usually just sends the image.
        # However, to be holistic, we use draw_image.
        # But wait, DisplayBitmap in LcdComm is often used to send a FULL image or a portion.
        # The existing code resizes the image object itself.
        
        if width != 0 and height != 0:
             if width != image.size[0] or height != image.size[1]:
                 image = image.resize((width, height))

        self.DisplayPILImage(image, x, y, width, height)

    def DisplayText(
            self,
            text: str,
            x: int = 0,
            y: int = 0,
            width: int = 0,
            height: int = 0,
            font: str = "./res/fonts/roboto-mono/RobotoMono-Regular.ttf",
            font_size: int = 20,
            font_color: Color = (0, 0, 0),
            background_color: Color = (255, 255, 255),
            background_image: Optional[str] = None,
            align: str = 'left',
            anchor: str = 'la',
            opacity: float = 1.0,
            rotation: float = 0,
            shadow: Optional[Dict] = None,
            outline: Optional[Dict] = None,
    ):
        # Resolve colors
        font_color_rgba = rendering_draw.resolve_color(font_color, override_alpha=opacity)
        bg_color_rgba = rendering_draw.resolve_color(background_color)
        
        # Load font
        ttfont = self.open_font(font, font_size)

        # We need a canvas. If we have a background image, we composite onto a crop of it.
        # Otherwise, we create a solid color patch.
        # LcdComm traditionally sends ONLY the modified area to the screen.
        
        # However, to use our unified 'text' helper, we need a canvas.
        # We'll use a temporary canvas for the bounding box allowed (width x height) if provided,
        # or we'll render to a large enough canvas and then send the result.
        
        # Determine canvas size
        canvas_w = width if width > 0 else self.get_width()
        canvas_h = height if height > 0 else self.get_height()
        
        if background_image:
             full_bg = self.open_image(background_image)
             canvas = rendering_draw.composite_background(canvas_w, canvas_h, bg_color_rgba, background_image=full_bg, crop_xy=(x, y))
        else:
             canvas = rendering_draw.composite_background(canvas_w, canvas_h, bg_color_rgba)
        
        # Draw text at (0,0) of this canvas if width/height were specified, 
        # but wait, LcdComm.DisplayText takes absolute (x, y).
        # We want the output to be at (x, y) on the screen.
        # So we draw at (0,0) relative to our cropped canvas.
        
        rx, ry, rw, rh = rendering_draw.text(
            canvas, text, (0, 0), ttfont, font_color_rgba,
            align=align, anchor=anchor, opacity=1.0, # Opacity already applied to font_color_rgba
            rotation=rotation, shadow=shadow, outline=outline
        )
        
        # Final result to send to screen
        # If width/height were 0, canvas is full screen size (inefficient to send)
        # So we crop it to the bounding box of what was actually drawn
        if width == 0 or height == 0:
             final_img = canvas.crop((rx, ry, rx + rw, ry + rh))
             self.DisplayPILImage(final_img.convert('RGB'), x + rx, y + ry)
        else:
             self.DisplayPILImage(canvas.convert('RGB'), x, y)

    def DisplayProgressBar(self, x: int, y: int, width: int, height: int, min_value: int = 0, max_value: int = 100,
                            value: int = 50,
                            bar_color: Color = (0, 0, 0),
                            bar_outline: bool = True,
                            background_color: Color = (255, 255, 255),
                            background_image: Optional[str] = None):
        # Resolve colors
        bar_color_rgba = rendering_draw.resolve_color(bar_color)
        bg_color_rgba = rendering_draw.resolve_color(background_color)

        # Prepare canvas
        if background_image:
             full_bg = self.open_image(background_image)
             canvas = rendering_draw.composite_background(width, height, bg_color_rgba, background_image=full_bg, crop_xy=(x, y))
        else:
             canvas = rendering_draw.composite_background(width, height, bg_color_rgba)

        # Draw bar at (0, 0) of our cropped canvas
        rendering_draw.progress_bar(
            canvas, (0, 0, width, height), value, min_value, max_value, bar_color_rgba, bar_outline
        )

        self.DisplayPILImage(canvas.convert('RGB'), x, y)

    def DisplayLineGraph(self, x: int, y: int, width: int, height: int,
                         values: List[float],
                         min_value: float = 0,
                         max_value: float = 100,
                         autoscale: bool = False,
                         line_color: Color = (0, 0, 0),
                         line_width: int = 2,
                         graph_axis: bool = True,
                         axis_color: Color = (0, 0, 0),
                         axis_font: str = "./res/fonts/roboto/Roboto-Black.ttf",
                         axis_font_size: int = 10,
                         background_color: Color = (255, 255, 255),
                         background_image: Optional[str] = None):
        # Resolve colors
        line_color_rgba = rendering_draw.resolve_color(line_color)
        axis_color_rgba = rendering_draw.resolve_color(axis_color)
        bg_color_rgba = rendering_draw.resolve_color(background_color)

        # Prepare canvas
        if background_image:
             full_bg = self.open_image(background_image)
             canvas = rendering_draw.composite_background(width, height, bg_color_rgba, background_image=full_bg, crop_xy=(x, y))
        else:
             canvas = rendering_draw.composite_background(width, height, bg_color_rgba)

        ttfont = self.open_font(axis_font, axis_font_size) if graph_axis else None

        # Draw graph at (0, 0)
        rendering_draw.line_graph(
            canvas, (0, 0, width, height), values, min_value, max_value,
            autoscale, line_color_rgba, line_width, graph_axis, axis_color_rgba, ttfont
        )

        self.DisplayPILImage(canvas.convert('RGB'), x, y)



    def DisplayRadialProgressBar(self, xc: int, yc: int, radius: int, bar_width: int,
                                 min_value: int = 0,
                                 max_value: int = 100,
                                 angle_start: float = 0,
                                 angle_end: float = 360,
                                 angle_sep: int = 5,
                                 angle_steps: int = 10,
                                 clockwise: bool = True,
                                 value: int = 50,
                                 text: Optional[str] = None,
                                 with_text: bool = True,
                                 font: str = "./res/fonts/roboto/Roboto-Black.ttf",
                                 font_size: int = 20,
                                 font_color: Color = (0, 0, 0),
                                 bar_color: Color = (0, 0, 0),
                                 background_color: Color = (255, 255, 255),
                                 background_image: Optional[str] = None,
                                 custom_bbox: Tuple[int, int, int, int] = (0, 0, 0, 0),
                                 text_offset: Tuple[int, int] = (0,0),
                                 bar_background_color: Color = (0, 0, 0),
                                 draw_bar_background: bool = False,
                                 bar_decoration: str = ""):
        # Resolve colors
        bar_color_rgba = rendering_draw.resolve_color(bar_color)
        bg_color_rgba = rendering_draw.resolve_color(background_color)
        font_color_rgba = rendering_draw.resolve_color(font_color)
        bar_bg_color_rgba = rendering_draw.resolve_color(bar_background_color)

        diameter = 2 * radius
        
        # Prepare canvas
        if background_image:
             full_bg = self.open_image(background_image)
             canvas = rendering_draw.composite_background(diameter, diameter, bg_color_rgba, background_image=full_bg, crop_xy=(xc - radius, yc - radius))
        else:
             canvas = rendering_draw.composite_background(diameter, diameter, bg_color_rgba)

        ttfont = self.open_font(font, font_size) if with_text else None
        if with_text and text is None:
             text = f"{int(((value - min_value) / (max_value - min_value)) * 100 + .5)}%"

        # Draw radial bar at (radius, radius) relative to our cropped canvas
        rendering_draw.radial_progress_bar(
            canvas, (radius, radius, radius), bar_width, value, min_value, max_value,
            angle_start, angle_end, angle_sep, angle_steps, clockwise,
            text, ttfont, font_color_rgba, bar_color_rgba, text_offset, 
            bar_bg_color_rgba, draw_bar_background, bar_decoration
        )

        if custom_bbox != (0, 0, 0, 0):
            canvas = canvas.crop(box=custom_bbox)
            self.DisplayPILImage(canvas.convert('RGB'), xc - radius + custom_bbox[0], yc - radius + custom_bbox[1])
        else:
            self.DisplayPILImage(canvas.convert('RGB'), xc - radius, yc - radius)

    # Load image from the filesystem, or get from the cache if it has already been loaded previously
    def open_image(self, bitmap_path: str) -> Image.Image:
        if bitmap_path not in self.image_cache:
            logger.debug("Bitmap " + bitmap_path + " is now loaded in the cache")
            self.image_cache[bitmap_path] = Image.open(bitmap_path)
        return copy.copy(self.image_cache[bitmap_path])

    def open_font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        if (name, size) not in self.font_cache:
            self.font_cache[(name, size)] = ImageFont.truetype(name, size)
        return self.font_cache[(name, size)]
