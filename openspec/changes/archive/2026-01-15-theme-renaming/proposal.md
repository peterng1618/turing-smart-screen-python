# Change: Theme Renaming

## Why
Theme folders were inconsistently named, making it difficult to identify their screen size and orientation without opening their configuration files.

## What Changes
- New utility script `tools/rename-themes.py` to automate folder renaming based on `theme.yaml` metadata.
- Support for inferring missing metadata from background image dimensions.
- Automatic update of `theme.yaml` with inferred screen size.
- Strictly renamed all theme folders in `res/themes/` to follow `{Size}_{Orientation}_{OriginalName}` convention.

## Impact
- Affected code: `tools/rename-themes.py`, `res/themes/*`
