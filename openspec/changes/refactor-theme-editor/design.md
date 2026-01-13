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


### 4. Handling Locked Elements
The Unified Store makes the "Locked" vs "Selectable" distinction much cleaner:

- **Canvas Interaction**: When a user clicks the canvas, the `Canvas` component queries `EditorState` to see if the element at that position is `locked`. If locked, the `Canvas` simply **does not** trigger a selection change.
- **Layer Panel Interaction**: When a user clicks a row in the `LayerPanel`, it **always** updates `EditorState.selection`.
- **Observer Logic (Selection Box)**:
    - The `Canvas` observes `EditorState.selection`.
    - For each selected ID, it checks if `element.locked == True`.
    - If locked: It shows a "Locked" selection box (e.g., dotted lines, no resize handles).
    - If NOT locked: It shows the standard transform handles.
- **Observer Logic (Properties)**:
    - The `PropertiesPanel` observes `EditorState.selection` and always shows the properties, allowing the user to unlock the element or edit values even when canvas interaction is blocked.

### 5. Modularization Strategy

## Testing Plan
- **Unit Tests**: Test the `EditorState` logic in isolation (selection logic, multi-select behavior).
- **Integration Tests**: Verify that updating selection in the `Store` correctly propagates to all panels without looping.
- **Regression Tests**: Ensure existing `UndoCommand` tests still pass with the new model.
