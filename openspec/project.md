# Project Context

## Purpose
turing-smart-screen-python is a Python system monitor program and abstraction library for small IPS USB-C (UART) displays (Turing Smart Screen, XuanFang, etc.). 
It allows users to:
1. Use the screen as a system monitor with customizable themes (YAML-based).
2. Control the display from Python projects (display images, text, progress bars, etc.).
3. Create and edit themes using a GUI Theme Editor.

This fork specifically focuses on:
1. Adding video background support for the 5-inch display (hardware revision C)
2. Improving the capabilities of the theming engine by supporting more advanced elements (more graphs types, more properties, more styles, more animations).
3. Developing a robust & interactive, WYSIWYG GUI Theme Editor.

## Tech Stack
- **Language**: Python 3.9+
- **GUI Frameworks**: 
    - `PyQt6` (for Theme Editor v2)
    - `tkinter` with `sv-ttk` (for Configuration Wizard)
    - `pystray` (System Tray Icon)
- **Core Dependencies**:
    - `pyserial`: Serial communication with displays.
    - `PyYAML`, `ruamel.yaml`: Theme and config parsing.
- **System Monitoring**:
    - `psutil` (Cross-platform metrics)
    - `GPUtil`, `pyadl`, `pyamdgpuinfo` (GPU stats)
    - `pythonnet` / `LibreHardwareMonitor` (Windows hardware stats)
- **Media Processing**:
    - `Pillow`: Image processing.
    - `numpy`: efficient array handling.
    - `av` (PyAV): Video decoding.
    - `numba`: JIT acceleration for video overlay.
- **Distribution**: `pyinstaller`

## Project Conventions

### Code Style
- **Naming**: Classes in `CamelCase`, functions and variables in `snake_case`.
- **Typing**: Extensive use of Python type hints (`List`, `Dict`, `Optional`, `Any` from `typing`).
- **Linting**: Run `ruff check .` before committing.
    - **Philosophy**: Correctness over style. Rules catching bugs (undefined names, bare excepts) are strict for new code. Legacy violations are locally suppressed (`# noqa`).
    - **Configuration**: `pyproject.toml` (phased approach).
- **Documentation**: Docstrings for all public classes and functions, detailing purpose, arguments, and return values (Google-style-ish).
- **Logging**: Use `logging.getLogger(__name__)`.



### Architecture Patterns
- **Modular Design**:
    - `library/`: Core abstraction logic, helpers, and managers (e.g., `font_manager.py`).
    - `theme_editor/`: GUI application for editing themes, following an MVC-like pattern (custom Models extending Qt models).
    - `res/`: Assets (themes, icons, docs).
- **Plugins/Drivers**: Abstraction layer to handle different hardware protocols (Turing, XuanFang) transparently.
- **Configuration**: YAML-based configuration (`config.yaml`) and theme definitions (`theme.yaml`).

### Testing Strategy
- Tests located in `tests/` directory.
- `repro_*.py` scripts used for reproducing specific issues.
- Integration tests for UI logic (e.g., `test_theme_save.py`).

### Git Workflow
- Standard feature-branch workflow.

## Domain Context
- **Hardware Protocols**: The screens communicate via USB-UART. Different revisions/vendors use different protocols (handshakes, commands).
- **Themes**: Defined in YAML, supporting static elements (text, images, shapes) and dynamic elements (bound to system stats).
- **Coordinates**: Global coordinate system for placing elements on the screen.

## Important Constraints
- **Performance**: Video/rendering needs to be efficient (using `numba`, `numpy`) as these are driven by Python on potentially modest hardware.
- **Hardware Compatibility**: Must support multiple vendors (Turing, XuanFang, Kipye) and OSes (Windows, Linux, macOS).
- **DPI Awareness**: GUI tools need to handle high-DPI screens correctly.

## External Dependencies
- **Font Awesome**: Used for icons, downloaded/cached via `FontManager`.
- **Github**: Used for self-update checks and downloading assets.
- **LibreHardwareMonitor**: Optional dependency on Windows for advanced sensors.
