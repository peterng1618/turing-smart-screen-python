import math
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

def draw_progress_bar(
    canvas: Image.Image,
    rect: Tuple[int, int, int, int],  # (x, y, width, height) relative to canvas
    value: float,
    min_value: float = 0,
    max_value: float = 100,
    bar_color: Tuple[int, int, int] = (0, 0, 0),
    bar_outline: bool = True
) -> None:
    """Draw a horizontal progress bar on the provided canvas."""
    x, y, width, height = rect
    
    # Clamp value
    value = max(min(value, max_value), min_value)
    
    # Calculate filled width
    range_val = max_value - min_value
    if range_val == 0:
        bar_filled_width = 0
    else:
        bar_filled_width = (value - min_value) / range_val * width - 1
        
    bar_filled_width = max(0, bar_filled_width)
    
    draw = ImageDraw.Draw(canvas)
    
    # Draw background/fill
    draw.rectangle([x, y, x + bar_filled_width, y + height - 1], fill=bar_color, outline=bar_color)
    
    if bar_outline:
        draw.rectangle([x, y, x + width - 1, y + height - 1], fill=None, outline=bar_color)

def draw_line_graph(
    canvas: Image.Image,
    rect: Tuple[int, int, int, int],  # (x, y, width, height)
    values: List[float],
    min_value: float = 0,
    max_value: float = 100,
    autoscale: bool = False,
    line_color: Tuple[int, int, int] = (0, 0, 0),
    line_width: int = 2,
    graph_axis: bool = True,
    axis_color: Tuple[int, int, int] = (0, 0, 0),
    axis_font: Optional[ImageFont.FreeTypeFont] = None
) -> None:
    """Draw a line graph on the provided canvas."""
    x, y, width, height = rect
    
    if autoscale:
        valid_values = [v for v in values if not math.isnan(v)]
        if valid_values:
            true_min = min(valid_values)
            true_max = max(valid_values)
            min_value = max(true_min - 5, min_value)
            max_value = min(true_max + 5, max_value)

    step = width / len(values) if len(values) > 1 else width
    range_val = max_value - min_value
    y_scale = height / range_val if range_val != 0 else 0

    plots_x = []
    plots_y = []
    for i, value in enumerate(values):
        if not math.isnan(value):
            value = max(min(value, max_value), min_value)
            plots_x.append(i * step)
            plots_y.append(height - (value - min_value) * y_scale)

    draw = ImageDraw.Draw(canvas)
    if len(plots_x) > 1:
        # Shift plots by x, y
        shifted_plots = [(px + x, py + y) for px, py in zip(plots_x, plots_y)]
        draw.line(shifted_plots, fill=line_color, width=line_width)

    if graph_axis:
        draw.line([x, y + height - 1, x + width - 1, y + height - 1], fill=axis_color)
        draw.line([x, y, x, y + height - 1], fill=axis_color)
        
        if axis_font:
            # Draw labels
            max_text = f"{int(max_value)}"
            _, top, _, _ = axis_font.getbbox(max_text)
            draw.text((x + 2, y + 0 - top), max_text, font=axis_font, fill=axis_color)

            min_text = f"{int(min_value)}"
            _, _, right, bottom = axis_font.getbbox(min_text)
            draw.text((x + width - 1 - right, y + height - 2 - bottom), min_text, font=axis_font, fill=axis_color)

