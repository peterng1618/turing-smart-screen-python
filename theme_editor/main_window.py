# SPDX-License-Identifier: GPL-3.0-or-later
"""
Main Window for Theme Editor v2.

Provides the main application window with:
- Menu bar with file, edit, view, and help menus
- Toolbar with common actions
- Dockable panels (layers, properties)
- Central canvas for visual editing
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QDockWidget, QToolBar, QStatusBar,
    QMenuBar, QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QUndoStack

from theme_editor.panels.layer_panel import LayerPanel
from theme_editor.panels.properties_panel import PropertiesPanel
from theme_editor.canvas.preview_canvas import PreviewCanvas
from theme_editor.models.theme_model import ThemeModel
from theme_editor.utils.yaml_io import ThemeYamlIO

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window for the Theme Editor v2 application."""
    
    # Default window size
    DEFAULT_WIDTH = 1400
    DEFAULT_HEIGHT = 900
    
    def __init__(
        self,
        theme_name: Optional[str] = None,
        is_new_theme: bool = False,
        debug: bool = False,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the main window.
        
        Args:
            theme_name: Name of theme to load, or None for empty editor
            is_new_theme: If True, create a new theme with theme_name
            debug: Enable debug logging
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._theme_name = theme_name
        self._is_new_theme = is_new_theme
        self._debug = debug
        self._modified = False
        
        # Configure logging
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        # Initialize undo stack
        self._undo_stack = QUndoStack(self)
        self._undo_stack.cleanChanged.connect(self._on_clean_changed)
        
        # Initialize model
        self._theme_model = ThemeModel(self._undo_stack)
        
        # Setup UI
        self._setup_window()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_panels()
        self._create_status_bar()
        self._restore_settings()
        
        # Load theme if specified
        if theme_name:
            self._load_theme(theme_name, is_new_theme)
        else:
            self._new_theme()
    
    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("Theme Editor v2")
        self.setMinimumSize(800, 600)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        
        # Enable window state saving
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks |
            QMainWindow.DockOption.AllowTabbedDocks |
            QMainWindow.DockOption.AnimatedDocks
        )
    
    def _create_actions(self) -> None:
        """Create all application actions."""
        # File actions
        self.action_new = QAction("&New Theme", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.setStatusTip("Create a new theme")
        self.action_new.triggered.connect(self._new_theme)
        
        self.action_open = QAction("&Open Theme...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.setStatusTip("Open an existing theme")
        self.action_open.triggered.connect(self._open_theme)
        
        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.setStatusTip("Save the current theme")
        self.action_save.triggered.connect(self._save_theme)
        
        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.setStatusTip("Save theme with a new name")
        self.action_save_as.triggered.connect(self._save_theme_as)
        
        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_exit.setStatusTip("Exit the application")
        self.action_exit.triggered.connect(self.close)
        
        # Edit actions
        self.action_undo = self._undo_stack.createUndoAction(self, "&Undo")
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        
        self.action_redo = self._undo_stack.createRedoAction(self, "&Redo")
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        
        self.action_cut = QAction("Cu&t", self)
        self.action_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self.action_cut.triggered.connect(self._cut)
        
        self.action_copy = QAction("&Copy", self)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.action_copy.triggered.connect(self._copy)
        
        self.action_paste = QAction("&Paste", self)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.action_paste.triggered.connect(self._paste)
        
        self.action_delete = QAction("&Delete", self)
        self.action_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.action_delete.triggered.connect(self._delete_selection)
        
        self.action_duplicate = QAction("D&uplicate", self)
        self.action_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.action_duplicate.triggered.connect(self._duplicate)
        
        self.action_group = QAction("&Group", self)
        self.action_group.setShortcut(QKeySequence("Ctrl+G"))
        self.action_group.triggered.connect(self._group_selection)
        
        self.action_ungroup = QAction("U&ngroup", self)
        self.action_ungroup.setShortcut(QKeySequence("Ctrl+Shift+G"))
        self.action_ungroup.triggered.connect(self._ungroup_selection)
        
        # View actions
        self.action_zoom_in = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.action_zoom_in.triggered.connect(self._zoom_in)
        
        self.action_zoom_out = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.action_zoom_out.triggered.connect(self._zoom_out)
        
        self.action_zoom_fit = QAction("Zoom to &Fit", self)
        self.action_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.action_zoom_fit.triggered.connect(self._zoom_fit)
        
        self.action_show_grid = QAction("Show &Grid", self)
        self.action_show_grid.setCheckable(True)
        self.action_show_grid.setChecked(True)
        self.action_show_grid.triggered.connect(self._toggle_grid)
        
        self.action_show_guides = QAction("Show G&uides", self)
        self.action_show_guides.setCheckable(True)
        self.action_show_guides.setChecked(True)
        self.action_show_guides.triggered.connect(self._toggle_guides)
    
    def _create_menus(self) -> None:
        """Create the menu bar and menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_cut)
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)
        edit_menu.addAction(self.action_delete)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_duplicate)
        edit_menu.addAction(self.action_group)
        edit_menu.addAction(self.action_ungroup)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.action_zoom_in)
        view_menu.addAction(self.action_zoom_out)
        view_menu.addAction(self.action_zoom_fit)
        view_menu.addSeparator()
        view_menu.addAction(self.action_show_grid)
        view_menu.addAction(self.action_show_guides)
        view_menu.addSeparator()
        
        # Panels submenu
        self._panels_menu = view_menu.addMenu("&Panels")
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        action_about = help_menu.addAction("&About")
        action_about.triggered.connect(self._show_about)
    
    def _create_toolbar(self) -> None:
        """Create the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)
        toolbar.addSeparator()
        toolbar.addAction(self.action_undo)
        toolbar.addAction(self.action_redo)
        toolbar.addSeparator()
        toolbar.addAction(self.action_zoom_in)
        toolbar.addAction(self.action_zoom_out)
        toolbar.addAction(self.action_zoom_fit)
    
    def _create_panels(self) -> None:
        """Create the dockable panels and central widget."""
        # Create central canvas
        self._canvas = PreviewCanvas(self._theme_model, self._undo_stack)
        self.setCentralWidget(self._canvas)
        
        # Create layer panel (left dock)
        self._layer_panel = LayerPanel(self._theme_model, self._undo_stack)
        layer_dock = QDockWidget("Layers", self)
        layer_dock.setObjectName("LayersDock")
        layer_dock.setWidget(self._layer_panel)
        layer_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, layer_dock)
        self._panels_menu.addAction(layer_dock.toggleViewAction())
        
        # Create properties panel (right dock)
        self._properties_panel = PropertiesPanel(self._theme_model, self._undo_stack)
        props_dock = QDockWidget("Properties", self)
        props_dock.setObjectName("PropertiesDock")
        props_dock.setWidget(self._properties_panel)
        props_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)
        self._panels_menu.addAction(props_dock.toggleViewAction())
        
        # Connect selection signals
        self._layer_panel.selection_changed.connect(self._on_layer_selection_changed)
        self._canvas.selection_changed.connect(self._on_canvas_selection_changed)
    
    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")
    
    def _restore_settings(self) -> None:
        """Restore window settings from previous session."""
        settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)
    
    def _save_settings(self) -> None:
        """Save window settings for next session."""
        settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
    
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        if self._maybe_save():
            self._save_settings()
            event.accept()
        else:
            event.ignore()
    
    def _maybe_save(self) -> bool:
        """
        Check if there are unsaved changes and prompt user.
        
        Returns:
            True if safe to proceed (saved or discarded), False to cancel
        """
        if not self._undo_stack.isClean():
            result = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "The theme has unsaved changes. Do you want to save?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if result == QMessageBox.StandardButton.Save:
                return self._save_theme()
            elif result == QMessageBox.StandardButton.Cancel:
                return False
        return True
    
    def _update_title(self) -> None:
        """Update window title with theme name and modified state."""
        title = "Theme Editor v2"
        if self._theme_name:
            title = f"{self._theme_name} - {title}"
        if not self._undo_stack.isClean():
            title = f"*{title}"
        self.setWindowTitle(title)
    
    def _on_clean_changed(self, clean: bool) -> None:
        """Handle undo stack clean state change."""
        self._update_title()
    
    # --- File Operations ---
    
    def _new_theme(self) -> None:
        """Create a new empty theme."""
        if not self._maybe_save():
            return
        
        self._theme_name = None
        self._theme_model.clear()
        self._undo_stack.clear()
        self._update_title()
        self._status_bar.showMessage("New theme created")
        logger.info("Created new theme")
    
    def _open_theme(self) -> None:
        """Open an existing theme."""
        if not self._maybe_save():
            return
        
        themes_dir = Path(__file__).parent / "res" / "themes"
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Theme",
            str(themes_dir),
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            theme_name = Path(folder).name
            self._load_theme(theme_name, is_new=False)
    
    def _load_theme(self, name: str, is_new: bool = False) -> None:
        """
        Load a theme by name.
        
        Args:
            name: Theme folder name
            is_new: If True, create new theme with this name
        """
        try:
            if is_new:
                self._theme_model.create_new(name)
                self._status_bar.showMessage(f"Created new theme: {name}")
            else:
                yaml_io = ThemeYamlIO()
                theme_data = yaml_io.load(name)
                self._theme_model.load_from_data(theme_data)
                self._status_bar.showMessage(f"Loaded theme: {name}")
            
            self._theme_name = name
            self._undo_stack.clear()
            self._update_title()
            logger.info(f"Loaded theme: {name}")
            
        except Exception as e:
            logger.error(f"Failed to load theme: {e}")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load theme '{name}':\n{e}"
            )
    
    def _save_theme(self) -> bool:
        """
        Save the current theme.
        
        Returns:
            True if saved successfully
        """
        if not self._theme_name:
            return self._save_theme_as()
        
        try:
            yaml_io = ThemeYamlIO()
            theme_data = self._theme_model.to_data()
            yaml_io.save(self._theme_name, theme_data)
            
            self._undo_stack.setClean()
            self._status_bar.showMessage(f"Saved: {self._theme_name}")
            logger.info(f"Saved theme: {self._theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save theme: {e}")
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save theme:\n{e}"
            )
            return False
    
    def _save_theme_as(self) -> bool:
        """
        Save theme with a new name.
        
        Returns:
            True if saved successfully
        """
        themes_dir = Path(__file__).parent / "res" / "themes"
        folder = QFileDialog.getExistingDirectory(
            self,
            "Save Theme As",
            str(themes_dir),
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self._theme_name = Path(folder).name
            return self._save_theme()
        return False
    
    # --- Edit Operations ---
    
    def _cut(self) -> None:
        """Cut selected elements."""
        self._copy()
        self._delete_selection()
    
    def _copy(self) -> None:
        """Copy selected elements."""
        # TODO: Implement copy
        self._status_bar.showMessage("Copy: Not yet implemented")
    
    def _paste(self) -> None:
        """Paste elements from clipboard."""
        # TODO: Implement paste
        self._status_bar.showMessage("Paste: Not yet implemented")
    
    def _delete_selection(self) -> None:
        """Delete selected elements."""
        # TODO: Implement delete
        self._status_bar.showMessage("Delete: Not yet implemented")
    
    def _duplicate(self) -> None:
        """Duplicate selected elements."""
        # TODO: Implement duplicate
        self._status_bar.showMessage("Duplicate: Not yet implemented")
    
    def _group_selection(self) -> None:
        """Group selected elements."""
        # TODO: Implement group
        self._status_bar.showMessage("Group: Not yet implemented")
    
    def _ungroup_selection(self) -> None:
        """Ungroup selected group."""
        # TODO: Implement ungroup
        self._status_bar.showMessage("Ungroup: Not yet implemented")
    
    # --- View Operations ---
    
    def _zoom_in(self) -> None:
        """Zoom in on canvas."""
        self._canvas.zoom_in()
    
    def _zoom_out(self) -> None:
        """Zoom out on canvas."""
        self._canvas.zoom_out()
    
    def _zoom_fit(self) -> None:
        """Zoom to fit theme in view."""
        self._canvas.zoom_fit()
    
    def _toggle_grid(self, checked: bool) -> None:
        """Toggle grid visibility."""
        self._canvas.set_grid_visible(checked)
    
    def _toggle_guides(self, checked: bool) -> None:
        """Toggle guides visibility."""
        self._canvas.set_guides_visible(checked)
    
    # --- Selection Sync ---
    
    _syncing_selection = False  # Guard against recursion
    
    def _on_layer_selection_changed(self, element_ids: list) -> None:
        """Handle layer panel selection change."""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self._canvas.select_elements(element_ids)
            if element_ids:
                self._properties_panel.show_properties(element_ids[0])
            else:
                self._properties_panel.clear()
        finally:
            self._syncing_selection = False
    
    def _on_canvas_selection_changed(self, element_ids: list) -> None:
        """Handle canvas selection change."""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self._layer_panel.select_elements(element_ids)
            if element_ids:
                self._properties_panel.show_properties(element_ids[0])
            else:
                self._properties_panel.clear()
        finally:
            self._syncing_selection = False
    
    # --- Help ---
    
    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Theme Editor v2",
            "<h2>Theme Editor v2</h2>"
            "<p>Version 2.0.0</p>"
            "<p>A visual WYSIWYG theme editor for Turing Smart Screen.</p>"
            "<p>Uses theme-v2.yaml format for themes.</p>"
            "<p><a href='https://github.com/mathoudebine/turing-smart-screen-python'>"
            "GitHub Repository</a></p>"
        )
