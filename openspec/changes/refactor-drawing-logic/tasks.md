# Tasks: Refactor Drawing Logic

- [x] **Infrastructure & Centralization**
    - [x] Create `library/rendering/draw.py` as a high-level orchestration layer.
    - [x] Move color parsing and background compositing logic to `library/rendering/draw.py`.
    - [x] Implement `text()`, `progress_bar()`, `line_graph()`, and `radial_progress_bar()` helpers.
    - [x] Add unit tests for `library/rendering/draw.py` in `tests/unit/test_rendering_draw.py`.

- [x] **LcdComm Refactoring**
    - [x] Refactor `LcdComm.DisplayText` to use `rendering.draw.text`.
    - [x] Refactor `LcdComm.DisplayProgressBar` to use `rendering.draw.progress_bar`.
    - [x] Refactor `LcdComm.DisplayLineGraph` to use `rendering.draw.line_graph`.
    - [x] Refactor `LcdComm.DisplayRadialProgressBar` to use `rendering.draw.radial_progress_bar`.
    - [x] Ensure all `LcdComm` subclasses still work correctly with these changes.
    - [x] Verify with `tests/library/lcd/test_lcd_comm_rev_*.py`.

- [x] **UiRenderer Refactoring**
    - [x] Refactor `UiRenderer.draw_text_to_image` to use `rendering.draw.text`.
    - [x] Verify that Theme Editor preview still matches hardware output.

- [x] **Cleanup & Validation**
    - [x] Remove redundant `font_cache` and `image_cache` logic from `LcdComm` (Decided to keep for in-memory performance, but unified calling path).
    - [x] Run full test suite: `pytest tests/unit`.
    - [x] Validate OpenSpec change: `openspec validate refactor-drawing-logic --strict`.
    - [x] Archive OpenSpec change upon approval.
