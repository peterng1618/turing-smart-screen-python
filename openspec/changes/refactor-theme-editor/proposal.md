# Change: refactor-theme-editor

## Why
The current Theme Editor architecture has evolved organically, resulting in several issues:
- **Fragmented State**: UI state (like selection) is synchronized manually between panels and the main window using debounce timers and recursive guards, leading to stability issues and "state chasing".
- **Monolithic Files**: `main_window.py` and `properties_panel.py` are excessively large (1000+ lines), making them difficult to maintain and test.
- **Inconsistent Patterns**: Mixed usage of direct model manipulation and command patterns, with some logic duplicated across components.
- **Limited Test Coverage**: While core undo commands are tested, higher-level interaction logic and panel state management lack comprehensive coverage.

## What Changes
- **Unified State Store**: Implemented `EditorState` as the Single Source of Truth for both persistent document data and ephemeral UI state (selection, guides, zoom).
- **Architecture Refactoring**:
    - **View Model Projection**: Refactored `ThemeModel` to act as a projection of `EditorState`, maintaining compatibility with `QAbstractItemModel` consumers.
    - **Modular Properties**: Decomposed `PropertiesPanel` into specialized, pluggable `PropertySection` components.
    - **Geometry Centralization**: Extracted complex geometry/snapping logic from `PreviewCanvas` to `theme_editor/utils/geometry.py`.
- **Improved Qt Patterns**: 
    - Eliminated "state chasing" by using a uni-directional selection flow (Component -> Store -> Signal -> All Components).
    - Reduced oversized files and addressed duplication in `PreviewCanvas`.
- **Enhanced Verification**:
    - Established a comprehensive test suite in `tests/theme_editor/` covering store integrity, selection sync, and hit-testing.

## Impact
- **Affected specs**: `theme-editor` (Modified architectural requirements)
- **Affected code**: 
    - `theme_editor/models/` (New `EditorState`, Refined `ThemeModel`)
    - `theme_editor/panels/` (Split `PropertiesPanel`, Simplified `LayerPanel`)
    - `theme_editor/main_window.py` (Decomposed into sub-modules)
    - `tests/theme_editor/` (New and updated tests)
