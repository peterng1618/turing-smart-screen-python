# SPDX-License-Identifier: GPL-3.0-or-later
import os
from typing import Tuple, Dict, Optional, List, Union, Any
import math
from PIL import Image, ImageDraw, ImageColor

from library.log import logger
from library import config
from library.font_manager import font_manager
import library.rendering.shapes as rendering_shapes
import library.rendering.text as rendering_text
import library.rendering.icons as rendering_icons
import library.rendering.effects as rendering_effects

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

    def draw_shape_to_image(self, shape_config: dict) -> Tuple[Image.Image, Tuple[int, int]]:
        """Render a shape to an RGBA image using the rendering library."""
        shape_type = shape_config.get('type')
        if not shape_type: return None, (0, 0)

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
                    'cap': shape_config.get('end_cap', 'butt')
                }
        
        if outline_cfg and 'color' in outline_cfg:
            outline_cfg = outline_cfg.copy()
            outline_cfg['color'] = self._resolve_color(outline_cfg['color'])

        # Resolve dash array from style if needed
        dash_array = outline_cfg.get('dash_array')
        if outline_cfg and not dash_array:
            style = outline_cfg.get('style')
            if style == 'dotted': dash_array = [2, 2]
            elif style == 'dashed': dash_array = [10, 5]

        # Extract other parameters
        outline_color = outline_cfg.get('color', (0, 0, 0, 0))
        outline_width = outline_cfg.get('width', 0)
        cap_style = outline_cfg.get('cap', 'butt')

        # Extract other shape-specific parameters
        w = shape_config.get('width')
        h = shape_config.get('height')
        rounding = shape_config.get('rounding', 0)
        coords = shape_config.get('coords')
        shear_left = shape_config.get('shear_left', 0)
        shear_right = shape_config.get('shear_right', 0)

        img, dx, dy = rendering_shapes.render_shape_to_image(
            type=shape_type,
            width=w,
            height=h,
            fill_color=fill_color,
            outline_color=outline_color,
            outline_width=outline_width,
            rounding=rounding,
            dash_array=dash_array,
            cap_style=cap_style,
            sampling=4,
            coords=coords,
            shear_left=shear_left,
            shear_right=shear_right
        )
        
        x = shape_config.get('x', 0)
        y = shape_config.get('y', 0)
        
        return img, (x + dx, y + dy)

    def draw_text_to_image(self, text_config: dict, sampling: int = 1) -> Tuple[Image.Image, Tuple[int, int]]:
        """Render text to an RGBA image using the rendering library."""
        text = text_config.get('text', '')
        if not text: return None, (0,0)
        
        font_path_rel = text_config.get('font', "roboto/Roboto-Regular.ttf")
        font_path = os.path.join(self.theme_path, font_path_rel)
        if not os.path.exists(font_path):
             if hasattr(config, 'FONTS_DIR'):
                 font_path = os.path.join(config.FONTS_DIR, font_path_rel)
        
        size = text_config.get('size', text_config.get('font_size', 20))
        color = self._resolve_color(text_config.get('color', text_config.get('font_color', 'white')), text_config.get('alpha'))
        
        outline_cfg = text_config.get('outline')
        if outline_cfg:
            outline_cfg = outline_cfg.copy()
            outline_cfg['color'] = self._resolve_color(outline_cfg.get('color', 'white'))

        img, dx, dy = rendering_text.render_text_block(
            text=text,
            font_path=font_path,
            font_size=size,
            color=color,
            sampling=sampling,
            outline_config=outline_cfg
        )
        
        x = text_config.get('x', 0)
        y = text_config.get('y', 0)
        
        return img, (x + dx, y + dy)

    def draw_icon_to_image(self, icon_config: dict, sampling: int = 1) -> Tuple[Image.Image, Tuple[int, int]]:
        """Render an icon with optional supersampling using the rendering library."""
        icon_val = icon_config.get('icon', '')
        if not icon_val: return None, (0, 0)
        
        auto_unicode, auto_link = font_manager.resolve_icon_metadata(icon_val)
        font_link = icon_config.get('link') or auto_link
        
        final_hex = auto_unicode or icon_val
        if len(final_hex) >= 4 and all(c in '0123456789abcdefABCDEF' for c in final_hex):
            try:
                text = chr(int(final_hex, 16))
            except Exception:
                text = final_hex
        else:
            text = final_hex

        if font_link:
            font_path = font_manager.get_font_path(font_link)
        else:
            font_path = os.path.join(config.FONTS_DIR, 'fa-solid-900.ttf')
            if not os.path.exists(font_path):
                font_path = os.path.join(config.FONTS_DIR, 'roboto/Roboto-Regular.ttf')

        size = icon_config.get('size', icon_config.get('font_size', 40))
        color = self._resolve_color(icon_config.get('color', 'white'), icon_config.get('alpha'))
        
        outline_cfg = icon_config.get('outline')
        if outline_cfg:
            outline_cfg = outline_cfg.copy()
            outline_cfg['color'] = self._resolve_color(outline_cfg.get('color', 'white'))

        img, dx, dy = rendering_icons.render_icon_block(
            text=text, # Assuming 'text' is the variable holding the character, as per original code. Instruction used 'icon_char' but it's not defined in the original context.
            font_path=font_path,
            font_size=size,
            color=color,
            sampling=sampling,
            outline_config=outline_cfg
        )
        
        x = icon_config.get('x', 0)
        y = icon_config.get('y', 0)
        
        return img, (int(x + dx), int(y + dy))

    def apply_element_styling(self, canvas: Image.Image, img: Image.Image, x: int, y: int, config_item: dict) -> None:
        """Apply opacity, rotation, and shadow to an element and composite it onto the canvas."""
        if not img: return
        
        opacity = config_item.get('opacity', 1.0)
        angle = config_item.get('angle', config_item.get('rotation', 0))
        shadow_config = config_item.get('shadow')
        
        # We need to resolve colors in shadow_config if present
        if shadow_config and 'color' in shadow_config:
            shadow_config = shadow_config.copy()
            shadow_config['color'] = self._resolve_color(shadow_config['color'])

        img, dx, dy = rendering_effects.apply_styling(img, opacity, angle, shadow_config)
        
        canvas.alpha_composite(img, (int(x + dx), int(y + dy)))

    def generate_overlay(self, exclude_types=None):
        """
        Generate a static UI overlay image from elements.
        
        :param exclude_types: List of element types to exclude from rendering (e.g. ['background_video'])
        """
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        ui_elements = self.theme_data.get('ui_elements', [])
        
        if exclude_types is None:
            exclude_types = []
            
        # Ensure it's a list (backward compatibility if user still uses dict structure)
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
            
            if elem_type in exclude_types:
                continue
            
            if elem_type in ('rectangle', 'ellipse', 'circle', 'line', 'triangle'):
                img, (x, y) = self.draw_shape_to_image(config_item)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type == 'text':
                img, (x, y) = self.draw_text_to_image(config_item, sampling=4)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type == 'icon':
                img, (x, y) = self.draw_icon_to_image(config_item, sampling=4)
                self.apply_element_styling(overlay, img, x, y, config_item)
                
            elif elem_type in ('image', 'background_image'):
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
