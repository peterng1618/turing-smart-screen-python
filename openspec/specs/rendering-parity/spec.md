# rendering-parity Specification

## Purpose
Ensures consistency and visual parity between the Theme Editor preview and the hardware display output by centralizing rendering logic and providing clear guidelines for component implementations.
## Requirements
### Requirement: Shared Rendering Library
The system SHALL provide a shared, Pillow-based rendering library (`library.rendering`) that serves as the source of truth for ALL rendering paths, including hardware display, static text, and Theme Editor baking.

#### Scenario: Unified Text Styling
- **GIVEN** a text element with rotation and a shadow
- **WHEN** rendered via `LcdComm.DisplayText` or `UiRenderer`
- **THEN** the output MUST be visually identical
- **AND** the implementation MUST delegate to `library.rendering.effects.apply_styling`

### Requirement: GUI Visual Parity
The Theme Editor GUI SHALL maintain visual parity with the hardware display. While the GUI may use native `QPainter` calls for performance during live editing, its output must align with the Pillow-rendered results.

#### Scenario: Text Element Rendering
Given a text element in a theme
When rendered by the shared library (hardware/legacy)
Then it must be rendered using the Pillow-based `library.rendering.text` module

#### Scenario: GUI Parity
Given an element displayed on a PreviewCanvas
When the canvas is repainted
Then it may use `QPainter` for performance
And it MUST be visually equivalent to the hardware-rendered Pillow output

### Requirement: Library Rendering
The library rendering functions SHALL be decoupled from global configuration and accept explicit parameters to support reuse by the Theme Editor.

#### Scenario: Decoupled Rendering Logic
Given the `library` package
When rendering functions are called
Then they must accept explicit parameters (text, font, color) or data objects
And they must NOT rely on the global `config.THEME_DATA` state

