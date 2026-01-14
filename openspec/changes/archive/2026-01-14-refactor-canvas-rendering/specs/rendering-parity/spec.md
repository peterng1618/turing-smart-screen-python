# Rendering Parity

## ADDED Requirements

### Requirement: Pillow-Based Rendering
The system SHALL render all Theme Editor canvas elements using Pillow (PIL) to ensure visual parity with the hardware display logic.

#### Scenario: Text Element Rendering
Given a text element with font "Roboto", size 16, and color white
When the element is displayed on the PreviewCanvas
Then it must be rendered using `PIL.ImageDraw.Draw.text` (via library)
And the resulting pixels must match the output of `library.display.Display` for the same configuration
And it must NOT use `QPainter.drawText` directly

#### Scenario: Shape Element Rendering
Given a rectangle element with specific dimensions and color
When the element is displayed
Then it must be rendered using `PIL.ImageDraw.Draw.rectangle`
And converted to a QPixmap for display

#### Scenario: Selection Overlay
Given a selected element
When the canvas is repainted
Then the selection halo/handles must be drawn using standard QPainter (overlay)
And the element content itself must remain the Pillow-rendered image

### Requirement: Library Rendering
The library rendering functions SHALL be decoupled from global configuration and accept explicit parameters to support reuse by the Theme Editor.

#### Scenario: Decoupled Rendering Logic
Given the `library` package
When rendering functions are called
Then they must accept explicit parameters (text, font, color) or data objects
And they must NOT rely on the global `config.THEME_DATA` state
