# Change: refactor-theme-editor

## Why
The current Theme Editor architecture has evolved organically, resulting in several issues:
- **Fragmented State**: UI state (like selection) is synchronized manually between panels and the main window using debounce timers and recursive guards, leading to stability issues and "state chasing".
- **Monolithic Files**: `main_window.py` and `properties_panel.py` are excessively large (1000+ lines), making them difficult to maintain and test.
- **Inconsistent Patterns**: Mixed usage of direct model manipulation and command patterns, with some logic duplicated across components.
- **Limited Test Coverage**: While core undo commands are tested, higher-level interaction logic and panel state management lack comprehensive coverage.

## What Changes
- **Unified State Store**: Reclaim the lost role of `ThemeModel` by replacing/encapsulating it within a comprehensive `EditorState`. This "Store" will be the single source of truth for both the theme document and the ephemeral UI state (selection, tools, view settings), eliminating "state chasing" across the app.
- **Architecture Refactoring**:
    - Split `MainWindow` into smaller, focused components (e.g., `ActionsManager`, `PanelManager`, `StatusBarController`).
    - Modularize `PropertiesPanel` by breaking it down into specialized property sections (Transform, Appearance, Typography, etc.) that can be independently developed and tested.
    - Standardize on a strict MVC/Mediator pattern where panels only communicate via the central `EditorState`.
- **Improved PyQt Patterns**: Use more robust signal/slot connections and avoid direct cross-component references where possible.
- **Enhanced Test Suite**:
    - Implement tests for the new `EditorState` logic.
    - Add integration tests for selection synchronization and property updates.
    - Ensure 100% coverage for all application logic.

## Impact
- **Affected specs**: `theme-editor` (Modified architectural requirements)
- **Affected code**: 
    - `theme_editor/models/` (New `EditorState`, Refined `ThemeModel`)
    - `theme_editor/panels/` (Split `PropertiesPanel`, Simplified `LayerPanel`)
    - `theme_editor/main_window.py` (Decomposed into sub-modules)
    - `tests/theme_editor/` (New and updated tests)
