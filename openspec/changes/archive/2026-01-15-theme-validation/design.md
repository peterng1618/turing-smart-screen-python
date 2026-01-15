# Design: Theme Regression Validation

## Overview
The validation script aims to identify themes that are currently broken due to hardware-specific requirements missing in a software-only environment (e.g., missing sensors, missing display size property) or actual bugs in the rendering logic.

## Architecture
The system will leverage existing application logic to ensure high fidelity to real usage.

### Theme Discovery
- Scan `res/themes/` for subdirectories containing `theme.yaml`.
- Ignore directories starting with `--` (common convention for disabled/example themes).

### Validation Loop
For each theme:
1. **Mock Configuration**: Use `library.config` with `HW_SENSORS=STATIC` and `REVISION=SIMU`.
2. **Setup Environment**:
    - Set `config.CONFIG_DATA['config']['THEME']` to the current theme.
    - Trigger `config.load_theme()`.
3. **Initialize Rendering**:
    - Instantiate `display` (which sets up `LcdSimulated`).
    - Call `display.initialize_display()`.
4. **Smoke Render**:
    - Call `display.display_static_images()`.
    - Call `display.display_static_text()`.
5. **Heuristic Checks**:
    - Check if `display.lcd.screen_image` is valid.
    - Monitor for `[ERROR]` logs during the process.

### Error Handling
- Use a `try-except` block per theme.
- Capture stack traces for the final report.
- Distinguish between "Fatals" (crash) and "Warnings" (missing non-critical keys like `DISPLAY_SIZE`).

## Alternatives Considered
- **Unit testing specific themes**: Too high maintenance as themes are added frequently.
- **Headless Theme Editor v2**: Better for regression of the editor itself, but too complex for a simple "Does my theme still work?" check.
- **Image Comparison**: Highly desirable but requires "Golden Images" for every theme, which is currently infeasible to maintain manually.
