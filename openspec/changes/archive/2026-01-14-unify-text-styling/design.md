# Design: Unified Text Styling

## Context
The project recently introduced a modular `library.rendering` package. While `UiRenderer` (used for baking and stats) uses this new pipeline, the core `LcdComm.DisplayText` method (used for legacy hardware paths) still manages its own Pillow canvases and ignores advanced styling properties like rotation and shadows.

## Decisions
- **Delegate to Library**: `LcdComm.DisplayText` will be refactored to call `rendering_text.render_text_block` and `rendering_effects.apply_styling`.
- **Zero-Impact Defaults**: Properties like `rotation=0` or `shadow=None` will bypass transformation logical paths to ensure no performance hit or visual regression for legacy themes.
- **Statelessness**: The hardware path will remain stateless, with `Display.py` resolving theme properties and passing them as explicit arguments.
- **Bounding Box Consistency**: Use the unified `get_text_bbox` to ensure that dimensions and offsets are calculated identically across all rendering paths.

## Risks / Trade-offs
- **Performance**: Double-buffering (rendering to small image then pasting) adds slight overhead compared to direct drawing, but the visual quality (anti-aliasing) and feature parity justify the cost.
