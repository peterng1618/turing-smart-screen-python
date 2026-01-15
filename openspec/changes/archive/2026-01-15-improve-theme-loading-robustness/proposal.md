# Improve Theme Loading Robustness

Following the theme renaming work, several themes failed to load due to strict metadata checks and inconsistent `DISPLAY_SIZE` formats in `theme.yaml`. This change addresses those issues by standardizing the `DISPLAY_SIZE` suffix and implementing robust normalization in the loading logic.

## User Review Required

> [!IMPORTANT]
> This change updates all `theme.yaml` files in `res/themes/` to ensure they have the proper `DISPLAY_SIZE` format (e.g., `3.5"`). Legcy formats (e.g., `'3.5'`) will be automatically corrected.

## Proposed Changes

### Theme Utilities
- Updated `tools/rename-themes.py` to ensure `DISPLAY_SIZE` is normalized with the `"` suffix when updating YAML files.
- Refined the renaming logic to always check and fix metadata, even for folders already matching the naming pattern.

### Core Library
- Updated `library/display.py` to normalize `DISPLAY_SIZE` from strings/floats before determining display resolution.
- Updated `library/config.py` to use normalized comparison for theme compatibility checks.

### Theme Editor
- Updated `theme-editor.py` to use normalized size checks for circular screen masking.

## Verification Results

### Automated Tests
- Verified `test_load_theme.py` successfully loads renamed themes (e.g., `5.0_H_NZXT_color`).
- Standard themes like `3.5_V_Theme2` are now correctly pointed to in `config.yaml`.

### Manual Verification
- Verified `theme-editor.py` loads multiple theme revisions successfully without errors.