def draw_radial_progress_bar(
    canvas: Image.Image,
    center: Tuple[int, int],
    radius: int,
    bar_width: int,
    value: float,
    min_value: float = 0,
    max_value: float = 100,
    angle_start: float = 0,
    angle_end: float = 360,
    angle_sep: int = 0,
    angle_steps: int = 1,
    clockwise: bool = True,
    bar_color: Tuple[int, int, int] = (0, 0, 0),
    bar_background_color: Tuple[int, int, int] = (0, 0, 0),
    draw_bar_background: bool = False,
    bar_decoration: str = "",
    text: Optional[str] = None,
    font: Optional[ImageFont.FreeTypeFont] = None,
    font_color: Tuple[int, int, int] = (0, 0, 0),
    text_offset: Tuple[int, int] = (0, 0)
) -> None:
    """Draw a radial progress bar on the provided canvas (assumed to be square of 2*radius)."""
    xc, yc = center
    diameter = 2 * radius
    
    # Handle the "full circle" case avoiding start==end
    angle_start_norm = angle_start % 360
    angle_end_norm = angle_end % 360
    if angle_start_norm == angle_end_norm:
        if clockwise:
            angle_start += 0.1
        else:
            angle_end += 0.1

    value = max(min(value, max_value), min_value)
    pct = (value - min_value) / (max_value - min_value) if (max_value - min_value) != 0 else 0
    
    draw = ImageDraw.Draw(canvas)
    
    # Calculate span
    if clockwise:
        ecart = (angle_end - angle_start) % 360
        if ecart == 0: ecart = 360
    else:
        ecart = (angle_start - angle_end) % 360
        if ecart == 0: ecart = 360

    # Draw background
    if draw_bar_background:
        s, e = (angle_start, angle_start + ecart) if clockwise else (angle_start - ecart, angle_start)
        draw.arc([xc - radius, yc - radius, xc + radius - 1, yc + radius - 1], s, e, fill=bar_background_color, width=bar_width)

    # Draw decoration
    if bar_decoration == "Ellipse":
        _draw_radial_decoration(draw, angle_end, radius, bar_width, bar_background_color)
        _draw_radial_decoration(draw, angle_start, radius, bar_width, bar_color)
        target_angle = angle_start + (pct * ecart) if clockwise else angle_start - (pct * ecart)
        _draw_radial_decoration(draw, target_angle, radius, bar_width, bar_color)

    # Draw bar
    if angle_sep == 0:
        s, e = (angle_start, angle_start + pct * ecart) if clockwise else (angle_start - pct * ecart, angle_start)
        draw.arc([xc - radius, yc - radius, xc + radius - 1, yc + radius - 1], s, e, fill=bar_color, width=bar_width)
    else:
        # Discontinued bar
        angle_complet = ecart / angle_steps
        etapes = int((pct * ecart) / angle_complet)
        for i in range(etapes):
            if clockwise:
                s = angle_start + i * angle_complet
                e = s + angle_complet - angle_sep
            else:
                e = angle_start - i * angle_complet
                s = e - angle_complet + angle_sep
            draw.arc([xc - radius, yc - radius, xc + radius - 1, yc + radius - 1], s, e, fill=bar_color, width=bar_width)
        
        # Draw remainder
        if clockwise:
            s_rem = angle_start + etapes * angle_complet
            e_rem = angle_start + pct * ecart
        else:
            e_rem = angle_start - etapes * angle_complet
            s_rem = angle_start - pct * ecart
        if (clockwise and e_rem > s_rem) or (not clockwise and s_rem < e_rem):
             draw.arc([xc - radius, yc - radius, xc + radius - 1, yc + radius - 1], s_rem, e_rem, fill=bar_color, width=bar_width)

    # Draw text
    if text is not None and font:
        left, top, right, bottom = font.getbbox(text)
        w, h = right - left, bottom - top
        draw.text(
            (xc - w / 2 + text_offset[0], yc - top - h / 2 + text_offset[1]),
            text,
            font=font,
            fill=font_color
        )

def _draw_radial_decoration(draw: ImageDraw.ImageDraw, angle: float, radius: float, width: float, color: Tuple[int, int, int]):
    i_cos = math.cos(angle * math.pi / 180)
    i_sin = math.sin(angle * math.pi / 180)
    
    def round_center(val, i_func):
        v = (i_func * (radius - width/2)) + radius
        if math.modf(v)[0] == 0.5:
             return math.floor(v) if i_func > 0 else math.ceil(v)
        return math.floor(v + 0.5)

    x_f = round_center(angle, i_cos)
    y_f = round_center(angle, i_sin)
    
    draw.ellipse([x_f - width/2, y_f - width/2, x_f + width/2, y_f - 1 + width/2 - 1], outline=color, fill=color, width=1)
