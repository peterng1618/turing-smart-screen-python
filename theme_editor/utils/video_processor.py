# SPDX-License-Identifier: GPL-3.0-or-later
"""
Video Processor for Theme Editor - PyAV Implementation

Processes videos for Turing Smart Screen themes using PyAV (bundled FFmpeg libraries).
No separate FFmpeg installation required.

Features:
- Seamless loop crossfade (LOOP_FADE_DURATION)
- Rotation (0, 90, 180, 270 degrees)
- Flip (horizontal, vertical, both)
- Resize & crop to target display dimensions
- Trim (START_OFFSET, DURATION)
- Audio removal
- UI overlay baking

This module is used by the Theme Editor for video background processing.
"""

import os
import sys
from pathlib import Path
from fractions import Fraction

import av
import numpy as np
from PIL import Image

# Add project root to path to allow imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from library import config
from library.ui_renderer import UiRenderer
from library.log import logger


def parse_time_string(time_str: str) -> float:
    """
    Parse mm:ss format time string to seconds.
    
    Args:
        time_str: Time in mm:ss format (e.g., "01:30" for 1 minute 30 seconds)
        
    Returns:
        Time in seconds as float
    """
    if not time_str:
        return 0.0
    
    parts = time_str.strip().split(':')
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), float(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 1:
        return float(parts[0])
    else:
        logger.warning(f"Invalid time format: {time_str}, expected mm:ss")
        return 0.0


def get_video_info(container: av.container.InputContainer) -> dict:
    """
    Get video stream information.
    
    Returns dict with: width, height, fps, duration, total_frames
    """
    video_stream = container.streams.video[0]
    
    # Calculate duration in seconds
    if video_stream.duration is not None:
        duration = float(video_stream.duration * video_stream.time_base)
    elif container.duration is not None:
        duration = container.duration / av.time_base
    else:
        duration = 0.0
    
    # Get FPS
    fps = float(video_stream.average_rate) if video_stream.average_rate else 30.0
    
    # Estimate total frames
    total_frames = int(video_stream.frames) if video_stream.frames else int(duration * fps)
    
    return {
        'width': video_stream.width,
        'height': video_stream.height,
        'fps': fps,
        'duration': duration,
        'total_frames': total_frames,
        'codec': video_stream.codec_context.name,
    }


def apply_rotation(frame_array: np.ndarray, rotation: int) -> np.ndarray:
    """
    Apply rotation to frame.
    
    Args:
        frame_array: NumPy array (H, W, C) in RGB
        rotation: Degrees (0, 90, 180, 270)
        
    Returns:
        Rotated frame array
    """
    if rotation == 0:
        return frame_array
    elif rotation == 90:
        return np.rot90(frame_array, k=-1)  # Clockwise
    elif rotation == 180:
        return np.rot90(frame_array, k=2)
    elif rotation == 270:
        return np.rot90(frame_array, k=1)  # Counter-clockwise
    else:
        logger.warning(f"Invalid rotation: {rotation}, using 0")
        return frame_array


def apply_flip(frame_array: np.ndarray, flip: str) -> np.ndarray:
    """
    Apply flip transformation to frame.
    
    Args:
        frame_array: NumPy array (H, W, C) in RGB
        flip: 'horizontal', 'vertical', or 'both'
        
    Returns:
        Flipped frame array
    """
    if not flip:
        return frame_array
    
    flip_lower = flip.lower()
    if flip_lower == 'horizontal':
        return np.fliplr(frame_array)
    elif flip_lower == 'vertical':
        return np.flipud(frame_array)
    elif flip_lower == 'both':
        return np.flipud(np.fliplr(frame_array))
    else:
        logger.warning(f"Invalid flip: {flip}, skipping")
        return frame_array


def resize_and_crop(frame_array: np.ndarray, target_w: int, target_h: int, 
                    crop_x: int = None, crop_y: int = None, 
                    crop_w: int = None, crop_h: int = None) -> np.ndarray:
    """
    Resize frame and apply custom or center crop.
    
    If crop_x/y/w/h are provided, they specify the crop rectangle in the resized image.
    If not provided, center-crops to target_w/h.
    """
    img = Image.fromarray(frame_array)
    src_w, src_h = img.size
    
    # Calculate scale to fill (cover) the target
    scale_w = target_w / src_w
    scale_h = target_h / src_h
    scale = max(scale_w, scale_h)
    
    # Resize
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Crop
    if crop_x is not None and crop_y is not None and crop_w and crop_h:
        # Custom crop (from editor)
        # Note: crop_w/h might be same as target_w/h if not intentionally cropped differently
        left = crop_x
        top = crop_y
        right = left + crop_w
        bottom = top + crop_h
    else:
        # Default: Center crop
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h
        
    img = img.crop((left, top, right, bottom))
    
    # Final resize to display resolution (in case crop size differs)
    if img.size != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
    return np.array(img)


def apply_overlay(frame_array: np.ndarray, overlay: Image.Image) -> np.ndarray:
    """
    Composite overlay image onto frame.
    
    Args:
        frame_array: NumPy array (H, W, C) in RGB
        overlay: PIL Image with alpha channel (RGBA)
        
    Returns:
        Composited frame array
    """
    frame_img = Image.fromarray(frame_array).convert('RGBA')
    overlay_resized = overlay.resize(frame_img.size, Image.Resampling.LANCZOS)
    
    # Composite
    result = Image.alpha_composite(frame_img, overlay_resized)
    
    return np.array(result.convert('RGB'))


def crossfade_frames(frames_a: list, frames_b: list) -> list:
    """
    Create crossfade transition between two frame sequences.
    
    Args:
        frames_a: List of ending frames (fade out)
        frames_b: List of beginning frames (fade in)
        
    Returns:
        List of blended frames (same length as inputs)
    """
    if len(frames_a) != len(frames_b):
        raise ValueError("Frame lists must have same length for crossfade")
    
    blended = []
    num_frames = len(frames_a)
    
    for i, (fa, fb) in enumerate(zip(frames_a, frames_b)):
        # Alpha goes from 0 to 1 (fa fades out, fb fades in)
        alpha = i / (num_frames - 1) if num_frames > 1 else 0.5
        
        # Blend: result = (1 - alpha) * fa + alpha * fb
        blended_frame = ((1 - alpha) * fa.astype(np.float32) + 
                         alpha * fb.astype(np.float32)).astype(np.uint8)
        blended.append(blended_frame)
    
    return blended


def process_video(theme_path_str: str, source_video_path: str, output_video_path: str = None) -> bool:
    """
    Process a video for a specific theme using PyAV.
    
    Pipeline:
    1. Load theme config and generate UI overlay
    2. Open source video
    3. Apply trim (START_OFFSET, DURATION)
    4. Apply rotation
    5. Apply flip
    6. Resize & crop to target dimensions
    7. Apply crossfade loop if LOOP_FADE_DURATION > 0
    8. Apply UI overlay
    9. Encode to MP4 (H.264, no audio)
    
    Returns:
        True on success, False on failure
    """
    theme_path = Path(theme_path_str).resolve()
    if not theme_path.exists():
        logger.error(f"Theme path not found: {theme_path}")
        return False
    
    if not Path(source_video_path).exists():
        logger.error(f"Source video not found: {source_video_path}")
        return False
    
    # Load theme data
    try:
        theme_yaml_path = theme_path / "theme.yaml"
        theme_data = config.load_yaml(theme_yaml_path)
    except Exception as e:
        logger.error(f"Failed to load theme YAML: {e}")
        return False
    
    # Get video processing options from theme
    video_bg = theme_data.get('video_background', {})
    loop_fade_duration = float(video_bg.get('LOOP_FADE_DURATION', 0))
    rotation = int(video_bg.get('ROTATE', 0))
    flip = video_bg.get('FLIP', None)
    start_offset = parse_time_string(video_bg.get('START_OFFSET', '00:00'))
    duration_str = video_bg.get('DURATION', None)
    
    # Custom crop fields (standardized x, y, width, height)
    crop_x = video_bg.get('x')
    crop_y = video_bg.get('y')
    crop_w = video_bg.get('width')
    crop_h = video_bg.get('height')
    
    # Initialize Renderer and get target dimensions
    renderer = UiRenderer(theme_data, theme_path)
    target_w = renderer.width
    target_h = renderer.height
    logger.info(f"Target resolution: {target_w}x{target_h}")
    
    # Generate Overlay
    logger.info("Generating UI overlay...")
    overlay_img = renderer.generate_overlay()
    
    # Determine output path
    if not output_video_path:
        source_path_obj = Path(source_video_path)
        output_video_path = str(source_path_obj.with_name(f"{source_path_obj.stem}_processed.mp4"))
    
    # Open source video
    logger.info(f"Opening source video: {source_video_path}")
    try:
        input_container = av.open(source_video_path)
    except av.AVError as e:
        logger.error(f"Failed to open video: {e}")
        return False
    
    video_info = get_video_info(input_container)
    logger.info(f"Source: {video_info['width']}x{video_info['height']}, "
                f"{video_info['fps']:.2f} fps, {video_info['duration']:.2f}s")
    
    # Calculate trim parameters
    source_duration = video_info['duration']
    if start_offset >= source_duration:
        logger.error(f"START_OFFSET ({start_offset}s) exceeds video duration ({source_duration}s)")
        return False
    
    if duration_str:
        target_duration = parse_time_string(duration_str)
        end_time = min(start_offset + target_duration, source_duration)
    else:
        target_duration = source_duration - start_offset
        end_time = source_duration
    
    logger.info(f"Trim: {start_offset:.2f}s to {end_time:.2f}s ({target_duration:.2f}s)")
    
    # Calculate crossfade frame count
    fps = video_info['fps']
    fade_frames = int(loop_fade_duration * fps) if loop_fade_duration > 0 else 0
    
    if fade_frames > 0:
        logger.info(f"Crossfade: {loop_fade_duration}s ({fade_frames} frames)")
    
    # --- Step 1: Cut (Decode raw frames with trim) ---
    logger.info("Step 1: Decoding raw frames (Cut)...")
    raw_frames = []
    frame_count = 0
    
    input_container.seek(int(start_offset * av.time_base))
    video_stream = input_container.streams.video[0]
    
    for frame in input_container.decode(video_stream):
        # Calculate frame time
        frame_time = float(frame.pts * frame.time_base) if frame.pts else frame_count / fps
        
        # Skip frames before start offset (in case seek wasn't exact)
        if frame_time < start_offset:
            continue
        
        # Stop at end time
        if frame_time >= end_time:
            break
        
        # Convert to numpy array (RGB)
        # We store RAW frames here. This might use significant memory for long videos.
        # But it is required to Crossfade BEFORE Transform.
        frame_array = frame.to_ndarray(format='rgb24')
        raw_frames.append(frame_array)
        frame_count += 1
        
        if frame_count % 100 == 0:
            logger.info(f"  Decoded {frame_count} frames...")
    
    input_container.close()
    logger.info(f"Decoded {len(raw_frames)} raw frames")
    
    if not raw_frames:
        logger.error("No frames decoded! Check start_offset/end_time.")
        return False

    # --- Step 2: Crossfade (Loop) ---
    # Apply crossfade to the raw sequence if requested
    processed_raw_frames = raw_frames
    
    if fade_frames > 0 and len(raw_frames) > fade_frames:
        logger.info("Step 2: applying crossfade loop...")
        # To create a seamless loop:
        # We take the LAST fade_frames and blend them into the FIRST fade_frames.
        # The resulting video will be length = len(raw) - fade_frames.
        
        overlap_start = raw_frames[:fade_frames]
        overlap_end = raw_frames[-fade_frames:]
        
        # Blend end into start (Fade Out End / Fade In Start)
        blended = crossfade_frames(overlap_end, overlap_start)
        
        # New sequence: [Blended] + [Middle part]
        # Middle part is raw_frames[fade_frames : -fade_frames]
        # Basically we removed the last chunk (overlap_end) and merged it into the first chunk.
        
        middle_part = raw_frames[fade_frames:-fade_frames]
        processed_raw_frames = blended + middle_part
        
        logger.info(f"Crossfade applied. Final frame count: {len(processed_raw_frames)}")
    elif fade_frames > 0:
        logger.warning(f"Video too short for crossfade ({len(raw_frames)} < {fade_frames}). Skipping crossfade.")

    # --- Step 3 & 4: Transform & Bake ---
    logger.info("Step 3 & 4: Transforming and Baking Overlay...")
    final_frames = []
    
    for i, frame_array in enumerate(processed_raw_frames):
        # a) Rotate
        if rotation:
            frame_array = apply_rotation(frame_array, rotation)
        
        # b) Flip
        if flip:
            frame_array = apply_flip(frame_array, flip)
            
        # c) Resize & Crop
        frame_array = resize_and_crop(frame_array, target_w, target_h, 
                                     crop_x, crop_y, crop_w, crop_h)
        
        # d) Bake Overlay
        frame_array = apply_overlay(frame_array, overlay_img)
        
        final_frames.append(frame_array)
        
        if (i + 1) % 50 == 0:
            logger.info(f"  Processed {i + 1}/{len(processed_raw_frames)} frames...")
            
    # --- Step 5: Encode ---
    
    # --- Step 5: Encode ---
    
    if len(final_frames) < 1:
        logger.error("No frames to encode")
        return False
    
    # Encode output video
    logger.info(f"Encoding output: {output_video_path}")
    
    output_container = av.open(output_video_path, mode='w')
    
    # Configure output stream (H.264, no audio)
    # Convert fps to Fraction for PyAV 16.x compatibility
    fps_fraction = Fraction(fps).limit_denominator(10000)
    output_stream = output_container.add_stream('libx264', rate=fps_fraction)
    output_stream.width = target_w
    output_stream.height = target_h
    output_stream.pix_fmt = 'yuv420p'
    
    # Quality settings (CRF mode for good quality/size balance)
    output_stream.options = {
        'crf': '23',
        'preset': 'medium',
    }
    
    # Encode frames
    for i, frame_array in enumerate(final_frames):
        frame = av.VideoFrame.from_ndarray(frame_array, format='rgb24')
        frame = frame.reformat(format='yuv420p')
        
        for packet in output_stream.encode(frame):
            output_container.mux(packet)
        
        if (i + 1) % 100 == 0:
            logger.info(f"  Encoded {i + 1}/{len(final_frames)} frames...")
    
    # Flush encoder
    for packet in output_stream.encode():
        output_container.mux(packet)
    
    output_container.close()
    
    logger.info("Video processing complete!")
    logger.info(f"Output: {output_video_path}")
    
    # Update theme configuration
    update_theme_config(theme_path, source_video_path, output_video_path)
    
    return True


def update_theme_config(theme_path: Path, source_path: str, processed_path: str):
    """
    Update theme.yaml:
    - Set video_background.LOCAL_PATH to the processed video (relative to theme).
    - Set video_background.REMOTE_PATH to point to the processed filename.
    - Add/Update video_background.SOURCE_PATH to point to the original source.
    """
    import yaml
    
    theme_yaml_path = theme_path / "theme.yaml"
    
    try:
        with open(theme_yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        
        if 'video_background' not in content:
            content['video_background'] = {}
        
        # Calculate relative paths
        processed_rel = os.path.relpath(processed_path, theme_path).replace('\\', '/')
        source_rel = source_path
        if os.path.isabs(source_path):
            try:
                source_rel = os.path.relpath(source_path, theme_path).replace('\\', '/')
            except ValueError:
                pass  # Keep absolute if on different drive
        
        content['video_background']['LOCAL_PATH'] = processed_rel
        content['video_background']['SOURCE_PATH'] = source_rel
        
        # Update REMOTE_PATH filename to match processed video
        current_remote = content['video_background'].get('REMOTE_PATH', '/mnt/SDCARD/video/video.mp4')
        remote_dir = os.path.dirname(current_remote)
        processed_filename = os.path.basename(processed_path)
        content['video_background']['REMOTE_PATH'] = f"{remote_dir}/{processed_filename}".replace('\\', '/')
        
        # Write back
        with open(theme_yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Updated {theme_yaml_path} with new video paths.")
        
    except Exception as e:
        logger.error(f"Failed to update theme config: {e}")
