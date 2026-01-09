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

import os

from PIL import Image

from library import config
from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a import LcdCommRevA
from library.lcd.lcd_comm_rev_b import LcdCommRevB
from library.lcd.lcd_comm_rev_c import LcdCommRevC
from library.lcd.lcd_comm_rev_d import LcdCommRevD
from library.lcd.lcd_comm_weact_a import LcdCommWeActA
from library.lcd.lcd_comm_weact_b import LcdCommWeActB
from library.lcd.lcd_simulated import LcdSimulated
from library.log import logger


def _get_full_path(path, name):
    if name:
        return path + name
    else:
        return None


def _get_theme_orientation() -> Orientation:
    if config.THEME_DATA["display"]["DISPLAY_ORIENTATION"] == 'portrait':
        if config.CONFIG_DATA["display"].get("DISPLAY_REVERSE", False):
            return Orientation.REVERSE_PORTRAIT
        else:
            return Orientation.PORTRAIT
    elif config.THEME_DATA["display"]["DISPLAY_ORIENTATION"] == 'landscape':
        if config.CONFIG_DATA["display"].get("DISPLAY_REVERSE", False):
            return Orientation.REVERSE_LANDSCAPE
        else:
            return Orientation.LANDSCAPE
    else:
        logger.warning("Orientation '", config.THEME_DATA["display"]["DISPLAY_ORIENTATION"],
                       "' unknown, using portrait")
        return Orientation.PORTRAIT


def _get_theme_size() -> tuple[int, int]:
    if config.THEME_DATA["display"].get("DISPLAY_SIZE", '') == '0.96"':
        return 80, 160
    if config.THEME_DATA["display"].get("DISPLAY_SIZE", '') == '2.1"':
        return 480, 480
    elif config.THEME_DATA["display"].get("DISPLAY_SIZE", '') == '3.5"':
        return 320, 480
    elif config.THEME_DATA["display"].get("DISPLAY_SIZE", '') == '5"':
        return 480, 800
    elif config.THEME_DATA["display"].get("DISPLAY_SIZE", '') == '8.8"':
        return 480, 1920
    else:
        logger.warning(
            f'Cannot find valid DISPLAY_SIZE property in selected theme {config.CONFIG_DATA["config"]["THEME"]}, defaulting to 3.5"')
        return 320, 480


