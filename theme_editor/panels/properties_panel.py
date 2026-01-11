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
    QFileDialog, QFontDialog
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
        """Update button background to show color."""
        r, g, b, a = self._color
        self.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, {a}); "
            f"border: 1px solid #888;"
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
        """
        Initialize the properties panel.
        
        Args:
            model: Theme data model
            undo_stack: Undo stack for operations
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._model = model
        self._undo_stack = undo_stack
        self._current_element_id: Optional[str] = None
        self._widgets: Dict[str, QWidget] = {}
        self._updating = False  # Prevent feedback loops
        
        self._setup_ui()
    
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
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        self._widgets.clear()
        self._current_element_id = None
        self._placeholder.show()
    
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
        
        if hasattr(element, 'shadow') and element.shadow:
            self._add_shadow_group(element)
        
        if hasattr(element, 'outline') and element.outline:
            self._add_outline_group(element)
        
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
        
        # Size (if applicable)
        if hasattr(element, 'width') and hasattr(element, 'height'):
            size_layout = QHBoxLayout()
            w_spin = QSpinBox()
            w_spin.setRange(1, 9999)
            w_spin.setValue(element.width)
            w_spin.valueChanged.connect(lambda v: self._on_property_changed("width", v))
            size_layout.addWidget(QLabel("W:"))
            size_layout.addWidget(w_spin)
            self._widgets["width"] = w_spin
            
            h_spin = QSpinBox()
            h_spin.setRange(1, 9999)
            h_spin.setValue(element.height)
            h_spin.valueChanged.connect(lambda v: self._on_property_changed("height", v))
            size_layout.addWidget(QLabel("H:"))
            size_layout.addWidget(h_spin)
            self._widgets["height"] = h_spin
            
            form.addRow("Size:", size_layout)
        
        # Radius (for circles)
        if hasattr(element, 'radius') and isinstance(element, CircleElement):
            radius_spin = QSpinBox()
            radius_spin.setRange(1, 9999)
            radius_spin.setValue(element.radius)
            radius_spin.valueChanged.connect(lambda v: self._on_property_changed("radius", v))
            form.addRow("Radius:", radius_spin)
            self._widgets["radius"] = radius_spin
        
        # Angle
        angle_spin = QDoubleSpinBox()
        angle_spin.setRange(-360, 360)
        angle_spin.setValue(element.angle)
        angle_spin.setSuffix("°")
        angle_spin.valueChanged.connect(lambda v: self._on_property_changed("angle", v))
        form.addRow("Rotation:", angle_spin)
        self._widgets["angle"] = angle_spin
        
        # Scale (for images/icons)
        if hasattr(element, 'scale'):
            scale_spin = QDoubleSpinBox()
            scale_spin.setRange(0.01, 10.0)
            scale_spin.setSingleStep(0.1)
            scale_spin.setValue(element.scale)
            scale_spin.valueChanged.connect(lambda v: self._on_property_changed("scale", v))
            form.addRow("Scale:", scale_spin)
            self._widgets["scale"] = scale_spin
        
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
        font_label.setStyleSheet("color: #666; font-size: 10px;")
        font_btn = QPushButton("Choose...")
        font_btn.clicked.connect(self._pick_font)
        font_layout.addWidget(font_label, 1)
        font_layout.addWidget(font_btn)
        form.addRow("Font:", font_layout)
        self._widgets["font_label"] = font_label
        
        # Font size
        if hasattr(element, 'font_size'):
            size_spin = QSpinBox()
            size_spin.setRange(6, 200)
            size_spin.setValue(element.font_size)
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
        """Add sensor binding properties group."""
        group = QGroupBox("Sensor Binding")
        form = QFormLayout(group)
        
        # Sensor type
        type_combo = QComboBox()
        type_combo.addItems(["CPU", "GPU", "MEMORY", "DISK", "NET", "DATE", "UPTIME"])
        type_combo.setCurrentText(element.sensor_type)
        type_combo.currentTextChanged.connect(
            lambda v: self._on_property_changed("sensor_type", v)
        )
        form.addRow("Sensor:", type_combo)
        
        # Metric
        metric_combo = QComboBox()
        metric_combo.addItems(["PERCENTAGE", "TEMPERATURE", "FREQUENCY", "USED", "TOTAL"])
        metric_combo.setCurrentText(element.sensor_metric)
        metric_combo.currentTextChanged.connect(
            lambda v: self._on_property_changed("sensor_metric", v)
        )
        form.addRow("Metric:", metric_combo)
        
        # Show unit
        unit_check = QCheckBox()
        unit_check.setChecked(element.show_unit)
        unit_check.toggled.connect(
            lambda v: self._on_property_changed("show_unit", v)
        )
        form.addRow("Show Unit:", unit_check)
        
        # Interval
        interval_spin = QDoubleSpinBox()
        interval_spin.setRange(0.1, 60.0)
        interval_spin.setSingleStep(0.5)
        interval_spin.setValue(element.interval)
        interval_spin.setSuffix(" sec")
        interval_spin.valueChanged.connect(
            lambda v: self._on_property_changed("interval", v)
        )
        form.addRow("Interval:", interval_spin)
        
        self._content_layout.addWidget(group)
    
    def _pick_font(self) -> None:
        """Open font picker dialog."""
        # TODO: Implement custom font picker for theme fonts
        font, ok = QFontDialog.getFont(self)
        if ok:
            font_path = f"{font.family()}.ttf"
            self._on_property_changed("font", font_path)
            if "font_label" in self._widgets:
                self._widgets["font_label"].setText(font_path)
    
    def _on_property_changed(self, prop_name: str, value: Any) -> None:
        """Handle property value change."""
        if self._updating or not self._current_element_id:
            return
        
        self._model.set_element_property(self._current_element_id, prop_name, value)
        self.property_changed.emit(self._current_element_id, prop_name, value)
    
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
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, ColorButton):
                widget.color = value
        finally:
            self._updating = False
