# Video Background Support for Turing Smart Screen Themes

> [!NOTE]
> This documentation describes the video background feature added to support animated backgrounds on Turing Smart Screen 5" (Revision C) displays.

## Overview

Video backgrounds allow you to use MP4 videos as animated backgrounds in your themes instead of static PNG images. This creates dynamic, eye-catching displays perfect for showing system monitoring information over custom visuals.

## Requirements

- **Hardware**: Turing Smart Screen 5\" (Revision C) display only
- **Software**: `numba~=0.63.0` (for optimized overlay rendering)
- **Videos**: MP4 format, 480x800 (portrait) or 800x480 (landscape) resolution

## Enabling Video Backgrounds in Themes

### Basic Configuration

Add a `video_background` section to your `theme.yaml`:

```yaml
video_background:
  # Enable video background (Revision C / 5" displays only)
  ENABLE: True
  
  # Path to video on display's storage
  REMOTE_PATH: /mnt/SDCARD/video/myvideo.mp4
  
  # Optional: Local path for automatic upload if not on display
  LOCAL_PATH: res/videos/myvideo.mp4
```

### Important Notes

1. **Mutual Exclusivity**: Video backgrounds and static `BACKGROUND` images are mutually exclusive. If you enable `video_background`, comment out or remove the `BACKGROUND` entry under `static_images`:

   ```yaml
   static_images:
     # BACKGROUND:  # Commented out when using video background
     #   PATH: background.png
     #   X: 0
     #   Y: 0
   ```

2. **UI Elements**: All other static images, text, and dynamic stats display elements (progress bars, graphs, etc.) will render as overlays on top of the video.

3. **Upload**: Videos must be uploaded to the display's internal storage or SD card. Use `LOCAL_PATH` for automatic upload on theme load, or manually upload using `UploadFile()` API.

## Theme Editor Support

The `theme-editor.py` tool has been updated to support video backgrounds:

1. **Automatic Frame Extraction**: When you load a theme with `video_background.ENABLE: True`, the editor automatically:
   - Opens the local video file specified in `LOCAL_PATH`
   - Extracts frame #10 (to avoid black intro frames)
   - Saves it as a static image: `res/themes/YourTheme/background.png`
   - Configures the preview to use this image as the background

2. **Text Visibility**: This ensures that text and other UI elements with `BACKGROUND_IMAGE: background.png` render correctly in the preview, with the proper video backdrop instead of a white box.

3. **Auto-Regeneration**: If you change the `LOCAL_PATH` in your theme file and save, the editor detects the change, extracts the new video frame, clears the internal image cache, and updates the preview automatically.

> [!TIP]
> Always include `BACKGROUND_IMAGE: background.png` for your text elements in video themes. This ensures they look correct in both the editor (using the extracted frame) and on the actual hardware (where the overlay system handles transparency).

## Video Storage Paths

The display supports two storage locations:

- **Internal Storage**: `/root/video/filename.mp4`
- **SD Card**: `/mnt/SDCARD/video/filename.mp4` (recommended for larger videos)

## Example Theme Configuration

```yaml
---
author: "@yourusername"

display:
  DISPLAY_SIZE: 5"
  DISPLAY_ORIENTATION: landscape
  DISPLAY_RGB_LED: 255, 0, 0

video_background:
  ENABLE: True
  REMOTE_PATH: /mnt/SDCARD/video/particles.mp4
  LOCAL_PATH: res/videos/particles.mp4

static_images:
  # BACKGROUND commented out - using video instead
  LOGO:
    PATH: logo.png
    X: 10
    Y: 10

STATS:
  CPU:
    PERCENTAGE:
      INTERVAL: 1
      TEXT:
        SHOW: True
        X: 50
        Y: 100
        FONT: roboto-mono/RobotoMono-Bold.ttf
        FONT_SIZE: 24
        FONT_COLOR: 255, 255, 255
        # Text will render over video with transparent background
        BACKGROUND_IMAGE: background.png  # Not used with  video, kept for fallback
```

## Creating Video Backgrounds

### Recommended Video Specifications

- **Resolution**: Match your display orientation
  - Portrait: 480x800 pixels
  - Landscape: 800x480 pixels
- **Format**: MP4 (H.264 codec)
- **Frame Rate**: 24-30 FPS
- **Duration**: Can be any length (video loops automatically)
- **File Size**: Keep under 50MB for best upload/playback performance

### Video Creation Tips

1. **Looping**: For seamless loops, ensure the last frame matches the first
2. **Content**: Abstract animations, particles, or slow-moving backgrounds work best
3. **Contrast**: Use darker backgrounds for better text readability
4. **Optimization**: Use video compression tools to reduce file size while maintaining quality

## Programming with Video Backgrounds

### Manual Video Control

