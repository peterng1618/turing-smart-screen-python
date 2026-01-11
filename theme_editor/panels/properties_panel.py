# SPDX-License-Identifier: GPL-3.0-or-later
"""
Properties Panel for Theme Editor v2.

Provides a property editor for the currently selected element with:
- Auto-generated form based on element type
- Type-appropriate widgets (spinbox, color picker, font selector, etc.)
- Real-time property updates with undo support
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QPushButton, QColorDialog, QSlider, QScrollArea,
    QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QUndoStack, QColor, QFont

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    Element, ElementType, Shadow, Outline,
    RectangleElement, CircleElement, TriangleElement, LineElement,
    TextElement, ImageElement, IconElement, GroupElement, DynamicTextElement
)

logger = logging.getLogger(__name__)


class ColorButton(QPushButton):
    """Button that shows a color preview and opens color picker."""
    
    color_changed = pyqtSignal(tuple)  # RGBA tuple
    
    def __init__(self, color: Tuple[int, int, int, int] = (255, 255, 255, 255), parent=None):
        super().__init__(parent)
        self._color = color
        self.setMinimumWidth(60)
        self.setMaximumHeight(24)
        self._update_style()
        self.clicked.connect(self._pick_color)
    
    @property
    def color(self) -> Tuple[int, int, int, int]:
        return self._color
    
    @color.setter
    def color(self, value: Tuple[int, int, int, int]) -> None:
        self._color = value
        self._update_style()
    
    def _update_style(self) -> None:
        """Update button background to show color and adjust text color for readability."""
        r, g, b, a = self._color
        
        # Calculate luminance to determine if black or white text is more readable
        # Standard formula: 0.299*R + 0.587*G + 0.114*B
        # If the background is bright, use black text; if dark, use white text.
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        text_color = "#000000" if luminance > 128 else "#ffffff"
        
        # We use a selector (ColorButton) to prevent the background-color 
        # from leaking into child dialogs (like QColorDialog)
        self.setStyleSheet(
            f"ColorButton {{ "
            f"  background-color: rgba({r}, {g}, {b}, {a}); "
            f"  color: {text_color}; "
            f"  border: 1px solid #888; "
            f"  border-radius: 2px; "
            f"  font-weight: bold; "
            f"}} "
            f"ColorButton:hover {{ "
            f"  border: 1px solid #aaa; "
            f"}}"
        )
        self.setText(f"{r},{g},{b},{a}")
    
    def _pick_color(self) -> None:
        """Open color picker dialog."""
        initial = QColor(*self._color)
        color = QColorDialog.getColor(
            initial,
            self,
            "Select Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue(), color.alpha())
            self._update_style()
            self.color_changed.emit(self._color)


class PropertiesPanel(QWidget):
    """
    Panel for viewing and editing properties of selected elements.
    
    Dynamically generates property widgets based on element type.
    """
    
    property_changed = pyqtSignal(str, str, object)  # element_id, property_name, value
    
    def __init__(
        self,
        model: ThemeModel,
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setMinimumWidth(320)
        
        self._model = model
        self._undo_stack = undo_stack
        self._current_element_id: Optional[str] = None
        self._widgets: Dict[str, QWidget] = {}
        self._updating = False  # Prevent feedback loops
        self._aspect_ratio: float = 1.0  # Aspect ratio for W/H lock
        self._aspect_locked: bool = True  # W/H linked by default
        
        self._setup_ui()
        self._model.element_changed.connect(self._on_model_element_changed)
    
    def _on_model_element_changed(self, element_id: str, prop_name: str, value: Any) -> None:
        """Handle element changes from model (e.g. from canvas or undo)."""
        if element_id != self._current_element_id or self._updating:
            return
        
        # When points change for triangles, we also need to update the virtual W/H
        if prop_name in ("x1", "y1", "x2", "y2", "x3", "y3"):
            element = self._model.get_element(element_id)
            if isinstance(element, TriangleElement):
                xs = [element.x1, element.x2, element.x3]
                ys = [element.y1, element.y2, element.y3]
                self.update_property("width", max(xs) - min(xs))
                self.update_property("height", max(ys) - min(ys))
        
        self.update_property(prop_name, value)
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Placeholder label
        self._placeholder = QLabel("Select an element to edit properties")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888;")
        self._content_layout.addWidget(self._placeholder)
        
        scroll.setWidget(self._content)
        layout.addWidget(scroll)
    
    def clear(self) -> None:
        """Clear all property widgets."""
        # Remove all widgets except placeholder
        try:
            while self._content_layout.count() > 1:
                item = self._content_layout.takeAt(1)
                if item.widget():
                    item.widget().deleteLater()
            
            self._widgets.clear()
            self._current_element_id = None
            self._placeholder.show()
        except Exception as e:
            # Log error but don't crash
            logger.error(f"Error clearing properties panel: {e}")
    
    def show_properties(self, element_id: str) -> None:
        """
        Show properties for the specified element.
        
        Args:
            element_id: ID of element to show properties for
        """
        element = self._model.get_element(element_id)
        if not element:
            self.clear()
            return
        
        # Clear existing widgets
        self.clear()
        self._placeholder.hide()
        self._current_element_id = element_id
        
        # Add property groups based on element type
        self._add_identity_group(element)
        self._add_transform_group(element)
        self._add_appearance_group(element)
        
        # Type-specific properties
        if isinstance(element, TextElement) or isinstance(element, DynamicTextElement):
            self._add_typography_group(element)
        
        if isinstance(element, ImageElement):
            self._add_image_group(element)
        
        if isinstance(element, IconElement):
            self._add_icon_group(element)
        
        if isinstance(element, DynamicTextElement):
            self._add_sensor_group(element)
        
        # Stretch at bottom
        self._content_layout.addStretch()
    
    def _add_identity_group(self, element: Element) -> None:
        """Add identity properties group (name, type)."""
        group = QGroupBox("Identity")
        form = QFormLayout(group)
        
        # Name
        name_edit = QLineEdit(element.name)
        name_edit.textChanged.connect(
            lambda v: self._on_property_changed("name", v)
        )
        form.addRow("Name:", name_edit)
        self._widgets["name"] = name_edit
        
        # Type (read-only)
        type_label = QLabel(element.element_type.name.title())
        type_label.setStyleSheet("color: #888;")
        form.addRow("Type:", type_label)
        
        self._content_layout.addWidget(group)
    
    def _add_transform_group(self, element: Element) -> None:
        """Add transform properties group (position, size, rotation)."""
        group = QGroupBox("Transform")
        form = QFormLayout(group)
        
        # Position
        pos_layout = QHBoxLayout()
        x_spin = QSpinBox()
        x_spin.setRange(-9999, 9999)
        x_spin.setValue(element.x)
        x_spin.valueChanged.connect(lambda v: self._on_property_changed("x", v))
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(x_spin)
        self._widgets["x"] = x_spin
        
        y_spin = QSpinBox()
        y_spin.setRange(-9999, 9999)
        y_spin.setValue(element.y)
        y_spin.valueChanged.connect(lambda v: self._on_property_changed("y", v))
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(y_spin)
        self._widgets["y"] = y_spin
        
        form.addRow("Position:", pos_layout)
        
        # Size with link/unlink button (if applicable)
        is_triangle = isinstance(element, TriangleElement)
        if (hasattr(element, 'width') and hasattr(element, 'height') and not isinstance(element, LineElement)) or is_triangle:
            size_layout = QHBoxLayout()
            
            # W spinbox
            w_spin = QSpinBox()
            w_spin.setRange(1, 9999)
            if is_triangle:
                xs = [element.x1, element.x2, element.x3]
                w_spin.setValue(int(max(xs) - min(xs)))
            else:
                w_spin.setValue(element.width)
            size_layout.addWidget(QLabel("W:"))
            size_layout.addWidget(w_spin)
            self._widgets["width"] = w_spin
            
            # Link/Unlink toggle button
            link_btn = QPushButton("🔗")
            link_btn.setCheckable(True)
            link_btn.setChecked(True)  # Linked by default
            link_btn.setFixedWidth(28)
            link_btn.setToolTip("Lock aspect ratio")
            link_btn.toggled.connect(self._on_aspect_lock_toggled)
            size_layout.addWidget(link_btn)
            self._widgets["aspect_lock"] = link_btn
            
            if is_triangle:
                xs = [element.x1, element.x2, element.x3]
                ys = [element.y1, element.y2, element.y3]
                cur_w = max(xs) - min(xs)
                cur_h = max(ys) - min(ys)
                self._aspect_ratio = cur_w / max(1, cur_h)
            else:
                self._aspect_ratio = element.width / max(1, element.height)
            self._aspect_locked = True
            
            # H spinbox
            h_spin = QSpinBox()
            h_spin.setRange(1, 9999)
            if is_triangle:
                ys = [element.y1, element.y2, element.y3]
                h_spin.setValue(int(max(ys) - min(ys)))
            else:
                h_spin.setValue(element.height)
            size_layout.addWidget(QLabel("H:"))
            size_layout.addWidget(h_spin)
            self._widgets["height"] = h_spin
            
            # Connect with aspect ratio handling
            w_spin.valueChanged.connect(lambda v: self._on_width_changed(v))
            h_spin.valueChanged.connect(lambda v: self._on_height_changed(v))
            
            form.addRow("Size:", size_layout)
        
        # Radius (for circles)
        if hasattr(element, 'radius') and isinstance(element, CircleElement):
            radius_spin = QSpinBox()
            radius_spin.setRange(1, 9999)
            radius_spin.setValue(element.radius)
            radius_spin.valueChanged.connect(lambda v: self._on_property_changed("radius", v))
            form.addRow("Radius:", radius_spin)
            self._widgets["radius"] = radius_spin
        
        # Font size (for icons)
        if isinstance(element, IconElement):
            size_spin = QSpinBox()
            size_spin.setRange(8, 512)
            size_spin.setValue(element.size)
            size_spin.setSuffix(" px")
            size_spin.valueChanged.connect(lambda v: self._on_property_changed("size", v))
            form.addRow("Font Size:", size_spin)
            self._widgets["size"] = size_spin
        
        # Triangle points
        if isinstance(element, TriangleElement):
            # Point 1
            p1_layout = QHBoxLayout()
            x1_spin = QSpinBox()
            x1_spin.setRange(-9999, 9999)
            x1_spin.setValue(element.x1)
            x1_spin.valueChanged.connect(lambda v: self._on_property_changed("x1", v))
            p1_layout.addWidget(QLabel("X1:"))
            p1_layout.addWidget(x1_spin)
            y1_spin = QSpinBox()
            y1_spin.setRange(-9999, 9999)
            y1_spin.setValue(element.y1)
            y1_spin.valueChanged.connect(lambda v: self._on_property_changed("y1", v))
            p1_layout.addWidget(QLabel("Y1:"))
            p1_layout.addWidget(y1_spin)
            form.addRow("Point 1:", p1_layout)
            self._widgets["x1"] = x1_spin
            self._widgets["y1"] = y1_spin
            
            # Point 2
            p2_layout = QHBoxLayout()
            x2_spin = QSpinBox()
            x2_spin.setRange(-9999, 9999)
            x2_spin.setValue(element.x2)
            x2_spin.valueChanged.connect(lambda v: self._on_property_changed("x2", v))
            p2_layout.addWidget(QLabel("X2:"))
            p2_layout.addWidget(x2_spin)
            y2_spin = QSpinBox()
            y2_spin.setRange(-9999, 9999)
            y2_spin.setValue(element.y2)
            y2_spin.valueChanged.connect(lambda v: self._on_property_changed("y2", v))
            p2_layout.addWidget(QLabel("Y2:"))
            p2_layout.addWidget(y2_spin)
            form.addRow("Point 2:", p2_layout)
            self._widgets["x2"] = x2_spin
            self._widgets["y2"] = y2_spin
            
            # Point 3
            p3_layout = QHBoxLayout()
            x3_spin = QSpinBox()
            x3_spin.setRange(-9999, 9999)
            x3_spin.setValue(element.x3)
            x3_spin.valueChanged.connect(lambda v: self._on_property_changed("x3", v))
            p3_layout.addWidget(QLabel("X3:"))
            p3_layout.addWidget(x3_spin)
            y3_spin = QSpinBox()
            y3_spin.setRange(-9999, 9999)
            y3_spin.setValue(element.y3)
            y3_spin.valueChanged.connect(lambda v: self._on_property_changed("y3", v))
            p3_layout.addWidget(QLabel("Y3:"))
            p3_layout.addWidget(y3_spin)
            form.addRow("Point 3:", p3_layout)
            self._widgets["x3"] = x3_spin
            self._widgets["y3"] = y3_spin
        
        # Line end point
        if isinstance(element, LineElement):
            end_layout = QHBoxLayout()
            x2_spin = QSpinBox()
            x2_spin.setRange(-9999, 9999)
            x2_spin.setValue(element.x2)
            x2_spin.valueChanged.connect(lambda v: self._on_property_changed("x2", v))
            end_layout.addWidget(QLabel("X2:"))
            end_layout.addWidget(x2_spin)
            y2_spin = QSpinBox()
            y2_spin.setRange(-9999, 9999)
            y2_spin.setValue(element.y2)
            y2_spin.valueChanged.connect(lambda v: self._on_property_changed("y2", v))
            end_layout.addWidget(QLabel("Y2:"))
            end_layout.addWidget(y2_spin)
            form.addRow("End Point:", end_layout)
            self._widgets["x2"] = x2_spin
            self._widgets["y2"] = y2_spin
        
        # Angle
        if not isinstance(element, LineElement):
            angle_spin = QDoubleSpinBox()
            angle_spin.setRange(-360, 360)
            angle_spin.setValue(element.angle)
            angle_spin.setSuffix("°")
            angle_spin.valueChanged.connect(lambda v: self._on_property_changed("angle", v))
            form.addRow("Rotation:", angle_spin)
            self._widgets["angle"] = angle_spin
        
        self._content_layout.addWidget(group)
    
    def _add_appearance_group(self, element: Element) -> None:
        """Add appearance properties group (color, opacity)."""
        group = QGroupBox("Appearance")
        form = QFormLayout(group)
        
        # Color (if applicable)
        if hasattr(element, 'color'):
            color_btn = ColorButton(element.color)
            color_btn.color_changed.connect(
                lambda v: self._on_property_changed("color", v)
            )
            form.addRow("Color:", color_btn)
            self._widgets["color"] = color_btn
        
        # Opacity
        opacity_layout = QHBoxLayout()
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(int(element.opacity * 100))
        
        opacity_spin = QDoubleSpinBox()
        opacity_spin.setRange(0.0, 1.0)
        opacity_spin.setSingleStep(0.1)
        opacity_spin.setValue(element.opacity)
        
        opacity_slider.valueChanged.connect(
            lambda v: opacity_spin.setValue(v / 100)
        )
        opacity_spin.valueChanged.connect(
            lambda v: self._on_property_changed("opacity", v)
        )
        
        opacity_layout.addWidget(opacity_slider)
        opacity_layout.addWidget(opacity_spin)
        form.addRow("Opacity:", opacity_layout)
        self._widgets["opacity"] = opacity_spin
        
        # Visibility
        visible_check = QCheckBox()
        visible_check.setChecked(element.visible)
        visible_check.toggled.connect(
            lambda v: self._on_property_changed("visible", v)
        )
        form.addRow("Visible:", visible_check)
        self._widgets["visible"] = visible_check
        
        # Corner radius (for rectangles)
        if hasattr(element, 'radius') and isinstance(element, RectangleElement):
            radius_spin = QSpinBox()
            radius_spin.setRange(0, 999)
            radius_spin.setValue(element.radius)
            radius_spin.valueChanged.connect(lambda v: self._on_property_changed("radius", v))
            form.addRow("Corner Radius:", radius_spin)
            self._widgets["radius"] = radius_spin
        
        # Shear (for rectangles)
        if isinstance(element, RectangleElement):
            shear_layout = QHBoxLayout()
            
            shear_left = QDoubleSpinBox()
            shear_left.setRange(-89, 89)
            shear_left.setValue(element.shear_left)
            shear_left.setSuffix("°")
            shear_left.valueChanged.connect(lambda v: self._on_property_changed("shear_left", v))
            shear_layout.addWidget(QLabel("L:"))
            shear_layout.addWidget(shear_left)
            self._widgets["shear_left"] = shear_left
            
            shear_right = QDoubleSpinBox()
            shear_right.setRange(-89, 89)
            shear_right.setValue(element.shear_right)
            shear_right.setSuffix("°")
            shear_right.valueChanged.connect(lambda v: self._on_property_changed("shear_right", v))
            shear_layout.addWidget(QLabel("R:"))
            shear_layout.addWidget(shear_right)
            self._widgets["shear_right"] = shear_right
            
            form.addRow("Shear:", shear_layout)
        
        # Line width and cap
        if isinstance(element, LineElement):
            width_spin = QSpinBox()
            width_spin.setRange(1, 100)
            width_spin.setValue(element.line_width)
            width_spin.valueChanged.connect(lambda v: self._on_property_changed("line_width", v))
            form.addRow("Stroke Width:", width_spin)
            self._widgets["line_width"] = width_spin
            
            cap_combo = QComboBox()
            cap_combo.addItems(["butt", "round"])
            cap_combo.setCurrentText(element.end_cap)
            cap_combo.currentTextChanged.connect(lambda v: self._on_property_changed("end_cap", v))
            form.addRow("End Cap:", cap_combo)
            self._widgets["end_cap"] = cap_combo
        
        # Nested Outline & Shadow sections
        if isinstance(element, (RectangleElement, CircleElement, TriangleElement, LineElement, ImageElement)):
            self._add_outline_section(element, form)
            
        self._add_shadow_section(element, form)
        
        self._content_layout.addWidget(group)
    
    def _add_typography_group(self, element: Element) -> None:
        """Add typography properties group (font, size, align)."""
        group = QGroupBox("Typography")
        form = QFormLayout(group)
        
        # Text content
        if hasattr(element, 'text'):
            text_edit = QLineEdit(element.text)
            text_edit.textChanged.connect(
                lambda v: self._on_property_changed("text", v)
            )
            form.addRow("Text:", text_edit)
            self._widgets["text"] = text_edit
        
        # Font
        font_layout = QHBoxLayout()
        font_label = QLabel(element.font if hasattr(element, 'font') else "")
        font_label.setStyleSheet("color: #888; font-size: 10px;")
        font_label.setMaximumWidth(180)
        full_font_path = element.font if hasattr(element, 'font') else ""
        font_label.setToolTip(f"<span style='color: white; background: #333; padding: 4px;'>{full_font_path}</span>")
        font_btn = QPushButton("...")
        font_btn.setFixedWidth(32)
        font_btn.setToolTip("Choose font from res/fonts")
        font_btn.clicked.connect(self._pick_font)
        font_layout.addWidget(font_label, 1)
        font_layout.addWidget(font_btn)
        form.addRow("Font:", font_layout)
        self._widgets["font_label"] = font_label
        
        # Font size
        if hasattr(element, 'font_size'):
            size_spin = QSpinBox()
            size_spin.setRange(6, 1000)
            # Clamp value to spinbox range to prevent overflow
            clamped_size = max(6, min(1000, int(element.font_size)))
            size_spin.setValue(clamped_size)
            size_spin.valueChanged.connect(lambda v: self._on_property_changed("font_size", v))
            form.addRow("Size:", size_spin)
            self._widgets["font_size"] = size_spin
        
        # Alignment
        if hasattr(element, 'align'):
            align_combo = QComboBox()
            align_combo.addItems(["left", "center", "right"])
            align_combo.setCurrentText(element.align)
            align_combo.currentTextChanged.connect(
                lambda v: self._on_property_changed("align", v)
            )
            form.addRow("Align:", align_combo)
            self._widgets["align"] = align_combo
        
        self._content_layout.addWidget(group)
    
    def _add_image_group(self, element: ImageElement) -> None:
        """Add image properties group (path, browse)."""
        from pathlib import Path
        
        group = QGroupBox("Image Source")
        layout = QVBoxLayout(group)
        
        # Current path
        path_layout = QHBoxLayout()
        path_label = QLabel(element.path if element.path else "(no image)")
        path_label.setStyleSheet("color: #888; font-size: 10px;")
        path_label.setWordWrap(True)
        path_label.setToolTip(element.path)
        path_layout.addWidget(path_label, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(lambda: self._pick_image())
        path_layout.addWidget(browse_btn)
        
        layout.addLayout(path_layout)
        self._widgets["path_label"] = path_label
        
        self._content_layout.addWidget(group)
    
    def _pick_image(self) -> None:
        """Open file dialog to select an image."""
        from pathlib import Path
        
        # Start from theme folder if available
        start_dir = ""
        if hasattr(self._model, 'theme_folder') and self._model.theme_folder:
            start_dir = str(self._model.theme_folder)
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            start_dir,
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )
        
        if file_path:
            self._on_property_changed("path", file_path)
            if "path_label" in self._widgets:
                self._widgets["path_label"].setText(file_path)
                self._widgets["path_label"].setToolTip(file_path)
            
            # Auto-set width/height from image
            try:
                # Load image to get dimensions
                # Use absolute path if possible, but we might be relative to theme
                # Try simple load first
                from PIL import Image
                img_path = Path(file_path)
                
                # If path is relative, we might need to resolve it (but file_path from dialog is usually absolute)
                if img_path.exists():
                     with Image.open(img_path) as img:
                         width, height = img.size
                         
                         # Update element properties
                         # We need to update both simultaneously ideally, but sequential is fine
                         self._on_property_changed("width", width)
                         self._on_property_changed("height", height)
                         
                         # Update UI widgets if they exist
                         if "width" in self._widgets:
                             self._widgets["width"].setValue(width)
                         if "height" in self._widgets:
                             self._widgets["height"].setValue(height)
            except Exception as e:
                logger.error(f"Failed to auto-size image: {e}")
    
    def _add_icon_group(self, element: IconElement) -> None:
        """Add icon properties group (FontAwesome URL)."""
        group = QGroupBox("Icon Source")
        layout = QVBoxLayout(group)
        
        # URL input
        url_label = QLabel("FontAwesome URL:")
        url_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(url_label)
        
        url_edit = QLineEdit(element.icon if element.icon else "")
        url_edit.setPlaceholderText("https://fontawesome.com/icons/laptop-code?f=classic&s=solid")
        url_edit.textChanged.connect(
            lambda v: self._on_property_changed("icon", v)
        )
        layout.addWidget(url_edit)
        self._widgets["icon"] = url_edit
        
        # Help text
        help_label = QLabel("Paste a FontAwesome icon URL to display the icon")
        help_label.setStyleSheet("color: #666; font-size: 9px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        self._content_layout.addWidget(group)
    
    def _add_shadow_group(self, element: Element) -> None:
        """Add shadow properties group."""
        if not element.shadow:
            return
        
        group = QGroupBox("Shadow")
        form = QFormLayout(group)
        
        # Blur
        blur_spin = QSpinBox()
        blur_spin.setRange(0, 100)
        blur_spin.setValue(element.shadow.blur)
        blur_spin.valueChanged.connect(
            lambda v: self._on_shadow_property_changed("blur", v)
        )
        form.addRow("Blur:", blur_spin)
        
        # Color
        color_btn = ColorButton(element.shadow.color)
        color_btn.color_changed.connect(
            lambda v: self._on_shadow_property_changed("color", v)
        )
        form.addRow("Color:", color_btn)
        
        # Offset
        offset_layout = QHBoxLayout()
        offset_x = QSpinBox()
        offset_x.setRange(-100, 100)
        offset_x.setValue(element.shadow.offset_x)
        offset_x.valueChanged.connect(
            lambda v: self._on_shadow_property_changed("offset_x", v)
        )
        offset_layout.addWidget(QLabel("X:"))
        offset_layout.addWidget(offset_x)
        
        offset_y = QSpinBox()
        offset_y.setRange(-100, 100)
        offset_y.setValue(element.shadow.offset_y)
        offset_y.valueChanged.connect(
            lambda v: self._on_shadow_property_changed("offset_y", v)
        )
        offset_layout.addWidget(QLabel("Y:"))
        offset_layout.addWidget(offset_y)
        form.addRow("Offset:", offset_layout)
        
        self._content_layout.addWidget(group)
    
    def _add_outline_group(self, element: Element) -> None:
        """Add outline properties group."""
        if not hasattr(element, 'outline') or not element.outline:
            return
        
        group = QGroupBox("Outline")
        form = QFormLayout(group)
        
        # Width
        width_spin = QSpinBox()
        width_spin.setRange(0, 50)
        width_spin.setValue(element.outline.width)
        width_spin.valueChanged.connect(
            lambda v: self._on_outline_property_changed("width", v)
        )
        form.addRow("Width:", width_spin)
        
        # Color
        color_btn = ColorButton(element.outline.color)
        color_btn.color_changed.connect(
            lambda v: self._on_outline_property_changed("color", v)
        )
        form.addRow("Color:", color_btn)
        
        self._content_layout.addWidget(group)
    
    def _add_sensor_group(self, element: DynamicTextElement) -> None:
        """Add dynamic settings properties group."""
        group = QGroupBox("Dynamic Settings")
        layout = QVBoxLayout(group)
        
        # Interval row
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Refresh:")
        interval_spin = QDoubleSpinBox()
        interval_spin.setRange(0.1, 60.0)
        interval_spin.setSingleStep(0.5)
        interval_spin.setValue(element.interval)
        interval_spin.setSuffix(" sec")
        interval_spin.valueChanged.connect(
            lambda v: self._on_property_changed("interval", v)
        )
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(interval_spin, 1)
        layout.addLayout(interval_layout)
        
        # Available sensors label
        sensors_label = QLabel("Insert Sensor (click to add):")
        sensors_label.setStyleSheet("color: #888; font-size: 10px; margin-top: 8px;")
        layout.addWidget(sensors_label)
        
        # Available sensor variables - organized by category: (sensor_id, display_label)
        sensors = [
            ("CPU", [("CPU_PERCENTAGE", "PERCENT"), ("CPU_TEMPERATURE", "TEMP"), ("CPU_FREQUENCY", "FREQ")]),
            ("GPU", [("GPU_PERCENTAGE", "PERCENT"), ("GPU_TEMPERATURE", "TEMP"), ("GPU_MEMORY_USED", "USED"), ("GPU_FPS", "FPS")]),
            ("Memory", [("MEM_VIRTUAL_PERCENT", "PERCENT"), ("MEM_VIRTUAL_USED", "USED"), ("MEM_VIRTUAL_TOTAL", "TOTAL")]),
            ("Disk", [("DISK_USED_PERCENT", "PERCENT"), ("DISK_USED", "USED"), ("DISK_TOTAL", "TOTAL")]),
            ("Network", [("NET_DOWNLOAD_RATE", "DOWN"), ("NET_UPLOAD_RATE", "UP")]),
            ("Time", [("DATE_DAY", "DAY"), ("DATE_HOUR", "HOUR"), ("UPTIME_FORMATTED", "UPTIME")]),
        ]
        
        for category, sensor_list in sensors:
            cat_layout = QHBoxLayout()
            cat_label = QLabel(f"{category}:")
            cat_label.setStyleSheet("color: #666; font-size: 9px; min-width: 50px;")
            cat_layout.addWidget(cat_label)
            
            for sensor_id, label in sensor_list:
                btn = QPushButton(label)
                btn.setToolTip(f"Insert {{{sensor_id}:u}}")
                btn.setFixedHeight(20)
                btn.setStyleSheet("font-size: 9px; padding: 2px 4px;")
                # Use a helper function to capture sensor value properly
                def make_handler(sid):
                    return lambda: self._insert_sensor(sid)
                btn.clicked.connect(make_handler(sensor_id))
                cat_layout.addWidget(btn)
            
            cat_layout.addStretch()
            layout.addLayout(cat_layout)
        
        self._content_layout.addWidget(group)
    
    def _insert_sensor(self, sensor_id: str) -> None:
        """Insert a sensor placeholder into the text field."""
        if "text" in self._widgets:
            text_edit = self._widgets["text"]
            current = text_edit.text()
            placeholder = f"{{{sensor_id}:u}}"
            # Insert at cursor position or end
            cursor_pos = text_edit.cursorPosition()
            new_text = current[:cursor_pos] + placeholder + current[cursor_pos:]
            text_edit.setText(new_text)
            text_edit.setCursorPosition(cursor_pos + len(placeholder))
            text_edit.setFocus()
    
    def _pick_font(self) -> None:
        """Open font picker dialog browsing res/fonts folder."""
        from pathlib import Path
        # Get res/fonts directory
        fonts_dir = Path(__file__).parent.parent.parent / "res" / "fonts"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Font",
            str(fonts_dir),
            "Font Files (*.ttf *.otf);;All Files (*)"
        )
        
        if file_path:
            # Convert to relative path from res/fonts
            try:
                rel_path = Path(file_path).relative_to(fonts_dir)
                font_path = str(rel_path).replace("\\", "/")
            except ValueError:
                # File not under res/fonts, use absolute path
                font_path = file_path
            
            self._on_property_changed("font", font_path)
            if "font_label" in self._widgets:
                self._widgets["font_label"].setText(font_path)
    
    def _on_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle property value change."""
        if self._updating or not self._current_element_id:
            return
        
        self._model.set_element_property(self._current_element_id, prop_name, value)
        self.property_changed.emit(self._current_element_id, prop_name, value)
    
    def _on_aspect_lock_toggled(self, checked: bool) -> None:
        """Handle aspect lock toggle."""
        self._aspect_locked = checked
        if "aspect_lock" in self._widgets:
            self._widgets["aspect_lock"].setText("🔗" if checked else "⛓️‍💥")
            self._widgets["aspect_lock"].setToolTip(
                "Lock aspect ratio" if checked else "Unlock aspect ratio"
            )
    
    def _on_width_changed(self, value: int) -> None:
        """Handle width change with aspect ratio lock."""
        if self._updating:
            return
        
        self._on_property_changed("width", value)
        
        if self._aspect_locked and "height" in self._widgets:
            # Calculate new height based on aspect ratio
            new_height = max(1, int(value / self._aspect_ratio))
            self._updating = True
            self._widgets["height"].setValue(new_height)
            self._updating = False
            self._on_property_changed("height", new_height)
    
    def _on_height_changed(self, value: int) -> None:
        """Handle height change with aspect ratio lock."""
        if self._updating:
            return
        
        self._on_property_changed("height", value)
        
        if self._aspect_locked and "width" in self._widgets:
            # Calculate new width based on aspect ratio
            new_width = max(1, int(value * self._aspect_ratio))
            self._updating = True
            self._widgets["width"].setValue(new_width)
            self._updating = False
            self._on_property_changed("width", new_width)
    
    def _add_outline_section(self, element: Element, parent_layout: QFormLayout = None) -> None:
        """Add outline controls for supported elements."""
        group = QGroupBox("Outline")
        group.setCheckable(True)
        group.setChecked(element.outline is not None)
        group.toggled.connect(self._on_outline_enabled_toggled)
        
        form = QFormLayout(group)
        
        # Width
        width_spin = QSpinBox()
        width_spin.setRange(1, 50)
        width_spin.setValue(element.outline.width if element.outline else 1)
        width_spin.valueChanged.connect(lambda v: self._on_outline_property_changed("width", v))
        form.addRow("Width:", width_spin)
        self._widgets["outline_width"] = width_spin
        
        # Color
        color = element.outline.color if element.outline else (255, 255, 255, 255)
        color_btn = ColorButton(color)
        color_btn.color_changed.connect(lambda v: self._on_outline_property_changed("color", v))
        form.addRow("Color:", color_btn)
        self._widgets["outline_color"] = color_btn
        
        # Dash array (optional)
        dash_edit = QLineEdit()
        dash_text = ", ".join(str(d) for d in element.outline.dash_array) if element.outline and element.outline.dash_array else ""
        dash_edit.setText(dash_text)
        dash_edit.setPlaceholderText("e.g. 10, 5")
        dash_edit.textChanged.connect(self._on_outline_dash_changed)
        form.addRow("Dash:", dash_edit)
        self._widgets["outline_dash"] = dash_edit
        
        # Cap
        cap_combo = QComboBox()
        cap_combo.addItems(["butt", "round"])
        cap_combo.setCurrentText(element.outline.cap if element.outline else "butt")
        cap_combo.currentTextChanged.connect(lambda v: self._on_outline_property_changed("cap", v))
        form.addRow("Cap:", cap_combo)
        self._widgets["outline_cap"] = cap_combo
        
        # Add to parent layout if provided, otherwise main content
        if parent_layout:
            parent_layout.addRow(group)
        else:
            self._content_layout.addWidget(group)
    
    def _on_outline_enabled_toggled(self, checked: bool) -> None:
        """Handle outline enable/disable toggle."""
        # Find the group box to collapse/expand if needed
        # But QGroupBox checkable automatically disables children, usually sufficient.
        # If we want to hide children (true collapse), we can do it here.
        # For now, let's stick to checkable behavior which toggles the `element.outline` property.
        
        if self._updating or not self._current_element_id:
            return
        
        element = self._model.get_element(self._current_element_id)
        if not element:
            return
        
        if checked:
            # Create outline with current widget values
            width = self._widgets.get("outline_width")
            color_btn = self._widgets.get("outline_color")
            cap = self._widgets.get("outline_cap")
            
            element.outline = Outline(
                width=width.value() if width else 1,
                color=color_btn.color if color_btn else (255, 255, 255, 255),
                cap=cap.currentText() if cap else "butt"
            )
        else:
            element.outline = None
        
        self._model.element_changed.emit(self._current_element_id, "outline", element.outline)
    
    def _on_outline_dash_changed(self, text: str) -> None:
        """Handle outline dash array change."""
        if self._updating or not self._current_element_id:
            return
        
        element = self._model.get_element(self._current_element_id)
        if not element or not hasattr(element, 'outline') or not element.outline:
            return
        
        # Parse dash array
        try:
            if text.strip():
                dash_array = [float(d.strip()) for d in text.split(",") if d.strip()]
                element.outline.dash_array = dash_array
            else:
                element.outline.dash_array = None
        except ValueError:
            pass  # Invalid input, ignore
        
        self._model.element_changed.emit(self._current_element_id, "outline.dash_array", element.outline.dash_array)
    
    def _add_shadow_section(self, element: Element, parent_layout: QFormLayout = None) -> None:
        """Add shadow controls for element."""
        group = QGroupBox("Shadow")
        group.setCheckable(True)
        group.setChecked(element.shadow is not None)
        group.toggled.connect(self._on_shadow_enabled_toggled)
        
        form = QFormLayout(group)
        
        # Blur
        blur_spin = QSpinBox()
        blur_spin.setRange(0, 100)
        blur_spin.setValue(element.shadow.blur if element.shadow else 5)
        blur_spin.valueChanged.connect(lambda v: self._on_shadow_property_changed("blur", v))
        form.addRow("Blur:", blur_spin)
        self._widgets["shadow_blur"] = blur_spin
        
        # Color
        color = element.shadow.color if element.shadow else (0, 0, 0, 128)
        color_btn = ColorButton(color)
        color_btn.color_changed.connect(lambda v: self._on_shadow_property_changed("color", v))
        form.addRow("Color:", color_btn)
        self._widgets["shadow_color"] = color_btn
        
        # Offset
        offset_layout = QHBoxLayout()
        offset_x = QSpinBox()
        offset_x.setRange(-100, 100)
        offset_x.setValue(element.shadow.offset_x if element.shadow else 3)
        offset_x.valueChanged.connect(lambda v: self._on_shadow_property_changed("offset_x", v))
        offset_layout.addWidget(QLabel("X:"))
        offset_layout.addWidget(offset_x)
        offset_y = QSpinBox()
        offset_y.setRange(-100, 100)
        offset_y.setValue(element.shadow.offset_y if element.shadow else 3)
        offset_y.valueChanged.connect(lambda v: self._on_shadow_property_changed("offset_y", v))
        offset_layout.addWidget(QLabel("Y:"))
        offset_layout.addWidget(offset_y)
        form.addRow("Offset:", offset_layout)
        self._widgets["shadow_offset_x"] = offset_x
        self._widgets["shadow_offset_y"] = offset_y
        
        # Add to parent layout if provided
        if parent_layout:
            parent_layout.addRow(group)
        else:
            self._content_layout.addWidget(group)
    
    def _on_shadow_enabled_toggled(self, checked: bool) -> None:
        """Handle shadow enable/disable toggle."""
        if self._updating or not self._current_element_id:
            return
        
        element = self._model.get_element(self._current_element_id)
        if not element:
            return
        
        if checked:
            # Create shadow with current widget values
            blur = self._widgets.get("shadow_blur")
            color_btn = self._widgets.get("shadow_color")
            offset_x = self._widgets.get("shadow_offset_x")
            offset_y = self._widgets.get("shadow_offset_y")
            
            element.shadow = Shadow(
                blur=blur.value() if blur else 5,
                color=color_btn.color if color_btn else (0, 0, 0, 128),
                offset_x=offset_x.value() if offset_x else 3,
                offset_y=offset_y.value() if offset_y else 3
            )
        else:
            element.shadow = None
        
        self._model.element_changed.emit(self._current_element_id, "shadow", element.shadow)
    
    def _on_shadow_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle shadow property change."""
        if self._updating or not self._current_element_id:
            return
        
        element = self._model.get_element(self._current_element_id)
        if element and element.shadow:
            setattr(element.shadow, prop_name, value)
            self._model.element_changed.emit(self._current_element_id, f"shadow.{prop_name}", value)
    
    def _on_outline_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle outline property change."""
        if self._updating or not self._current_element_id:
            return
        
        element = self._model.get_element(self._current_element_id)
        if element and hasattr(element, 'outline') and element.outline:
            setattr(element.outline, prop_name, value)
            self._model.element_changed.emit(self._current_element_id, f"outline.{prop_name}", value)
    
    def update_property(self, prop_name: str, value: Any) -> None:
        """
        Update a property widget value (called when model changes externally).
        
        Args:
            prop_name: Property name
            value: New value
        """
        widget = self._widgets.get(prop_name)
        if not widget:
            return
        
        self._updating = True
        try:
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QSpinBox):
                clamped_val = int(max(-2147483648, min(2147483647, int(value))))
                widget.setValue(clamped_val)
            elif isinstance(widget, QDoubleSpinBox):
                clamped_val = float(max(-1000000, min(1000000, float(value))))
                widget.setValue(clamped_val)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, ColorButton):
                widget.color = value
        finally:
            self._updating = False
