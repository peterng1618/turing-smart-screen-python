# Change: review-video-gui

## Why
To ensure the project adheres to conventions (code style, architecture, testing) for critical components: Video Background Support and GUI Theme Editor. Currently, these features lack formal specifications and have gaps in integration testing.

## What Changes
- Formalize specifications for "Video Support" and "Theme Editor".
- Add missing integration tests for `video_processor.py`.
- Add smoke tests for `main_window.py` initialization.
- Implement comprehensive Theme Editor features:
    - Layer Management (Duplicate, Reorder, Delete, Group/Ungroup) with full Undo/Redo support.
    - Legacy Theme compatibility (Import/Export).
    - UI Refinements: Enhanced icons (Eye/Lock), intuitive shortcuts (Delete key), and dedicated buttons for all management actions.
    - Interaction improvements: Locked layers are unselectable on canvas but manageable in panel.

## Impact
- Affected specs: `video-support`, `theme-editor` (New, Refined)
- Affected code: 
    - `theme_editor/models/` (ThemeModel, Element)
    - `theme_editor/panels/` (LayerPanel)
    - `theme_editor/commands/` (Undo Commands)
    - `theme_editor/canvas/` (Canvas Interaction)
    - `tests/` (New advanced model/undo tests)
