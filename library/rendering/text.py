import math
import os
from typing import Tuple, Optional, List
from PIL import Image, ImageDraw, ImageFont
from library.log import logger

def draw_text(
    canvas: Image.Image,
    text: str,
    xy: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str = "la",
    align: str = "left"
) -> None:
    """Draw text on the provided PIL canvas."""
    draw = ImageDraw.Draw(canvas)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor, align=align)

def get_text_bbox(
    text: str,
    font: ImageFont.FreeTypeFont,
    xy: Tuple[int, int] = (0, 0),
    anchor: str = "la",
    align: str = "left"
) -> Tuple[int, int, int, int]:
    """Calculate the bounding box of the text. Returns (left, top, right, bottom)."""
    # Create a dummy image to get the draw object
    dummy = Image.new('1', (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox(xy, text, font=font, anchor=anchor, align=align)
    
    # Extend to next whole pixel as per existing logic in LcdComm
    return (
        math.floor(bbox[0]),
        math.floor(bbox[1]),
        math.ceil(bbox[2]),
        math.ceil(bbox[3])
    )

def render_text_block(
    text: str,
    font_path: Optional[str] = None,
    font_size: Optional[int] = None,
    color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    sampling: int = 1,
    outline_config: Optional[dict] = None,
    font: Optional[ImageFont.FreeTypeFont] = None,
    align: str = "left",
    anchor: str = "la"
) -> Tuple[Image.Image, int, int]:
    """Render a text block to an image with optional supersampling and outline."""
    if not text: return Image.new('RGBA', (1,1), (0,0,0,0)), 0, 0
    
    # Load font if not provided
    if font is None:
        if font_path and font_size:
            s_size = int(font_size * sampling)
            try:
                font = ImageFont.truetype(font_path, s_size)
            except OSError:
                logger.warning(f"Could not load font {font_path}, fallback to default")
                font = ImageFont.load_default()
        else:
            font = ImageFont.load_default()
    elif sampling > 1:
        # If font provided but sampling requested, we might need to reload or just accept current size
        # Usually for pre-loaded fonts in LcdComm, sampling is 1.
        pass

    # Calculate size at current font scale (if sampling > 1, font is already scaled)
    dummy = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy)
    
    # We use anchor="la" for the internal buffer drawing to simplify bounding box logic,
    # but we store the real anchor offsets.
    bbox = draw.textbbox((0, 0), text, font=font, anchor=anchor, align=align)
    
    # Bounding box is relative to the anchor point (0,0)
    # We need to map this to an image with top-left at (0,0)
    left, top, right, bottom = bbox
    w = int(math.ceil(right - left))
    h = int(math.ceil(bottom - top))

    # Create image with some padding to avoid clipping during anti-aliasing or rotated drawing
    pad = 2 * sampling
    img_w, img_h = w + pad * 2, h + pad * 2
    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Draw text such that the requested anchor point (0,0) is at (pad - left, pad - top)
    d.text((pad - left, pad - top), text, font=font, fill=color, anchor=anchor, align=align)
    
    # Cropping to content
    bbox_crop = img.getbbox()
    if bbox_crop: 
        # Calculate how much we cropped from the left/top to maintain coordinate parity
        img = img.crop(bbox_crop)
        crop_left, crop_top, _, _ = bbox_crop
    else:
        crop_left, crop_top = 0, 0
    
    # Offset from requested (x,y) to current top-left of img
    # If anchor was "la", x=0, y=0. bbox[0]=0, bbox[1]=0.
    # draw point was (pad, pad). If bbox_crop[0]=pad, crop_left=pad.
    # final dx = left + crop_left - pad
    dx = left + crop_left - pad
    dy = top + crop_top - pad

    # Downscale if sampling used
    if sampling > 1:
        new_w, new_h = img.width // sampling, img.height // sampling
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            dx //= sampling
            dy //= sampling
    
    if outline_config:
        from . import effects
        width = outline_config.get('width', 0)
        outline_color = outline_config.get('color', (255, 255, 255, 255))
        img, px, py = effects.apply_outline(img, width, outline_color)
        dx -= px
        dy -= py
        
    return img, int(dx), int(dy)
