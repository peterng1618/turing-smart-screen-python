import os
from typing import Tuple, List, Optional, Dict, Union
from PIL import Image, ImageColor, ImageDraw, ImageFont

from library.log import logger
from library.lcd.color import Color, parse_color
import library.rendering.text as rendering_text
import library.rendering.image as rendering_image
import library.rendering.graphs as rendering_graphs
import library.rendering.effects as rendering_effects

def resolve_color(color_value: Union[str, Tuple, List, Color], override_alpha: Optional[float] = None) -> Tuple[int, int, int, int]:
    """
    Resolve various color formats (string, tuple, hex) to an RGBA tuple.
    Consistent with legacy LcdComm and UiRenderer behavior.
    """
    color = (0, 0, 0, 255) # Default
    
    if isinstance(color_value, str):
        # Check for "R, G, B" or "R, G, B, A" format
        if ',' in color_value:
            parts = [p.strip() for p in color_value.split(',')]
            if len(parts) in (3, 4):
                try:
                    c = tuple(int(p) for p in parts)
                    if len(c) == 3:
                        color = c + (255,)
                    else:
                        color = c
                except ValueError:
                    pass
        else:
            try:
                c = ImageColor.getrgb(color_value)
                color = c + (255,) if len(c) == 3 else c
            except ValueError:
                logger.warning(f"Invalid color string: {color_value}")
    elif isinstance(color_value, (list, tuple)):
        if len(color_value) == 3: color = tuple(color_value) + (255,)
        elif len(color_value) >= 4: color = tuple(color_value[:4])
    
    if override_alpha is not None:
         # override_alpha is expected to be 0-255 or 0.0-1.0? 
         # UiRenderer uses 0-255 (int). LcdComm uses 0.0-1.0 (float).
         # We'll support both by checking if it's <= 1.0
         alpha = int(override_alpha) if override_alpha > 1.0 else int(override_alpha * 255)
         color = (color[0], color[1], color[2], alpha)
         
    return color

def composite_background(
    width: int, 
    height: int, 
    background_color: Tuple[int, int, int, int], 
    background_image: Optional[Image.Image] = None,
    crop_xy: Tuple[int, int] = (0, 0)
) -> Image.Image:
    """Create a canvas with either a solid color or a cropped background image."""
    if background_image is None:
        return Image.new('RGBA', (width, height), background_color)
    else:
        # background_image is assumed to be the full theme background or similar
        return background_image.crop(box=(crop_xy[0], crop_xy[1], crop_xy[0] + width, crop_xy[1] + height)).convert('RGBA')

def text(
    canvas: Image.Image,
    text_str: str,
    xy: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    color: Tuple[int, int, int, int],
    align: str = 'left',
    anchor: str = 'la',
    opacity: float = 1.0,
    rotation: float = 0,
    shadow: Optional[Dict] = None,
    outline: Optional[Dict] = None,
) -> Tuple[int, int, int, int]:
    """
    High-level text drawing with effects.
    Returns the bounding box (x, y, w, h) of the DRAWN content relative to canvas origin.
    """
    # Prepare outline config
    outline_cfg = None
    if outline:
         outline_cfg = {
             'color': resolve_color(outline.get('color', (0,0,0,255))),
             'width': outline.get('width', 1)
         }

    # Render text block
    res_image, dx, dy = rendering_text.render_text_block(
        text=text_str, 
        color=color, 
        font=font,
        align=align, 
        anchor=anchor, 
        outline_config=outline_cfg
    )

    # Apply shadow, rotation, opacity
    shadow_cfg = None
    if shadow:
        shadow_cfg = {
            'color': resolve_color(shadow.get('color', (0,0,0,128))),
            'blur': shadow.get('blur', 5),
            'offset': shadow.get('offset', (5,5))
        }

    res_image, s_dx, s_dy = rendering_effects.apply_styling(
        res_image, 
        opacity=opacity, 
        rotation=rotation, 
        shadow=shadow_cfg
    )

    # Final position relative to requested xy
    render_x = xy[0] + dx + s_dx
    render_y = xy[1] + dy + s_dy

    # Composite
    canvas.alpha_composite(res_image, (int(render_x), int(render_y)))
    
    return (int(render_x), int(render_y), res_image.width, res_image.height)

def progress_bar(
    canvas: Image.Image,
    xy_wh: Tuple[int, int, int, int],
    value: float,
    min_value: float = 0,
    max_value: float = 100,
    bar_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    bar_outline: bool = True
):
    """Draw a progress bar onto the canvas."""
    rendering_graphs.draw_progress_bar(
        canvas, xy_wh, value, min_value, max_value, bar_color, bar_outline
    )

def line_graph(
    canvas: Image.Image,
    xy_wh: Tuple[int, int, int, int],
    values: List[float],
    min_value: float = 0,
    max_value: float = 100,
    autoscale: bool = False,
    line_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    line_width: int = 2,
    graph_axis: bool = True,
    axis_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    axis_font: Optional[ImageFont.FreeTypeFont] = None
):
    """Draw a line graph onto the canvas."""
    rendering_graphs.draw_line_graph(
        canvas, xy_wh, values, min_value, max_value,
        autoscale, line_color, line_width, graph_axis, axis_color, axis_font
    )

def radial_progress_bar(
    canvas: Image.Image,
    xc_yc_radius: Tuple[int, int, int],
    bar_width: int,
    value: float,
    min_value: float = 0,
    max_value: float = 100,
    angle_start: float = 0,
    angle_end: float = 360,
    angle_sep: int = 5,
    angle_steps: int = 10,
    clockwise: bool = True,
    text_str: Optional[str] = None,
    font: Optional[ImageFont.FreeTypeFont] = None,
    font_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    bar_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    text_offset: Tuple[int, int] = (0,0),
    bar_background_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    draw_bar_background: bool = False,
    bar_decoration: str = ""
):
    """Draw a radial progress bar onto the canvas."""
    xc, yc, radius = xc_yc_radius
    
    # xc, yc in radial_progress_bar (graphs.py) are relative to the canvas provided.
    # But LcdComm.DisplayRadialProgressBar creates a diameter x diameter image and draws at (radius, radius)
    # We'll assume the canvas passed here is the target area.
    
    rendering_graphs.draw_radial_progress_bar(
        canvas, (xc, yc), radius, bar_width, value, min_value, max_value,
        angle_start, angle_end, angle_sep, angle_steps, clockwise,
        bar_color, bar_background_color, draw_bar_background, bar_decoration,
        text_str, font, font_color, text_offset
    )
