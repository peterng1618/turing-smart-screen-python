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
    QMenuBar, QMenu, QMessageBox, QFileDialog, QApplication,
    QColorDialog, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QUndoStack, QColor

from theme_editor.panels.layer_panel import LayerPanel
from theme_editor.panels.properties_panel import PropertiesPanel
from theme_editor.panels.tool_panel import ToolPanel
from theme_editor.canvas.preview_canvas import PreviewCanvas
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import Element, ElementType, create_element, GroupElement
from theme_editor.commands.undo_commands import (
    MoveElementCommand, ChangePropertyCommand, AddElementCommand, 
    DeleteElementCommand, GroupElementsCommand, UngroupElementsCommand
)
from theme_editor.utils.yaml_io import ThemeYamlIO
from library.mock_data import MockDataProvider

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
        self._create_main_toolbar()
        self._create_panels()
        self._create_status_bar()
        self._restore_settings()
        
        # Populate mock sensor data for preview
        MockDataProvider.populate()
        
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
        
        # Selection debounce timer
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(100)  # 100ms debounce
        self._selection_timer.timeout.connect(self._process_selection_change)
        self._pending_selection_ids = []
        self._pending_selection_source = None
        
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
        
        self.action_restore_layout = QAction("&Restore Default Layout", self)
        self.action_restore_layout.setStatusTip("Reset panels to their default positions")
        self.action_restore_layout.triggered.connect(self._restore_default_layout)
        
        # --- Creation Tools ---
        # Text
        self.action_add_static_text = QAction("📝 Static Text", self)
        self.action_add_static_text.triggered.connect(lambda: self._add_element(ElementType.TEXT))
        
        self.action_add_dynamic_text = QAction("🔄 Dynamic Text", self)
        self.action_add_dynamic_text.triggered.connect(lambda: self._add_element(ElementType.DYNAMIC_TEXT))
        
        # Stats (CPU, GPU, etc.)
        self.action_add_cpu = QAction("💻 CPU", self)
        self.action_add_gpu = QAction("🎮 GPU", self)
        self.action_add_ram = QAction("💾 RAM", self)
        self.action_add_disk = QAction("💽 Disk", self)
        self.action_add_net = QAction("🌐 Net", self)
        
        # Shapes & UI
        self.action_add_rect = QAction("🟦 Rect", self)
        self.action_add_rect.triggered.connect(lambda: self._add_element(ElementType.RECTANGLE))
        
        self.action_add_circle = QAction("🟡 Circle", self)
        self.action_add_circle.triggered.connect(lambda: self._add_element(ElementType.CIRCLE))
        
        self.action_add_image = QAction("🖼️ Image", self)
        self.action_add_image.triggered.connect(lambda: self._add_element(ElementType.IMAGE))
        
        self.action_add_icon = QAction("⚙️ Icon", self)
        self.action_add_icon.triggered.connect(lambda: self._add_element(ElementType.ICON))
    
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
        self._panels_menu.addSeparator()
        self._panels_menu.addAction(self.action_restore_layout)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        action_about = help_menu.addAction("&About")
        action_about.triggered.connect(self._show_about)

    def _create_main_toolbar(self) -> None:
        """Create the main horizontal toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
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
        
    def _create_tools_toolbar(self) -> None:
        """Create the Photoshop-style left vertical toolbar."""
        toolbar = QToolBar("Tools")
        toolbar.setObjectName("ToolsToolbar")
        toolbar.setMovable(False)
        toolbar.setOrientation(Qt.Orientation.Vertical)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)
        
        # Group 1: Text
        toolbar.addAction(self.action_add_static_text)
        toolbar.addAction(self.action_add_dynamic_text)
        toolbar.addSeparator()
        
        # Group 2: Stats
        # For stats, we'll use a single button with a menu for now, or just line up the main ones
        for action in [self.action_add_cpu, self.action_add_gpu, self.action_add_ram, self.action_add_disk, self.action_add_net]:
            menu = QMenu(self)
            t_act = menu.addAction("Text Variant")
            t_act.triggered.connect(lambda checked, a=action: self._add_stat(a.text()[2:], "TEXT"))
            g_act = menu.addAction("Graph Variant")
            g_act.triggered.connect(lambda checked, a=action: self._add_stat(a.text()[2:], "GRAPH"))
            r_act = menu.addAction("Radial Variant")
            r_act.triggered.connect(lambda checked, a=action: self._add_stat(a.text()[2:], "RADIAL"))
            
            action.setMenu(menu)
            action.setToolTip(f"Add {action.text()[2:]} element")
            
            # Create a tool button to show the menu
            from PyQt6.QtWidgets import QToolButton
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            toolbar.addWidget(btn)
            
        toolbar.addSeparator()
        
        # Group 3: UI elements
        toolbar.addAction(self.action_add_rect)
        toolbar.addAction(self.action_add_circle)
        toolbar.addAction(self.action_add_image)
        toolbar.addAction(self.action_add_icon)
    
    def _create_panels(self) -> None:
        """Create the dockable panels and central widget."""
        # Create central canvas
        self._canvas = PreviewCanvas(self._theme_model, self._undo_stack)
        self.setCentralWidget(self._canvas)
        
        # Create tool panel (default left)
        self._tool_panel = ToolPanel()
        self._tool_dock = QDockWidget("Tools", self)
        self._tool_dock.setObjectName("ToolsDock")
        self._tool_dock.setWidget(self._tool_panel)
        self._tool_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tool_dock)
        self._panels_menu.insertAction(self.action_restore_layout, self._tool_dock.toggleViewAction())
        
        # Create properties panel (default top-right)
        self._properties_panel = PropertiesPanel(self._theme_model, self._undo_stack)
        self._props_dock = QDockWidget("Properties", self)
        self._props_dock.setObjectName("PropertiesDock")
        self._props_dock.setWidget(self._properties_panel)
        self._props_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_dock)
        self._panels_menu.insertAction(self.action_restore_layout, self._props_dock.toggleViewAction())
        
        # Create layer panel (default bottom-right)
        self._layer_panel = LayerPanel(self._theme_model, self._undo_stack)
        self._layer_dock = QDockWidget("Layers", self)
        self._layer_dock.setObjectName("LayersDock")
        self._layer_dock.setWidget(self._layer_panel)
        self._layer_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_dock)
        self._panels_menu.insertAction(self.action_restore_layout, self._layer_dock.toggleViewAction())
        
        # Position Layers below Properties and set 2:1 ratio
        self.splitDockWidget(self._props_dock, self._layer_dock, Qt.Orientation.Vertical)
        self.resizeDocks([self._props_dock, self._layer_dock], [200, 100], Qt.Orientation.Vertical)
        
        # Connect signals
        self._tool_panel.add_element_requested.connect(self._on_tool_requested)
        self._canvas.selection_changed.connect(self._on_canvas_selection_changed)
        self._canvas.mouse_moved.connect(self._on_canvas_mouse_moved)
        self._layer_panel.selection_changed.connect(self._on_layer_selection_changed)
    
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
        
        self._load_custom_colors()
    
    def _save_settings(self) -> None:
        """Save window settings for next session."""
        settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        
        self._save_custom_colors()
    
    def _load_custom_colors(self) -> None:
        """Load custom colors for QColorDialog from settings."""
        settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
        custom_colors = settings.value("customColors")
        if custom_colors and isinstance(custom_colors, list):
            for i, rgba_val in enumerate(custom_colors):
                if i < QColorDialog.customCount():
                    try:
                        # QSettings might return strings or ints
                        color = QColor(int(rgba_val))
                        QColorDialog.setCustomColor(i, color)
                    except (ValueError, TypeError):
                        continue

    def _save_custom_colors(self) -> None:
        """Save custom colors from QColorDialog to settings."""
        settings = QSettings("TuringSmartScreen", "ThemeEditorV2")
        custom_colors = []
        for i in range(QColorDialog.customCount()):
            color = QColorDialog.customColor(i)
            custom_colors.append(color.rgba())
        settings.setValue("customColors", custom_colors)
    
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
            yaml_io.save_all(self._theme_name, theme_data)
            
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
    
    # --- Element Creation ---
    
    def _on_tool_requested(self, tool_data) -> None:
        """Handle tool panel request."""
        if isinstance(tool_data, ElementType):
            self._add_element(tool_data)
        elif isinstance(tool_data, tuple):
            self._add_stat(*tool_data)

    def _add_element(self, element_type: ElementType) -> None:
        """Add a new element of the given type at the center of the view."""
        
        # Get center of view in scene coordinates

        center = self._canvas.get_scene_center()
        
        # Special handling for IMAGE: show file picker
        if element_type == ElementType.IMAGE:
            # Get the theme folder for relative path calculation
            if self._theme_name:
                themes_dir = Path(__file__).parent.parent / "res" / "themes"
                theme_folder = themes_dir / self._theme_name
                start_dir = str(theme_folder)
            else:
                start_dir = ""
            
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Image",
                start_dir,
                "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
            )
            if not file_path:
                return  # User cancelled
            
            element = create_element(
                element_type,
                x=int(center.x() - 50),
                y=int(center.y() - 50),
                path=file_path
            )
            self._theme_model.add_element(element)
            self._status_bar.showMessage(f"Added image: {Path(file_path).name}")
            return
        
        # Special handling for ICON: show URL input dialog
        if element_type == ElementType.ICON:
            default_url = "https://fontawesome.com/icons/laptop-code?f=classic&s=solid"
            
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Add Icon")
            dialog.setLabelText("Paste FontAwesome icon URL:")
            
            dialog.setTextValue(default_url)
            
            # Set placeholder on the internal LineEdit
            line_edit = dialog.findChild(QLineEdit)
            if line_edit:
                line_edit.setMinimumWidth(400)
                # Select the text so it's easy to overwrite
                line_edit.selectAll()
                
                line_edit.setStyleSheet("""
                    QLineEdit {
                        color: #ffffff;
                        background-color: #2b2b2b;
                        border: 1px solid #3d3d3d;
                        border-radius: 4px;
                        padding: 4px;
                        selection-background-color: #007acc;
                    }
                    QLineEdit:focus {
                        border: 1px solid #007acc;
                    }
                """)

            
            dialog.resize(400, dialog.sizeHint().height())
            
            if not dialog.exec():
                return  # User cancelled
            
            url = dialog.textValue().strip()
            if not url:
                url = default_url
            
            # Store the URL in the 'icon' field - it will be resolved at render time
            element = create_element(
                element_type,
                x=int(center.x() - 12),
                y=int(center.y() - 12),
                icon=url
            )
            self._theme_model.add_element(element)
            self._status_bar.showMessage(f"Added icon: {url.split('/')[-1].split('?')[0]}")
            return
        
        if element_type == ElementType.LINE:
            element = create_element(
                element_type,
                x=50,
                y=50,
                x2=300,
                y2=50
            )
        else:
            element = create_element(
                element_type,
                x=int(center.x() - 50),
                y=int(center.y() - 50)
            )
        self._theme_model.add_element(element)
        self._status_bar.showMessage(f"Added {element.name}")


    def _add_stat(self, sensor_type: str, variant: str) -> None:
        """Add a sensor-bound element (Text, Graph, Radial, or Line Graph)."""
        center = self._canvas.get_scene_center()
        
        props = {"sensor_type": sensor_type, "sensor_metric": "PERCENTAGE"}
        
        if variant == "TEXT":
            etype = ElementType.DYNAMIC_TEXT
            # Set the text property to use the correct sensor
            props["text"] = f"{{{sensor_type}_PERCENTAGE:u}}"
        elif variant == "GRAPH":
            etype = ElementType.GRAPH
        elif variant == "RADIAL":
            etype = ElementType.RADIAL
        elif variant == "LINE_GRAPH":
            etype = ElementType.LINE_GRAPH
        else:
            return
            
        element = create_element(
            etype,
            x=int(center.x() - 50),
            y=int(center.y() - 50),
            **props
        )
        self._theme_model.add_element(element)
        self._status_bar.showMessage(f"Added {sensor_type} {variant}")
        
    def _on_canvas_mouse_moved(self, scene_pos) -> None:
        """Update status bar with coordinates."""
        self._status_bar.showMessage(f"X: {int(scene_pos.x())}, Y: {int(scene_pos.y())}", 2000)
    
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
        selected_ids = self._canvas.get_selected_elements()
        if not selected_ids:
            return
            
        # Filter out children if their parent is also selected (avoid double grouping)
        # Actually, grouping logic in command handles flat list.
        # But we should prefer grouping top-level selection only.
        
        cmd = GroupElementsCommand(self._theme_model, selected_ids)
        self._undo_stack.push(cmd)
        self._status_bar.showMessage(f"Grouped {len(selected_ids)} elements")
    
    def _ungroup_selection(self) -> None:
        """Ungroup selected group."""
        selected_ids = self._canvas.get_selected_elements()
        if not selected_ids:
            return
            
        # Ungroup all selected groups
        if len(selected_ids) > 1:
            self._undo_stack.beginMacro("Ungroup Elements")
            
        count = 0
        for elem_id in selected_ids:
            elem = self._theme_model.get_element(elem_id)
            if elem and elem.element_type == ElementType.GROUP:
                cmd = UngroupElementsCommand(self._theme_model, elem_id)
                self._undo_stack.push(cmd)
                count += 1
                
        if len(selected_ids) > 1:
            self._undo_stack.endMacro()
            
        if count > 0:
            self._status_bar.showMessage(f"Ungrouped {count} groups")
        else:
            self._status_bar.showMessage("No groups selected")
    
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
        
    def _restore_default_layout(self) -> None:
        """Reset panels to their default arrangement."""
        # Reset docking areas
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tool_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_dock)
        
        # Stop floating and unhide
        for dock in [self._tool_dock, self._props_dock, self._layer_dock]:
            dock.setFloating(False)
            dock.show()
            dock.setVisible(True)
        
        # Split vertical and set ratio
        self.splitDockWidget(self._props_dock, self._layer_dock, Qt.Orientation.Vertical)
        
        # Final layout synchronization
        QApplication.processEvents()
        
        # Set 2:1 ratio (Properties 2/3, Layers 1/3)
        # Using large values to ensure ratio is respected
        self.resizeDocks([self._props_dock, self._layer_dock], [2000, 1000], Qt.Orientation.Vertical)
        
        self._status_bar.showMessage("Layout restored")
    
    # --- Selection Sync ---
    
    _syncing_selection = False  # Guard against recursion
    
    def _process_selection_change(self) -> None:
        """Actually process the selection change after debounce."""
        if not self._pending_selection_ids:
            # Clear properties
            self._properties_panel.clear()
            if self._pending_selection_source == 'canvas':
                self._layer_panel.select_elements([])
            elif self._pending_selection_source == 'layer':
                self._canvas.select_elements([])
            return
            
        element_ids = self._pending_selection_ids
        source = self._pending_selection_source
        
        if self._syncing_selection:
            return
            
        self._syncing_selection = True
        try:
            if source == 'layer':
                # Layer panel changed -> Update Canvas
                self._canvas.select_elements(element_ids)
            elif source == 'canvas':
                # Canvas changed -> Update Layer Panel
                self._layer_panel.select_elements(element_ids)
            
            # Update Properties Panel (common for both)
            # Handle multi-select in properties?
            # Currently properties panel likely only supports single selection
            # We'll show the first one for now
            if element_ids:
                # If multiple, maybe show "Multiple Selection" or just first?
                # For now, first one.
                self._properties_panel.show_properties(element_ids[0])
            else:
                self._properties_panel.clear()
        finally:
            self._syncing_selection = False

    def _on_layer_selection_changed(self, element_ids: list) -> None:
        """Handle layer panel selection change with debounce."""
        if self._syncing_selection:
            return
        self._pending_selection_ids = element_ids
        self._pending_selection_source = 'layer'
        self._selection_timer.start()
    
    def _on_canvas_selection_changed(self, element_ids: list) -> None:
        """Handle canvas selection change with debounce."""
        if self._syncing_selection:
            return
        self._pending_selection_ids = element_ids
        self._pending_selection_source = 'canvas'
        self._selection_timer.start()
    
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
