# Video Support for Turing Smart Screen 5"

This directory contains a test video file for demonstrating video playback features on Revision C (Turing 5") displays.

## Video Requirements

- **Resolution**: 480x800 pixels (portrait) or 800x480 pixels (landscape)
- **Format**: MP4 (H.264 codec recommended)
- **Location**: Videos can be stored on internal storage (`/root/video/`) or SD card (`/mnt/SDCARD/video/`)

## Usage

See `simple-program-video-mode.py` for a complete example of:
- Uploading videos to the display
- Playing videos as backgrounds
- Drawing dynamic overlays (text, progress bars) on top of videos

## Sample Video

The `gunpla.mp4` file in this directory is a sample video for testing video playback functionality.

## Additional Videos

For more sample videos compatible with the Turing 5" display, see the original PR:
https://github.com/mathoudebine/turing-smart-screen-python/pull/348

Sample videos from the PR include:
- ethereal_wave.mp4
- particles.mp4
- matrix.mp4
- And more...

You can download these videos from the PR and place them in this directory for use with your display.
