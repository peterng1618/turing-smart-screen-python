## ADDED Requirements
### Requirement: Theme Renaming Tool
The system SHALL provide a utility to rename theme folders based on their screen size and orientation.

#### Scenario: Rename unformatted folder
- **WHEN** the script is run on a folder containing a valid `theme.yaml`
- **THEN** the folder is renamed with the `{Size}_{Orientation}_` prefix
