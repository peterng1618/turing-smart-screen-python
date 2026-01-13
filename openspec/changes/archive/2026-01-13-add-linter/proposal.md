## Why
The project currently lacks automated code quality enforcement. Adding a linter will ensures consistent code style, catch potential bugs early, and maintain maintainability as the codebase grows. Ruff is chosen as a modern & performant tool.

## What Changes
- Add `ruff` to `requirements.txt`.
- Configure `tool.ruff` in `pyproject.toml` with a **phased strategy**:
    - **Global**: Ignore legacy style issues (`E402`, `F401`, `F403`, etc.) but **enforce correctness** (`F821`, `E722`, `E711`).
    - **Per-Directory**: Apply stricter or relaxed rules based on component constraints (e.g., allow wildcards in `theme_editor` due to Qt, loose imports in `tests`).
- Update `openspec/project.md` with the "Linting Philosophy" (pragmatism over purity).

## Impact
- New dependency: `ruff`
- New file: `pyproject.toml`
- CI/Local workflow: Developers should run `ruff check .` before committing.
- **Safety**: Legacy code remains untouched; new bugs are caught.
