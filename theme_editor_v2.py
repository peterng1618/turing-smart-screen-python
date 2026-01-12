#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Theme Editor v2 - Main Entry Point

A visual WYSIWYG theme editor for Turing Smart Screen.
Uses PyQt6 for the UI and theme-v2.yaml format for themes.

Usage:
    python theme_editor_v2.py [theme_name]
    
Examples:
    python theme_editor_v2.py                    # Create new theme
    python theme_editor_v2.py Cyberpunk          # Edit existing theme
"""

import sys
import os
import argparse
from pathlib import Path

# Prevent library.config from loading default theme on import
os.environ["SKIP_GLOBAL_THEME_LOAD"] = "1"

# Add project root to path for library imports
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from library.pythoncheck import check_python_version
check_python_version()

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon, QPalette, QColor
except ImportError:
    print("[ERROR] PyQt6 is required for Theme Editor v2.")
    print("Install with: pip install PyQt6~=6.6.0")
    sys.exit(1)


def set_app_theme(app: QApplication, mode: str = "dark") -> None:
    """Apply dark or light theme to the application."""
    app.setStyle("Fusion")
    
    palette = QPalette()
    
    if mode == "light":
        # Clean Material Light Theme
        window = QColor(245, 245, 245)
        base = QColor(255, 255, 255)
        text = QColor(33, 33, 33)
        highlight = QColor(42, 130, 218)
        
        palette.setColor(QPalette.ColorRole.Window, window)
        palette.setColor(QPalette.ColorRole.WindowText, text)
        palette.setColor(QPalette.ColorRole.Base, base)
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(235, 235, 235))
        palette.setColor(QPalette.ColorRole.ToolTipBase, base)
        palette.setColor(QPalette.ColorRole.ToolTipText, text)
        palette.setColor(QPalette.ColorRole.Text, text)
        palette.setColor(QPalette.ColorRole.Button, window)
        palette.setColor(QPalette.ColorRole.ButtonText, text)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Link, highlight)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
    else:
        # Deep Dark theme
        dark_gray = QColor(45, 45, 45)
        darker_gray = QColor(30, 30, 30)
        blue = QColor(42, 130, 218)
        
        palette.setColor(QPalette.ColorRole.Window, dark_gray)
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, darker_gray)
        palette.setColor(QPalette.ColorRole.AlternateBase, dark_gray)
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, dark_gray)
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, blue)
        palette.setColor(QPalette.ColorRole.Highlight, blue)
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    # Apply disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
    
    app.setPalette(palette)


from theme_editor.main_window import MainWindow
from PyQt6.QtCore import QSettings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Theme Editor v2 - Visual theme editor for Turing Smart Screen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                    Create a new theme
    %(prog)s Cyberpunk          Edit existing 'Cyberpunk' theme
    %(prog)s --new MyTheme      Create new theme named 'MyTheme'
        """
    )
    parser.add_argument(
        "theme",
        nargs="?",
        default=None,
        help="Name of existing theme to edit (folder name in res/themes/)"
    )
    parser.add_argument(
        "--new",
        metavar="NAME",
        help="Create a new theme with the specified name"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging"
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for Theme Editor v2."""
    args = parse_args()
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Turing Theme Editor")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("Turing Smart Screen")
    
    # Initial theme from settings
    settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
    current_theme = settings.value("appTheme", "dark")
    set_app_theme(app, current_theme)
    
    # Set application icon
    icon_path = PROJECT_ROOT / "res" / "icons" / "monitor-icon-17865" / "64.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Determine theme to load
    theme_name = args.new if args.new else args.theme
    is_new_theme = args.new is not None
    
    # Create and show main window
    window = MainWindow(
        theme_name=theme_name,
        is_new_theme=is_new_theme,
        debug=args.debug
    )
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
