# Tasks

## 1. Refactor LcdComm
- [ ] 1.1 Update `LcdComm.DisplayText` to use `library.rendering` <!-- id: 0 -->
    - Delegate to `render_text_block` and `apply_styling`
    - Ensure `opacity` and `rotation` are correctly handled

## 2. Update Display Orchestration
- [ ] 2.1 Update `Display.display_static_text` to pass styling keys <!-- id: 1 -->
    - Extract `rotation`, `shadow`, `outline` from theme YAML

## 3. Verification
- [ ] 3.1 Create a test theme with rotated/shadowed static text <!-- id: 2 -->
- [ ] 3.2 Verify visual parity between Theme Editor preview and hardware simulation <!-- id: 3 -->
- [ ] 3.3 Regression test: Load a legacy theme (e.g., `LandscapeMagicBlue`) and verify pixel-perfect parity with existing rendering <!-- id: 4 -->
