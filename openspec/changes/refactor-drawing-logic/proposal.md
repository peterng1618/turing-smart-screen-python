# Change: Refactor Drawing Logic

## Why
The current architecture has drawing logic spread across multiple layers (LcdComm, UiRenderer, library/rendering), leading to code duplication, inconsistencies in rendered output, and increased maintenance burden.

## What Changes
- **NEW**: Centralized high-level drawing orchestration in `library/rendering/draw.py`.
- **REFACTOR**: `LcdComm` high-level methods (`DisplayText`, `DisplayProgressBar`, etc.) converted to thin wrappers delegating to `rendering.draw`.
- **REFACTOR**: `UiRenderer` updated to use shared rendering helpers for consistent theme-based output.
- **IMPROVE**: Decouple hardware drivers from visual presentation logic.

## Impact
- Affected specs: `rendering-parity`, `drawing-unification`
- Affected code: `library/lcd/lcd_comm.py`, `library/ui_renderer.py`, `library/display.py`, `library/stats.py`

## Risks & Mitigations
- **Breaking Changes**: External scripts relying on `LcdComm` drawing methods might be affected if the signature changes.
  - *Mitigation*: Maintain signature compatibility for `LcdComm` methods while refactoring their internal implementation.
- **Performance**: Adding a delegation layer might introduce slight overhead.
  - *Mitigation*: Ensure the orchestration layer is lightweight and utilizes efficient Pillow/Numpy operations.
- **Hardware Specifics**: Different hardware revisions might have subtle drawing differences.
  - *Mitigation*: Keep hardware-specific logic (like the RGB565 conversion or specific command sequences) isolated in `LcdComm` and its subclasses.
