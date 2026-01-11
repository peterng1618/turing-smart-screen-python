# SPDX-License-Identifier: GPL-3.0-or-later
"""
Preview Canvas for Theme Editor v2.

Provides a QGraphicsView-based canvas for visual editing with:
- Theme preview rendering
- Element selection and manipulation
- Rulers and guides
- Grid overlay
- Zoom and pan
"""

import logging
from typing import Dict, List, Optional, Set

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSizeF
from PyQt6.QtGui import (
    QUndoStack, QPainter, QPen, QBrush, QColor, QPixmap,
    QWheelEvent, QMouseEvent, QKeyEvent, QTransform
)

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import Element, ElementType

logger = logging.getLogger(__name__)


class ElementItem(QGraphicsRectItem):
    """
    Base graphics item for theme elements.
    
    Wraps an Element and provides visual representation on the canvas.
    Overrides paint() to render different element types.
    Supports interactive resizing via corner handles.
    """
    
    HANDLE_SIZE = 8
    ROTATE_HANDLE_OFFSET = 25  # Distance above top of element
    
    # Corner handles (diagonal resize) + midpoint handles (single-axis resize) + rotate
    HANDLE_CURSORS = {
        'tl': Qt.CursorShape.SizeFDiagCursor,  # Top-left
        'tr': Qt.CursorShape.SizeBDiagCursor,  # Top-right
        'bl': Qt.CursorShape.SizeBDiagCursor,  # Bottom-left
        'br': Qt.CursorShape.SizeFDiagCursor,  # Bottom-right
        't': Qt.CursorShape.SizeVerCursor,     # Top (vertical resize)
        'b': Qt.CursorShape.SizeVerCursor,     # Bottom (vertical resize)
        'l': Qt.CursorShape.SizeHorCursor,     # Left (horizontal resize)
        'r': Qt.CursorShape.SizeHorCursor,     # Right (horizontal resize)
        'rot': None,  # Custom rotation cursor (set below)
    }
    
    # Custom rotation cursor (created once per class)
    _rotate_cursor = None
    
    @classmethod
    def _get_rotate_cursor(cls):
        """Create a custom rotation cursor with a circular arrow."""
        if cls._rotate_cursor is None:
            from PyQt6.QtGui import QCursor, QPixmap
            
            # Create 24x24 pixmap for cursor
            size = 24
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw circular arrow
            pen = QPen(QColor(0, 0, 0), 2)
            painter.setPen(pen)
            
            # Draw arc (270 degrees)
            rect = QRectF(4, 4, 16, 16)
            painter.drawArc(rect.toRect(), 45 * 16, 270 * 16)
            
            # Draw arrowhead at the end of the arc
            import math
            # Arrow at approximately 45 degrees (start of arc)
            cx, cy = 12, 12
            radius = 8
            angle = math.radians(45)
            tip_x = cx + radius * math.cos(angle)
            tip_y = cy - radius * math.sin(angle)
            
            # Arrow points
            arrow_len = 5
            painter.drawLine(
                QPointF(tip_x, tip_y),
                QPointF(tip_x - arrow_len, tip_y - 2)
            )
            painter.drawLine(
                QPointF(tip_x, tip_y),
                QPointF(tip_x + 2, tip_y + arrow_len)
            )
            
            painter.end()
            
            cls._rotate_cursor = QCursor(pixmap, 12, 12)
        
        return cls._rotate_cursor
    
    def __init__(self, element: Element, parent=None):
        super().__init__(parent)
        
        self._element = element
        self._resizing = False
        self._rotating = False
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_pos = None
        self._resize_start_aspect = 1.0  # Original aspect ratio
        self._rotate_start_angle = 0.0  # Starting rotation
        self._rotate_center = None  # Center point for rotation
        self._setup_item()
    
    @property
    def element(self) -> Element:
        return self._element
    
    @property
    def element_id(self) -> str:
        return self._element.id
    
    def _setup_item(self) -> None:
        """Configure item properties from element."""
        self.setPos(self._element.x, self._element.y)
        self.setRect(0, 0, self._element.width, self._element.height)
        
        # Set transform origin to center for center-pivot rotation
        self.setTransformOriginPoint(self.rect().center())
        
        # Enable selection and movement
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self._element.locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        # Accept hover events for cursor changes
        self.setAcceptHoverEvents(True)
        
        # Apply rotation
        if self._element.angle:
            self.setRotation(self._element.angle)
        
        # Apply opacity
        self.setOpacity(self._element.opacity)
        
        # Set visibility
        self.setVisible(self._element.visible)
        
        # Default appearance
        self._update_appearance()
    
    def boundingRect(self) -> QRectF:
        """Override to include rotate handle in clickable area."""
        rect = super().boundingRect()
        # Extend upward to include rotate handle
        hs = self.HANDLE_SIZE
        rect = rect.adjusted(
            -hs/2,  # left
            -self.ROTATE_HANDLE_OFFSET - hs,  # top (extend for rotate handle)
            hs/2,   # right
            hs/2    # bottom
        )
        return rect
    
    def shape(self):
        """Override to include rotate handle in hit testing (clickable area)."""
        from PyQt6.QtGui import QPainterPath
        
        path = QPainterPath()
        # Add the main element rectangle
        path.addRect(self.rect())
        
        # Add the rotate handle area when selected
        if self.isSelected():
            handles = self._get_handle_rects()
            for name, handle_rect in handles.items():
                if name == 'rot':
                    path.addEllipse(handle_rect)
                else:
                    path.addRect(handle_rect)
        
        return path
    
    def _get_element_color(self):
        """Get element color as QColor."""
        if hasattr(self._element, 'color'):
            r, g, b, a = self._element.color
            return QColor(r, g, b, a)
        return QColor(100, 100, 100, 128)
    
    def _get_selection_pen(self):
        """Get pen for selection state."""
        if self.isSelected():
            pen = QPen(QColor(0, 150, 255))  # Blue when selected
            pen.setWidthF(2.0)
        else:
            pen = QPen(QColor(150, 150, 150))  # Gray when not selected
            pen.setWidthF(1.0)
        return pen
    
    def _update_appearance(self) -> None:
        """Update visual appearance based on element type."""
        # Set pen for selection feedback
        self.setPen(self._get_selection_pen())
        
        # Set brush with element color
        self.setBrush(QBrush(self._get_element_color()))
    
    def _get_handle_rects(self) -> Dict[str, QRectF]:
        """Get rectangles for all resize handles (corners + midpoints)."""
        rect = self.rect()
        hs = self.HANDLE_SIZE
        cx = rect.center().x()
        cy = rect.center().y()
        
        return {
            # Corner handles
            'tl': QRectF(rect.left() - hs/2, rect.top() - hs/2, hs, hs),
            'tr': QRectF(rect.right() - hs/2, rect.top() - hs/2, hs, hs),
            'bl': QRectF(rect.left() - hs/2, rect.bottom() - hs/2, hs, hs),
            'br': QRectF(rect.right() - hs/2, rect.bottom() - hs/2, hs, hs),
            # Midpoint handles
            't': QRectF(cx - hs/2, rect.top() - hs/2, hs, hs),
            'b': QRectF(cx - hs/2, rect.bottom() - hs/2, hs, hs),
            'l': QRectF(rect.left() - hs/2, cy - hs/2, hs, hs),
            'r': QRectF(rect.right() - hs/2, cy - hs/2, hs, hs),
            # Rotate handle (above element)
            'rot': QRectF(cx - hs/2, rect.top() - self.ROTATE_HANDLE_OFFSET - hs/2, hs, hs),
        }
    
    def _handle_at(self, pos: QPointF) -> Optional[str]:
        """Get handle name at position, or None."""
        if not self.isSelected():
            return None
        for name, rect in self._get_handle_rects().items():
            if rect.contains(pos):
                return name
        return None
    
    def hoverMoveEvent(self, event):
        """Update cursor based on position over handles."""
        handle = self._handle_at(event.pos())
        if handle:
            if handle == 'rot':
                # Use custom rotation cursor
                self.setCursor(self._get_rotate_cursor())
            else:
                self.setCursor(self.HANDLE_CURSORS[handle])
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press for resize/rotate start."""
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle == 'rot':
                # Start rotation
                self._rotating = True
                self._resize_handle = 'rot'
                self._rotate_center = self.rect().center()
                self._rotate_start_angle = self.rotation()
                self._resize_start_pos = event.pos()
                event.accept()
                return
            elif handle:
                # Start resize
                self._resizing = True
                self._resize_handle = handle
                self._resize_start_rect = self.rect()
                self._resize_start_pos = event.pos()
                # Store aspect ratio for proportional resize
                if self._resize_start_rect.height() > 0:
                    self._resize_start_aspect = self._resize_start_rect.width() / self._resize_start_rect.height()
                else:
                    self._resize_start_aspect = 1.0
                event.accept()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for resizing/rotating."""
        if self._rotating:
            # Calculate rotation angle from center
            import math
            center = self._rotate_center
            start_vec = self._resize_start_pos - center
            curr_vec = event.pos() - center
            
            # Calculate angles
            start_angle = math.atan2(start_vec.y(), start_vec.x())
            curr_angle = math.atan2(curr_vec.y(), curr_vec.x())
            
            # Delta in degrees
            delta_degrees = math.degrees(curr_angle - start_angle)
            new_rotation = self._rotate_start_angle + delta_degrees
            
            # Snap to 15 degree increments if Shift held
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                new_rotation = round(new_rotation / 15) * 15
            
            self.setRotation(new_rotation)
            self.update()
            event.accept()
            return
        
        if self._resizing and self._resize_handle:
            delta = event.pos() - self._resize_start_pos
            rect = QRectF(self._resize_start_rect)
            handle = self._resize_handle
            
            min_size = 10  # Minimum element size
            
            # Check if Shift is held for proportional resize (corners only)
            proportional = (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and handle in ('tl', 'tr', 'bl', 'br')
            
            # Apply resize based on handle type
            if handle == 'tl':
                rect.setTopLeft(rect.topLeft() + delta)
                if proportional:
                    new_width = rect.width()
                    rect.setHeight(new_width / self._resize_start_aspect)
            elif handle == 'tr':
                rect.setTopRight(rect.topRight() + delta)
                if proportional:
                    new_width = rect.width()
                    new_height = new_width / self._resize_start_aspect
                    rect.setTop(rect.bottom() - new_height)
            elif handle == 'bl':
                rect.setBottomLeft(rect.bottomLeft() + delta)
                if proportional:
                    new_width = rect.width()
                    rect.setHeight(new_width / self._resize_start_aspect)
            elif handle == 'br':
                rect.setBottomRight(rect.bottomRight() + delta)
                if proportional:
                    new_width = rect.width()
                    rect.setHeight(new_width / self._resize_start_aspect)
            # Midpoint handles - single axis only
            elif handle == 't':
                rect.setTop(rect.top() + delta.y())
            elif handle == 'b':
                rect.setBottom(rect.bottom() + delta.y())
            elif handle == 'l':
                rect.setLeft(rect.left() + delta.x())
            elif handle == 'r':
                rect.setRight(rect.right() + delta.x())
            
            # Enforce minimum size
            if rect.width() >= min_size and rect.height() >= min_size:
                self.setRect(rect.normalized())
                self.update()
            
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for resize/rotate end."""
        if self._rotating:
            self._rotating = False
            self._resize_handle = None
            # Update element angle
            self._element.angle = self.rotation()
            event.accept()
            return
        
        if self._resizing:
            self._resizing = False
            self._resize_handle = None
            
            # Update element dimensions
            rect = self.rect()
            self._element.width = int(rect.width())
            self._element.height = int(rect.height())
            
            # Adjust position if top-left changed
            if rect.left() != 0 or rect.top() != 0:
                new_pos = self.pos() + rect.topLeft()
                self.setPos(new_pos)
                self._element.x = int(new_pos.x())
                self._element.y = int(new_pos.y())
                self.setRect(0, 0, rect.width(), rect.height())
            
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def paint(self, painter: QPainter, option, widget=None):
        """Custom paint method to render based on element type."""
        rect = self.rect()
        pen = self._get_selection_pen()
        brush = QBrush(self._get_element_color())
        
        painter.setPen(pen)
        painter.setBrush(brush)
        
        elem_type = self._element.element_type
        
        if elem_type == ElementType.RECTANGLE:
            # Draw rectangle (with corner radius if set)
            radius = getattr(self._element, 'radius', 0)
            if radius > 0:
                painter.drawRoundedRect(rect, radius, radius)
            else:
                painter.drawRect(rect)
        
        elif elem_type == ElementType.CIRCLE:
            # Draw circle/ellipse
            painter.drawEllipse(rect)
        
        elif elem_type == ElementType.TRIANGLE:
            # Draw triangle
            from PyQt6.QtGui import QPolygonF
            points = [
                QPointF(rect.center().x(), rect.top()),       # Top center
                QPointF(rect.left(), rect.bottom()),          # Bottom left
                QPointF(rect.right(), rect.bottom()),         # Bottom right
            ]
            painter.drawPolygon(QPolygonF(points))
        
        elif elem_type == ElementType.LINE:
            # Draw line from top-left to bottom-right
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        
        elif elem_type == ElementType.TEXT or elem_type == ElementType.DYNAMIC_TEXT:
            # Draw text placeholder with label
            painter.setBrush(QBrush(QColor(50, 50, 50, 100)))
            painter.drawRect(rect)
            
            # Draw text label
            text = getattr(self._element, 'text', None) or self._element.name
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text[:20])
        
        elif elem_type == ElementType.IMAGE:
            # Draw image placeholder
            painter.setBrush(QBrush(QColor(80, 80, 120, 100)))
            painter.drawRect(rect)
            
            # Draw diagonal lines to indicate image
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            
            # Label
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "IMG")
        
        elif elem_type == ElementType.ICON:
            # Draw icon placeholder (circle with icon indicator)
            painter.setBrush(QBrush(QColor(100, 80, 120, 100)))
            painter.drawEllipse(rect)
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "⚙")
        
        elif elem_type == ElementType.GRAPH:
            # Draw graph placeholder
            painter.setBrush(QBrush(QColor(60, 100, 60, 100)))
            painter.drawRect(rect)
            
            # Draw bar indication
            bar_height = rect.height() * 0.6
            bar_rect = QRectF(
                rect.left() + 2, rect.bottom() - bar_height,
                rect.width() - 4, bar_height
            )
            painter.setBrush(QBrush(QColor(0, 200, 0, 150)))
            painter.drawRect(bar_rect)
        
        elif elem_type == ElementType.RADIAL:
            # Draw radial gauge placeholder
            painter.setBrush(QBrush(QColor(60, 80, 100, 100)))
            painter.drawEllipse(rect)
            
            # Draw arc indicator
            painter.setPen(QPen(QColor(0, 200, 200), 3))
            # Draw simple arc (270 degrees)
            painter.drawArc(rect.adjusted(5, 5, -5, -5).toRect(), 45 * 16, 270 * 16)
        
        elif elem_type == ElementType.LINE_GRAPH:
            # Draw line graph placeholder
            painter.setBrush(QBrush(QColor(60, 60, 100, 100)))
            painter.drawRect(rect)
            
            # Draw sample line
            painter.setPen(QPen(QColor(100, 200, 100), 2))
            points = [
                QPointF(rect.left(), rect.center().y()),
                QPointF(rect.left() + rect.width() * 0.25, rect.top() + rect.height() * 0.3),
                QPointF(rect.left() + rect.width() * 0.5, rect.top() + rect.height() * 0.7),
                QPointF(rect.left() + rect.width() * 0.75, rect.top() + rect.height() * 0.4),
                QPointF(rect.right(), rect.center().y()),
            ]
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
        
        else:
            # Default: draw as rectangle
            painter.drawRect(rect)
        
        # Draw selection handles if selected
        if self.isSelected():
            self._draw_selection_handles(painter)
    
    def _draw_selection_handles(self, painter: QPainter):
        """Draw selection handles at corners, midpoints, and rotate handle."""
        painter.setPen(QPen(QColor(0, 150, 255)))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        
        rect = self.rect()
        cx = rect.center().x()
        
        for name, handle_rect in self._get_handle_rects().items():
            if name == 'rot':
                # Draw connecting line from top center to rotate handle
                painter.drawLine(
                    QPointF(cx, rect.top()),
                    QPointF(cx, rect.top() - self.ROTATE_HANDLE_OFFSET)
                )
                # Draw rotate handle as circle
                painter.drawEllipse(handle_rect)
            else:
                # Draw resize handles as rectangles
                painter.drawRect(handle_rect)
    
    def itemChange(self, change, value):
        """Handle item changes for position updates."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update element position
            new_pos = value
            self._element.x = int(new_pos.x())
            self._element.y = int(new_pos.y())
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_appearance()
            self.update()  # Trigger repaint
        
        # Return value - base class behavior is to return value unchanged
        return value
    
    def update_from_element(self) -> None:
        """Sync graphics item with element data."""
        self.setPos(self._element.x, self._element.y)
        self.setRect(0, 0, self._element.width, self._element.height)
        # Update transform origin to center after rect change
        self.setTransformOriginPoint(self.rect().center())
        self.setRotation(self._element.angle)
        self.setOpacity(self._element.opacity)
        self.setVisible(self._element.visible)
        self._update_appearance()
        self.update()  # Trigger repaint


class PreviewCanvas(QWidget):
    """
    Canvas widget for visual theme editing.
    
    Contains a QGraphicsView with rulers, guides, and element items.
    
    Signals:
        selection_changed: Emitted when canvas selection changes
        element_moved: Emitted when an element is moved on canvas
    """
    
    selection_changed = pyqtSignal(list)  # List of selected element IDs
    element_moved = pyqtSignal(str, int, int)  # element_id, new_x, new_y
    
    # Zoom limits
    MIN_ZOOM = 0.1
    MAX_ZOOM = 5.0
    ZOOM_STEP = 0.1
    
    # Grid settings
    GRID_SIZE = 16
    
    def __init__(
        self,
        model: ThemeModel,
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the preview canvas.
        
        Args:
            model: Theme data model
            undo_stack: Undo stack for operations
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._model = model
        self._undo_stack = undo_stack
        
        self._zoom_level = 1.0
        self._show_grid = True
        self._show_guides = True
        self._guides_h: List[int] = []
        self._guides_v: List[int] = []
        
        self._element_items: Dict[str, ElementItem] = {}
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Set up the canvas UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create graphics scene
        self._scene = QGraphicsScene()
        self._scene.setBackgroundBrush(QBrush(QColor(40, 40, 40)))
        
        # Create graphics view
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Fix for drag trails - use full viewport update
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        layout.addWidget(self._view)
        
        # Set initial scene rect based on display size
        self._update_scene_rect()
        
        # Draw theme background
        self._draw_background()
    
    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.element_added.connect(self._on_element_added)
        self._model.element_removed.connect(self._on_element_removed)
        self._model.element_changed.connect(self._on_element_changed)
        self._model.element_moved.connect(self._on_element_moved)
        
        # Listen for model reset to refresh canvas
        self._model.layoutChanged.connect(self._on_model_layout_changed)
        self._model.modelReset.connect(self._refresh_canvas)
        
        # Connect scene selection changes
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)
    
    def _update_scene_rect(self) -> None:
        """Update scene rectangle based on display size."""
        width = self._model.display_width
        height = self._model.display_height
        
        # Add some margin around the theme area
        margin = 50
        self._scene.setSceneRect(
            -margin, -margin,
            width + 2 * margin,
            height + 2 * margin
        )
    
    def _draw_background(self) -> None:
        """Draw the theme background area."""
        width = self._model.display_width
        height = self._model.display_height
        
        # Theme background rectangle
        bg_rect = self._scene.addRect(
            0, 0, width, height,
            QPen(QColor(100, 100, 100)),
            QBrush(QColor(30, 30, 30))
        )
        bg_rect.setZValue(-1000)
        
        # Draw grid if enabled
        if self._show_grid:
            self._draw_grid()
    
    def _draw_grid(self) -> None:
        """Draw grid overlay."""
        width = self._model.display_width
        height = self._model.display_height
        
        pen = QPen(QColor(60, 60, 60))
        pen.setWidth(1)
        
        # Vertical lines
        for x in range(0, width + 1, self.GRID_SIZE):
            line = self._scene.addLine(x, 0, x, height, pen)
            line.setZValue(-999)
        
        # Horizontal lines
        for y in range(0, height + 1, self.GRID_SIZE):
            line = self._scene.addLine(0, y, width, y, pen)
            line.setZValue(-999)
    
    def _draw_guides(self) -> None:
        """Draw guide lines."""
        if not self._show_guides:
            return
        
        width = self._model.display_width
        height = self._model.display_height
        
        pen = QPen(QColor(0, 255, 255))
        pen.setWidth(1)
        
        # Horizontal guides
        for y in self._guides_h:
            line = self._scene.addLine(0, y, width, y, pen)
            line.setZValue(1000)
        
        # Vertical guides
        for x in self._guides_v:
            line = self._scene.addLine(x, 0, x, height, pen)
            line.setZValue(1000)
    
    # --- Element Management ---
    
    def _on_element_added(self, element_id: str) -> None:
        """Handle element added to model."""
        element = self._model.get_element(element_id)
        if not element:
            return
        
        # Don't create items for groups
        if element.element_type == ElementType.GROUP:
            return
        
        # Create graphics item
        item = ElementItem(element)
        self._scene.addItem(item)
        self._element_items[element_id] = item
        
        logger.debug(f"Added canvas item for: {element.name}")
    
    def _on_element_removed(self, element_id: str) -> None:
        """Handle element removed from model."""
        item = self._element_items.pop(element_id, None)
        if item:
            self._scene.removeItem(item)
            logger.debug(f"Removed canvas item: {element_id}")
    
    def _on_element_changed(self, element_id: str, prop_name: str, value) -> None:
        """Handle element property changed."""
        item = self._element_items.get(element_id)
        if item:
            item.update_from_element()
    
    def _on_element_moved(self, element_id: str, new_x: int, new_y: int) -> None:
        """Handle element moved in model."""
        item = self._element_items.get(element_id)
        if item:
            item.setPos(new_x, new_y)
    
    def _on_model_layout_changed(self) -> None:
        """Handle model layout change (e.g., elements removed)."""
        # Remove items for elements that no longer exist in model
        model_ids = {elem.id for elem in self._model.get_all_elements()}
        for elem_id in list(self._element_items.keys()):
            if elem_id not in model_ids:
                item = self._element_items.pop(elem_id, None)
                if item:
                    self._scene.removeItem(item)
    
    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change."""
        try:
            selected_ids = [
                item.element_id
                for item in self._scene.selectedItems()
                if isinstance(item, ElementItem)
            ]
            self.selection_changed.emit(selected_ids)
        except RuntimeError:
            # Scene may be deleted during application close
            pass
    
    # --- Selection ---
    
    def select_elements(self, element_ids: List[str]) -> None:
        """
        Select elements by ID.
        
        Args:
            element_ids: List of element IDs to select
        """
        # Clear current selection
        self._scene.clearSelection()
        
        # Select specified items
        for elem_id in element_ids:
            item = self._element_items.get(elem_id)
            if item:
                item.setSelected(True)
    
    def get_selected_elements(self) -> List[str]:
        """Get list of selected element IDs."""
        return [
            item.element_id
            for item in self._scene.selectedItems()
            if isinstance(item, ElementItem)
        ]
    
    # --- Zoom ---
    
    def zoom_in(self) -> None:
        """Zoom in by one step."""
        self._zoom_level = min(self._zoom_level + self.ZOOM_STEP, self.MAX_ZOOM)
        self._apply_zoom()
    
    def zoom_out(self) -> None:
        """Zoom out by one step."""
        self._zoom_level = max(self._zoom_level - self.ZOOM_STEP, self.MIN_ZOOM)
        self._apply_zoom()
    
    def zoom_fit(self) -> None:
        """Zoom to fit theme in view."""
        self._view.fitInView(
            0, 0,
            self._model.display_width,
            self._model.display_height,
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self._zoom_level = self._view.transform().m11()
    
    def _apply_zoom(self) -> None:
        """Apply current zoom level."""
        self._view.setTransform(QTransform().scale(self._zoom_level, self._zoom_level))
    
    # --- Grid and Guides ---
    
    def set_grid_visible(self, visible: bool) -> None:
        """Set grid visibility."""
        self._show_grid = visible
        self._refresh_canvas()
    
    def set_guides_visible(self, visible: bool) -> None:
        """Set guides visibility."""
        self._show_guides = visible
        self._refresh_canvas()
    
    def add_guide_h(self, y: int) -> None:
        """Add horizontal guide at y position."""
        self._guides_h.append(y)
        self._draw_guides()
    
    def add_guide_v(self, x: int) -> None:
        """Add vertical guide at x position."""
        self._guides_v.append(x)
        self._draw_guides()
    
    def _refresh_canvas(self) -> None:
        """Refresh the entire canvas."""
        # Clear and redraw
        self._scene.clear()
        self._element_items.clear()
        
        self._draw_background()
        self._draw_guides()
        
        # Recreate element items
        for element in self._model.get_all_elements():
            if element.element_type != ElementType.GROUP:
                item = ElementItem(element)
                self._scene.addItem(item)
                self._element_items[element.id] = item
    
    # --- Event Handling ---
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zoom."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts."""
        # Arrow key nudging
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            nudge = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx, dy = 0, 0
            
            if event.key() == Qt.Key.Key_Left:
                dx = -nudge
            elif event.key() == Qt.Key.Key_Right:
                dx = nudge
            elif event.key() == Qt.Key.Key_Up:
                dy = -nudge
            elif event.key() == Qt.Key.Key_Down:
                dy = nudge
            
            for item in self._scene.selectedItems():
                if isinstance(item, ElementItem):
                    new_x = int(item.pos().x() + dx)
                    new_y = int(item.pos().y() + dy)
                    self._model.move_element(item.element_id, new_x, new_y)
            
            event.accept()
        elif event.key() == Qt.Key.Key_Delete:
            for item in list(self._scene.selectedItems()):
                if isinstance(item, ElementItem):
                    self._model.remove_element(item.element_id)
            event.accept()
        else:
            super().keyPressEvent(event)
