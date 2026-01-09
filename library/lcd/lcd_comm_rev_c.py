# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
# Copyright (C) 2023 Alex W. Baulé (alexwbaule)
# Copyright (C) 2023 Arthur Ferrai (arthurferrai)
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

import queue
import re
import string
import struct
import os
import time
from enum import Enum
from math import ceil
from typing import Optional, Tuple, List
import numpy as np
from numba import jit

import serial
from PIL import Image,ImageDraw
from serial.tools.list_ports import comports

from library.lcd.lcd_comm import Orientation, LcdComm
from library.lcd.serialize import image_to_BGRA, image_to_BGR, chunked
from library.log import logger


class Count:
    Start = 0


# READ HELLO ALWAYS IS 23.
# ALL READS IS 1024

# ORDER:
# SEND HELLO
# READ HELLO (23)
# SEND STOP_VIDEO
# SEND STOP_MEDIA
# READ STATUS (1024)
# SEND SET_BRIGHTNESS
# SEND SET_OPTIONS WITH ORIENTATION ?
# SEND PRE_UPDATE_BITMAP
# SEND START_DISPLAY_BITMAP
# SEND DISPLAY_BITMAP
# READ STATUS (1024)
# SEND QUERY_STATUS
# READ STATUS (1024)
# WHILE:
#   SEND UPDATE_BITMAP
#   SEND QUERY_STATUS
#   READ STATUS(1024)

class Command(Enum):
    # COMMANDS
    HELLO = bytearray((0x01, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0xc5, 0xd3))
    OPTIONS = bytearray((0x7d, 0xef, 0x69, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x2d))
    RESTART = bytearray((0x84, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))
    TURNOFF = bytearray((0x83, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))
    TURNON = bytearray((0x83, 0xef, 0x69, 0x00, 0x00, 0x00, 0x00))

    SET_BRIGHTNESS = bytearray((0x7b, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00))

    # STOP COMMANDS
    STOP_VIDEO = bytearray((0x79, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))
    STOP_MEDIA = bytearray((0x96, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))

    # IMAGE QUERY STATUS
    QUERY_STATUS = bytearray((0xcf, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))

    # STATIC IMAGE
    START_DISPLAY_BITMAP = bytearray((0x2c,))
    PRE_UPDATE_BITMAP = bytearray((0x86, 0xef, 0x69, 0x00, 0x00, 0x00, 0x01))
    UPDATE_BITMAP = bytearray((0xcc, 0xef, 0x69, 0x00))
    DISPLAY_BITMAP_2INCH = bytearray((0xc8, 0xef, 0x69, 0x00)) + bytearray((0x0E, 0x10))
    DISPLAY_BITMAP_5INCH = bytearray((0xc8, 0xef, 0x69, 0x00)) + bytearray((0x17, 0x70))
    DISPLAY_BITMAP_8INCH = bytearray((0xc8, 0xef, 0x69, 0x00)) + bytearray((0x38, 0x40))

    # VIDEO
    START_VIDEO = bytearray((0x78, 0xef, 0x69, 0x00, 0x00, 0x00))
    INIT_VIDEO_OVERLAY = bytearray((0xd0, 0xef, 0x69, 0x00, 0x00, 0x00))

    # FILES
    LIST_FILES = bytearray((0x65, 0xef, 0x69, 0x00, 0x00, 0x00))
    UPLOAD_FILE = bytearray((0x6f, 0xef, 0x69, 0x00, 0x00, 0x00))
    DELETE_FILE = bytearray((0x66, 0xef, 0x69, 0x00, 0x00, 0x00))
    GET_FILE_SIZE = bytearray((0x6e, 0xef, 0x69, 0x00, 0x00, 0x00))

    DISPLAY_BITMAP_ON_VIDEO = bytearray((0xca, 0xef, 0x69, 0x00, 0x17, 0x70))

    STARTMODE_DEFAULT = bytearray((0x00,))
    STARTMODE_IMAGE = bytearray((0x01,))
    STARTMODE_VIDEO = bytearray((0x02,))
    FLIP_180 = bytearray((0x01,))
    NO_FLIP = bytearray((0x00,))
    SEND_PAYLOAD = bytearray((0xFF,))


class Padding(Enum):
    NULL = bytearray([0x00])
    START_DISPLAY_BITMAP = bytearray([0x2c])


class SleepInterval(Enum):
    OFF = bytearray((0x00,))
    ONE = bytearray((0x01,))
    TWO = bytearray((0x02,))
    THREE = bytearray((0x03,))
    FOUR = bytearray((0x04,))
    FIVE = bytearray((0x05,))
    SIX = bytearray((0x06,))
    SEVEN = bytearray((0x07,))
    EIGHT = bytearray((0x08,))
    NINE = bytearray((0x09,))
    TEN = bytearray((0x0a,))


