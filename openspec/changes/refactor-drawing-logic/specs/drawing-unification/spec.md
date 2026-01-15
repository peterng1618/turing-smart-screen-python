# drawing-unification Specification Delta

## MODIFIED Requirements
### Requirement: Shared Rendering Library
The system SHALL provide a shared, Pillow-based rendering library (`library.rendering`) that serves as the source of truth for ALL rendering paths. **Crucially, high-level drawing orchestration SHALL be centralized in this library to ensure consistency across hardware drivers and theme engines.**

#### Scenario: Unified Text Styling
- **GIVEN** a text element with rotation and a shadow
- **WHEN** rendered via `LcdComm.DisplayText` or `UiRenderer`
- **THEN** the output MUST be visually identical
- **AND** the implementation MUST delegate to `library.rendering.effects.apply_styling`

#### Scenario: Unified Element Drawing
- **GIVEN** a request to draw a complex element (e.g., progress bar or graph)
- **WHEN** executed via any presentation layer (`LcdComm`, `UiRenderer`, or Theme Editor)
- **THEN** the core drawing logic MUST be provided by `library.rendering`
- **AND** presentation-specific wrappers MUST only handle target-specific orchestration (e.g., PIL canvas vs Hardware transmission).

## ADDED Requirements

### Requirement: Driver Layer Decoupling
The hardware communication layer (`LcdComm`) SHALL be decoupled from high-level drawing logic. It SHOULD only provide low-level primitives for bitmap transmission and hardware control.

#### Scenario: Text Drawing Delegation
- **GIVEN** a call to `LcdComm.DisplayText`
- **WHEN** implemented
- **THEN** it MUST internally delegate to `library.rendering.text` or a shared drawing orchestration helper
- **AND** it MUST NOT contain standalone PIL drawing logic for text, shadows, or outlines.

### Requirement: Unified Graphics API
The system SHALL provide a unified graphics API for drawing common system monitor elements (graphs, bars) that is consistent regardless of the output target.

#### Scenario: Progress Bar Parity
- **GIVEN** a progress bar definition in a theme
- **WHEN** rendered on hardware via `LcdComm` or in the Theme Editor preview
- **THEN** both MUST use the same `library.rendering.graphs` implementation
- **AND** the visual styling (colors, outlines, dimensions) MUST be identical.
