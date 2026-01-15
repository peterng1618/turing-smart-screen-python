import subprocess
import os
import sys
import traceback
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Set environment variable to skip global theme load on library import
os.environ["SKIP_GLOBAL_THEME_LOAD"] = "1"

from library import config

class ThemeValidationResult:
    def __init__(self, theme_name: str, success: bool, error: Optional[str] = None, traceback: Optional[str] = None):
        self.theme_name = theme_name
        self.success = success
        self.error = error
        self.traceback = traceback

    def to_dict(self):
        return {
            "theme_name": self.theme_name,
            "success": self.success,
            "error": self.error,
            "traceback": self.traceback
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class ThemeValidator:
    def __init__(self):
        self.themes_dir = config.MAIN_DIRECTORY / "res" / "themes"

    def list_active_themes(self) -> List[str]:
        """List all directories in res/themes that contain a theme.yaml and don't start with --"""
        themes = []
        for item in self.themes_dir.iterdir():
            if item.is_dir() and not item.name.startswith("--"):
                if (item / "theme.yaml").exists():
                    themes.append(item.name)
        return sorted(themes)

    def validate_theme(self, theme_name: str) -> ThemeValidationResult:
        """Attempt to load and smoke-render a single theme."""
        import unittest.mock
        
        def mock_exit(code=0):
            raise Exception(f"Application triggered sys.exit({code}) during theme load - check theme.yaml syntax")

        try:
            # 1. Setup mock config for validation
            config.CONFIG_DATA["config"]["HW_SENSORS"] = "STATIC"
            config.CONFIG_DATA["config"]["THEME"] = theme_name
            config.CONFIG_DATA["display"]["REVISION"] = "SIMU"
            
            # 2. Load theme with sys.exit protection
            # Legacy code might call sys.exit(0) on fatal errors
            with unittest.mock.patch("sys.exit", side_effect=mock_exit), \
                 unittest.mock.patch("os._exit", side_effect=mock_exit):
                config.load_theme()
            
            # 3. Initialize display (Simulated)
            from library.display import display
            display.initialize_display()
            
            # 4. Smoke render static elements
            display.display_static_images()
            display.display_static_text()
            
            # 5. Check if screen_image was created
            if display.lcd.screen_image is None:
                return ThemeValidationResult(theme_name, False, "Simulated display failed to create screen_image")
            
            return ThemeValidationResult(theme_name, True)

        except Exception as e:
            return ThemeValidationResult(
                theme_name, 
                False, 
                str(e), 
                traceback.format_exc()
            )

    def validate_theme_subprocess(self, theme_name: str, timeout: int = 20) -> ThemeValidationResult:
        """Validate a theme in a completely separate OS process using subprocess.run."""
        script_path = Path(__file__).parent.parent.parent / "tools" / "validate-themes.py"
        try:
            cmd = [
                sys.executable, 
                str(script_path), 
                "--theme", theme_name,
                "--json-output"
            ]
            
            cp = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                check=False
            )
            
            if cp.returncode == 0:
                # Try to parse JSON from stdout
                try:
                    data = json.loads(cp.stdout)
                    return ThemeValidationResult.from_dict(data[0])
                except json.JSONDecodeError:
                    return ThemeValidationResult(theme_name, False, f"CLI output was not valid JSON: {cp.stdout[:200]}")
            else:
                return ThemeValidationResult(theme_name, False, f"CLI failed with code {cp.returncode}: {cp.stderr[:500]}")

        except subprocess.TimeoutExpired:
            return ThemeValidationResult(theme_name, False, f"Validation timed out after {timeout}s")
        except Exception as e:
            return ThemeValidationResult(theme_name, False, f"Subprocess execution failed: {e}")

    def validate_all(self) -> List[ThemeValidationResult]:
        """Validate all discovered themes."""
        results = []
        themes = self.list_active_themes()
        for theme in themes:
            print(f"Validating {theme}...")
            results.append(self.validate_theme_subprocess(theme))
        return results
