import os
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional, Union, Dict
from library.log import logger

def draw_icon(
    canvas: Image.Image,
    text: str,
    xy: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str = "la"
) -> None:
    """Draw an icon (text character) onto the canvas."""
    draw = ImageDraw.Draw(canvas)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)

def get_icon_bbox(
    text: str,
    font: ImageFont.FreeTypeFont,
    xy: Tuple[int, int] = (0, 0),
    anchor: str = "la"
) -> Tuple[int, int, int, int]:
    """Get the bounding box of an icon."""
    dummy = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy)
    return draw.textbbox(xy, text, font=font, anchor=anchor)

def render_icon_block(
    text: str,
    font_path: str,
    font_size: int,
    color: Tuple[int, int, int, int],
    sampling: int = 4,
    outline_config: Optional[Dict] = None
) -> Tuple[Image.Image, Tuple[int, int]]:
    """Render an icon block to an image with Multisampled anti-aliasing."""
    if not text: return Image.new('RGBA', (1,1), (0,0,0,0)), 0, 0
    
    s_size = int(font_size * sampling)
    try:
        font = ImageFont.truetype(font_path, s_size)
    except OSError:
        logger.warning(f"Could not load font {font_path}, fallback to default")
        font = ImageFont.load_default()

    # Calculate size at supersampled scale
    dummy = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # Add padding
    pad = int(s_size * 0.1) + 5 * sampling
    img_w, img_h = w + pad * 2, h + pad * 2
    img = Image.new('RGBA', (int(img_w), int(img_h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=color)
    
    dx, dy = 0, 0
    if outline_config:
        from library.rendering.effects import apply_outline
        width = outline_config.get('width', 0)
        color = outline_config.get('color', (255, 255, 255, 255))
        if width > 0:
            img, ox, oy = apply_outline(img, width * sampling, color)
            dx -= ox / sampling
            dy -= oy / sampling

    # Cropping to content
    bbox_crop = img.getbbox()
    if bbox_crop:
        # Before crop, we need to adjust dx, dy by the crop offset
        dx -= bbox_crop[0] / sampling
        dy -= bbox_crop[1] / sampling
        img = img.crop(bbox_crop)
    
    # Downscale
    new_w, new_h = img.width // sampling, img.height // sampling
    if new_w > 0 and new_h > 0:
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
    return img, int(dx), int(dy)
