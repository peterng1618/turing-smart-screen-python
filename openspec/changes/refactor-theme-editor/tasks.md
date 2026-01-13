## 1. Preparation & Model Refinement
- [ ] 1.1 Create `theme_editor/models/editor_state.py` to hold both persistent `ThemeDoc` and ephemeral UI state (Store pattern).
- [ ] 1.2 Refactor `ThemeModel` to be a lightweight View Model that projects data from `EditorState`.
- [ ] 1.3 Implement comprehensive tests for `EditorState` using a TDD approach (selection, transformation logic).

## 2. Global State Integration
- [ ] 2.1 Refactor `PreviewCanvas` to observe and update `EditorState` directly via signals.
- [ ] 2.2 Refactor `LayerPanel` to observe and update `EditorState` via the View Model wrapper.
- [ ] 2.3 Remove manual recursive guards and debounce timers from `MainWindow`.


## 3. Modularizing Properties Panel
- [ ] 3.1 Create `theme_editor/panels/properties/` directory structure.
- [ ] 3.2 Extract property sections into separate files (Transform, Appearance, Shadow, etc.).
- [ ] 3.3 Re-implement `PropertiesPanel` as a light container that bootstraps these sections.
- [ ] 3.4 Add unit tests for individual property sections.

## 4. MainWindow Decomposition
- [ ] 4.1 Extract `ActionsManager` logic to handle all `QAction` creation and shortcut mapping.
- [ ] 4.2 Extract `ThemeController` to handle file I/O and "Bake" logic.
- [ ] 4.3 Simplify `main_window.py` to only handle high-level layout and dock management.

## 5. Verification & Finalization
- [ ] 5.1 Run full regression suite (`tests/`).
- [ ] 5.2 Implement missing integration tests for the new architecture.
- [ ] 5.3 Manual validation of all editor features.
