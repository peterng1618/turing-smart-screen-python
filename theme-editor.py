#!/usr/bin/env python
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

# theme-editor.py: Allow to easily edit themes for System Monitor (main.py) in a preview window on the computer
# The preview window is refreshed as soon as the theme file is modified

from library.pythoncheck import check_python_version
check_python_version()

import locale
import logging
import os
import platform
import subprocess
from pathlib import Path
import sys
import time
import gc
import threading
import queue

ui_queue = queue.Queue()

try:
    import tkinter
    from PIL import ImageTk, Image
except:
    print(
        "[ERROR] Tkinter dependency not installed. Please follow troubleshooting page: https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting#all-os-tkinter-dependency-not-installed")
    try:
        sys.exit(0)
    except:
        os._exit(0)

if len(sys.argv) != 2:
    print("Usage :")
    print("        theme-editor.py theme-name")
    print("Examples : ")
    print("        theme-editor.py 3.5inchTheme2")
    print("        theme-editor.py Landscape6Grid")
    print("        theme-editor.py Cyberpunk")
    try:
        sys.exit(0)
    except:
        os._exit(0)

import library.log

library.log.logger.setLevel(logging.NOTSET)  # Disable system monitor logging for the editor

# Create a logger for the editor
logger = logging.getLogger('turing-editor')
logger.setLevel(logging.DEBUG)

# Hardcode specific configuration for theme editor
from library import config

config.CONFIG_DATA["config"]["HW_SENSORS"] = "STATIC"  # For theme editor always use stub data
config.CONFIG_DATA["config"]["THEME"] = sys.argv[1]  # Theme is given as argument

config.load_theme()

# For theme editor, always use simulated LCD
config.CONFIG_DATA["display"]["REVISION"] = "SIMU"
RULER_SIZE = 25
GUIDE_COLOR = "#00ffff"  # Cyan

from library.display import display  # Only import display after hardcoded config is set

RGB_LED_MARGIN = 12

# Resize editor if display is too big (e.g. 8.8" displays are 1920x480), can be changed later by zoom buttons
RESIZE_FACTOR = 2 if (display.lcd.get_width() > 1000 or display.lcd.get_height() > 1000) else 1

ERROR_IN_THEME = Image.open("res/docs/error-in-theme.png")


