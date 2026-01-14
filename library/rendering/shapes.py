import math
from typing import Tuple, Optional, Union, List, Dict
from PIL import Image, ImageDraw

def draw_rectangle(
    canvas: Image.Image,
    rect: Tuple[int, int, int, int],  # (x, y, width, height)
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1
) -> None:
    """Draw a rectangle."""
    x, y, w, h = rect
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, w - 1, h - 1], fill=fill, outline=outline, width=width)

def draw_ellipse(
    canvas: Image.Image,
    rect: Tuple[int, int, int, int],
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1
) -> None:
    """Draw an ellipse."""
    x, y, w, h = rect
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([0, 0, w - 1, h - 1], fill=fill, outline=outline, width=width)

def draw_line(
    canvas: Image.Image,
    xy: list, # List of (x, y)
    fill: Tuple[int, int, int, int] = (0, 0, 0, 255),
    width: int = 1
) -> None:
    """Draw a line."""
    draw = ImageDraw.Draw(canvas)
    draw.line(xy, fill=fill, width=width)

def draw_arc(
    canvas: Image.Image,
    rect: Tuple[int, int, int, int],
    start: float,
    end: float,
    fill: Tuple[int, int, int, int] = (0, 0, 0, 255),
    width: int = 1
) -> None:
    """Draw an arc."""
    x, y, w, h = rect
    draw = ImageDraw.Draw(canvas)
    draw.arc([0, 0, w - 1, h - 1], start, end, fill=fill, width=width)

def get_rounded_polygon_path(vertices: List[Tuple[float, float]], radius: float) -> List[Tuple[float, float]]:
    """Calculate high-precision path for a rounded convex polygon."""
    num = len(vertices)
    if radius <= 0: return vertices

    # Shoelace formula to ensure CW order (Y-down)
    area = 0
    for i in range(num):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % num]
        area += (p2[0] - p1[0]) * (p2[1] + p1[1])
    if area > 0:
        vertices = list(reversed(vertices))
    
    # Calculate edges and inward normals
    normals = []
    edges = []
    lengths = []
    for i in range(num):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % num]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        l = math.hypot(dx, dy)
        if l == 0: continue
        edges.append((p1, p2))
        normals.append((-dy/l, dx/l))
        lengths.append(l)
    
    num = len(edges)
    if num < 3: return vertices

    centers = []
    for i in range(num):
        n_prev = normals[(i - 1 + num) % num]
        n_curr = normals[i]
        e_prev = edges[(i - 1 + num) % num]
        e_curr = edges[i]
        
        dot = max(-1, min(1, n_prev[0]*n_curr[0] + n_prev[1]*n_curr[1]))
        alpha = math.acos(dot)
        theta = math.pi - alpha
        
        half_min_edge = min(lengths[(i-1+num)%num], lengths[i]) / 2.0
        r_limit = half_min_edge * math.tan(theta/2.0)
        corner_radius = min(radius, r_limit)
        
        # Shifted lines intersection
        def intersect(p1, p2, p3, p4):
            x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            if abs(denom) < 1e-9: return None
            ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
            return (x1 + ua * (x2 - x1), y1 + ua * (y2 - y1))

        s_prev_1 = (e_prev[0][0] + n_prev[0] * corner_radius, e_prev[0][1] + n_prev[1] * corner_radius)
        s_prev_2 = (e_prev[1][0] + n_prev[0] * corner_radius, e_prev[1][1] + n_prev[1] * corner_radius)
        s_curr_1 = (e_curr[0][0] + n_curr[0] * corner_radius, e_curr[0][1] + n_curr[1] * corner_radius)
        s_curr_2 = (e_curr[1][0] + n_curr[0] * corner_radius, e_curr[1][1] + n_curr[1] * corner_radius)
        
        center = intersect(s_prev_1, s_prev_2, s_curr_1, s_curr_2)
        centers.append((center if center else e_curr[0], corner_radius))
        
    poly_points = []
    for i in range(num):
        center, r = centers[i]
        n_prev = normals[(i - 1 + num) % num]
        n_curr = normals[i]
        start_angle = math.atan2(-n_prev[1], -n_prev[0])
        end_angle = math.atan2(-n_curr[1], -n_curr[0])
        if end_angle < start_angle: end_angle += 2 * math.pi
        steps = 12
        for s in range(steps + 1):
            angle = start_angle + (end_angle - start_angle) * (s / steps)
            poly_points.append((center[0] + math.cos(angle) * r, center[1] + math.sin(angle) * r))
    return poly_points

