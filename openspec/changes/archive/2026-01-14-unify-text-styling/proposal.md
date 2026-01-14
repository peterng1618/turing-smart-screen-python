# Change: Unify Text Styling

## Why
Currently, advanced styling features (rotation, shadow, opacity, outline) are implemented in the `UiRenderer` but aren't fully accessible to legacy hardware display paths like `LcdComm.DisplayText`. This creates a disconnect between what the Theme Editor can preview (baked UI) and what is rendered at runtime for static/dynamic text.

## What Changes
- **MODIFIED** `LcdComm.DisplayText` to utilize the `library.rendering` package for all text blocks, while maintaining strict backward compatibility for legacy callers.
- **ADDED** support for `rotation`, `shadow`, and `outline` in the static text processing logic of `Display.py`.
- **UNIFIED** the rendering pipeline so that hardware display and pre-backed images use identical drawing logic.

## Backward Compatibility
- **Legacy Themes**: Static text without `rotation`, `shadow`, or `outline` keys will render exactly as before (defaults to 0/None).
- **LcdComm API**: The signature of `DisplayText` will be preserved or gracefully extended with optional arguments to avoid breaking existing integrations.
- **Visual Parity**: No-effect rendering results MUST be pixel-identical to the current implementation.

## Impact
- **Affected specs**: `rendering-parity`
- **Affected code**: `library/lcd/lcd_comm.py`, `library/display.py`, `library/ui_renderer.py`