def refresh_theme():
    config.load_theme()

    # Initialize the display
    display.initialize_display()

    # Check if video background is enabled
    video_config = config.THEME_DATA.get('video_background', {})
    if video_config.get('ENABLE', False):
        # Extract frame #10 from video for preview
        # Prioritize SOURCE_PATH (raw video) over LOCAL_PATH (possibly baked with UI)
        local_path = video_config.get('SOURCE_PATH') or video_config.get('LOCAL_PATH')
        if local_path:
            try:
                import cv2
                
                # Resolve video path
                # 1. Try relative to theme folder (as saved by video_processor.py)
                video_path = Path(config.THEME_DATA['PATH']) / local_path
                if not video_path.exists():
                    # 2. Try relative to project root
                    video_path = config.MAIN_DIRECTORY / local_path
                
                video_path = str(video_path)
                
                if os.path.exists(video_path):
                    # Open video
                    video = cv2.VideoCapture(video_path)
                    if video.isOpened():
                        # Seek to frame 10 (to avoid black intro frames)
                        video.set(cv2.CAP_PROP_POS_FRAMES, 10)
                        ret, frame = video.read()
                        video.release()
                        
                        if ret:
                            # Convert BGR to RGB
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            video_image = Image.fromarray(frame_rgb)
                            
                            # Resize to display dimensions if needed
                            if video_image.size != (display.lcd.get_width(), display.lcd.get_height()):
                                video_image = video_image.resize((display.lcd.get_width(), display.lcd.get_height()), Image.Resampling.LANCZOS)
                            
                            # Save as background.png in theme folder for BACKGROUND_IMAGE references
                            background_path = config.THEME_DATA['PATH'] + "background.png"
                            
                            # Delete old file to force complete cache invalidation
                            if os.path.exists(background_path):
                                os.remove(background_path)
                                logger.debug(f"Deleted old {background_path}")
                            
                            # Save new video frame
                            video_image.save(background_path)
                            
                            logger.info(f"Saved video frame #10 as {background_path} (will clear cache before rendering)")
                            
                            # Display video frame as background
                            display.lcd.DisplayPILImage(video_image, 0, 0)
                            logger.info(f"Video background preview: showing frame #10 from {os.path.basename(video_path)}")
            except ImportError:
                logger.warning("opencv-python not installed - cannot preview video background. Install with: pip install opencv-python")
            except Exception as e:
                logger.error(f"Error loading video background preview: {e}")
    
    # Clear display module's image cache before rendering to ensure fresh load of background.png
    # The display module caches images in self.image_cache to avoid repeated file I/O
    if hasattr(display.lcd, 'image_cache'):
        display.lcd.image_cache.clear()
        logger.debug(f"Cleared display.lcd.image_cache ({len(display.lcd.image_cache)} items before clear)")
    
    # Also clear PIL's cache as a safety measure
    if hasattr(Image, '_image_cache'):
        Image._image_cache.clear()
    gc.collect()
    logger.debug("Cleared all image caches before rendering")
    
    # Create all static images (if no video, BACKGROUND will be rendered; if video, other images)
    display.display_static_images()

    # Create all static texts
    display.display_static_text()

    # Display all data on screen once
    import library.stats as stats
    if config.THEME_DATA['STATS']['CPU']['PERCENTAGE'].get("INTERVAL", 0) > 0:
        stats.CPU.percentage()
    if config.THEME_DATA['STATS']['CPU']['FREQUENCY'].get("INTERVAL", 0) > 0:
        stats.CPU.frequency()
    if config.THEME_DATA['STATS']['CPU']['LOAD'].get("INTERVAL", 0) > 0:
        stats.CPU.load()
    if config.THEME_DATA['STATS']['CPU']['TEMPERATURE'].get("INTERVAL", 0) > 0:
        stats.CPU.temperature()
    if config.THEME_DATA['STATS']['CPU']['FAN_SPEED'].get("INTERVAL", 0) > 0:
        stats.CPU.fan_speed()
    if config.THEME_DATA['STATS']['GPU'].get("INTERVAL", 0) > 0:
        stats.Gpu.stats()
    if config.THEME_DATA['STATS']['MEMORY'].get("INTERVAL", 0) > 0:
        stats.Memory.stats()
    if config.THEME_DATA['STATS']['DISK'].get("INTERVAL", 0) > 0:
        stats.Disk.stats()
    if config.THEME_DATA['STATS']['NET'].get("INTERVAL", 0) > 0:
        stats.Net.stats()
    if config.THEME_DATA['STATS']['DATE'].get("INTERVAL", 0) > 0:
        stats.Date.stats()
    if config.THEME_DATA['STATS']['UPTIME'].get("INTERVAL", 0) > 0:
        stats.SystemUptime.stats()
    if config.THEME_DATA['STATS']['CUSTOM'].get("INTERVAL", 0) > 0:
        stats.Custom.stats()
    if config.THEME_DATA['STATS']['WEATHER'].get("INTERVAL", 0) > 0:
        stats.Weather.stats()
    if config.THEME_DATA['STATS']['PING'].get("INTERVAL", 0) > 0:
        stats.Ping.stats()


def get_processed_video_path(local_path):
    """Calculate the expected path for a processed video."""
    if not local_path:
        return None
    path = Path(local_path)
    return str(path.parent / f"{path.stem}_processed.mp4")