```python
from library.lcd.lcd_comm_rev_c import LcdCommRevC

# Initialize display
lcd = LcdCommRevC(com_port="AUTO", display_width=480, display_height=800)
lcd.InitializeComm()

# Upload video if needed
video_local = "res/videos/myvideo.mp4"
video_remote = "/mnt/SDCARD/video/myvideo.mp4"

if lcd.GetFileSize(video_remote) == 0:
    lcd.UploadFile(video_local, video_remote)

# Start video playback
lcd.StartVideo(video_remote)

# Initialize overlay for drawing UI elements
lcd.InitializeVideoOverlay()

# Draw dynamic content over video
lcd.DrawTextOnVideo("CPU: 45%", 100, 100, font_size=30, font_color=(255, 255, 255))
lcd.DrawProgressBarOnVideo(50, 200, 300, 40, value=75)

# Refresh overlay to display changes
lcd.RefreshVideoOverlay()

# Stop video when done
lcd.StopVideo()
```

### Theme-Based Video Backgrounds

When using video in `theme.yaml`, the display module handles video initialization automatically:

```python
from library import display

# Video starts automatically if enabled in theme
display.initialize_display()

# UI elements render as overlays automatically
# No manual overlay management needed
```

## Performance Considerations

The video overlay system uses optimized rendering:

- **Differential Updates**: Only changed pixels are transmitted to display
- **JIT Compilation**: Numba accelerates pixel difference calculations
- **Segment-Based Transfer**: Contiguous pixel runs sent together

This enables smooth, real-time updates of stats over video backgrounds with minimal performance impact.

## Troubleshooting

### Video Not Playing