class SubRevision(Enum):
    UNKNOWN = 0
    REV_2INCH = 1  # For 2.1" and 2.8" models
    REV_5INCH = 2
    REV_8INCH = 3


WAKE_RETRIES = 15


# This class is for Turing Smart Screen 2.1" / 2.8" / 5" / 8" screens
class LcdCommRevC(LcdComm):
    def __init__(self, com_port: str = "AUTO", display_width: int = 480, display_height: int = 800,
                 update_queue: Optional[queue.Queue] = None):
        logger.debug("HW revision: C")
        LcdComm.__init__(self, com_port, display_width, display_height, update_queue)
        self.openSerial()
        # Video overlay is the image to be drawn on the video.
        self.video_overlay = None
        # Previous video overlay stores the image previously drawn on the video (so only the updated pixels can be sent).
        self.previous_video_overlay = None

    def __del__(self):
        self.closeSerial()

    @staticmethod
    def auto_detect_com_port() -> Optional[str]:
        # If sleeping device is detected through serial number or vid/pid, try to wake it up
        for com_port in comports():
            if com_port.serial_number == 'USB7INCH' or com_port.serial_number == 'CT21INCH':
                LcdCommRevC._wake_up_device(com_port)
            elif com_port.vid == 0x1a86 and com_port.pid == 0xca21:
                LcdCommRevC._wake_up_device(com_port)

        return LcdCommRevC._get_awake_com_port(comports())

    @staticmethod
    def _get_awake_com_port(com_ports) -> Optional[str]:
        # Try to find awake device through serial number or vid/pid
        for com_port in com_ports:
            if com_port.serial_number == '20080411':
                return com_port.device
            if com_port.vid == 0x0525 and com_port.pid == 0xa4a7:
                return com_port.device
            if com_port.vid == 0x1d6b and (com_port.pid == 0x0121 or com_port.pid == 0x0106):
                return com_port.device

        return None

    @staticmethod
    def _wake_up_device(com_port):
        # Connect to the device to wake it up
        logger.debug(f"Waiting for device {com_port} to be turned ON...")

        for i in range(WAKE_RETRIES):
            try:
                # Try to connect every second, since it takes sometimes multiple connect to wake up the device
                serial.Serial(com_port.device, 115200, timeout=1, rtscts=True)
            except serial.SerialException:
                pass

            if LcdCommRevC._get_awake_com_port(comports()) is not None:
                time.sleep(1)
                logger.debug(f"Detected screen turned ON")
                return

            time.sleep(1)

        logger.error(f"Could not turn screen on after {WAKE_RETRIES} seconds, aborting.")

    def _send_command(self, cmd: Command, payload: Optional[bytearray] = None, padding: Optional[Padding] = None,
                      bypass_queue: bool = False, readsize: Optional[int] = None):
        message = bytearray()

        if cmd != Command.SEND_PAYLOAD:
            message = bytearray(cmd.value)

        # logger.debug("Command: {}".format(cmd.name))

        if not padding:
            padding = Padding.NULL

        if payload:
            message.extend(payload)

        msg_size = len(message)

        if not (msg_size / 250).is_integer():
            pad_size = (250 * ceil(msg_size / 250) - msg_size)
            message += bytearray(padding.value * pad_size)

        # If no queue for async requests, or if asked explicitly to do the request sequentially: do request now
        if not self.update_queue or bypass_queue:
            self.WriteData(message)
            if readsize:
                self.ReadData(readsize)
        else:
            # Lock queue mutex then queue the request
            self.update_queue.put((self.WriteData, [message]))
            if readsize:
                self.update_queue.put((self.ReadData, [readsize]))

    def _hello(self):
        # This command reads LCD answer on serial link, so it bypasses the queue
        self.sub_revision = SubRevision.UNKNOWN
        self.serial_flush_input()
        self._send_command(Command.HELLO, bypass_queue=True)
        response = ''.join(
            filter(lambda x: x in set(string.printable), str(self.serial_read(23).decode(errors="ignore"))))
        self.serial_flush_input()
        logger.debug("Display ID returned: %s" % response)
        while not response.startswith("chs_"):
            logger.warning("Display returned invalid or unsupported ID, try again in 1 second")
            time.sleep(1)
            self._send_command(Command.HELLO, bypass_queue=True)
            response = ''.join(
                filter(lambda x: x in set(string.printable), str(self.serial_read(23).decode(errors="ignore"))))
            self.serial_flush_input()
            logger.debug("Display ID returned: %s" % response)

        # Note: ID returned by display are not reliable for some models e.g. 2.1" displays return "chs_5inch"
        # Rely on width/height for sub-revision detection
        if self.display_width == 480 and self.display_height == 480:
            self.sub_revision = SubRevision.REV_2INCH
        elif self.display_width == 480 and self.display_height == 800:
            self.sub_revision = SubRevision.REV_5INCH
        elif self.display_width == 480 and self.display_height == 1920:
            self.sub_revision = SubRevision.REV_8INCH
        else:
            logger.error(f"Unsupported resolution {self.display_width}x{self.display_height} for revision C")

        # Detect ROM version
        try:
            self.rom_version = int(response.split(".")[2])
            if self.rom_version < 80 or self.rom_version > 100:
                logger.warning("ROM version %d may be invalid, use default ROM version 87" % self.rom_version)
                self.rom_version = 87
        except:
            logger.warning("Display returned invalid or unsupported ID, use default ROM version 87")
            self.rom_version = 87

        logger.debug("HW sub-revision detected: %s, ROM version: %d" % ((str(self.sub_revision)), self.rom_version))

    def InitializeComm(self):
        self._hello()

    def Reset(self):
        logger.info("Display reset (COM port may change)...")
        # Reset command bypasses queue because it is run when queue threads are not yet started
        self._send_command(Command.RESTART, bypass_queue=True)
        self.closeSerial()
        # Wait for disconnection (max. 15 seconds)
        for i in range(15):
            if LcdCommRevC._get_awake_com_port(comports()) is not None:
                time.sleep(1)
        # Wait for reconnection (max. 15 seconds)
        for i in range(15):
            if LcdCommRevC._get_awake_com_port(comports()) is None:
                time.sleep(1)
        # Reconnect to device
        self.openSerial()

    def Clear(self):
        # This hardware does not implement a Clear command: display a blank image on the whole screen
        # Force an orientation in case the screen is currently configured with one different from the theme
        backup_orientation = self.orientation
        self.SetOrientation(orientation=Orientation.PORTRAIT)

        blank = Image.new("RGB", (self.get_width(), self.get_height()), (255, 255, 255))
        self.DisplayPILImage(blank)

        # Restore orientation
        self.SetOrientation(orientation=backup_orientation)

    def ScreenOff(self):
        # logger.info("Calling ScreenOff")
        self._send_command(Command.STOP_VIDEO)
        self._send_command(Command.STOP_MEDIA, readsize=1024)
        self._send_command(Command.TURNOFF)

    def ScreenOn(self):
        # logger.info("Calling ScreenOn")
        self._send_command(Command.STOP_VIDEO)
        self._send_command(Command.STOP_MEDIA, readsize=1024)
        # self._send_command(Command.SET_BRIGHTNESS, payload=bytearray([255]))

    def SetBrightness(self, level: int = 25):
        # logger.info("Call SetBrightness")
        assert 0 <= level <= 100, 'Brightness level must be [0-100]'

        # Brightness scales from 0 to 255, with 255 being the brightest and 0 being the darkest.
        # Convert our brightness % to an absolute value.
        converted_level = int((level / 100) * 255)

        self._send_command(Command.SET_BRIGHTNESS, payload=bytearray((converted_level,)), bypass_queue=True)

    def SetOrientation(self, orientation: Orientation = Orientation.PORTRAIT):
        self.orientation = orientation
        # logger.info(f"Call SetOrientation to: {self.orientation.name}")

        # if self.orientation == Orientation.REVERSE_LANDSCAPE or self.orientation == Orientation.REVERSE_PORTRAIT:
        #   b = Command.STARTMODE_DEFAULT.value + Padding.NULL.value + Command.FLIP_180.value + SleepInterval.OFF.value
        #   self._send_command(Command.OPTIONS, payload=b)
        # else:
        b = Command.STARTMODE_DEFAULT.value + Padding.NULL.value + Command.NO_FLIP.value + SleepInterval.OFF.value
        self._send_command(Command.OPTIONS, payload=b)

    def DisplayPILImage(
            self,
            image: Image.Image,
            x: int = 0, y: int = 0,
            image_width: int = 0,
            image_height: int = 0
    ):
        # If the image height/width isn't provided, use the native image size
        if not image_height:
            image_height = image.size[1]
        if not image_width:
            image_width = image.size[0]

        # If our image is bigger than our display, resize it to fit our screen
        if image.size[1] > self.get_height():
            image_height = self.get_height()
        if image.size[0] > self.get_width():
            image_width = self.get_width()

        if image_width != image.size[0] or image_height != image.size[1]:
            image = image.crop((0, 0, image_width, image_height))

        assert x <= self.get_width(), 'Image X coordinate must be <= display width'
        assert y <= self.get_height(), 'Image Y coordinate must be <= display height'
        assert image_height > 0, 'Image height must be > 0'
        assert image_width > 0, 'Image width must be > 0'

        if x == 0 and y == 0 and (image_width == self.get_width()) and (image_height == self.get_height()):
            with self.update_queue_mutex:
                self._send_command(Command.PRE_UPDATE_BITMAP)
                self._send_command(Command.START_DISPLAY_BITMAP, padding=Padding.START_DISPLAY_BITMAP)

                if self.sub_revision == SubRevision.REV_5INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_5INCH
                elif self.sub_revision == SubRevision.REV_2INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_2INCH
                elif self.sub_revision == SubRevision.REV_8INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_8INCH

                self._send_command(display_bmp_cmd,
                                   payload=bytearray(
                                       int(self.display_width * self.display_width / 64).to_bytes(2, "big")))
                self._send_command(Command.SEND_PAYLOAD,
                                   payload=bytearray(self._generate_full_image(image)),
                                   readsize=1024)
                self._send_command(Command.QUERY_STATUS, readsize=1024)
        else:
            with self.update_queue_mutex:
                img, pyd = self._generate_update_image(image, x, y, Count.Start, Command.UPDATE_BITMAP)
                self._send_command(Command.SEND_PAYLOAD, payload=pyd)
                self._send_command(Command.SEND_PAYLOAD, payload=img)
                self._send_command(Command.QUERY_STATUS, readsize=1024)
            Count.Start += 1

    def _generate_full_image(self, image: Image.Image) -> bytes:
        if self.sub_revision == SubRevision.REV_8INCH:
            # Switch landscape/portrait mode for 8"
            if self.orientation == Orientation.LANDSCAPE:
                image = image.rotate(270, expand=True)
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(90, expand=True)
            elif self.orientation == Orientation.PORTRAIT:
                image = image.rotate(180, expand=True)
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                pass
        else:
            if self.orientation == Orientation.PORTRAIT:
                image = image.rotate(90, expand=True)
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                image = image.rotate(270, expand=True)
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(180)

        bgra_data, pixel_size = image_to_BGRA(image)

        return b'\x00'.join(chunked(bgra_data, 249))

    def _generate_update_image(
            self, image: Image.Image, x: int, y: int, count: int, cmd: Optional[Command] = None
    ) -> Tuple[bytearray, bytearray]:
        x0, y0 = x, y
        if self.sub_revision == SubRevision.REV_8INCH:
            # Switch landscape/portrait mode for 8"
            if self.orientation == Orientation.LANDSCAPE:
                image = image.rotate(270, expand=True)
                y0 = self.get_height() - y - image.width
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(90, expand=True)
                x0 = self.get_width() - x - image.height
            elif self.orientation == Orientation.PORTRAIT:
                image = image.rotate(180, expand=True)
                x0 = self.get_height() - y - image.height
                y0 = self.get_height() - x - image.width
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                x0 = y
                y0 = x
        else:
            if self.orientation == Orientation.PORTRAIT:
                image = image.rotate(90, expand=True)
                x0 = self.get_width() - x - image.height
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                image = image.rotate(270, expand=True)
                y0 = self.get_height() - y - image.width
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(180)
                y0 = self.get_width() - x - image.width
                x0 = self.get_height() - y - image.height
            elif self.orientation == Orientation.LANDSCAPE:
                x0 = y
                y0 = x

        img_raw_data = bytearray()

        # Some screens require different RGBA encoding
        if self.sub_revision != SubRevision.REV_2INCH and self.rom_version > 88:
            # BGRA mode on 4 bytes : [B, G, R, A]
            img_data, pixel_size = image_to_BGRA(image)
        else:
            # BGRA mode on 3 bytes: [6-bit B + 2-bit A, 6-bit G + 2-bit A, 8-bit R]
            # img_data, pixel_size = image_to_compressed_BGRA(image)
            # For now use simple BGR that is more optimized, because this program does not support transparent background
            img_data, pixel_size = image_to_BGR(image)

        for h, line in enumerate(chunked(img_data, image.width * pixel_size)):
            if self.sub_revision == SubRevision.REV_8INCH:
                # Switch landscape/portrait mode for 8"
                img_raw_data += int(((x0 + h) * self.display_width) + y0).to_bytes(3, "big")
            else:
                img_raw_data += int(((x0 + h) * self.display_height) + y0).to_bytes(3, "big")
            img_raw_data += int(image.width).to_bytes(2, "big")
            img_raw_data += line

        image_size = int(len(img_raw_data) + 2).to_bytes(3, "big")  # The +2 is for the "ef69" that will be added later.

        # logger.debug("Render Count: {}".format(count))
        payload = bytearray()

        if cmd:
            payload.extend(cmd.value)
        payload.extend(image_size)
        payload.extend(Padding.NULL.value * 3)
        payload.extend(count.to_bytes(4, 'big'))

        if len(img_raw_data) > 250:
            img_raw_data = bytearray(b'\x00').join(chunked(bytes(img_raw_data), 249))
        img_raw_data += b'\xef\x69'

        return img_raw_data, payload

   # ===== FILE MANAGEMENT METHODS =====

    def ListFiles(self, dir_path: str) -> Tuple[List[str], List[str]]:
        """List files and directories in the display's storage at specified path.
        
        Args:
            dir_path: Path to directory (e.g., "/root/video/", "/mnt/SDCARD/img/")
            
        Returns:
            Tuple of (list of subdirectories, list of files)
        """
        pyd = bytearray()
        pyd.extend(len(dir_path).to_bytes(1))
        pyd.extend(Padding.NULL.value * 3)
        pyd.extend(map(ord, dir_path))

        self._send_command(Command.LIST_FILES, payload=pyd, bypass_queue=True)
        # Read the reply (10240 bytes)
        reply = self.ReadData(10240)

        reply = reply.strip(bytearray((0x0,)))
        reply = reply.decode('ascii')

        # Reply format: result:dir:A/B/C/file:D/E/F/
        # Extract the list of subdirectories and the list of files from the reply.

        directories_match = re.findall('dir:(.*)file', reply)
        directories = []
        if len(directories_match) > 0:
            directories = directories_match[0].split('/')
            directories.remove('')

        files_match = re.findall('file:(.*)', reply)
        files = []
        if len(files_match) > 0:
            files = files_match[0].split('/')
            files.remove('')

        # Return the list of subdirectories and the list of files.
        return directories, files

    def ListImagesInternalStorage(self) -> Tuple[List[str], List[str]]:
        """List images in internal storage."""
        return self.ListFiles("/root/img/")

    def ListVideosInternalStorage(self) -> Tuple[List[str], List[str]]:
        """List videos in internal storage."""
        return self.ListFiles("/root/video/")

    def ListImagesSDStorage(self) -> Tuple[List[str], List[str]]:
        """List images in SD card storage."""
        return self.ListFiles("/mnt/SDCARD/img/")

    def ListVideosSDStorage(self) -> Tuple[List[str], List[str]]:
        """List videos in SD card storage."""
        return self.ListFiles("/mnt/SDCARD/video/")

    def _read_in_chunks(self, file_object, chunk_size=249):
        """Generator to read file in chunks."""
        while True:
            data = file_object.read(chunk_size)
            if not data:
                break
            yield data

    def UploadFile(self, local_path: str, destination_path: str):
        """Upload a file to the display's storage.
        
        Args:
            local_path: Local path to file on computer
            destination_path: Destination path on display (e.g., "/root/video/myvideo.mp4")
        """
        pyd = bytearray()
        pyd.extend(len(destination_path).to_bytes(1))
        pyd.extend(Padding.NULL.value * 3)
        pyd.extend(map(ord, destination_path))

        file_size_bytes = os.path.getsize(local_path)
        pyd.extend(struct.pack('<i', file_size_bytes))
        self._send_command(Command.UPLOAD_FILE, payload=pyd)

        # Upload file (raw data).
        with open(local_path, "rb") as file:
            for packet in self._read_in_chunks(file):
                self._send_command(Command.SEND_PAYLOAD, payload=packet)

        # Wait for the file creation on the SD card and flush serial port.
        time.sleep(1)
        reply = self.serial_readall()

    def DeleteFile(self, file_path: str):
        """Delete a file from the display's storage.
        
        Args:
            file_path: Path to file on display (e.g., "/root/video/myvideo.mp4")
        """
        pyd = bytearray()
        pyd.extend(len(file_path).to_bytes(1))
        pyd.extend(Padding.NULL.value * 3)
        pyd.extend(map(ord, file_path))
        self._send_command(Command.DELETE_FILE, payload=pyd)

    def GetFileSize(self, file_path: str) -> int:
        """Get size of a file on the display's storage.
        
        Args:
            file_path: Path to file on display
            
        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        pyd = bytearray()
        pyd.extend(len(file_path).to_bytes(1))
        pyd.extend(Padding.NULL.value * 3)
        pyd.extend(map(ord, file_path))
        self._send_command(Command.GET_FILE_SIZE, payload=pyd, bypass_queue=True)
        reply = self.ReadData(1024)
        reply = reply.strip(bytearray((0x0,)))
        file_size = int(reply.decode('ascii'))
        return file_size

    # ===== VIDEO PLAYBACK METHODS =====

    def StartVideo(self, video_path: str):
        """Start playing a video file on the display.
        
        Args:
            video_path: Path to video on display (e.g., "/root/video/myvideo.mp4")
        """
        # Check if the video is present.
        video_size = self.GetFileSize(video_path)

        if video_size == 0:
            logger.warning(f"Video \"{video_path}\" not found!")
        else:
            pyd = bytearray()
            pyd.extend(len(video_path).to_bytes(1))
            pyd.extend(Padding.NULL.value * 3)
            pyd.extend(map(ord, video_path))

            # Start video.
            logger.info(f"Playing video \"{video_path}\"")
            self._send_command(Command.START_VIDEO, payload=pyd, readsize=1024)

    def StopVideo(self):
        """Stop the currently playing video."""
        self._send_command(Command.STOP_VIDEO)

    # ===== VIDEO OVERLAY METHODS =====

    def InitializeVideoOverlay(self):
        """Initialize the video overlay system. Must be called before drawing anything on the video."""
        self._send_command(Command.PRE_UPDATE_BITMAP)
        self._send_command(Command.START_DISPLAY_BITMAP, padding=Padding.START_DISPLAY_BITMAP)
        self._send_command(Command.DISPLAY_BITMAP_ON_VIDEO)

        self.video_overlay = Image.new("RGBA", (self.get_width(), self.get_height()), (255, 255, 255, 0))
        self.previous_video_overlay = self.video_overlay.copy()

        # Generate full image for initial overlay
        rgb565be = self._generate_full_image(self.video_overlay)
        self._send_command(Command.SEND_PAYLOAD, payload=bytearray(rgb565be))

        # Init visible pixels: no visible pixels.
        visible_pixels = bytearray((0xef, 0x69))

        packet_size = len(visible_pixels).to_bytes(1)
        self._send_command(Command.INIT_VIDEO_OVERLAY, payload=packet_size)
        self._send_command(Command.SEND_PAYLOAD, visible_pixels)
        time.sleep(1)
        self.serial_readall()
        self._send_command(Command.QUERY_STATUS, readsize=1024)

    def _generate_full_image(self, image: Image.Image) -> bytes:
        """Generate full image data for display (used for overlay initialization)."""
        if self.sub_revision == SubRevision.REV_8INCH:
            # Switch landscape/portrait mode for 8"
            if self.orientation == Orientation.LANDSCAPE:
                image = image.rotate(270, expand=True)
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(90, expand=True)
            elif self.orientation == Orientation.PORTRAIT:
                image = image.rotate(180, expand=True)
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                pass
        else:
            if self.orientation == Orientation.PORTRAIT:
                image = image.rotate(90, expand=True)
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                image = image.rotate(270, expand=True)
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(180)

        image_data = image.convert("RGBA").load()
        image_ret = ''
        for y in range(image.height):
            for x in range(image.width):
                pixel = image_data[x, y]
                image_ret += f'{pixel[2]:02x}{pixel[1]:02x}{pixel[0]:02x}{pixel[3]:02x}'

        hex_data = bytearray.fromhex(image_ret)
        return b'\x00'.join(hex_data[i:i + 249] for i in range(0, len(hex_data), 249))

    def _get_diff_image(self) -> Image.Image:
        """Calculate the update image (returns image with only the updated pixels)."""
        update_array = np.zeros((self.get_height(), self.get_width(), 4), dtype=np.uint8)
        previous_video_overlay_array = np.asarray(self.previous_video_overlay)
        video_overlay_array = np.asarray(self.video_overlay)

        # Numpy to speed up the calculation.
        # For each pixel, compare video overlay with previous video overlay and return
        # an image with only the modified pixels.
        diff_array = np.any(previous_video_overlay_array != video_overlay_array, axis=-1)
        update_array[diff_array] = video_overlay_array[diff_array]

        update_image = Image.fromarray(update_array.astype('uint8'), 'RGBA')
        return update_image

    @staticmethod
    @jit(nopython=True, cache=True)
    def _get_visible_segments_numba(image_data: np.ndarray, y: int = 0, image_width: int = 800):
        """Get visible (non-transparent) pixel segments from an image at a given line.
        
        Optimized with numba JIT compilation for performance.
        
        Args:
            image_data: numpy array of image data
            y: line number
            image_width: width of image
            
        Returns:
            List of [start_x, width] segments
        """
        visible_segments = []

        i = 0
        j = 0
        while i < image_width:
            # First non transparent pixel.
            if image_data[y, i][3] > 0:
                # visible segment = position and length.
                visible_segment = [i, 1]
                j = i + 1
                while j < image_width and (image_data[y, j][3] > 0 or (j + 1 < image_width and image_data[y, j + 1][3] > 0)):
                    visible_segment[1] = visible_segment[1] + 1
                    j = j + 1
                i = j
                visible_segments.append(visible_segment)

            i = i + 1

        return visible_segments

    def RefreshVideoOverlay(self):
        """Refresh the video overlay by sending only changed pixels to the display.
        
        This method uses numba-optimized diff calculation to efficiently update
        only the pixels that have changed since the last refresh.
        """
        update_image = self._get_diff_image()
        video_overlay_data = self.video_overlay.load()

        update_image_array = np.asarray(update_image)
        video_overlay_array = np.asarray(self.video_overlay)

        # Build image payload.
        img_raw_data = []
        visible_pixels = []

        for h in range(self.video_overlay.height):
            # Get the updated pixels segments for each screen line (so only the updated pixels are sent).
            updated_pixels_segments = LcdCommRevC._get_visible_segments_numba(update_image_array, h, self.get_width())

            # Get the visible segments for each screen line.
            visible_segments = LcdCommRevC._get_visible_segments_numba(video_overlay_array, h, self.get_width())

            # Send only updated pixels.
            for segment in updated_pixels_segments:
                x = segment[0] 
                segment_width = segment[1]
                img_raw_data.append(f'{(h * self.display_height + x):06x}{segment_width:04x}')

                # Color.
                for w in range(segment_width):
                    red, green, blue, alpha = video_overlay_data[x + w, h]
                    alpha_byte = int(alpha / 255 * 15)
                    # color format (binary):  b4 b3 b2 b1 0 0 a4 a3 | g4 g3 g2 g1 0 0 a2 a1 | r4 r3 r2 r1 0 0 0 0
                    img_raw_data.append(f'{int(blue / 255 * 15) << 4 | ((alpha_byte & 0xc) >> 2):02x}{int(green / 255 * 15) << 4 | alpha_byte & 0x3:02x}{int(red / 255 * 15) << 4:02x}')

            # All visible pixels.
            for segment in visible_segments:
                x = segment[0]
                segment_width = segment[1]

                # Set each segment as visible for the screen.
                visible_pixels.append(f'{(h * self.display_height + x):06x}{segment_width:04x}')

        image_msg = ''.join(img_raw_data)
        image_msg = image_msg + ''.join(visible_pixels)

        visible_pixels_msg = ''.join(visible_pixels)
        visible_pixels_size = int(len(visible_pixels_msg) / 2)

        if len(image_msg) > 500:
            image_msg_temp = '00'.join(image_msg[i:i + 498] for i in range(0, len(image_msg), 498))
        else:
            image_msg_temp = image_msg

        img_payload = bytearray.fromhex(image_msg_temp)

        # Fix image payload: last 250 bytes packet must not end with 0xef 0x69.
        #                and last 250 bytes packet must not be "0x69 0x0000..." nor "0xef 0x69 0x0000..."
        if len(img_payload) > 250 and (len(img_payload) % 250 == 0 or len(img_payload) % 250 == 248 or len(img_payload) % 250 == 249):
            # Add a dummy "visible pixel" field to fix image payload format.
            img_payload.extend(bytearray((0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0xef, 0x69)))
            image_size = f'{int((len(image_msg) / 2) + 7):06x}'
            visible_pixels_size = visible_pixels_size + 5
        else:
            img_payload.extend(bytearray((0xef, 0x69)))
            image_size = f'{int((len(image_msg) / 2) + 2):06x}'

        # Build update image command.
        update_image_payload = bytearray()
        update_image_payload.extend(Command.UPDATE_BITMAP.value)
        update_image_payload.extend(bytearray.fromhex(image_size))
        update_image_payload.extend(Padding.NULL.value * 3)
        update_image_payload.extend(Count.Start.to_bytes(4, 'big'))
        update_image_payload.extend(visible_pixels_size.to_bytes(4, 'big'))

        # Increment message ID counter.
        Count.Start = Count.Start + 1
        self.previous_video_overlay = self.video_overlay.copy()

        self._send_command(Command.SEND_PAYLOAD, payload=update_image_payload)
        self._send_command(Command.SEND_PAYLOAD, payload=img_payload)

    def DrawPILImageOnVideo(self, image: Image.Image, x: int = 0, y: int = 0):
        """Draw a PIL image on the video overlay at specified position.
        
        Args:
            image: PIL Image to draw (should have RGBA mode for transparency)
            x: X position
            y: Y position
        """
        # Paste image to draw on the video overlay image.
        self.video_overlay.paste(image, (x, y), image if image.mode == 'RGBA' else None)

    def DrawTextOnVideo(self, text: str, x: int = 0, y: int = 0,
                        font: str = "./res/fonts/roboto-mono/RobotoMono-Regular.ttf", 
                        font_size: int = 20, 
                        font_color: Tuple[int, int, int] = (255, 255, 255),
                        background_color: Optional[Tuple[int, int, int, int]] = None,
                        align: str = 'left',
                        anchor: str = None):
        """Draw text on the video overlay.
        
        Args:
            text: Text to display
            x, y: Position
            font: Font file path (relative to res/fonts/)
            font_size: Font size in pixels
            font_color: RGB tuple for text color
            background_color: Optional RGBA tuple for background (None for transparent)
            align: Text alignment ('left', 'center', 'right')
            anchor: Anchor point for text positioning
        """
        # Create transparent background for text
        max_width = self.get_width() - x
        max_height = self.get_height() - y
        
        if background_color is None:
            text_image = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 0))
        else:
            text_image = Image.new('RGBA', (max_width, max_height), background_color)
        
        # Get font and draw text
        ttfont = self.open_font(font, font_size)
        draw = ImageDraw.Draw(text_image)
        
        # Get text bounding box
        left, top, right, bottom = draw.textbbox((0, 0), text, font=ttfont, align=align, anchor=anchor)
        
        # Draw text
        draw.text((0, 0), text, font=ttfont, fill=font_color, align=align, anchor=anchor)
        
        # Crop to text size
        text_image = text_image.crop((left, top, right, bottom))
        
        # Paste text image on the video overlay image.
        self.video_overlay.paste(text_image, (x + left, y + top), text_image)

    def DrawProgressBarOnVideo(self, x: int, y: int, width: int, height: int, 
                                min_value: int = 0, max_value: int = 100,
                                value: int = 50,
                                bar_color: Tuple[int, int, int] = (0, 255, 0),
                                bar_outline: bool = True,
                                background_color: Optional[Tuple[int, int, int, int]] = None):
        """Draw a progress bar on the video overlay.
        
        Args:
            x, y: Position
            width, height: Dimensions
            min_value, max_value: Value range
            value: Current value
            bar_color: RGB tuple for bar color
            bar_outline: Whether to draw outline
            background_color: Optional RGBA tuple for background (None for transparent)
        """
        # Create progress bar image
        if background_color is None:
            bar_image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        else:
            bar_image = Image.new('RGBA', (width, height), background_color)
        
        # Draw progress bar
        bar_filled_width = (value / (max_value - min_value) * width) - 1
        if bar_filled_width < 0:
            bar_filled_width = 0
        
        draw = ImageDraw.Draw(bar_image)
        draw.rectangle([0, 0, bar_filled_width, height - 1], fill=bar_color, outline=bar_color)
        
        if bar_outline:
            # Draw outline
            draw.rectangle([0, 0, width - 1, height - 1], fill=None, outline=bar_color)
        
        self.video_overlay.paste(bar_image, (x, y), bar_image)

    def DrawRadialProgressBarOnVideo(self, xc: int, yc: int, radius: int, bar_width: int,
                                     min_value: int = 0,
                                     max_value: int = 100,
                                     angle_start: int = 0,
                                     angle_end: int = 360,
                                     angle_sep: int = 5,
                                     angle_steps: int = 10,
                                     clockwise: bool = True,
                                     value: int = 50,
                                     text: Optional[str] = None,
                                     with_text: bool = True,
                                     font: str = "./res/fonts/roboto/Roboto-Black.ttf",
                                     font_size: int = 20,
                                     font_color: Tuple[int, int, int] = (255, 255, 255),
                                     bar_color: Tuple[int, int, int] = (0, 255, 0),
                                     background_color: Optional[Tuple[int, int, int, int]] = None):
        """Draw a radial (circular) progress bar on the video overlay.
        
        Args:
            xc, yc: Center position
            radius: Radius of the progress bar
            bar_width: Width of the progress bar line
            min_value, max_value: Value range
            angle_start, angle_end: Start and end angles (0 = 3 o'clock, clockwise)
            angle_sep: Separation between segments  
            angle_steps: Number of steps/segments
            clockwise: Direction of progress
            value: Current value
            text: Optional text to display in center (None = percentage)
            with_text: Whether to display text
            font, font_size, font_color: Text appearance
            bar_color: RGB tuple for bar color
            background_color: Optional RGBA tuple for background (None for transparent)
        """
        # Generate a radial progress bar using parent class method
        from library.lcd.color import parse_color
        bar_image = self.DrawRadialProgressBar(
            xc, yc, radius, bar_width, min_value, max_value, angle_start, angle_end,
            angle_sep, angle_steps, clockwise, value, text, with_text, font, font_size,
            parse_color(font_color), parse_color(bar_color), (255, 255, 255, 0) if background_color is None else parse_color(background_color), None
        )
        
        # Convert to RGBA if needed
        if bar_image.mode != 'RGBA':
            bar_image = bar_image.convert('RGBA')
        
        self.video_overlay.paste(bar_image, (xc - radius, yc - radius), bar_image)

