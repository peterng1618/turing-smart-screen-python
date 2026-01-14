from typing import Tuple, Optional
from PIL import Image

def draw_image(
    canvas: Image.Image,
    image: Image.Image,
    xy: Tuple[int, int] = (0, 0),
    size: Optional[Tuple[int, int]] = None,
) -> None:
    """Paste an image onto a canvas with optional resizing."""
    if size and (size[0] != image.size[0] or size[1] != image.size[1]):
        image = image.resize(size)
    
    # Use the image itself as mask if it has alpha channel for proper blending
    mask = image if image.mode == 'RGBA' else None
    canvas.paste(image, xy, mask=mask)