def draw_dashed_path(draw: ImageDraw.ImageDraw, points: List[Tuple[float, float]], width: int, color: Tuple[int, int, int, int], dash_array: Tuple[int, int], closed: bool = True) -> None:
    """Draw high-quality dashed segments along a path."""
    if not points: return
    pts = list(points)
    if closed: pts.append(pts[0])
    dash_len, gap_len = dash_array[0], dash_array[1]
    current_offset = 0
    is_dash = True
    dash_pts = []
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i+1]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist == 0: continue
        vx, vy = dx / dist, dy / dist
        rem = dist
        seg_off = 0
        while rem > 0:
            target = dash_len if is_dash else gap_len
            space = target - current_offset
            step = min(rem, space)
            if is_dash:
                if not dash_pts: dash_pts.append((p1[0] + vx * seg_off, p1[1] + vy * seg_off))
                dash_pts.append((p1[0] + vx * (seg_off + step), p1[1] + vy * (seg_off + step)))
            seg_off += step
            current_offset += step
            rem -= step
            if current_offset >= target - 1e-6:
                if is_dash and len(dash_pts) > 1:
                    draw.line(dash_pts, fill=color, width=width, joint='curve')
                dash_pts, current_offset, is_dash = [], 0, not is_dash
    if is_dash and len(dash_pts) > 1:
        draw.line(dash_pts, fill=color, width=width, joint='curve')

def draw_rounded_polygon(draw: ImageDraw.ImageDraw, vertices: List[Tuple[float, float]], radius: float, fill: Optional[Tuple[int, int, int, int]] = None, outline: Optional[Tuple[int, int, int, int]] = None, width: int = 1, dash_array: Optional[Tuple[int, int]] = None) -> None:
    """Draw a convex polygon with rounded corners."""
    poly_points = get_rounded_polygon_path(vertices, radius)
    if fill: draw.polygon(poly_points, fill=fill)
    if outline and width > 0:
        if dash_array:
            draw_dashed_path(draw, poly_points, width, outline, dash_array, closed=True)
        else:
            draw.line(poly_points + [poly_points[0]], fill=outline, width=width, joint='curve')

def draw_dashed_line(draw: ImageDraw.ImageDraw, p1: Tuple[float, float], p2: Tuple[float, float], width: int, color: Tuple[int, int, int, int], dash_array: Tuple[int, int], cap: str = 'butt') -> None:
    """Draw a dashed line between p1 and p2."""
    x1, y1 = p1; x2, y2 = p2
    dash_len, gap_len = dash_array[0], dash_array[1]
    total_dist = math.hypot(x2 - x1, y2 - y1)
    if total_dist == 0: return
    vx, vy = (x2 - x1) / total_dist, (y2 - y1) / total_dist
    current_dist = 0
    while current_dist < total_dist:
        seg_len = min(dash_len, total_dist - current_dist)
        if seg_len <= 0 and dash_len > 0: break
        start_x, start_y = x1 + vx * current_dist, y1 + vy * current_dist
        end_x, end_y = x1 + vx * (current_dist + seg_len), y1 + vy * (current_dist + seg_len)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
        if cap == 'round':
            r = width / 2
            draw.ellipse([start_x - r, start_y - r, start_x + r, start_y + r], fill=color)
            draw.ellipse([end_x - r, end_y - r, end_x + r, end_y + r], fill=color)
        current_dist += dash_len + gap_len

def get_sheared_rect_vertices(w: float, h: float, shear_left: float, shear_right: float) -> List[Tuple[float, float]]:
    """Calculate vertices for a sheared rectangle."""
    half_h = h / 2
    left_offset = half_h * math.tan(math.radians(shear_left))
    right_offset = half_h * math.tan(math.radians(shear_right))
    
    tl = (left_offset, 0)
    tr = (w + right_offset, 0)
    br = (w - right_offset, h)
    bl = (-left_offset, h)
    return [tl, tr, br, bl]

