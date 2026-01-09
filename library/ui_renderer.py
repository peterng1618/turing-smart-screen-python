# SPDX-License-Identifier: GPL-3.0-or-later
import os
import math
from PIL import Image, ImageDraw, ImageFilter, ImageColor, ImageFont, ImageChops

from library.log import logger
from library import config # We need config to access FONTS_DIR if needed or pass it in

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

    def _draw_dashed_line(self, draw, p1, p2, width, color, dash_array):
        """
        Draw a dashed line between p1 and p2.
        dash_array: [draw_pixels, gap_pixels]
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
            
            start_x = x1 + vx * current_dist
            start_y = y1 + vy * current_dist
            end_x = x1 + vx * (current_dist + seg_len)
            end_y = y1 + vy * (current_dist + seg_len)
            
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
            
            current_dist += dash_len + gap_len

    def draw_shape_to_image(self, shape_config):
        shape_type = shape_config.get('type')
        if not shape_type: return None, (0,0)

        # Normalize x,y to be top-left start, but wait, if we rotate, x,y matters.
        # We process local drawing first.
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
        outline_color_raw = shape_config.get('outline_color')
        outline_width = shape_config.get('outline_width', 0)
        resolved_outline = self._resolve_color(outline_color_raw) if outline_color_raw else None
        
        # Dash support
        dash_array = shape_config.get('dash_array') # e.g. [5, 5]
        # Or 'style': 'dotted' -> [1, width], 'dashed' -> [width*3, width]
        if not dash_array:
            style = shape_config.get('style')
            if style == 'dotted': dash_array = [2, 2] # simplified
            elif style == 'dashed': dash_array = [10, 5]
        
        pad = math.ceil(outline_width / 2) + 1
        
        if shape_type == 'line':
            # Calculate bounds
            lx = min(x, x2)
            ly = min(y, y2)
            lw = abs(x2 - x)
            lh = abs(y2 - y)
            
            canvas_w = lw + outline_width + 20 
            canvas_h = lh + outline_width + 20
            img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            
            offset_x = lx - 10
            offset_y = ly - 10
            
            p1 = (x - offset_x, y - offset_y)
            p2 = (x2 - offset_x, y2 - offset_y)
            
            joint = shape_config.get('end_cap', 'butt')

            # Helper to draw line (solid or dashed)
            def draw_the_line(dr, pt1, pt2, wd, col, dashes):
                if dashes:
                    self._draw_dashed_line(dr, pt1, pt2, wd, col, dashes)
                else:
                    dr.line([pt1, pt2], fill=col, width=wd)
                    # Caps only apply to solid lines in native PIL, 
                    # but if we are manual, we skip caps for dashes for now to keep it simple, 
                    # OR we implement caps for dash segments (too complex for now).
                    # Just solid caps at ends of the main line if requested?
                    pass
            
            # Draw Outline
            if resolved_outline:
                draw_the_line(d, p1, p2, w + (outline_width*2), resolved_outline, dash_array)
                if joint == 'round' and not dash_array:
                     r = (w + outline_width*2) / 2
                     d.ellipse([p1[0]-r, p1[1]-r, p1[0]+r, p1[1]+r], fill=resolved_outline)
                     d.ellipse([p2[0]-r, p2[1]-r, p2[0]+r, p2[1]+r], fill=resolved_outline)

            # Draw Main
            draw_the_line(d, p1, p2, w, fill_color, dash_array)
            if joint == 'round' and not dash_array:
                r = w / 2
                d.ellipse([p1[0]-r, p1[1]-r, p1[0]+r, p1[1]+r], fill=fill_color)
                d.ellipse([p2[0]-r, p2[1]-r, p2[0]+r, p2[1]+r], fill=fill_color)
                
            return img, (offset_x, offset_y)
            
        # Supersampling factor for anti-aliasing
        sampling = 4
        
        if shape_type == 'rectangle':
            radius = shape_config.get('radius', 0) * sampling
            # Check if using simple dashed rect logic (no radius support usually)
            if dash_array:
                # Dashed rectangle doesn't support radius easily in current impl
                # Fallback to 1x for dashed to avoid complexity, or just dont supersample dashes yet
                pass 
            else:
                # Supersample standard shapes
                canvas_w = (w + pad * 2) * sampling
                canvas_h = (h + pad * 2) * sampling
                
                img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                
                # Adjust bounds and widths
                s_pad = pad * sampling
                s_w = w * sampling
                s_h = h * sampling
                s_outline = outline_width * sampling
                
                bounds = [s_pad, s_pad, s_pad + s_w, s_pad + s_h]
                
                d.rounded_rectangle(bounds, radius=radius, fill=fill_color, outline=resolved_outline, width=s_outline)
                
                # Resize down
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

        # Fallback for complex dashed rects if any, or just legacy path if we skipped above
        # Note: 'line' is handled in previous block, so this `else` was only for rect/ellipse.
        # But we replaced the `else` with specific `if/elif`.
        # If we are here, it might be a dashed rectangle which we skipped above?
        
        # Original logic for non-supersampled (dashed rects)
        canvas_w = w + pad * 2
        canvas_h = h + pad * 2
        img = Image.new('RGBA', (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        bounds = [pad, pad, pad + w, pad + h]
        
        if shape_type == 'rectangle' and dash_array:
            if fill_color[3] > 0:
                 radius = shape_config.get('radius', 0)
                 d.rounded_rectangle(bounds, radius=radius, fill=fill_color, width=0)
            
            if resolved_outline:
                 pts = [
                     ((pad, pad), (pad+w, pad)),
                     ((pad+w, pad), (pad+w, pad+h)),
                     ((pad+w, pad+h), (pad, pad+h)),
                     ((pad, pad+h), (pad, pad))
                 ]
                 for s, e in pts:
                     self._draw_dashed_line(d, s, e, outline_width, resolved_outline, dash_array)

        return img, (x - pad, y - pad)

    def draw_text_to_image(self, text_config):
        """Render text to an RGBA image."""
        text = text_config.get('text', '')
        if not text: return None, (0,0)
        
        font_path_rel = text_config.get('font', "roboto/Roboto-Regular.ttf")
        # Try to locate font. config.FONTS_DIR is usually absolute path from library
        # But we want to support relative to theme?
        # Usually fonts are in res/fonts. User might supply custom one in theme.
        
        # Check theme folder first
        font_path = os.path.join(self.theme_path, font_path_rel)
        if not os.path.exists(font_path):
             # Try global fonts
             if hasattr(config, 'FONTS_DIR'):
                 font_path = os.path.join(config.FONTS_DIR, font_path_rel)
        
        size = text_config.get('size', text_config.get('font_size', 20))
        color = self._resolve_color(text_config.get('color', text_config.get('font_color', 'white')), text_config.get('alpha'))
        
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            logger.warning(f"Could not load font {font_path}, fallback to default")
            font = ImageFont.load_default()

        # Calculate size
        # ImageDraw.textbbox is preferred in newer Pillow, textsize is deprecated
        dummy = Image.new('RGBA', (1,1))
        draw = ImageDraw.Draw(dummy)
        
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            offset_y = bbox[1] # usually negative (ascent)
        except AttributeError:
            # Old Pillow fallback
            w, h = draw.textsize(text, font=font)
            offset_y = 0

        img_w = w + 10 # Padding
        img_h = h + 10
        
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        # Draw Text
        draw_x = 0
        draw_y = 0 
        
        d.text((draw_x, draw_y), text, font=font, fill=color)
        
        # Cropping to content
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        
        x = text_config.get('x', 0)
        y = text_config.get('y', 0)
        
        # Alignment logic (simple offset adjustment)
        # Note: if user specifies center align, x represents the center.
        align = text_config.get('align', 'left')
        anchor = text_config.get('anchor', 'nw') # Pillow anchors are confusing, let's stick to theme logic
        
        # Simplistic anchor handling if not 'default'
        # If align center, shift x by w/2?
        # Standard theme usage: x,y is top-left usually.
        
        return img, (x, y)

    def generate_overlay(self):
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        ui_elements = self.theme_data.get('ui_elements', [])
        
        # Ensure it's a list (backward compatibility if user still uses dict structure might be nice, 
        # but requested flattened list implies checking type)
        if isinstance(ui_elements, dict):
            # Convert legacy dict structure to flat list for backward compatibility or transition
            flat_list = []
            for shape in ui_elements.get('shapes', []):
                shape['type'] = shape.get('type', 'rectangle') # Default
                flat_list.append(shape)
            for text in ui_elements.get('ui_text', []):
                text['type'] = 'text'
                flat_list.append(text)
            for img in ui_elements.get('images', []):
                img['type'] = 'image'
                flat_list.append(img)
            ui_elements = flat_list # Use this temporary flat list

        if not isinstance(ui_elements, list):
             # Log warning or just return empty?
             return overlay

        # Helper to process an element (Rotations, Shadows, Composite)
        def process_element(img, x, y, config_item):
            if not img: return
            
            # Opacity/Alpha (Global for element, distinct from color alpha)
            opacity = config_item.get('opacity', 1.0)
            if opacity < 1.0:
                # Multiply alpha channel
                # This is expensive, check if separate alpha can be applied
                # Image.putalpha sets constant alpha, we need to multiply.
                r, g, b, a = img.split()
                a = a.point(lambda p: int(p * opacity))
                img = Image.merge('RGBA', (r, g, b, a))

            # Rotation
            angle = config_item.get('angle', 0)
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
                    overlay.alpha_composite(shadow_img, (int(x + sx), int(y + sy)))
            
            overlay.alpha_composite(img, (int(x), int(y)))

        # Process Queue Linear
        for config_item in ui_elements:
            elem_type = config_item.get('type')
            
            if elem_type in ('rectangle', 'ellipse', 'circle', 'line'):
                img, (x, y) = self.draw_shape_to_image(config_item)
                process_element(img, x, y, config_item)
                
            elif elem_type == 'text':
                img, (x, y) = self.draw_text_to_image(config_item)
                process_element(img, x, y, config_item)
                
            elif elem_type == 'image':
                 path = config_item.get('path')
                 if path:
                    full_path = os.path.join(self.theme_path, path)
                    if os.path.exists(full_path):
                        try:
                            ui_img = Image.open(full_path).convert('RGBA')
                            
                            # Scale
                            scale = config_item.get('scale', 1.0)
                            if scale != 1.0:
                                new_w = int(ui_img.width * scale)
                                new_h = int(ui_img.height * scale)
                                ui_img = ui_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                                
                            x = config_item.get('x', 0)
                            y = config_item.get('y', 0)
                            process_element(ui_img, x, y, config_item)
                        except Exception as e:
                            logger.error(f"Error drawing image {path}: {e}")
        
        return overlay