def check_video_processing_needed():
    """Check if the current video background needs processing."""
    video_config = config.THEME_DATA.get('video_background', {})
    if not video_config.get('ENABLE', False):
        return False, None, None

    local_path = video_config.get('LOCAL_PATH')
    if not local_path:
        return False, None, None

    # Resolve video path
    # 1. Try relative to theme folder
    video_path = Path(config.THEME_DATA['PATH']) / local_path
    if not video_path.exists():
        # 2. Try relative to project root
        video_path = config.MAIN_DIRECTORY / local_path

    if not video_path.exists():
        return False, None, None
    
    video_path = str(video_path)

    # If it's already a processed file, we probably don't need to do anything
    # unless it's missing or some other conditions are met.
    # However, the user logic is: if LOCAL_PATH points to a raw video, we need to process it.
    if "_processed.mp4" in local_path:
        return False, None, None

    processed_path = get_processed_video_path(video_path)
    needed = not os.path.exists(processed_path)
    
    return needed, video_path, processed_path


def run_video_processing(bake_btn):
    """Run the video processor in a separate thread."""
    # Lazy import to avoid requiring av module when not using video features
    try:
        from tools.video_processor import process_video, update_theme_config
    except ImportError as e:
        ui_queue.put(lambda: bake_btn.config(text="💀 PyAV not installed", fg="red"))
        logger.error(f"Video processor unavailable: {e}")
        return
    
    needed, video_path, processed_path = check_video_processing_needed()
    if not video_path:
        video_config = config.THEME_DATA.get('video_background', {})
        local_path = video_config.get('SOURCE_PATH') or video_config.get('LOCAL_PATH')
        if not local_path:
            ui_queue.put(lambda: bake_btn.config(text="💀 No Source Video", fg="red"))
            return
        
        # Resolve video path
        # 1. Try relative to theme folder
        video_path = Path(config.THEME_DATA['PATH']) / local_path
        if not video_path.exists():
            # 2. Try relative to project root
            video_path = config.MAIN_DIRECTORY / local_path
            
        if not video_path.exists():
            ui_queue.put(lambda: bake_btn.config(text="💀 Source Not Found", fg="red"))
            return

        video_path = str(video_path)
        processed_path = get_processed_video_path(video_path)

    def _worker():
        try:
            ui_queue.put(lambda: bake_btn.config(text="🔃 Baking UI Overlay...", fg="blue", state="disabled"))
            
            theme_path = config.THEME_DATA['PATH']
            success = process_video(theme_path, video_path, processed_path)
            
            if success:
                logger.info(f"Video processing complete: {processed_path}")
                ui_queue.put(lambda: bake_btn.config(text="✅ Bake UI Overlay to Video", fg="green"))
            else:
                ui_queue.put(lambda: bake_btn.config(text="💀 Baking Failed", fg="red"))
        except Exception as e:
            logger.error(f"Error in video processing worker: {e}")
            ui_queue.put(lambda: bake_btn.config(text=f"💀 Error: {str(e)[:20]}", fg="red"))
        finally:
            ui_queue.put(lambda: bake_btn.config(state="normal"))

    threading.Thread(target=_worker, daemon=True).start()


