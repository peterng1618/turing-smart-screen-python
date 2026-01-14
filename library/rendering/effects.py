from PIL import Image, ImageFilter
from typing import Tuple, Optional

def apply_shadow(
    image: Image.Image,
    blur: float = 5,
    color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    offset: Tuple[int, int] = (5, 5)
) -> Tuple[Image.Image, int, int]:
    """Create a shadow layer for the given image. Returns (shadow_image, dx, dy)."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    mask = image.split()[3]
    padding = int(blur * 3) if blur > 0 else 0
    
    new_w = image.width + padding * 2
    new_h = image.height + padding * 2
    
    expanded_mask = Image.new('L', (new_w, new_h), 0)
    expanded_mask.paste(mask, (padding, padding))
    
    if blur > 0:
        expanded_mask = expanded_mask.filter(ImageFilter.GaussianBlur(blur))
        
    shadow = Image.new('RGBA', (new_w, new_h), color)
    shadow.putalpha(expanded_mask)
    
    return shadow, offset[0] - padding, offset[1] - padding

def apply_outline(
    image: Image.Image,
    width: int = 1,
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
) -> Tuple[Image.Image, int, int]:
    """Apply an outline and return the new image and its offset."""
    if width <= 0:
        return image, 0, 0
        
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
        
    filter_size = width * 2 + 1
    padding = width
    new_w = image.width + padding * 2
    new_h = image.height + padding * 2
    
    mask = image.split()[3]
    expanded_mask = Image.new('L', (new_w, new_h), 0)
    expanded_mask.paste(mask, (padding, padding))
    
    outline_mask = expanded_mask.filter(ImageFilter.MaxFilter(filter_size))
    outline_layer = Image.new('RGBA', (new_w, new_h), color)
    outline_layer.putalpha(outline_mask)
    
    fg = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
    fg.paste(image, (padding, padding))
    
    final_img = Image.alpha_composite(outline_layer, fg)
    return final_img, padding, padding

def apply_styling(
    image: Image.Image,
    opacity: float = 1.0,
    rotation: float = 0,
    shadow: Optional[dict] = None
) -> Tuple[Image.Image, float, float]:
    """Apply opacity, rotation, and shadow to an image. Returns (styled_image, dx, dy)."""
    img = image
    if opacity < 1.0:
        r, g, b, a = img.split()
        a = a.point(lambda p: int(p * opacity))
        img = Image.merge('RGBA', (r, g, b, a))

    dx, dy = 0.0, 0.0
    
    # Handle rotation
    if rotation != 0:
        orig_w, orig_h = img.size
        img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
        # Shift to keep center
        dx -= (img.width - orig_w) / 2
        dy -= (img.height - orig_h) / 2

    # Handle shadow
    if shadow:
        blur = shadow.get('blur', 5)
        color = shadow.get('color', (0, 0, 0, 255))
        # Ensure color is tuple
        if isinstance(color, str):
            from PIL import ImageColor
            color = ImageColor.getrgb(color)
            if len(color) == 3: color = color + (255,)
            
        offset_x = shadow.get('offset_x', 5)
        offset_y = shadow.get('offset_y', 5)
        
        shadow_img, sx, sy = apply_shadow(img, blur, color, (offset_x, offset_y))
        
        # We need to composite shadow behind img
        # Result canvas must be large enough for both
        res_w = max(img.width, shadow_img.width + abs(sx)) # Rough estimate
        res_h = max(img.height, shadow_img.height + abs(sy))
        
        # Actually it's easier to just return the two images or a merged one.
        # Standard composite:
        # We need to know where sx, sy are relative to img.
        # apply_shadow returns sx, sy such that (0,0) in shadow_img + (sx, sy) yields correct offset relative to (0,0) in img.
        
        # If sx < 0, it means shadow starts LEFT of img.
        # If sy < 0, it means shadow starts ABOVE img.
        
        final_x = max(0, -sx)
        final_y = max(0, -sy)
        shadow_x = max(0, sx)
        shadow_y = max(0, sy)
        
        canvas_w = int(max(final_x + img.width, shadow_x + shadow_img.width))
        canvas_h = int(max(final_y + img.height, shadow_y + shadow_img.height))
        
        canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        canvas.alpha_composite(shadow_img, (int(shadow_x), int(shadow_y)))
        canvas.alpha_composite(img, (int(final_x), int(final_y)))
        
        dx -= final_x
        dy -= final_y
        img = canvas

    return img, float(dx), float(dy)
