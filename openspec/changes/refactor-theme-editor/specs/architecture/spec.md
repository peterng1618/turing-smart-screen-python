# Capability: architecture

## MODIFIED Requirements
### Requirement: Centralized State Management (Unified Store)
The Theme Editor MUST maintain a single source of truth for all application state, encapsulated in a unified `EditorState` store. This store SHALL manage both the persistent document data (`ThemeDoc`) and the ephemeral UI state (selection, tools, view settings).

#### Scenario: Selection Synchronization
- **WHEN** the selection state is updated in the unified `EditorState` store
- **THEN** all registered UI components (Layer Panel, Canvas, Properties Panel) MUST automatically reflect this change via direct signal observation
- **AND** there MUST NOT be any manual cross-component synchronization logic (e.g., recursive guards or debounce timers in MainWindow).

### Requirement: View Model Separation
The Theme Editor SHALL use specialized View Models to project the central state for specific UI components.

#### Scenario: Layer Panel Projection
- **GIVEN** the unified `EditorState`
- **WHEN** the `LayerPanel` needs to display the element tree
- **THEN** it MUST interact with a `ThemeModel` that acts as a projection of the `EditorState`, rather than owning the data itself.

### Requirement: Modular Component Architecture
The Theme Editor SHALL be composed of modular, decoupled components with single responsibilities.

#### Scenario: Property Panel Extensibility
- **GIVEN** a requirement to add a new element type
- **WHEN** implementing the properties for this element
- **THEN** it MUST be possible to add a new property section in a separate file without modifying the main PropertiesPanel logic.
