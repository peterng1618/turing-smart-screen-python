## ADDED Requirements
### Requirement: Video Processing Pipeline
The system SHALL provide a video processing pipeline to prepare video backgrounds for themes.

#### Scenario: Full Pipeline Execution
- **WHEN** `process_video` is called with a source video and theme configuration
- **THEN** it MUST triger the UI overlay baking process
- **AND** it MUST trim, rotate, crop, crossfade (loop), and bake the UI overlay onto the video frames
- **AND** encode the result to a compatible MP4 format (H.264, no audio)

### Requirement: Seamless Loop
The system SHALL support creating seamless loops via crossfading.

#### Scenario: Crossfade Loop
- **WHEN** `LOOP_FADE_DURATION` is greater than 0
- **THEN** the end of the video MUST be blended into the start of the video
- **AND** the final duration MUST be reduced by the fade duration
