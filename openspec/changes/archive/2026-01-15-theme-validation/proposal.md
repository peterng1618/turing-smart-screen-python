# Change: Theme Regression Validation Script

## Why
As the library adds new features, existing themes might break. A regression test script ensures that changes to the core library or rendering engine don't break the massive library of existing themes.

## What Changes
- Implement `ThemeValidator` class to discover and validate themes via smoke rendering.
- Create `tools/validate-themes.py` CLI for standalone validation.
- Add `tests/repro_theme_regression.py` for automated pytest-based testing.
- **BUGS**: Fixed corrupted `NZXT_color` theme.

## Impact
- Affected specs: `theme-validation` (NEW)
- Affected code: `library/config.py`, `library/display.py`, `tests/tools/`
