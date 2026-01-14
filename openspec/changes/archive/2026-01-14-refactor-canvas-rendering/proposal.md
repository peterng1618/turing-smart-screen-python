# Change: Refactor PreviewCanvas to use Pillow Rendering

## Why
Currently, the Theme Editor uses `QPainter` instructions to approximate the look of elements.
The runtime (`library/display.py`) uses `PIL` (Pillow) to generate images.
This leads to inconsistencies (font rendering discrepancies, anti-aliasing differences, layout drifts).
The goal is to replicate the display behaviour as closely as possible, so that what the user sees while designing the theme matches what will be rendered on the monitor.

## What Changes
1.  **Holistic Modularization**: Refactor ALL character/graph/shape/image rendering logic from `library/display.py` and `library/lcd/*` into a new `library/rendering/` package.
2.  **Pure Functions**: Ensure new rendering functions are stateless and accept explicit arguments (decoupled from `config.THEME_DATA`).
3.  **Legacy Compatibility**: Retain Text, Graph, and Image rendering in `Display`/`LcdComm` (delegating to new pure functions) to support existing themes.
4.  **Cleanup**: Remove recently added Shape/Line/Icon drawing methods from `Display`/`LcdComm` as they are unused by legacy themes and new themes will use the Editor's baked UI.
5.  **Extensive Testing**: Implement a comprehensive test suite (Unit, Integration, Smoke) to guarantee no regressions in display behavior.

## Impact
*   **Affected Specs**: `rendering-parity` (new capability - library side only).
*   **Affected Code**:
    *   `library/display.py`
    *   `library/lcd/*`
    *   `library/stats.py`
    *   `tests/` (significant additions)
*   **Excluded**: No changes to `theme_editor/` at this stage.

## Risks
*   **Regression**: Refactoring core display logic puts the main functionality at risk.
    *   *Mitigation*: The requested extensive test suite is the primary mitigation. We will not merge without 100% pass rate on regression tests.

## Verification
*   Visual comparison between `theme-editor.py` (simulated device) and `Theme Editor v2`.
*   Unit tests for the renderer.
