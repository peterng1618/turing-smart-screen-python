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
import argparse
from pathlib import Path

# Add project root to path for library imports
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from library.pythoncheck import check_python_version
check_python_version()

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
except ImportError:
    print("[ERROR] PyQt6 is required for Theme Editor v2.")
    print("Install with: pip install PyQt6~=6.6.0")
    sys.exit(1)

from theme_editor.main_window import MainWindow


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
