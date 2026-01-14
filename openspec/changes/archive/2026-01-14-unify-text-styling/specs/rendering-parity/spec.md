## MODIFIED Requirements
### Requirement: Shared Rendering Library
The system SHALL provide a shared, Pillow-based rendering library (`library.rendering`) that serves as the source of truth for ALL rendering paths, including hardware display, static text, and Theme Editor baking.

#### Scenario: Unified Text Styling
- **GIVEN** a text element with rotation and a shadow
- **WHEN** rendered via `LcdComm.DisplayText` or `UiRenderer`
- **THEN** the output MUST be visually identical
- **AND** the implementation MUST delegate to `library.rendering.effects.apply_styling`
