# SPDX-License-Identifier: GPL-3.0-or-later
import os
from typing import Tuple, Dict, Optional, List, Union, Any
from PIL import Image, ImageColor

from library.log import logger
from library import config
from library.font_manager import font_manager
import library.rendering.shapes as rendering_shapes
import library.rendering.text as rendering_text
import library.rendering.icons as rendering_icons
import library.rendering.effects as rendering_effects
import library.rendering.draw as rendering_draw

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







    def draw_shape_to_image(self, shape_config: dict) -> Tuple[Image.Image, Tuple[int, int]]:
        """Render a shape to an RGBA image using the rendering library."""
        shape_type = shape_config.get('type')
        if not shape_type: return None, (0, 0)

        # Resolve fill color
        fill_color = self._resolve_color(
            shape_config.get('color', (255, 255, 255)), 
            shape_config.get('alpha')
        )
        
        # Resolve outline config
        outline_cfg = shape_config.get('outline', {})
        # Support legacy keys fallback (outline_color, outline_width)
        if not outline_cfg and 'outline_color' in shape_config:
             outline_cfg = {
                 'color': shape_config.get('outline_color'),
                 'width': shape_config.get('outline_width', 0),
                 'dash_array': shape_config.get('dash_array'),
                 'style': shape_config.get('style'),
                 'cap': shape_config.get('end_cap', 'butt')
             }
        
        if outline_cfg:
            outline_cfg = outline_cfg.copy()
            if 'color' in outline_cfg:
                outline_cfg['color'] = self._resolve_color(outline_cfg['color'])
            
            # Legacy style->dash_array logic
            if not outline_cfg.get('dash_array'):
                style = outline_cfg.get('style')
                if style == 'dotted': outline_cfg['dash_array'] = [2, 2]
                elif style == 'dashed': outline_cfg['dash_array'] = [10, 5]
        
        # Call the library
        img, dx, dy = rendering_shapes.render_shape_to_image(
            shape_type=shape_type,
            shape_config=shape_config,
            fill_color=fill_color,
            outline_config=outline_cfg if outline_cfg.get('width', 0) > 0 else None,
            sampling=4
        )
        
        x = shape_config.get('x', 0)
        y = shape_config.get('y', 0)
        
        return img, (x + dx, y + dy)

    def draw_text_to_image(self, text_config: dict, sampling: int = 1) -> Tuple[Image.Image, Tuple[int, int]]:
        """Render text to an RGBA image using the rendering library via the orchestration layer."""
        text = text_config.get('text', '')
        if not text: return None, (0,0)
        
        # Resolve font path
        font_path_rel = text_config.get('font', "roboto/Roboto-Regular.ttf")
        font_path = os.path.join(self.theme_path, font_path_rel)
        if not os.path.exists(font_path):
             if hasattr(config, 'FONTS_DIR'):
                 font_path = os.path.join(config.FONTS_DIR, font_path_rel)
        
        # Resolve parameters
        size = text_config.get('size', text_config.get('font_size', 20))
        color = self._resolve_color(text_config.get('color', text_config.get('font_color', 'white')), text_config.get('alpha'))
        
        # Load font (UiRenderer doesn't have a cache like LcdComm, but rendering_text might)
        # For now we use ImageFont.truetype directly or a local cache if we want.
        # But wait, LcdComm has open_font. UiRenderer should probably have one too or use a global one.
        # For minimal change, we use ImageFont.truetype.
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            font = ImageFont.load_default()

        # UiRenderer creates an element image that is then layered.
        # We'll create a large enough canvas for the text, render it, and then return it.
        # Since we use alpha_composite, we need an RGBA canvas. 
        # We don't know the exact size yet, so we'll use a larger one and crop, 
        # OR we use the fact that rendering_draw.text returns the image but wait, 
        # I made rendering_draw.text draw ONTO a canvas.
        
        # To get the standalone image, we can just call rendering_text.render_text_block directly,
        # OR we create a temporary canvas. 
        # Let's create a temporary canvas of 1024x1024 and crop to the bbox.
        temp_canvas = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
        rx, ry, rw, rh = rendering_draw.text(
            temp_canvas, text, (0, 0), font, color,
            align=text_config.get('align', 'left'),
            anchor=text_config.get('anchor', 'la'),
            opacity=1.0, # Opacity/Shadow/Rotation are applied by apply_element_styling later in generate_overlay
            rotation=0, # Rotation is applied by apply_element_styling
            shadow=None, # Shadow is applied by apply_element_styling
            outline=text_config.get('outline')
        )
        
        # Crop to the actual drawn content
        element_img = temp_canvas.crop((rx, ry, rx + rw, ry + rh))
        
        x = text_config.get('x', 0)
        y = text_config.get('y', 0)
        
        return element_img, (x + rx, y + ry)

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

    def _apply_image_outline(self, image: Image.Image, outline_config: dict) -> Tuple[Image.Image, int, int]:
        """Apply outline to an image using rendering effects."""
        width = outline_config.get('width', 0)
        if width <= 0:
            return image, 0, 0
            
        color_val = outline_config.get('color', 'white')
        color = self._resolve_color(color_val)
        
        return rendering_effects.apply_outline(image, width, color)

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
