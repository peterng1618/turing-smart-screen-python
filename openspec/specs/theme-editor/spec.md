# theme-editor Specification

## Purpose
TBD - created by archiving change review-video-gui. Update Purpose after archive.
## Requirements
### Requirement: Theme Management
The Theme Editor SHALL allow creating, opening, and saving themes.

#### Scenario: Create New Theme
- **WHEN** user selects "New Theme"
- **THEN** a new theme structure MUST be initialized with default layers (Backgrounds, Groups)
- **AND** the Undo stack MUST be cleared

#### Scenario: Open Existing Theme
- **WHEN** user selects "Open Theme"
- **THEN** the theme MUST be loaded from the theme-editor.yaml from the selected folder
- **AND** the Undo stack MUST be cleared

#### Scenario: Open Existing Legacy Theme
- **WHEN** user selects "Open Theme"
- **AND** the theme-editor.yaml is not found BUT only a theme.yaml is found
- **THEN** the theme MUST be loaded from the theme.yaml from the selected folder
- **AND** the properties required for the theme-editor.yaml BUT not found in the theme.yaml MUST be generated and set to default values
- **AND** the Undo stack MUST be cleared

### Requirement: Theme Save and Export
The Theme Editor SHALL always export themes to the legacy theme.yaml format for compatibility. Strictly follows the yaml schema as defined in the theme_example.yaml file.

#### Scenario: Save & Export Theme
- **WHEN** user selects "Save Theme"
- **THEN** the theme MUST be saved to the theme-editor.yaml in the selected folder
- **AND** the theme MUST be exported to the theme.yaml in the selected folder
- **AND** the Undo stack MUST NOT be cleared

#### Scenario: Save Reminder
- **WHEN** user tries to open a theme or create a new theme
- **AND** the theme has changes that have not been saved
- **THEN** the Theme Editor MUST display a message asking the user if the user wants to save the changes, discard the changes, or cancel the operation. With the save option selected by default
- **AND** if the user wants to save the changes, the Theme Editor MUST save the theme and then continue with the open or create operation
- **AND** if the user wants to discard the changes, the Theme Editor MUST discard the changes and then continue with the open or create operation
- **AND** if the user wants to cancel the operation, the Theme Editor MUST cancel the operation and do nothing

### Requirement: Layer Management
The Theme Editor SHALL provide a Layer Panel to manage UI elements using buttons, context menus, and keyboard shortcuts.

#### Scenario: Layer Panel UI
- **ALL** layer management actions (Duplicate, Group, Ungroup, Delete, Rename) MUST be available as buttons at the bottom of the panel.
- **EXCEPT** for Visibility and Lock toggles, which SHALL be managed via icons on the layer item itself.
- **AND** standard context menu options (Duplicate, Group, Ungroup, Delete, Rename, Move Up, Move Down) MUST be available.
- **AND** the Visibility checkbox MUST be removed (use Eye icon only).
- **AND** the Eye and Lock icons MUST visually reflect their state (Open/Closed Eye, Closed/Open Lock).
- **AND** the Delete action MUST use a "Trash Can" icon instead of "-".

#### Scenario: Keyboard Deletion
- **WHEN** an element is selected
- **AND** the "Delete" key is pressed
- **THEN** the element MUST be deleted (with undo support).

#### Scenario: Locked Layer Interaction
- **WHEN** a layer is locked
- **THEN** it MUST NOT be selectable on the Canvas.
- **AND** it MUST NOT be draggable/movable on the Canvas.
- **BUT** it MUST remain selectable in the Layer Panel.

#### Scenario: Add Element
- **WHEN** an element is added via toolbar
- **THEN** it MUST appear in the Layer Panel
- **AND** be selected in the Properties Panel
- **AND** it MUST be recoverable via the Undo stack

#### Scenario: Duplicate Element
- **WHEN** an element is duplicated via a Layer Panel button or right click menu
- **THEN** the element MUST be duplicated
- **AND** it MUST appear in the Layer Panel below the original e;ement
- **AND** it MUST be selected in the Properties Panel
- **AND** it MUST be recoverable via the Undo stack

#### Scenario: Delete Element
- **WHEN** an element is deleted via a Layer Panel button, right click menu, or keyboard shortcut
- **THEN** the element MUST be deleted
- **AND** it MUST be removed from the Layer Panel
- **AND** it MUST be removed from the Properties Panel
- **AND** it MUST be recoverable via the Undo stack

#### Scenario: Reorder Layer/Element
- **WHEN** an element order is changed via a Layer Panel up/down button, right click menu (Move Up/Down), or Drag-and-Drop
- **THEN** the element MUST be moved one position up or down (or to target position) in the Layer Panel
- **AND** the element data MUST be moved accordingly in the theme-editor.yaml
- **AND** it MUST be recoverable via the Undo stack

### Requirement: Undo/Redo Support
All model-changing operations SHALL be undoable, including Element Creation, Deletion, Duplication, and Property Changes.

#### Scenario: Undo Property Change
- **WHEN** a property is changed
- **AND** "Undo" is triggered
- **THEN** the property MUST revert to its previous value

#### Scenario: Redo Property Change
- **WHEN** "Undo" is triggered
- **AND** "Redo" is triggered
- **THEN** the property MUST revert to its previous value before the "Undo" operation

#### Scenario: Undo/Redo Create/Delete/Duplicate
- **WHEN** an element is Created, Deleted, or Duplicated
- **THEN** the action MUST be fully reversible via Undo/Redo.

