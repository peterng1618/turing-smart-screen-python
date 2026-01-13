# Design: Theme Editor Refactor

## Current Architecture
The current implementation uses a "Sync via MainWindow" pattern:
1. `LayerPanel` emits `selection_changed`.
2. `MainWindow` catches it, starts a timer.
3. Timer triggers `_process_selection_change`.
4. `MainWindow` manually calls `canvas.select_elements()` and `properties_panel.show_properties()`.
5. `PreviewCanvas` also emits `selection_changed`, triggering the reverse sync.

## Proposed Architecture: Unified Editor Store

We will introduce `EditorState` as the **Single Source of Truth**. Instead of having a separate `ThemeModel` and `EditorState` chasing each other, we will unify them into a robust Store pattern that encapsulates both the persistent document and ephemeral UI state.

### 1. The Unified State Store (`EditorState`)
`EditorState` will be the central registry and primary entry point for all data operations. It will hold:

- **The Document (`ThemeDoc`)**: The raw, persistent data (elements, theme info, background). This is what gets serialized to YAML.
- **The UI State**: 
    - `selection`: A set of currently selected element IDs.
    - `hover`: The ID of the element currently under the mouse.
    - `active_tool`: The current tool selected (Select, Move, Add, etc.).
    - `view_settings`: Zoom level, grid visibility, guide positions.
- **The Undo History**: Owns the `QUndoStack`.

### 2. Implementation: From Model to Store
We will refactor the existing `ThemeModel` (a `QAbstractItemModel`) to be a **View Model** that merely projects the data inside `EditorState`.
- `EditorState` manages the logic and state.
- `ThemeModel` provides the tree structure for the `LayerPanel`.
- Signals like `selectionChanged` will originate from `EditorState` and be observed by all components.

### 3. Flow of Control (Uni-directional)
1. **User Action**: User interacts with a component (e.g., clicks Canvas).
2. **Command Dispatch**: An action creates a `QUndoCommand`.
3. **State Update**: The command modifies the `EditorState` (and its nested `ThemeDoc`).
4. **Signal Propagation**: `EditorState` emits refined signals (e.g., `selectionChanged`, `elementUpdated`).
5. **UI Refresh**: All panels (Layer, Properties, Canvas) listen to these signals and update their display.


### 3. Modularization Strategy

#### PropertiesPanel
Instead of one massive file, we will use a registry of property editors:
- `PropertiesPanel` (Main Container)
- `BasePropertySection` (Abstract base)
- `TransformSection`, `AppearanceSection`, `TypographySection`, `ShadowSection`, `OutlineSection` (Modular files in `theme_editor/panels/properties/`)

#### MainWindow
Decompose into:
- `theme_editor/ui/main_window.py`: Entry point and layout.
- `theme_editor/ui/actions.py`: QAction definitions and management.
- `theme_editor/ui/menus.py`: Menu bar construction.
- `theme_editor/controllers/theme_controller.py`: High-level operations (New, Open, Save, Bake).

## Testing Plan
- **Unit Tests**: Test the `EditorState` logic in isolation (selection logic, multi-select behavior).
- **Integration Tests**: Verify that updating selection in the `Store` correctly propagates to all panels without looping.
- **Regression Tests**: Ensure existing `UndoCommand` tests still pass with the new model.
