# Design: Automated Linting with Ruff

## Context
The project uses a variety of Python modules across core library, GUI, and tests. A one-size-fits-all linting approach is too restrictive, especially for legacy code and GUI (Qt) patterns.

## Decisions
- **Tool Selection**: Use `ruff` for both linting (`ruff check`) and formatting (`ruff format`).
- **Contextual Rules**:
    - Allow wildcard imports in `theme_editor/` (Qt compatibility).
    - Allow non-top-level imports in `library/` (platform-specific / lazy loading).
    - Allow math-heavy variable names (x, y, w, h) via `E741` exclusion.
- **Enforcement**: Linting MUST be run as part of the `openspec validate` process and before declaring tasks complete.

## Risks / Trade-offs
- **Legacy Violations**: Attempting to fix all legacy violations would create massive, risky diffs.
- **Mitigation**: Use `# noqa` locally or global `ignore` rules for established patterns.