def render_shape_to_image(
    shape_type: str,
    shape_config: Dict,
    fill_color: Tuple[int, int, int, int],
    outline_config: Optional[Dict] = None,
    sampling: int = 4
) -> Tuple[Image.Image, Tuple[float, float]]:
    """
    High-level function to render a shape to an RGBA image with multisampling.
    Returns (image, (dx, dy)) where dx, dy is the offset to apply to the original (x, y).
    """
    w = shape_config.get('width', 0)
    h = shape_config.get('height', 0)
    radius = (shape_config.get('radius', 0) or 0) * sampling
    
    outline_width = outline_config.get('width', 0) if outline_config else 0
    outline_color = outline_config.get('color', (255, 255, 255, 255)) if outline_config else None
    dash_array = outline_config.get('dash_array') if outline_config else None
    s_dash_array = [v * sampling for v in dash_array] if dash_array else None
    
    pad = math.ceil(outline_width / 2) + 1
    s_pad = pad * sampling
    s_outline = outline_width * sampling

    if shape_type == 'line':
        x1, y1 = shape_config.get('x', 0), shape_config.get('y', 0)
        x2, y2 = shape_config.get('x2', 0), shape_config.get('y2', 0)
        lx, ly = min(x1, x2), min(y1, y2)
        lw, lh = abs(x2 - x1), abs(y2 - y1)
        
        s_lw, s_lh = lw * sampling, lh * sampling
        # Extra padding for lines to ensure caps aren't cut
        line_pad = 10 * sampling
        s_canvas_w = int(s_lw + s_outline + line_pad * 2)
        s_canvas_h = int(s_lh + s_outline + line_pad * 2)
        
        img = Image.new('RGBA', (s_canvas_w, s_canvas_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        s_off_x = (lx * sampling) - line_pad
        s_off_y = (ly * sampling) - line_pad
        s_p1 = (x1 * sampling - s_off_x, y1 * sampling - s_off_y)
        s_p2 = (x2 * sampling - s_off_x, y2 * sampling - s_off_y)
        
        cap_style = (outline_config or {}).get('cap', 'butt')
        s_w = w * sampling

        def _draw_line_internal(dr, pt1, pt2, wd, col, dashes, cap):
            if dashes:
                draw_dashed_line(dr, pt1, pt2, wd, col, dashes, cap)
            else:
                dr.line([pt1, pt2], fill=col, width=wd)
                if cap == 'round':
                    r = wd / 2
                    dr.ellipse([pt1[0]-r, pt1[1]-r, pt1[0]+r, pt1[1]+r], fill=col)

        if outline_color:
            _draw_line_internal(d, s_p1, s_p2, int(s_w + s_outline*2), outline_color, s_dash_array, cap_style)
        _draw_line_internal(d, s_p1, s_p2, int(s_w), fill_color, s_dash_array, cap_style)
        
        dx = (s_off_x / sampling) - x1
        dy = (s_off_y / sampling) - y1
        
    elif shape_type == 'rectangle' or shape_type == 'triangle':
        if shape_type == 'rectangle':
            sl = shape_config.get('shear_left', 0)
            sr = shape_config.get('shear_right', 0)
            vertices = get_sheared_rect_vertices(w, h, sl, sr)
        else:
            x1, y1 = shape_config.get('x1', 0), shape_config.get('y1', 0)
            x2, y2 = shape_config.get('x2', 0), shape_config.get('y2', 0)
            x3, y3 = shape_config.get('x3', 0), shape_config.get('y3', 0)
            # Use relative points if provided, otherwise absolute (though theme usually uses absolute)
            # We normalize to local min_x, min_y
            mx = min(x1, x2, x3)
            my = min(y1, y2, y3)
            vertices = [(x1-mx, y1-my), (x2-mx, y2-my), (x3-mx, y3-my)]
            
        # Calculate bounding box for the vertices
        v_xs = [v[0] for v in vertices]
        v_ys = [v[1] for v in vertices]
        min_vx, max_vx = min(v_xs), max(v_xs)
        min_vy, max_vy = min(v_ys), max(v_ys)
        
        v_w = max_vx - min_vx
        v_h = max_vy - min_vy
        
        s_v_w = v_w * sampling
        s_v_h = v_h * sampling
        
        s_canvas_w = int(s_v_w + s_pad * 2)
        s_canvas_h = int(s_v_h + s_pad * 2)
        
        img = Image.new('RGBA', (s_canvas_w, s_canvas_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        s_vertices = [((v[0] - min_vx) * sampling + s_pad, (v[1] - min_vy) * sampling + s_pad) for v in vertices]
        
        draw_rounded_polygon(d, s_vertices, radius, 
                             fill=fill_color if fill_color[3] > 0 else None,
                             outline=outline_color,
                             width=int(s_outline),
                             dash_array=s_dash_array)
        
        # dx, dy is relative to the shape's pivot (x, y) or (x1, y1)
        # For rect, (x, y) is TopLeft of NON-SHEARED rect.
        # min_vx might be negative (if sheared left).
        dx = (min_vx - pad)
        dy = (min_vy - pad)
        
    elif shape_type == 'ellipse':
        s_canvas_w = int((w + pad * 2) * sampling)
        s_canvas_h = int((h + pad * 2) * sampling)
        
        img = Image.new('RGBA', (s_canvas_w, s_canvas_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        bounds = [s_pad, s_pad, s_pad + w * sampling, s_pad + h * sampling]
        d.ellipse(bounds, fill=fill_color, outline=outline_color, width=int(s_outline))
        dx, dy = -pad, -pad
    else:
        return Image.new('RGBA', (1,1), (0,0,0,0)), 0, 0

    # Downscale
    final_w = img.width // sampling
    final_h = img.height // sampling
    if final_w > 0 and final_h > 0:
        img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
    
    return img, int(dx), int(dy)
