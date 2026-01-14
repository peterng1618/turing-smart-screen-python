# Change: Add Linter (Ruff)

## Why
To ensure consistent code quality and catch errors early, the project needs an automated linting tool. `ruff` has been chosen for its speed and comprehensive rule set, replacing the placeholder `pylint` mentioned in early specs.

## What Changes
- **MODIFIED** `project-conventions` specification to explicitly require `ruff`.
- **FORMALIZED** the linting rules (E4, E7, E9, F) and exclusions (E402, F401, etc.) in the project's baseline.
- **ESTABLISHED** the pragmatic linting philosophy in the automated verification requirements.

## Impact
- **Affected specs**: `project-conventions`
- **Affected code**: `pyproject.toml` (already exists, but now strictly enforced)
