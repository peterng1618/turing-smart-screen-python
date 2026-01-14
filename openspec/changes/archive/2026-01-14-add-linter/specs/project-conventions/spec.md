## MODIFIED Requirements
### Requirement: Code Quality Enforcement
The project SHALL use `ruff` to enforce code quality and stylistic consistency.

#### Scenario: Running Ruff Linter
- **WHEN** a developer runs `ruff check .`
- **THEN** it MUST check all Python files for syntax errors (E9), logic bugs (F), and style violations (E).
- **AND** it MUST respect component-specific exclusions defined in `pyproject.toml`.

#### Scenario: Running Ruff Formatter
- **WHEN** a developer runs `ruff format .`
- **THEN** it MUST reformat code to match the project's line length (120) and indent style (4 spaces).
