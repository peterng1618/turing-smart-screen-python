# Design: Decoupled Pillow Rendering Library

## Problem
Rendering logic is tightly coupled to `library/display.py` and global `config.THEME_DATA`, making it hard to maintain and impossible to reuse in the Theme Editor.
However, we must preserve exact backward compatibility for existing themes and the "Display" API used by `main.py`.

## Solution
Extract ALL rendering logic into a pure `library.rendering` package, covering Text, Graphs, Shapes, and Images.
The existing `Display` and `LcdComm` classes will become thin wrappers that resolve config data and delegate drawing to these pure functions.

### 1. New Package Structure
```
library/
  rendering/
    __init__.py
    text.py    # text drawing, font loading, render_text_block (supersampling)
    graphs.py  # bar charts, radial gauges, line graphs
    shapes.py  # rectangle (shearing), circle, arc, triangle, line, render_shape_to_image
    icons.py   # FontAwesome icon rendering, unicode resolution, render_icon_block
    effects.py # opacity, rotation, shadow, outline
    image.py   # image loading, resizing
```

### 2. Function Signatures (Pure)
Functions must NOT access `config.THEME_DATA`. All data must be passed as arguments.

```python
# library/rendering/text.py
def render_text(
    canvas: Image.Image,
    text: str,
    xy: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    anchor: str = "lt",
    ...
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)
```

### 3. Testing Strategy

#### Unit Tests
- Test each pure function in isolation.
- Verify pixel output for known inputs (e.g., render a red square, assert center pixel is red).

#### Integration Tests (Regression)
- **Golden Image Testing**: 
    1. Create a set of "golden" expected images from the *curren* codebase (before refactor) for standard themes.
    2. After refactor, run the same rendering sequence.
    3. Compare output pixels. Tolerance should be 0% for pure refactor.

#### Smoke Tests
- Run the full `Display` initialization sequence with a complex theme (e.g., `features_test_theme.yaml`) to catch crashes or missing assets.

### 4. `Display` Class Refactor
The `Display` class will become a coordinator:
1. Read `config.THEME_DATA`.
2. Resolve assets (fonts, images) to absolute paths/objects.
3. Call `library.rendering` functions.

```python
# library/display.py
def display_static_text(self):
    for text_conf in config.THEME_DATA['static_text']:
        # ... resolve args ...
        rendering.text.render_text(self.lcd.screen_image, ...)
```

## Risks
- **Performance**: Function call overhead is negligible in Python compared to I/O and PIL operations.
- **Complexity**: Passing many arguments ("prop drilling") might make `Display` code verbose. *Mitigation*: Use data classes or typed dictionaries if argument lists grow too large.
