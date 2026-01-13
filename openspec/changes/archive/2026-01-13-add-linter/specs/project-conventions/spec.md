## ADDED Requirements
### Requirement: Code Quality Enforcement
The project SHALL use automated tools to enforce code quality.

#### Scenario: Running Linter
- **WHEN** a developer runs the lint command (e.g., `pylint .`)
- **THEN** it MUST check all Python files for syntax errors, coding standards violations, and potential bugs
- **AND** report them according to the project's configuration

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