def draw_ruler(canvas, orientation, length, factor):
    """Draw a ruler with ticks and numbers on a canvas."""
    canvas.delete("all")
    canvas.config(bg="#606060")
    
    # Draw background line
    if orientation == "horizontal":
        canvas.create_line(0, RULER_SIZE-1, length, RULER_SIZE-1, fill="white")
    else:
        canvas.create_line(RULER_SIZE-1, 0, RULER_SIZE-1, length, fill="white")

    step = 50 / factor
    if step < 10: step = 10
    
    # Ensure step is a multiple of 10 for clean look
    step = (step // 10 + 1) * 10 
    
    for i in range(0, int(length * factor) + 1, 10):
        pos = i / factor
        
        is_major = (i % step == 0)
        is_medium = (i % (step/2) == 0) if step >= 20 else False
        
        tick_len = 5
        if is_major: tick_len = 15
        elif is_medium: tick_len = 10
            
        if orientation == "horizontal":
            canvas.create_line(pos, RULER_SIZE - tick_len, pos, RULER_SIZE, fill="white")
            if is_major:
                canvas.create_text(pos + 2, 2, text=str(i), anchor="nw", font=("Arial", 7), fill="white")
        else:
            canvas.create_line(RULER_SIZE - tick_len, pos, RULER_SIZE, pos, fill="white")
            if is_major:
                # Vertical text
                canvas.create_text(2, pos + 2, text=str(i), anchor="nw", font=("Arial", 7), fill="white")


def save_guides(guides_h, guides_v):
    """Save current guides to theme.yaml."""
    import yaml
    theme_file = config.THEME_DATA['PATH'] + "theme.yaml"
    try:
        with open(theme_file, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        
        content['editor_guides'] = {
            'horizontal': [int(g) for g in guides_h],
            'vertical': [int(g) for g in guides_v]
        }
        
        with open(theme_file, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False)
        logger.debug(f"Saved guides to {theme_file}")
    except Exception as e:
        logger.error(f"Failed to save guides: {e}")


if __name__ == "__main__":
    def on_closing():
        logger.debug("Exit Theme Editor...")
        try:
            sys.exit(0)
        except:
            os._exit(0)


    x0 = 0
    y0 = 0


    def draw_zone(x0, y0, x1, y1):
        x = min(x0, x1)
        y = min(y0, y1)
        width = max(x0, x1) - min(x0, x1)
        height = max(y0, y1) - min(y0, y1)
        if width > 0 and height > 0:
            label_zone.place(x=x + RGB_LED_MARGIN + RULER_SIZE, y=y + RGB_LED_MARGIN + RULER_SIZE, width=width, height=height)
        else:
            label_zone.place_forget()


    def on_button1_press(event):
        global x0, y0
        x0, y0 = event.x, event.y
        label_zone.place_forget()


    def on_button1_press_and_drag(event):
        display_width, display_height = int(display.lcd.get_width() / RESIZE_FACTOR), int(
            display.lcd.get_height() / RESIZE_FACTOR)
        x1, y1 = event.x, event.y

        # Do not draw zone outside of theme preview
        if x1 < 0:
            x1 = 0
        elif x1 >= display_width:
            x1 = display_width - 1
        if y1 < 0:
            y1 = 0
        elif y1 >= display_height:
            y1 = display_height - 1

        label_coord.config(text='Drawing zone from [{:0.0f},{:0.0f}] to [{:0.0f},{:0.0f}]'.format(x0 * RESIZE_FACTOR,
                                                                                                  y0 * RESIZE_FACTOR,
                                                                                                  x1 * RESIZE_FACTOR,
                                                                                                  y1 * RESIZE_FACTOR))
        draw_zone(x0, y0, x1, y1)


    def on_button1_release(event):
        display_width, display_height = int(display.lcd.get_width() / RESIZE_FACTOR), int(
            display.lcd.get_height() / RESIZE_FACTOR)
        x1, y1 = event.x, event.y
        if x1 != x0 or y1 != y0:
            # Do not draw zone outside of theme preview
            if x1 < 0:
                x1 = 0
            elif x1 >= display_width:
                x1 = display_width - 1
            if y1 < 0:
                y1 = 0
            elif y1 >= display_height:
                y1 = display_height - 1

            # Display drawn zone and coordinates
            draw_zone(x0, y0, x1, y1)

            # Display relative zone coordinates, to set in theme
            x = min(x0, x1)
            y = min(y0, y1)
            width = max(x0, x1) - min(x0, x1)
            height = max(y0, y1) - min(y0, y1)

            label_coord.config(text='Zone: X={:0.0f}, Y={:0.0f}, width={:0.0f} height={:0.0f}'.format(x * RESIZE_FACTOR,
                                                                                                      y * RESIZE_FACTOR,
                                                                                                      width * RESIZE_FACTOR,
                                                                                                      height * RESIZE_FACTOR))
        else:
            # Display click coordinates
            label_coord.config(
                text='X={:0.0f}, Y={:0.0f} (click and drag to draw a zone)'.format(x0 * RESIZE_FACTOR,
                                                                                   y0 * RESIZE_FACTOR))


    def on_zone_click(event):
        label_zone.place_forget()


    def on_mousewheel(event):
        global RESIZE_FACTOR
        if event.delta > 0:
            RESIZE_FACTOR = RESIZE_FACTOR - 0.2
        else:
            RESIZE_FACTOR = RESIZE_FACTOR + 0.2


    def on_zoom_plus():
        global RESIZE_FACTOR
        RESIZE_FACTOR = RESIZE_FACTOR - 0.2


    def on_zoom_minus():
        global RESIZE_FACTOR
        RESIZE_FACTOR = RESIZE_FACTOR + 0.2


    # Apply system locale to this program
    locale.setlocale(locale.LC_ALL, '')

    logger.debug("Starting Theme Editor...")

    # Get theme file to edit
    theme_file = config.THEME_DATA['PATH'] + "theme.yaml"
    last_edit_time = os.path.getmtime(theme_file)
    logger.debug("Using theme file " + theme_file)

    # Open theme in default editor. You can also open the file manually in another program
    logger.debug("Opening theme file in your default editor. If it does not work, open it manually in the "
                 "editor of your choice")
    if platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', config.MAIN_DIRECTORY / theme_file))
    elif platform.system() == 'Windows':  # Windows
        os.startfile(config.MAIN_DIRECTORY / theme_file)
    else:  # linux variants
        subprocess.call(('xdg-open', config.MAIN_DIRECTORY / theme_file))

    # Load theme file and generate first preview
    try:
        refresh_theme()
        error_in_theme = False
    except Exception as e:
        logger.error(f"Error in theme: {e}")
        error_in_theme = True

    while True:
        display_width, display_height = int(display.lcd.get_width() / RESIZE_FACTOR), int(
            display.lcd.get_height() / RESIZE_FACTOR)
        current_resize_factor = RESIZE_FACTOR

        # Create preview window
        logger.debug("Opening theme preview window with static data")
        viewer = tkinter.Tk()
        viewer.title("Turing SysMon Theme Editor")
        viewer.iconphoto(True, tkinter.PhotoImage(file=config.MAIN_DIRECTORY / "res/icons/monitor-icon-17865/64.png"))
        
        # Window geometry includes rulers
        win_w = display_width + 2 * RGB_LED_MARGIN + RULER_SIZE
        win_h = display_height + 2 * RGB_LED_MARGIN + RULER_SIZE + 60
        viewer.geometry(f"{win_w}x{win_h}")
        
        viewer.protocol("WM_DELETE_WINDOW", on_closing)
        viewer.call('wm', 'attributes', '.', '-topmost', '1')  # Preview window always on top
        viewer.config(cursor="cross")
        viewer.resizable(False, False)  # Prevent window resize

        # Load guides from theme
        guides_h = config.THEME_DATA.get('editor_guides', {}).get('horizontal', [])
        guides_v = config.THEME_DATA.get('editor_guides', {}).get('vertical', [])

        # Display RGB backplate LEDs color as background color
        led_color = config.THEME_DATA['display'].get("DISPLAY_RGB_LED", (255, 255, 255))
        if isinstance(led_color, str):
            led_color = tuple(map(int, led_color.split(', ')))
        viewer.configure(bg='#%02x%02x%02x' % led_color)

        circular_mask = Image.open(config.MAIN_DIRECTORY / "res/backgrounds/circular-mask.png")

        # Rulers
        top_ruler = tkinter.Canvas(viewer, height=RULER_SIZE, width=display_width, highlightthickness=0)
        top_ruler.place(x=RGB_LED_MARGIN + RULER_SIZE, y=RGB_LED_MARGIN)
        draw_ruler(top_ruler, "horizontal", display_width, RESIZE_FACTOR)

        left_ruler = tkinter.Canvas(viewer, width=RULER_SIZE, height=display_height, highlightthickness=0)
        left_ruler.place(x=RGB_LED_MARGIN, y=RGB_LED_MARGIN + RULER_SIZE)
        draw_ruler(left_ruler, "vertical", display_height, RESIZE_FACTOR)

        corner_box = tkinter.Frame(viewer, width=RULER_SIZE, height=RULER_SIZE, bg="#d0d0d0", borderwidth=1, relief="raised")
        corner_box.place(x=RGB_LED_MARGIN, y=RGB_LED_MARGIN)

        # Main preview canvas (instead of Label)
        canvas_preview = tkinter.Canvas(viewer, width=display_width, height=display_height, highlightthickness=0, borderwidth=0)
        canvas_preview.place(x=RGB_LED_MARGIN + RULER_SIZE, y=RGB_LED_MARGIN + RULER_SIZE)

        def update_canvas_image():
            global display_image
            if not error_in_theme:
                screen_image = display.lcd.screen_image
                if config.THEME_DATA["display"].get("DISPLAY_SIZE", '3.5"') == '2.1"':
                    screen_image.paste(circular_mask, mask=circular_mask)
                resized_img = screen_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
                display_image = ImageTk.PhotoImage(resized_img)
            else:
                size = display_width if display_width < display_height else display_height
                display_image = ImageTk.PhotoImage(ERROR_IN_THEME.resize((size, size)))
            
            canvas_preview.delete("preview_img")
            canvas_preview.create_image(0, 0, anchor="nw", image=display_image, tags="preview_img")
            redraw_guides()

        def redraw_guides():
            canvas_preview.delete("guide")
            for y in guides_h:
                canvas_preview.create_line(0, y / RESIZE_FACTOR, display_width, y / RESIZE_FACTOR, fill=GUIDE_COLOR, tags="guide", width=1)
            for x in guides_v:
                canvas_preview.create_line(x / RESIZE_FACTOR, 0, x / RESIZE_FACTOR, display_height, fill=GUIDE_COLOR, tags="guide", width=1)
            canvas_preview.tag_raise("guide")

        display_image = None
        update_canvas_image()

        # Hover cursor feedback for guides
        def on_canvas_motion(event):
            """Change cursor when hovering over a guide."""
            mouse_x, mouse_y = event.x * RESIZE_FACTOR, event.y * RESIZE_FACTOR
            threshold = 5 * RESIZE_FACTOR
            
            # Check if near any horizontal guide
            for y in guides_h:
                if abs(mouse_y - y) < threshold:
                    viewer.config(cursor="sb_v_double_arrow")
                    return
            
            # Check if near any vertical guide
            for x in guides_v:
                if abs(mouse_x - x) < threshold:
                    viewer.config(cursor="sb_h_double_arrow")
                    return
            
            # No guide nearby, use default cursor
            viewer.config(cursor="cross")

        canvas_preview.bind("<Motion>", on_canvas_motion)

        # Guide Interaction Logic
        def on_canvas_click(event):
            # Check if clicked near a guide to drag it, otherwise handle zone drawing
            click_x, click_y = event.x * RESIZE_FACTOR, event.y * RESIZE_FACTOR
            
            # Find closest guide
            threshold = 5 * RESIZE_FACTOR
            for i, y in enumerate(guides_h):
                if abs(click_y - y) < threshold:
                    viewer.config(cursor="sb_v_double_arrow")
                    canvas_preview.bind("<B1-Motion>", lambda e, idx=i: move_guide_h(e, idx))
                    canvas_preview.bind("<ButtonRelease-1>", on_guide_release)
                    return
            for i, x in enumerate(guides_v):
                if abs(click_x - x) < threshold:
                    viewer.config(cursor="sb_h_double_arrow")
                    canvas_preview.bind("<B1-Motion>", lambda e, idx=i: move_guide_v(e, idx))
                    canvas_preview.bind("<ButtonRelease-1>", on_guide_release)
                    return
            
            # If no guide, handle zone drawing (reuse existing functions but adjust for canvas coords)
            on_button1_press(event)
            canvas_preview.bind("<B1-Motion>", on_button1_press_and_drag)
            canvas_preview.bind("<ButtonRelease-1>", on_button1_release)

        def move_guide_h(event, idx):
            guides_h[idx] = event.y * RESIZE_FACTOR
            redraw_guides()

        def move_guide_v(event, idx):
            guides_v[idx] = event.x * RESIZE_FACTOR
            redraw_guides()

        def on_guide_release(event):
            viewer.config(cursor="cross")
            save_guides(guides_h, guides_v)
            canvas_preview.bind("<B1-Motion>", on_button1_press_and_drag)
            canvas_preview.bind("<ButtonRelease-1>", on_button1_release)

        def on_ruler_h_press(event):
            # Start dragging a new horizontal guide from top ruler
            guides_h.append(0)  # Start at top
            idx = len(guides_h) - 1
            
            def on_motion(e):
                # Update guide position as mouse moves
                new_y = e.y_root - canvas_preview.winfo_rooty()
                if 0 <= new_y <= display_height:
                    guides_h[idx] = new_y * RESIZE_FACTOR
                    redraw_guides()
            
            def on_release(e):
                # Finalize guide or remove if outside bounds
                final_y = e.y_root - canvas_preview.winfo_rooty()
                if final_y < 0 or final_y > display_height:
                    guides_h.pop(idx)
                    redraw_guides()
                else:
                    guides_h[idx] = final_y * RESIZE_FACTOR
                    save_guides(guides_h, guides_v)
                viewer.config(cursor="cross")
                top_ruler.unbind("<B1-Motion>")
                top_ruler.unbind("<ButtonRelease-1>")
            
            top_ruler.bind("<B1-Motion>", on_motion)
            top_ruler.bind("<ButtonRelease-1>", on_release)
            viewer.config(cursor="sb_v_double_arrow")

        def on_ruler_v_press(event):
            # Start dragging a new vertical guide from left ruler
            guides_v.append(0)  # Start at left
            idx = len(guides_v) - 1
            
            def on_motion(e):
                # Update guide position as mouse moves
                new_x = e.x_root - canvas_preview.winfo_rootx()
                if 0 <= new_x <= display_width:
                    guides_v[idx] = new_x * RESIZE_FACTOR
                    redraw_guides()
            
            def on_release(e):
                # Finalize guide or remove if outside bounds
                final_x = e.x_root - canvas_preview.winfo_rootx()
                if final_x < 0 or final_x > display_width:
                    guides_v.pop(idx)
                    redraw_guides()
                else:
                    guides_v[idx] = final_x * RESIZE_FACTOR
                    save_guides(guides_h, guides_v)
                viewer.config(cursor="cross")
                left_ruler.unbind("<B1-Motion>")
                left_ruler.unbind("<ButtonRelease-1>")
            
            left_ruler.bind("<B1-Motion>", on_motion)
            left_ruler.bind("<ButtonRelease-1>", on_release)
            viewer.config(cursor="sb_h_double_arrow")

        top_ruler.bind("<ButtonPress-1>", on_ruler_h_press)
        left_ruler.bind("<ButtonPress-1>", on_ruler_v_press)
        canvas_preview.bind("<ButtonPress-1>", on_canvas_click)

        # Allow to resize editor using mouse wheel or buttons
        viewer.bind_all("<MouseWheel>", on_mousewheel)

        # Zoom and Bake UI row
        zoom_w = int(display_width * 0.25)
        bake_w = display_width - (zoom_w * 2)
        
        zoom_plus_btn = tkinter.Button(viewer, text="Zoom +", command=lambda: on_zoom_plus())
        zoom_plus_btn.place(x=RGB_LED_MARGIN + RULER_SIZE, y=display_height + 2 * RGB_LED_MARGIN + RULER_SIZE, height=30,
                            width=zoom_w)

        zoom_minus_btn = tkinter.Button(viewer, text="Zoom -", command=lambda: on_zoom_minus())
        zoom_minus_btn.place(x=RGB_LED_MARGIN + RULER_SIZE + zoom_w, y=display_height + 2 * RGB_LED_MARGIN + RULER_SIZE,
                             height=30, width=zoom_w)

        # Video Processing UI
        needed, _, _ = check_video_processing_needed()
        bake_btn_text = "Bake UI Overlay to Video"
        btn_fg = "black"
        if needed:
            bake_btn_text = "⚠️ " + bake_btn_text + " (Recommended)"
            btn_fg = "red"
            
        bake_btn = tkinter.Button(viewer, text=bake_btn_text, command=lambda: run_video_processing(bake_btn))
        bake_btn.place(x=RGB_LED_MARGIN + RULER_SIZE + zoom_w * 2, y=display_height + 2 * RGB_LED_MARGIN + RULER_SIZE, height=30,
                        width=bake_w)
        
        if needed:
            bake_btn.config(fg=btn_fg, font=("TkDefaultFont", 9, "bold"))

        label_coord = tkinter.Label(viewer, text="Click or draw a zone to show coordinates")
        label_coord.place(x=0, y=display_height + 2 * RGB_LED_MARGIN + RULER_SIZE + 35,
                          width=display_width + 2 * RGB_LED_MARGIN + RULER_SIZE)

        label_zone = tkinter.Label(viewer, bg='#%02x%02x%02x' % tuple(map(lambda x: 255 - x, led_color)))
        label_zone.bind("<ButtonRelease-1>", on_zone_click)

        viewer.update()

        logger.debug(
            "You can now edit the theme file in the editor. When you save your changes, the preview window will "
            "update automatically")

        while current_resize_factor == RESIZE_FACTOR:
            # Every time the theme file is modified: reload preview
            if os.path.exists(theme_file) and os.path.getmtime(theme_file) > last_edit_time:
                logger.debug("The theme file has been updated, the preview window will refresh")
                try:
                    refresh_theme()
                    error_in_theme = False
                except Exception as e:
                    logger.error(f"Error in theme: {e}")
                    error_in_theme = True
                last_edit_time = os.path.getmtime(theme_file)

                # Update the preview.png that is in the theme folder
                display.lcd.screen_image.save(config.THEME_DATA['PATH'] + "preview.png", "PNG")

                # Display new picture
                update_canvas_image()

                # Refresh RGB backplate LEDs color
                led_color = config.THEME_DATA['display'].get("DISPLAY_RGB_LED", (255, 255, 255))
                if isinstance(led_color, str):
                    led_color = tuple(map(int, led_color.split(', ')))
                viewer.configure(bg='#%02x%02x%02x' % led_color)
                label_zone.configure(bg='#%02x%02x%02x' % tuple(map(lambda x: 255 - x, led_color)))

            # Handle UI tasks from other threads
            while not ui_queue.empty():
                try:
                    task = ui_queue.get_nowait()
                    task()
                except queue.Empty:
                    break
            
            # Update Bake button status periodically
            if 'bake_btn' in locals() and bake_btn.cget("state") != "disabled":
                needed, _, _ = check_video_processing_needed()
                current_text = bake_btn.cget("text")
                is_red = bake_btn.cget("fg") == "red"
                
                if needed:
                    if not is_red or "Recommended" not in current_text:
                        bake_btn.config(text="⚠️ Bake UI Overlay to Video (Recommended)", fg="red", font=("TkDefaultFont", 9, "bold"))
                elif not needed:
                    # If it was marked as recommended or failed/processing, but now not needed
                    if is_red or "🔃" in current_text or "⚠️" in current_text:
                        # Only reset to normal if not already in a special state like success ✅
                        if "✅" not in current_text:
                            bake_btn.config(text="Bake UI Overlay to Video", fg="black", font=("TkDefaultFont", 9, "normal"))

            viewer.update()

            time.sleep(0.1)

        # Zoom level changed, reload editor
        logger.info(
            f"Zoom level changed from {current_resize_factor:.1f} to {RESIZE_FACTOR:.1f}, reloading theme editor")
        viewer.destroy()