class Display:
    def __init__(self):
        self.lcd = None
        width, height = _get_theme_size()
        if config.CONFIG_DATA["display"]["REVISION"] == "A":
            self.lcd = LcdCommRevA(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue)
        elif config.CONFIG_DATA["display"]["REVISION"] == "B":
            self.lcd = LcdCommRevB(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue)
        elif config.CONFIG_DATA["display"]["REVISION"] == "C":
            # Because of issue with Turing rev. C size auto-detection, manually configure screen width/height from theme
            self.lcd = LcdCommRevC(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue, display_width=width, display_height=height)
        elif config.CONFIG_DATA["display"]["REVISION"] == "D":
            self.lcd = LcdCommRevD(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue)
        elif config.CONFIG_DATA["display"]["REVISION"] == "WEACT_A":
            self.lcd = LcdCommWeActA(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue)
        elif config.CONFIG_DATA["display"]["REVISION"] == "WEACT_B":
            self.lcd = LcdCommWeActB(com_port=config.CONFIG_DATA['config']['COM_PORT'],
                                   update_queue=config.update_queue)
        elif config.CONFIG_DATA["display"]["REVISION"] == "SIMU":
            # Simulated display: always set width/height from theme
            self.lcd = LcdSimulated(display_width=width, display_height=height)
        else:
            logger.error("Unknown display revision '", config.CONFIG_DATA["display"]["REVISION"], "'")

    def initialize_display(self):
        # Reset screen in case it was in an unstable state (screen is also cleared)
        # Can be disabled by config. option. Assume true if key not present in config.yaml
        if config.CONFIG_DATA["display"].get("RESET_ON_STARTUP", True):
            self.lcd.Reset()
        else:
            logger.debug("RESET_ON_STARTUP is false: display will not be reset")

        # Send initialization commands
        self.lcd.InitializeComm()

        # Turn on display, set brightness and LEDs for supported HW
        self.turn_on()

        # Set orientation
        self.lcd.SetOrientation(_get_theme_orientation())

    def turn_on(self):
        # Turn screen on in case it was turned off previously
        self.lcd.ScreenOn()

        # Set brightness
        self.lcd.SetBrightness(config.CONFIG_DATA["display"]["BRIGHTNESS"])

        # Set backplate RGB LED color (for supported HW only)
        self.lcd.SetBackplateLedColor(config.THEME_DATA['display'].get("DISPLAY_RGB_LED", (255, 255, 255)))

    def turn_off(self):
        # Turn screen off
        self.lcd.ScreenOff()

        # Turn off backplate RGB LED
        self.lcd.SetBackplateLedColor(led_color=(0, 0, 0))

    def display_video_background(self):
        """Start video background playback if enabled in theme (Revision C / 5\" displays only)."""
        if not config.THEME_DATA.get('video_background', {}).get('ENABLE', False):
            return False  # Video background not enabled
        
        # Check if this is a simulated display (for theme editor preview)
        from library.lcd.lcd_simulated import LcdSimulated
        from library.lcd.lcd_comm_rev_c import LcdCommRevC
        
        is_simulated = isinstance(self.lcd, LcdSimulated)
        is_rev_c = isinstance(self.lcd, LcdCommRevC)
        
        if not is_simulated and not is_rev_c:
            logger.warning("Video backgrounds are only supported on Revision C (5\") displays. Falling back to static image background.")
            return False
        
        # For simulated displays, use local video file for preview
        if is_simulated:
            local_path = config.THEME_DATA['video_background'].get('LOCAL_PATH')
            if not local_path:
                logger.error("VIDEO BACKGROUND: LOCAL_PATH not specified for simulated preview")
                return False
            
            
            try:
                # Get full path to local video
                # LOCAL_PATH is relative to project root, not theme directory
                if os.path.isabs(local_path):
                    full_local_path = local_path
                else:
                    # Combine with project root directory
                    full_local_path = str(config.MAIN_DIRECTORY / local_path)
                
                print(f"DEBUG: Resolved video path: {full_local_path}")  # Debug print
                
                if not os.path.exists(full_local_path):
                    logger.error(f"Video file not found: {full_local_path}")
                    return False
                
                # For theme editor preview, open video for continuous playback
                try:
                    import cv2
                    logger.info(f"Loading video for preview: {full_local_path}")
                    print(f"DEBUG: Loading video from: {full_local_path}")  # Debug print
                    
                    # Open video file and store in display object for continuous playback
                    video = cv2.VideoCapture(full_local_path)
                    if not video.isOpened():
                        logger.error(f"Could not open video file: {full_local_path}")
                        print(f"DEBUG: Failed to open video!")  # Debug print
                        return False
                    
                    # Get video properties
                    fps = video.get(cv2.CAP_PROP_FPS)
                    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # Read first frame for initial display
                    ret, frame = video.read()
                    
                    if not ret:
                        logger.error("Could not read frame from video")
                        print(f"DEBUG: Could not read frame!")  # Debug print
                        video.release()
                        return False
                    
                    print(f"DEBUG: Video loaded - {frame_count} frames at {fps} FPS, shape: {frame.shape}")  # Debug print
                    
                    # Convert BGR (OpenCV) to RGB (PIL)
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    video_image = Image.fromarray(frame_rgb)
                    
                    # Resize to display dimensions if needed
                    if video_image.size != (self.lcd.get_width(), self.lcd.get_height()):
                        video_image = video_image.resize((self.lcd.get_width(), self.lcd.get_height()), Image.Resampling.LANCZOS)
                    
                    print(f"DEBUG: About to display video image at 0,0 size={video_image.size}")  # Debug print
                    
                    # Display first frame as background
                    self.lcd.DisplayPILImage(video_image, 0, 0)
                    
                    # Store video capture object for continuous playback
                    self.lcd.video_capture = video
                    self.lcd.video_fps = fps
                    self.lcd.video_frame_index = 1  # We already read frame 0
                    self.lcd.video_frame_count = frame_count
                    self.lcd.video_playing = True
                    
                    logger.info(f"Video background preview loaded - {frame_count} frames at {fps:.1f} FPS")
                    print(f"DEBUG: Video background loaded successfully!")  # Debug print
                    return True
                    
                except ImportError:
                    logger.warning("opencv-python (cv2) not installed - cannot preview video. Install with: pip install opencv-python")
                    logger.warning("Falling back to static background")
                    return False
                except Exception as e:
                    logger.error(f"Error loading video for preview: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error in simulated video background: {e}")
                return False
        
        # For real Revision C displays, use normal video playback
        remote_path = config.THEME_DATA['video_background'].get('REMOTE_PATH')
        if not remote_path:
            logger.error("VIDEO BACKGROUND: REMOTE_PATH not specified in theme")
            return False
        
        # Check if video exists on display, upload if needed
        try:
            # Extract filename from remote path
            filename = os.path.basename(remote_path)
            
            # Define preferred storage locations (SD card first, then internal)
            storage_locations = [
                f"/mnt/SDCARD/video/{filename}",  # SD card (preferred)
                f"/root/video/{filename}"          # Internal storage (fallback)
            ]
            
            # Try to find video in preferred locations
            found_path = None
            for path in storage_locations:
                video_size = self.lcd.GetFileSize(path)
                if video_size > 0:
                    found_path = path
                    logger.debug(f"Found existing video at {path} ({video_size} bytes)")
                    break
            
            # If video not found anywhere, upload to SD card (or user-specified location)
            if not found_path:
                local_path = config.THEME_DATA['video_background'].get('LOCAL_PATH')
                if not local_path:
                    logger.error(f"Video {filename} not found on display and no LOCAL_PATH provided")
                    return False
                
                # Upload to SD card by default (preferred), unless user explicitly specified /root/
                upload_path = storage_locations[0]  # Default: SD card
                if remote_path.startswith("/root/"):
                    upload_path = storage_locations[1]  # User wants internal storage
                
                # Upload from local path
                full_local_path = config.THEME_DATA['PATH'] + local_path if not os.path.isabs(local_path) else local_path
                logger.info(f"Uploading video from {full_local_path} to {upload_path}...")
                
                try:
                    self.lcd.UploadFile(full_local_path, upload_path)
                    logger.info(f"Video upload complete to {upload_path}")
                    found_path = upload_path
                except Exception as upload_error:
                    # If SD card upload fails, try internal storage as fallback
                    if upload_path == storage_locations[0]:
                        logger.warning(f"SD card upload failed ({upload_error}), trying internal storage...")
                        upload_path = storage_locations[1]
                        self.lcd.UploadFile(full_local_path, upload_path)
                        logger.info(f"Video uploaded to internal storage: {upload_path}")
                        found_path = upload_path
                    else:
                        raise  # Re-raise if internal storage also failed
            
            # Start video playback
            logger.info(f"Starting video background: {found_path}")
            self.lcd.StartVideo(found_path)
            
            # Initialize video overlay for UI elements
            logger.debug("Initializing video overlay system")
            self.lcd.InitializeVideoOverlay()
            
            return True  # Video background started successfully
            
        except Exception as e:
            logger.error(f"Error starting video background: {e}")
            return False

    def display_static_images(self):
        # Check if video background is enabled and skip static BACKGROUND if so
        video_enabled = config.THEME_DATA.get('video_background', {}).get('ENABLE', False)
        
        if config.THEME_DATA.get('static_images', False):
            for image in config.THEME_DATA['static_images']:
                # Skip BACKGROUND image if video background is enabled
                if video_enabled and image == 'BACKGROUND':
                    logger.debug("Skipping static BACKGROUND image (video background enabled)")
                    continue
                    
                logger.debug(f"Drawing Image: {image}")
                self.lcd.DisplayBitmap(
                    bitmap_path=config.THEME_DATA['PATH'] + config.THEME_DATA['static_images'][image].get("PATH"),
                    x=config.THEME_DATA['static_images'][image].get("X", 0),
                    y=config.THEME_DATA['static_images'][image].get("Y", 0),
                    width=config.THEME_DATA['static_images'][image].get("WIDTH", 0),
                    height=config.THEME_DATA['static_images'][image].get("HEIGHT", 0)
                )

        # Draw UI Elements (Shapes & Extra Images) using UiRenderer
        # This allows the theme editor to preview them, and the actual display to show them 
        # (if not using video baking, or as a fallback)
        try:
            from library.ui_renderer import UiRenderer
            renderer = UiRenderer(config.THEME_DATA, config.THEME_DATA['PATH'])
            overlay = renderer.generate_overlay()
            
            # Composite overlay onto screen_image
            # screen_image is available in self.lcd for simulated/PIL usage
            if hasattr(self.lcd, 'screen_image'):
                 self.lcd.screen_image.alpha_composite(overlay, (0, 0))
            # specific LCD implementations might handle this differently, but for now 
            # we rely on the fact that most use PIL or we just write to the buffer.
            # However, `DisplayBitmap` writes directly to device for some revisions.
            # If we want to support this generally, we might need a dedicated method in LCD classes.
            # For Theme Editor (which uses LcdSimulated -> screen_image), this alpha_composite works.
            
        except Exception as e:
            logger.error(f"Error rendering UI elements: {e}")

    def display_static_text(self):
        if config.THEME_DATA.get('static_text', False):
            for text in config.THEME_DATA['static_text']:
                logger.debug(f"Drawing Text: {text}")
                self.lcd.DisplayText(
                    text=config.THEME_DATA['static_text'][text].get("TEXT"),
                    x=config.THEME_DATA['static_text'][text].get("X", 0),
                    y=config.THEME_DATA['static_text'][text].get("Y", 0),
                    width=config.THEME_DATA['static_text'][text].get("WIDTH", 0),
                    height=config.THEME_DATA['static_text'][text].get("HEIGHT", 0),
                    font=config.FONTS_DIR + config.THEME_DATA['static_text'][text].get("FONT",
                                                                                       "roboto-mono/RobotoMono-Regular.ttf"),
                    font_size=config.THEME_DATA['static_text'][text].get("FONT_SIZE", 10),
                    font_color=config.THEME_DATA['static_text'][text].get("FONT_COLOR", (0, 0, 0)),
                    background_color=config.THEME_DATA['static_text'][text].get("BACKGROUND_COLOR", (255, 255, 255)),
                    background_image=_get_full_path(config.THEME_DATA['PATH'],
                                                    config.THEME_DATA['static_text'][text].get("BACKGROUND_IMAGE",
                                                                                               None)),
                    align=config.THEME_DATA['static_text'][text].get("ALIGN", "left"),
                    anchor=config.THEME_DATA['static_text'][text].get("ANCHOR", "lt"),
                )


display = Display()
