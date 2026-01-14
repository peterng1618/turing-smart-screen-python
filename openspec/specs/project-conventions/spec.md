# project-conventions Specification

## Purpose
TBD - created by archiving change add-linter. Update Purpose after archive.
## Requirements
### Requirement: Code Quality Enforcement
The project SHALL use `ruff` to enforce code quality and stylistic consistency.

#### Scenario: Running Ruff Linter
- **WHEN** a developer runs `ruff check .`
- **THEN** it MUST check all Python files for syntax errors (E9), logic bugs (F), and style violations (E).
- **AND** it MUST respect component-specific exclusions defined in `pyproject.toml`.

#### Scenario: Running Ruff Formatter
- **WHEN** a developer runs `ruff format .`
- **THEN** it MUST reformat code to match the project's line length (120) and indent style (4 spaces).

### Requirement: Architecture-Aware Linting
The linter configuration SHALL apply rules contextually based on the component architecture.

#### Scenario: Theme Editor Wildcards
- **GIVEN** `theme_editor` module relies on Qt
- **THEN** wildcard imports (`from PyQt6.QtCore import *`) MUST be permitted in that directory
- **BUT** restricted elsewhere (e.g., core logic)

### Requirement: Linting Philosophy
The project documentation SHALL explicitly define the pragmatic linting approach.

#### Scenario: Philosophy Documentation
- **WHEN** a contributor checks project conventions
- **THEN** they MUST see the "Linting Philosophy" section
- **AND** understand that legacy violations are tolerated but new correctness bugs are strictly forbidden

