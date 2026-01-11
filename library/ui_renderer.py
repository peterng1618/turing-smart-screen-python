# SPDX-License-Identifier: GPL-3.0-or-later
import os
import math
from PIL import Image, ImageDraw, ImageFilter, ImageColor, ImageFont, ImageChops

from library.log import logger
from library import config # We need config to access FONTS_DIR if needed or pass it in
from library.font_manager import font_manager

class UiRenderer:
    def __init__(self, theme_data, theme_path):
        """
        Initialize the UI Renderer.
        
        :param theme_data: Dictionary containing the theme configuration (loaded from YAML).
        :param theme_path: Base path for the theme (to resolve relative image paths).
        """
        self.theme_data = theme_data
        self.theme_path = theme_path
        self.width = 480  # Default, will be updated from display config
        self.height = 320 # Default
        
        self._parse_display_size()

    def _parse_display_size(self):
        """Parse display size from theme configuration."""
        if 'display' in self.theme_data:
            orientation = self.theme_data['display'].get('DISPLAY_ORIENTATION', 'portrait')
            size_str = self.theme_data['display'].get('DISPLAY_SIZE', '3.5"')
            
            w, h = 320, 480 # Default
            if size_str == '3.5"': w, h = 320, 480
            elif size_str == '5"': w, h = 480, 800
            elif size_str == '2.1"': w, h = 480, 480
            elif size_str == '8.8"': w, h = 480, 1920
                
            # Swap if landscape
            if orientation == 'landscape':
                 self.width = h
                 self.height = w
            else:
                self.width = w
                self.height = h

    def _resolve_color(self, color_value, override_alpha=None):
        """Resolve color to RGBA tuple."""
        color = (0, 0, 0, 255) # Default
        if isinstance(color_value, str):
            # Check for "R, G, B" or "R, G, B, A" format common in this project
            if ',' in color_value:
                parts = [p.strip() for p in color_value.split(',')]
                if len(parts) in (3, 4):
                    try:
                        c = tuple(int(p) for p in parts)
                        if len(c) == 3:
                            color = c + (255,)
                        else:
                            color = c
                        
                        if override_alpha is not None:
                             color = (color[0], color[1], color[2], int(override_alpha))
                        return color
                    except ValueError:
                        pass # Valid comma string but invalid ints, fall through to ImageColor

            try:
                c = ImageColor.getrgb(color_value)
                color = c + (255,) if len(c) == 3 else c
            except ValueError:
                logger.warning(f"Invalid color string: {color_value}")
        elif isinstance(color_value, (list, tuple)):
            if len(color_value) == 3: color = tuple(color_value) + (255,)
            elif len(color_value) >= 4: color = tuple(color_value[:4])
        
        if override_alpha is not None:
             color = (color[0], color[1], color[2], int(override_alpha))
        return color

    def _create_shadow_layer(self, shape_img, shadow_config):
        """Create a shadow layer from the shape image, handling expanding blur."""
        if not shadow_config: return None
        blur = shadow_config.get('blur', 5)
        color = self._resolve_color(shadow_config.get('color', 'black'))
        offset_x = shadow_config.get('offset_x', 5)
        offset_y = shadow_config.get('offset_y', 5)
        
        # Original mask
        mask = shape_img.split()[3]
        
        # Calculate padding needed for blur to spread
        # 3 sigma is good rule of thumb for Gaussian
        padding = int(blur * 3) if blur > 0 else 0
        
        new_w = shape_img.width + padding * 2
        new_h = shape_img.height + padding * 2
        
        # Create a large mask canvas
        # 1. Place original alpha in center
        expanded_mask = Image.new('L', (new_w, new_h), 0)
        expanded_mask.paste(mask, (padding, padding))
        
        # 2. Blur the mask
        if blur > 0:
            expanded_mask = expanded_mask.filter(ImageFilter.GaussianBlur(blur))
            
        # 3. Create shadow block with this alpha
        shadow = Image.new('RGBA', (new_w, new_h), color)
        shadow.putalpha(expanded_mask)
        
        # Adjust offset because we added padding to the top-left (so we must shift "draw" position left/up)
        return shadow, offset_x - padding, offset_y - padding

    def _apply_image_outline(self, img, outline_config):
        """
        Apply an outline (stroke) to an image by dilating its alpha channel.
        Returns a new image (larger by 2*width) with the outline composited behind.
        """
        if not outline_config: return img, 0, 0
        
        width = outline_config.get('width', 0)
        if width <= 0: return img, 0, 0
        
        color = self._resolve_color(outline_config.get('color', 'white'))
        
        # Dilation kernel size. 
        # width=1 -> 1px expansion on all sides? 
        # MaxFilter w/ size=3 (radius 1) examines 1 pixel around.
        # size = w*2 + 1
        filter_size = width * 2 + 1
        
        # Expand canvas to fit outline
        # We need padding = width
        padding = width
        new_w = img.width + padding * 2
        new_h = img.height + padding * 2
        
        # Create padded mask
        mask = img.split()[3]
        expanded_mask = Image.new('L', (new_w, new_h), 0)
        expanded_mask.paste(mask, (padding, padding))
        
        # Dilate (Grow) the mask
        # MaxFilter is square. For small widths this is fine.
        # For rounded dilation, we might chain filters or use a different approach, 
        # but MaxFilter is standard for simple "Stroke" effects in PIL.
        outline_mask = expanded_mask.filter(ImageFilter.MaxFilter(filter_size))
        
        # Create outline layer
        outline_layer = Image.new('RGBA', (new_w, new_h), color)
        outline_layer.putalpha(outline_mask)
        
        # Paste original image on top
        # We assume original image is "foreground"
        # Since we just want the outline sticking out, we composite:
        # Result = Outline over Empty, then Original over Result.
        
        # Just paste original? Alpha composite is safer for semi-transparent pixels in original.
        # Create a temp image for original placed in center
        fg = Image.new('RGBA', (new_w, new_h), (0,0,0,0))
        fg.paste(img, (padding, padding))
        
        # Composite: Outline is background, FG is foreground
        # But wait, outline_layer is full block. We only want outline visible where FG is transparent?
        # Standard stroke usually is drawn *behind* the object. So opacity in the object reveals the stroke?
        # Usually yes. If object is semi-transparent, stroke shows through.
        
        final_img = Image.alpha_composite(outline_layer, fg)
        
        return final_img, padding, padding

    def _get_intersection(self, p1, p2, p3, p4):
        """Find intersection of two lines: p1-p2 and p3-p4."""
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        
        denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
        if abs(denom) < 1e-9:
            return None # Parallel
        
        ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
        return (x1 + ua * (x2 - x1), y1 + ua * (y2 - y1))

    def _normalize_winding(self, vertices):
        """Ensure convex polygon vertices are in Clockwise (CW) order (Y-down coordinates)."""
        # Shoelace formula: sum (x2-x1)(y2+y1). 
        # Area < 0 is CW, Area > 0 is CCW in Y-down screen coordinates.
        area = 0
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            area += (p2[0] - p1[0]) * (p2[1] + p1[1])
        if area > 0:
            return list(reversed(vertices))
        return list(vertices)

    def _get_rounded_polygon_path(self, vertices, radius):
        """Calculate high-precision path for a rounded convex polygon."""
        num = len(vertices)
        if radius <= 0: return vertices

        # Normalize to CW
        vertices = self._normalize_winding(vertices)
        
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

        # Calculate arc centers by intersecting shifted edges
        # We also calculate the maximum safe radius for each corner to prevent overlap
        centers = []
        for i in range(num):
            n_prev = normals[(i - 1 + num) % num]
            n_curr = normals[i]
            e_prev = edges[(i - 1 + num) % num]
            e_curr = edges[i]
            
            # Interior angle theta
            # dot(n_prev, n_curr) = cos(alpha) where alpha is exterior angle. alpha = 180 - theta.
            dot = max(-1, min(1, n_prev[0]*n_curr[0] + n_prev[1]*n_curr[1]))
            alpha = math.acos(dot)
            theta = math.pi - alpha
            
            # Max radius for this corner such that tangent distance <= half of adjacent edges
            # T = R / tan(theta/2)
            half_min_edge = min(lengths[(i-1+num)%num], lengths[i]) / 2.0
            r_limit = half_min_edge * math.tan(theta/2.0)
            corner_radius = min(radius, r_limit)
            
            # Shifted lines
            s_prev_1 = (e_prev[0][0] + n_prev[0] * corner_radius, e_prev[0][1] + n_prev[1] * corner_radius)
            s_prev_2 = (e_prev[1][0] + n_prev[0] * corner_radius, e_prev[1][1] + n_prev[1] * corner_radius)
            s_curr_1 = (e_curr[0][0] + n_curr[0] * corner_radius, e_curr[0][1] + n_curr[1] * corner_radius)
            s_curr_2 = (e_curr[1][0] + n_curr[0] * corner_radius, e_curr[1][1] + n_curr[1] * corner_radius)
            
            center = self._get_intersection(s_prev_1, s_prev_2, s_curr_1, s_curr_2)
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

    def _draw_dashed_path(self, draw, points, width, color, dash_array, closed=True):
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

    def _draw_rounded_polygon(self, draw, vertices, radius, fill=None, outline=None, width=1, dash_array=None):
        """Draw a convex polygon with rounded corners."""
        poly_points = self._get_rounded_polygon_path(vertices, radius)
        if fill: draw.polygon(poly_points, fill=fill)
        if outline and width > 0:
            if dash_array:
                self._draw_dashed_path(draw, poly_points, width, outline, dash_array, closed=True)
            else:
                draw.line(poly_points + [poly_points[0]], fill=outline, width=width, joint='curve')

    def _draw_dashed_line(self, draw, p1, p2, width, color, dash_array, cap='butt'):
        """
        Draw a dashed line between p1 and p2.
        dash_array: [draw_pixels, gap_pixels]
        cap: 'butt' (default) or 'round'
        """
        x1, y1 = p1
        x2, y2 = p2
        dash_len = dash_array[0]
        gap_len = dash_array[1]
        
        total_dist = math.hypot(x2 - x1, y2 - y1)
        if total_dist == 0: return

        vx = (x2 - x1) / total_dist
        vy = (y2 - y1) / total_dist
        
        current_dist = 0
        while current_dist < total_dist:
            # Determine segment end
            seg_len = min(dash_len, total_dist - current_dist)
            
            # If segment is very short (end of line), strictly clip it? 
            # Or just draw what fits.
            # Fix: Allow 0-length segments if dash_len is 0 (for dots with caps)
            if seg_len <= 0 and dash_len > 0: break
            
            start_x = x1 + vx * current_dist
            start_y = y1 + vy * current_dist
            end_x = x1 + vx * (current_dist + seg_len)
            end_y = y1 + vy * (current_dist + seg_len)
            
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
            
            if cap == 'round':
                # Draw rounded caps for this segment
                # Since PIL draw.line is usually flat cap (butt), we add circles at endpoints.
                r = width / 2
                # Start cap
                draw.ellipse([start_x - r, start_y - r, start_x + r, start_y + r], fill=color)
                # End cap
                draw.ellipse([end_x - r, end_y - r, end_x + r, end_y + r], fill=color)
            
            current_dist += dash_len + gap_len

    def draw_shape_to_image(self, shape_config):
        shape_type = shape_config.get('type')
        if not shape_type: return None, (0,0)

        x = shape_config.get('x', 0)
        y = shape_config.get('y', 0)
        w = shape_config.get('width', 0)
        h = shape_config.get('height', 0)
        x2 = shape_config.get('x2', 0)
        y2 = shape_config.get('y2', 0)
        
        if shape_type == 'circle':
            shape_type = 'ellipse'
            radius = shape_config.get('radius')
            if radius: w, h = radius*2, radius*2
            else: w = h = max(w, h)
        
        fill_color = self._resolve_color(shape_config.get('color', (255, 255, 255)), shape_config.get('alpha'))
        
        # --- Parse Outline Config ---
        outline_cfg = shape_config.get('outline', {})
        if not outline_cfg:
            # Fallback to legacy keys
            if 'outline_color' in shape_config:
                outline_cfg = {
                    'color': shape_config.get('outline_color'),
                    'width': shape_config.get('outline_width', 0),
                    'dash_array': shape_config.get('dash_array'),
                    'style': shape_config.get('style'),
                    'cap': shape_config.get('end_cap', 'butt') # Inherit main cap for legacy lines
                }
        
        # Supersampling factor for anti-aliasing (applied to all shapes)
        sampling = 4
        
        outline_color_raw = outline_cfg.get('color')
        outline_width = outline_cfg.get('width', 0) or 0
        resolved_outline = self._resolve_color(outline_color_raw) if outline_color_raw else None
        
        # Dash support
        dash_array = outline_cfg.get('dash_array') 
        if not dash_array:
            style = outline_cfg.get('style')
            if style == 'dotted': dash_array = [2, 2] 
            elif style == 'dashed': dash_array = [10, 5]
            
        s_dash_array = [v * sampling for v in dash_array] if dash_array else None
        outline_cap = outline_cfg.get('cap', 'butt')
        
        pad = math.ceil(outline_width / 2) + 1
        
        if shape_type == 'line':
            # Calculate bounds
            lx = min(x, x2)
            ly = min(y, y2)
            lw = abs(x2 - x)
            lh = abs(y2 - y)
            
            # Apply supersampling to line
            s_lw = lw * sampling
            s_lh = lh * sampling
            s_w = w * sampling  # Line width
            s_outline = outline_width * sampling
            
            s_canvas_w = s_lw + s_outline + 20 * sampling
            s_canvas_h = s_lh + s_outline + 20 * sampling
            
            img = Image.new('RGBA', (int(s_canvas_w), int(s_canvas_h)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            
            # Scale offset and points
            s_offset_x = (lx - 10) * sampling
            s_offset_y = (ly - 10) * sampling
            
            s_p1 = (x * sampling - s_offset_x, y * sampling - s_offset_y)
            s_p2 = (x2 * sampling - s_offset_x, y2 * sampling - s_offset_y)
            
            # Line can have its own end_cap property (legacy) or outline.cap (new)
            joint = shape_config.get('end_cap', outline_cap)

            # Helper to draw line (solid or dashed)
            def draw_the_line(dr, pt1, pt2, wd, col, dashes, cap_style):
                if dashes:
                    self._draw_dashed_line(dr, pt1, pt2, wd, col, dashes, cap_style)
                else:
                    dr.line([pt1, pt2], fill=col, width=wd)
                    if cap_style == 'round':
                        r = wd / 2
                        dr.ellipse([pt1[0]-r, pt1[1]-r, pt1[0]+r, pt1[1]+r], fill=col)
                        dr.ellipse([pt2[0]-r, pt2[1]-r, pt2[0]+r, pt2[1]+r], fill=col)
            
            # Draw Outline
            if resolved_outline:
                draw_the_line(d, s_p1, s_p2, s_w + (s_outline*2), resolved_outline, s_dash_array, outline_cap)

            # Draw Main
            draw_the_line(d, s_p1, s_p2, s_w, fill_color, s_dash_array, joint)
            
            # Resize down
            final_w = int(s_canvas_w // sampling)
            final_h = int(s_canvas_h // sampling)
            img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
            
            offset_x = lx - 10
            offset_y = ly - 10
                
            return img, (offset_x, offset_y)
        
        if shape_type == 'rectangle':
            # Check for shear (parallelogram effect)
            shear_left = shape_config.get('shear_left', 0)
            shear_right = shape_config.get('shear_right', 0)
            
            # Legacy 'shear' applies to both edges (creates classic parallelogram)
            legacy_shear = shape_config.get('shear', 0)
            if legacy_shear != 0 and shear_left == 0 and shear_right == 0:
                shear_left = legacy_shear
                shear_right = legacy_shear # Both rotate same direction for parallelogram
            
            # Clamp to valid range (-89 to 89 degrees)
            shear_left = max(-89, min(89, shear_left))
            shear_right = max(-89, min(89, shear_right))
            
            if shear_left != 0 or shear_right != 0:
                # Shear rotates an edge around its CENTER (midpoint at h/2).
                # offset = (half_h) * tan(angle)
                # target: Positive angle = Clockwise rotation for BOTH edges.
                # Left edge CW: top moves RIGHT (+), bottom moves LEFT (-)
                # Right edge CW: top moves RIGHT (+), bottom moves LEFT (-)
                
                half_h = h / 2
                
                # Displacement at top/bottom from center
                left_offset = half_h * math.tan(math.radians(shear_left))
                right_offset = half_h * math.tan(math.radians(shear_right))
                
                # Calculate bounding box - need extra width for displaced corners
                # X-coordinates relative to origin (top-left of un-sheared rect):
                # TL.x = 0 + left_offset (positive angle -> moves right)
                # BL.x = 0 - left_offset (positive angle -> moves left)
                # TR.x = w + right_offset (positive angle -> moves right)
                # BR.x = w - right_offset (positive angle -> moves left)
                
                xs = [left_offset, -left_offset, w + right_offset, w - right_offset]
                min_x = min(xs)
                max_x = max(xs)
                
                extra_left = max(0, -min_x)
                total_w = max_x + extra_left + pad * 2
                total_h = h + pad * 2
                
                # Supersampling
                s_total_w = total_w * sampling
                s_total_h = total_h * sampling
                s_w = w * sampling
                s_h = h * sampling
                s_outline = outline_width * sampling
                s_pad = pad * sampling
                s_extra_left = extra_left * sampling
                
                img = Image.new('RGBA', (int(s_total_w), int(s_total_h)), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                
                # Scale offsets
                s_left_off = left_offset * sampling
                s_right_off = right_offset * sampling
                
                # Base position: origin of rectangle in canvas coords
                origin_x = s_pad + s_extra_left
                origin_y = s_pad
                
                tl = (origin_x + s_left_off, origin_y)
                tr = (origin_x + s_w + s_right_off, origin_y)
                br = (origin_x + s_w - s_right_off, origin_y + s_h)
                bl = (origin_x - s_left_off, origin_y + s_h)
                
                s_radius = (shape_config.get('radius', 0) or 0) * sampling
                
                # Draw using the new helper which handles both fill and (solid/dashed) outline
                self._draw_rounded_polygon(d, [tl, tr, br, bl], s_radius, 
                                         fill=fill_color if fill_color[3] > 0 else None, 
                                         outline=resolved_outline, 
                                         width=int(s_outline),
                                         dash_array=s_dash_array if dash_array else None)
                
                img = img.resize((int(s_total_w // sampling), int(s_total_h // sampling)), Image.Resampling.LANCZOS)
                return img, (x - pad - extra_left, y - pad)
            
            # Standard rectangle (no shear)
            s_radius = (shape_config.get('radius', 0) or 0) * sampling
            
            canvas_w = (w + pad * 2) * sampling
            canvas_h = (h + pad * 2) * sampling
            
            img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            
            s_pad = pad * sampling
            s_w = w * sampling
            s_h = h * sampling
            s_outline = outline_width * sampling
            
            # Vertices for a standard rectangle
            tl = (s_pad, s_pad)
            tr = (s_pad + s_w, s_pad)
            br = (s_pad + s_w, s_pad + s_h)
            bl = (s_pad, s_pad + s_h)

            # Use the unified rounded polygon drawer (handles fill, rounding, and dashes)
            self._draw_rounded_polygon(d, [tl, tr, br, bl], s_radius, 
                                     fill=fill_color if fill_color[3] > 0 else None, 
                                     outline=resolved_outline, 
                                     width=int(s_outline),
                                     dash_array=s_dash_array if dash_array else None)
            
            img = img.resize((int(canvas_w // sampling), int(canvas_h // sampling)), Image.Resampling.LANCZOS)
            return img, (x - pad, y - pad)

        elif shape_type == 'ellipse':
             canvas_w = (w + pad * 2) * sampling
             canvas_h = (h + pad * 2) * sampling
             
             img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
             d = ImageDraw.Draw(img)
             
             s_pad = pad * sampling
             s_w = w * sampling
             s_h = h * sampling
             s_outline = outline_width * sampling
             
             bounds = [s_pad, s_pad, s_pad + s_w, s_pad + s_h]
             
             d.ellipse(bounds, fill=fill_color, outline=resolved_outline, width=s_outline)
             
             img = img.resize((int(canvas_w // sampling), int(canvas_h // sampling)), Image.Resampling.LANCZOS)
             return img, (x - pad, y - pad)

        elif shape_type == 'triangle':
            # Triangle defined by 3 points
            x1, y1 = shape_config.get('x1', x), shape_config.get('y1', y)
            x2, y2 = shape_config.get('x2', x), shape_config.get('y2', y)
            x3, y3 = shape_config.get('x3', x), shape_config.get('y3', y)
            
            # Calculate bounding box
            min_x = min(x1, x2, x3)
            min_y = min(y1, y2, y3)
            max_x = max(x1, x2, x3)
            max_y = max(y1, y2, y3)
            
            tri_w = max_x - min_x
            tri_h = max_y - min_y
            
            # Supersampling
            s_outline = outline_width * sampling
            s_tri_w = tri_w * sampling
            s_tri_h = tri_h * sampling
            s_pad = pad * sampling
            
            canvas_w = (tri_w + pad * 2) * sampling
            canvas_h = (tri_h + pad * 2) * sampling
            
            img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            
            # Scale and offset points
            def scale_pt(px, py):
                return ((px - min_x) * sampling + s_pad, (py - min_y) * sampling + s_pad)
            
            s_p1 = scale_pt(x1, y1)
            s_p2 = scale_pt(x2, y2)
            s_p3 = scale_pt(x3, y3)
            
            s_radius = (shape_config.get('radius', 0) or 0) * sampling
            
            # Draw using the new helper which handles fill, rounding, and (solid/dashed) outline
            self._draw_rounded_polygon(d, [s_p1, s_p2, s_p3], s_radius, 
                                     fill=fill_color if fill_color[3] > 0 else None, 
                                     outline=resolved_outline, 
                                     width=int(s_outline),
                                     dash_array=s_dash_array if dash_array else None)
            
            img = img.resize((int(canvas_w // sampling), int(canvas_h // sampling)), Image.Resampling.LANCZOS)
            return img, (min_x - pad, min_y - pad)

        # Fallback for unknown types
        return None, (0, 0)

    def draw_text_to_image(self, text_config, sampling=1):
        """Render text to an RGBA image with optional supersampling."""
        text = text_config.get('text', '')
        if not text: return None, (0,0)
        
        # Supersampling factor is now a parameter
        
        font_path_rel = text_config.get('font', "roboto/Roboto-Regular.ttf")
        font_path = os.path.join(self.theme_path, font_path_rel)
        if not os.path.exists(font_path):
             if hasattr(config, 'FONTS_DIR'):
                 font_path = os.path.join(config.FONTS_DIR, font_path_rel)
        
        size = text_config.get('size', text_config.get('font_size', 20))
        s_size = int(size * sampling)
        color = self._resolve_color(text_config.get('color', text_config.get('font_color', 'white')), text_config.get('alpha'))
        
        try:
            font = ImageFont.truetype(font_path, s_size)
        except OSError:
            logger.warning(f"Could not load font {font_path}, fallback to default")
            font = ImageFont.load_default()

        # Calculate size at supersampled scale
        dummy = Image.new('RGBA', (1,1))
        draw = ImageDraw.Draw(dummy)
        
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            offset_y = bbox[1]
        except AttributeError:
            w, h = draw.textsize(text, font=font)
            offset_y = 0

        # Create image at 4x
        pad = 5 * sampling
        img_w = w + pad * 2
        img_h = h + pad * 2
        
        img = Image.new('RGBA', (int(img_w), int(img_h)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((pad - bbox[0] if 'bbox' in locals() else pad, pad - bbox[1] if 'bbox' in locals() else pad), 
               text, font=font, fill=color)
        
        # Cropping to content at 4x
        bbox_crop = img.getbbox()
        if bbox_crop:
            img = img.crop(bbox_crop)
        
        # Downscale
        new_w = img.width // sampling
        new_h = img.height // sampling
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        x = text_config.get('x', 0)
        y = text_config.get('y', 0)
        
        return img, (x, y)

    def draw_icon_to_image(self, icon_config, sampling=1):
        """Render an icon with optional supersampling."""
        icon_val = icon_config.get('icon', '')
        if not icon_val: return None, (0,0)
        
        # 1. Resolve Unicode and Font Link
        auto_unicode, auto_link = font_manager.resolve_icon_metadata(icon_val)
        font_link = icon_config.get('link') or auto_link
        
        # 2. Determine text character
        if not auto_unicode and ('http://' in icon_val or 'https://' in icon_val):
            logger.warning(f"Could not resolve icon from URL: {icon_val}")
            return None, (0,0)
            
        final_hex = auto_unicode or icon_val
        if len(final_hex) >= 4 and all(c in '0123456789abcdefABCDEF' for c in final_hex):
            try:
                text = chr(int(final_hex, 16))
            except Exception:
                text = final_hex
        else:
            text = final_hex

        # 3. Font resolution
        if font_link:
            font_path = font_manager.get_font_path(font_link)
        else:
            font_path = os.path.join(config.FONTS_DIR, 'fa-solid-900.ttf')
            if not os.path.exists(font_path):
                font_path = os.path.join(config.FONTS_DIR, 'roboto/Roboto-Regular.ttf')

        size = icon_config.get('size', icon_config.get('font_size', 40))
        s_size = int(size * sampling)
        color = self._resolve_color(icon_config.get('color', 'white'), icon_config.get('alpha'))
        
        try:
            font = ImageFont.truetype(font_path, s_size)
        except OSError:
            logger.warning(f"Could not load icon font {font_path}")
            return None, (0,0)

        # Precise BBox calculation at 4x
        dummy = Image.new('RGBA', (1,1))
        d_dummy = ImageDraw.Draw(dummy)
        bbox = d_dummy.textbbox((0, 0), text, font=font)
        
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # Add padding
        pad = int(s_size * 0.1) + 5 * sampling
        img = Image.new('RGBA', (int(w + pad*2), int(h + pad*2)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        # Shift to fit in padded canvas
        d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=color)
        
        bbox_final = img.getbbox()
        if bbox_final:
            img = img.crop(bbox_final)
            
        # Downscale
        new_w = img.width // sampling
        new_h = img.height // sampling
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        x = icon_config.get('x', 0)
        y = icon_config.get('y', 0)
        
        return img, (x, y)

    def apply_element_styling(self, canvas, img, x, y, config_item):
        """Apply opacity, rotation, and shadow to an element and composite it onto the canvas."""
        if not img: return
        
        # Opacity/Alpha (Global for element, distinct from color alpha)
        opacity = config_item.get('opacity', 1.0)
        if opacity < 1.0:
            r, g, b, a = img.split()
            a = a.point(lambda p: int(p * opacity))
            img = Image.merge('RGBA', (r, g, b, a))

        # Rotation (supports both 'angle' and 'rotation' property names)
        angle = config_item.get('angle', config_item.get('rotation', 0))
        if angle != 0:
            cx = x + img.width / 2
            cy = y + img.height / 2
            img = img.rotate(-angle, expand=True, resample=Image.BICUBIC)
            x = cx - img.width / 2
            y = cy - img.height / 2
        
        # Shadow
        shadow_config = config_item.get('shadow')
        if shadow_config:
            shadow_img, sx, sy = self._create_shadow_layer(img, shadow_config)
            if shadow_img:
                canvas.alpha_composite(shadow_img, (int(x + sx), int(y + sy)))
        
        canvas.alpha_composite(img, (int(x), int(y)))

    def generate_overlay(self):
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        ui_elements = self.theme_data.get('ui_elements', [])
        
        # Ensure it's a list (backward compatibility if user still uses dict structure might be nice)
        if isinstance(ui_elements, dict):
            flat_list = []
            for shape in ui_elements.get('shapes', []):
                shape['type'] = shape.get('type', 'rectangle')
                flat_list.append(shape)
            for text in ui_elements.get('ui_text', []):
                text['type'] = 'text'
                flat_list.append(text)
            for img in ui_elements.get('images', []):
                img['type'] = 'image'
                flat_list.append(img)
            ui_elements = flat_list

        if not isinstance(ui_elements, list):
             return overlay

        # Process Queue Linear
        for config_item in ui_elements:
            elem_type = config_item.get('type')
            
            if elem_type in ('rectangle', 'ellipse', 'circle', 'line', 'triangle'):
                img, (x, y) = self.draw_shape_to_image(config_item)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type == 'text':
                img, (x, y) = self.draw_text_to_image(config_item, sampling=4)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type == 'icon':
                img, (x, y) = self.draw_icon_to_image(config_item, sampling=4)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type == 'image':
                 path = config_item.get('path')
                 if path:
                    full_path = os.path.join(self.theme_path, path)
                    if os.path.exists(full_path):
                        try:
                            ui_img = Image.open(full_path).convert('RGBA')
                            
                            # Resize to target width/height
                            w = config_item.get('width')
                            h = config_item.get('height')
                            
                            # If W/H not set (legacy themes?), default to original size
                            if not w or not h:
                                # Keep original dimensions
                                pass
                            else:
                                if w != ui_img.width or h != ui_img.height:
                                    ui_img = ui_img.resize((w, h), Image.Resampling.LANCZOS)
                            
                            # Apply Outline (Stroke)
                            outline_cfg = config_item.get('outline', {})
                            # Support top-level outline keys for consistency? Users might guess 'outline_color'. 
                            # But better to stick to 'outline' dict from now on.
                            if not outline_cfg and 'outline_color' in config_item:
                                 outline_cfg = {
                                     'color': config_item.get('outline_color'),
                                     'width': config_item.get('outline_width', 0)
                                 }
                            
                            if outline_cfg:
                                ui_img, px, py = self._apply_image_outline(ui_img, outline_cfg)
                                # Adjust draw position to account for padding added by outline
                                # x, y passed to process_element are the top-left.
                                # The image grew by px, py (top/left padding).
                                # So effective origin shifts by -px, -py?
                                # Wait. If I want the image at (100, 100).
                                # original image was at (100, 100).
                                # new image has 5px padding. center of new = center of old.
                                # top-left of new is at 95, 95.
                                # So we must subtract padding from x, y.
                                x_shift = px
                                y_shift = py
                            else:
                                x_shift = 0
                                y_shift = 0
                                
                            x = config_item.get('x', 0) - x_shift
                            y = config_item.get('y', 0) - y_shift
                            self.apply_element_styling(overlay, ui_img, x, y, config_item)
                        except Exception as e:
                            logger.error(f"Error drawing image {path}: {e}")
        
        return overlay
