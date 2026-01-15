# Capability: Theme Validation

The theme validation capability ensures that any directory within `res/themes/` containing a `theme.yaml` file is structurally sound and can be rendered by the application without fatal errors.

## ADDED Requirements
### Requirement: Theme Discovery
The system MUST be able to automatically discover all active themes in the `res/themes/` directory.

#### Scenario: Discovering valid themes
- **WHEN** several directories in `res/themes/` exist: `ThemeA` (with `theme.yaml`), `ThemeB` (with `theme.yaml`), and `--ThemeC` (with `theme.yaml`).
- **AND** the discovery logic is executed.
- **THEN** `ThemeA` and `ThemeB` MUST be included in the list.
- **AND** directories starting with `--` SHOULD be ignored.

### Requirement: Loading Verification
The system MUST attempt to load each theme's configuration and report any syntax or structural errors.

#### Scenario: Invalid YAML structure
- **WHEN** a theme with a malformed `theme.yaml` is validated.
- **THEN** the validation MUST fail and report the specific YAML error.

### Requirement: Render Smoke Test
The system MUST attempt to initialize the display and render the theme's static elements using a simulated LCD.

#### Scenario: Missing background asset
- **WHEN** a theme where `BACKGROUND` points to a non-existent file is validated.
- **THEN** the rendering pass MUST fail.
- **AND** the error MUST indicate the missing asset path.

### Requirement: Automated Reporting
The system MUST provide a summarized report of all validated themes, indicating success or failure for each.

#### Scenario: Multi-theme validation report
- **WHEN** 10 themes where 9 are valid and 1 has a broken image path are validated.
- **THEN** the report MUST show 9 PASSED and 1 FAILED.
- **AND** the FAILED entry MUST include the error reason.