1. **Check Hardware**: Verify you have a Revision C (5\") display
2. **Check Path**: Ensure `REMOTE_PATH` is correct
3. **Check Upload**: If using `LOCAL_PATH`, confirm file exists locally
4. **Check Format**: Verify MP4 file with H.264 codec

### Performance Issues

1. **Reduce Video Resolution**: Use exact display resolution
2. **Lower Frame Rate**: 24 FPS is usually sufficient
3. **Compress Video**: Use smaller file sizes
4. **Limit Overlay Updates**: Increase `INTERVAL` values in theme stats

### Overlay Not Visible

1. **Check Transparency**: Ensure overlay has sufficient contrast with video
2. **Verify Initialization**: Confirm `InitializeVideoOverlay()` was called
3. **Check Refresh**: Ensure `RefreshVideoOverlay()` is called after drawing

## Additional Resources

- **Example Program**: See `simple-program-video-mode.py` for complete demonstration
- **Test Script**: Use `test_new_features.py` to verify file management and video APIs
- **Sample Videos**: Check `res/videos/README.md` for links to compatible sample videos
- **API Documentation**: See [PR #348](https://github.com/mathoudebine/turing-smart-screen-python/pull/348) for detailed API reference

## Compatibility

| Display Revision    | Video Background Support |
| ------------------- | ------------------------ |
| Revision A (3.5")   | ❌ No                     |
| Revision B (3.5")   | ❌ No                     |
| **Revision C (5")** | ✅ **Yes**                |
| Revision D (3.5")   | ❌ No                     |

## See Also

- [Theme Creation Wiki](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-themes)
- [Supported Hardware](https://github.com/mathoudebine/turing-smart-screen-python/wiki/Hardware-revisions)

## Advanced UI Layer

For more complex themes, you can now define an "advanced UI layer" in your `theme.yaml` under the `ui_elements` section. This allows you to draw vector shapes, lines, and text that are either:
1.  **Overlaid** dynamically on top of the video (if using `video_background.ENABLE: True`).
2.  **Baked** into the video itself using the `video_processor.py` tool.

### UI Elements Configuration

The `ui_elements` section is a flat list of elements drawn sequentially, with later elements appearing on top of earlier ones (painter's algorithm).

#### Common Properties
All element types support these properties:

| Property  | Type    | Description                      | Default |
| :-------- | :------ | :------------------------------- | :------ |
| `x`       | Integer | X coordinate (Left)              | 0       |
| `y`       | Integer | Y coordinate (Top)               | 0       |
| `angle`   | Number  | Rotation in degrees (clockwise)  | 0       |
| `opacity` | Float   | Opacity multiplier (0.0 to 1.0)  | 1.0     |
| `shadow`  | Object  | Shadow configuration (see below) | None    |

> [!NOTE]
> **Opacity vs Color Alpha**: The `opacity` property multiplies with the alpha channel in `color`. For example, if `color: "255, 0, 0, 128"` (50% alpha) and `opacity: 0.5`, the final opacity will be 25% (0.5 × 0.5).

**Shadow Configuration:**
```yaml
shadow:
  blur: 5                # Blur radius
  color: "0, 0, 0, 128"  # Shadow color (RGBA)
  offset_x: 5            # Horizontal offset
  offset_y: 5            # Vertical offset
```

---

#### 1. Rectangle
Draws a rectangle, optionally with rounded corners.

| Property        | Type    | Description                             |
| :-------------- | :------ | :-------------------------------------- |
| `type`          | String  | Must be `rectangle`                     |
| `width`         | Integer | Width of the rectangle                  |
| `height`        | Integer | Height of the rectangle                 |
| `color`         | String  | Fill color (RGBA: "r,g,b,a")            |
| `radius`        | Integer | Corner radius for rounded corners       |
| `outline_color` | String  | Outline color (RGBA)                    |
| `outline_width` | Integer | Thickness of the outline                |
| `dash_array`    | List    | Custom dash pattern `[draw_px, gap_px]` |
| `style`         | String  | Preset dash style: `dotted` or `dashed` |

**Example:**
```yaml
  - type: rectangle
    x: 10
    y: 10
    width: 200
    height: 100
    color: "255, 0, 0, 128"
    radius: 15
    outline_color: "255, 255, 255, 255"
    outline_width: 2
    dash_array: [10, 5]  # Alternative to style
    # style: dashed  # Use either dash_array OR style, not both
    angle: 15
    opacity: 0.9
    shadow:
      blur: 5
      color: "0, 0, 0, 128"
      offset_x: 3
      offset_y: 3
```

#### 2. Circle / Ellipse
Draws a circle or ellipse.

| Property        | Type    | Description                                   |
| :-------------- | :------ | :-------------------------------------------- |
| `type`          | String  | `circle` or `ellipse`                         |
| `width`         | Integer | Width (Ellipse only)                          |
| `height`        | Integer | Height (Ellipse only)                         |
| `radius`        | Integer | Radius (Circle only). Overrides width/height. |
| `color`         | String  | Fill color (RGBA)                             |
| `outline_color` | String  | Outline color (RGBA)                          |
| `outline_width` | Integer | Thickness of the outline                      |

**Example:**
```yaml
  - type: circle
    x: 100
    y: 100
    radius: 50
    color: "0, 0, 255, 200"
    outline_color: "255, 255, 255, 255"
    outline_width: 3
    angle: 0  # Rotation (not visually apparent for perfect circles)
    opacity: 0.8
    shadow:
      blur: 10
      color: "0, 0, 0, 150"
      offset_x: 5
      offset_y: 5
```

#### 3. Line
Draws a line between two points.

| Property        | Type    | Description                              |
| :-------------- | :------ | :--------------------------------------- |
| `type`          | String  | Must be `line`                           |
| `x2`            | Integer | End X coordinate                         |
| `y2`            | Integer | End Y coordinate                         |
| `width`         | Integer | Line thickness                           |
| `color`         | String  | Line color (RGBA)                        |
| `end_cap`       | String  | Line ending: `butt` (default) or `round` |
| `outline_color` | String  | Outline color around the line            |
| `outline_width` | Integer | Thickness of the outline                 |
| `style`         | String  | `dotted` or `dashed`                     |

**Example:**
```yaml
  - type: line
    x: 10
    y: 50
    x2: 200
    y2: 50
    width: 5
    color: "0, 255, 0, 255"
    end_cap: round
    outline_color: "0, 0, 0, 255"
    outline_width: 1
    style: dashed
    angle: 0  # Rotation applied from (x, y)
    opacity: 1.0
    shadow:
      blur: 3
      color: "0, 0, 0, 100"
      offset_x: 2
      offset_y: 2
```

#### 4. Text
Draws text using a TrueType font.

| Property    | Type    | Description                        |
| :---------- | :------ | :--------------------------------- |
| `type`      | String  | Must be `text`                     |
| `text`      | String  | The text string to display         |
| `font`      | String  | Font file path (relative to theme) |
| `font_size` | Integer | Font size in pixels                |
| `color`     | String  | Text color (RGBA)                  |

**Example:**
```yaml
  - type: text
    text: "Status: Online"
    x: 20
    y: 20
    font: "fonts/Roboto-Bold.ttf"
    font_size: 24
    color: "255, 255, 255, 255"
    angle: 0
    opacity: 1.0
    shadow:
      blur: 4
      color: "0, 0, 0, 180"
      offset_x: 2
      offset_y: 2
```

#### 5. Image
Draws a PNG image.

| Property  | Type   | Description                          |
| :-------- | :----- | :----------------------------------- |
| `type`    | String | Must be `image`                      |
| `path`    | String | Image file path (relative to theme)  |
| `scale`   | Float  | Scaling factor (1.0 = original size) |
| `opacity` | Float  | Opacity multiplier (0.0 to 1.0)      |

**Example:**
```yaml
  - type: image
    path: "icons/warning.png"
    x: 300
    y: 10
    scale: 0.5
    opacity: 0.8
    angle: 45
    shadow:
      blur: 6
      color: "0, 0, 0, 120"
      offset_x: 4
      offset_y: 4
```

### Video Processor Tool

If you want to permanently "bake" these UI elements into your video (to save performance on the device, or to handle complex effects like blurs/shadows that might be slow to render in real-time), you can use the `video_processor.py` tool.

**Usage:**
```bash
python tools/video_processor.py "path/to/theme/folder" "path/to/source_video.mp4"
```

**What it does:**
1.  Reads your `theme.yaml`.
2.  Generates the UI overlay from `ui_elements`.
3.  Resizes and crops the source video to match your display configuration.
4.  Overlays the UI elements onto every frame of the video.
5.  Updates your `theme.yaml` to point to the new processed video.

**Prerequisites:**
- FFmpeg installed and in your system PATH.
