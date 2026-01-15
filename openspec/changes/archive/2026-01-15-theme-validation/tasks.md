# Tasks: Theme Regression Validation

- [x] Core Logic: Implement `ThemeValidator` class in `tests/tools/theme_validator.py`.
    - [x] Add method to list all available themes.
    - [x] Add method to validate a single theme (load + static render).
- [x] Test CLI: Create `tools/validate-themes.py` script.
    - [x] Support validating a single theme by name.
    - [x] Support validating all themes.
    - [x] Output a clear summary table (Theme, Status, Error).
- [x] Integration: Add a pytest-based wrapper in `tests/repro_theme_regression.py`.
    - [x] Parameterize tests over all themes discovered in `res/themes`.
- [x] Verification:
    - [x] Run validator against all themes.
    - [x] Fix any themes found with errors (if minor).
