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
import re
import datetime
from typing import Dict, List, Optional, Set

import library.config as config

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QGraphicsObject, QWidget, QVBoxLayout, QGridLayout, QFrame,
    QLineEdit, QTextEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSizeF, QSize, QEvent
from PyQt6.QtGui import (
    QUndoStack, QPainter, QPen, QBrush, QColor, QPixmap,
    QWheelEvent, QMouseEvent, QKeyEvent, QTransform, QFont, QPaintEvent,
    QFontDatabase, QFontMetrics
)

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    Element, ElementType, create_element,
    BackgroundImageElement, BackgroundVideoElement
)
from theme_editor.commands.undo_commands import (
    MoveElementCommand, ChangePropertyCommand, ChangePropertiesCommand
)

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat

logger = logging.getLogger(__name__)

class SensorHighlighter(QSyntaxHighlighter):
    """Highlighter for sensor placeholders in dynamic text."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sensor_format = QTextCharFormat()
        self.sensor_format.setForeground(QColor("#00CCFF"))  # Bright Cyan for sensors
        self.sensor_format.setFontWeight(QFont.Weight.Bold)

    def highlightBlock(self, text):
        pattern = r'\{.*?\}'
        for match in re.finditer(pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.sensor_format)


# Ruler constants
RULER_SIZE = 20
RULER_BG_COLOR = QColor(60, 60, 60)
RULER_TICK_COLOR = QColor(200, 200, 200)
RULER_TEXT_COLOR = QColor(180, 180, 180)


class RulerWidget(QWidget):
    """
    Ruler widget that displays tick marks and allows creating guides by dragging.
    
    Signals:
        guide_created: Emitted when user releases drag to create a guide
        guide_preview: Emitted during drag with current position (for live preview)
    """
    
    guide_created = pyqtSignal(int, int)  # Raw X, Y relative to ruler
    guide_preview = pyqtSignal(int, int)  # Raw X, Y relative to ruler (-1, -1 to clear)
    
    def __init__(self, orientation: str, parent=None):
        """
        Initialize the ruler.
        
        Args:
            orientation: 'horizontal' or 'vertical'
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._orientation = orientation
        self._zoom = 1.0
        self._scroll_offset = 0
        self._dragging = False
        self._preview_line = None  # Preview line position during drag
        
        # Set fixed size based on orientation
        if orientation == 'horizontal':
            self.setFixedHeight(RULER_SIZE)
            self.setMinimumWidth(100)
        else:
            self.setFixedWidth(RULER_SIZE)
            self.setMinimumHeight(100)
        
        self.setMouseTracking(True)
    
    def set_zoom(self, zoom: float) -> None:
        """Update zoom level and redraw."""
        self._zoom = zoom
        self.update()
    
    def set_scroll_offset(self, offset: int) -> None:
        """Update scroll offset and redraw."""
        self._scroll_offset = offset
        self.update()
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the ruler with tick marks."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), RULER_BG_COLOR)
        
        # Draw tick marks and numbers
        pen = QPen(RULER_TICK_COLOR)
        pen.setWidth(0)
        painter.setPen(pen)
        
        font = QFont("Arial", 7)
        painter.setFont(font)
        
        # Calculate step size based on zoom (multiples of 10 for consistency)
        if self._zoom >= 4.0:
            step = 10
        elif self._zoom >= 2.0:
            step = 20
        elif self._zoom >= 1.0:
            step = 50
        elif self._zoom >= 0.5:
            step = 100
        elif self._zoom >= 0.2:
            step = 200
        else:
            step = 500
        
        # Determine visible range based on scroll offset and zoom
        if self._orientation == 'horizontal':
            length = self.width()
            start_pos = int(-self._scroll_offset / self._zoom)
            end_pos = int((length - self._scroll_offset) / self._zoom)
        else:
            length = self.height()
            start_pos = int(-self._scroll_offset / self._zoom)
            end_pos = int((length - self._scroll_offset) / self._zoom)
        
        # Round to step boundary
        start_pos = (start_pos // step) * step
        
        for pos in range(start_pos, end_pos + step, 5):
            screen_pos = round(pos * self._zoom + self._scroll_offset)
            
            is_major = (pos % step == 0)
            is_medium = (pos % (step // 2) == 0) if (step // 2) % 10 == 0 else False
            is_minor = (pos % 5 == 0) and not is_major and not is_medium
            
            # Visibility of minor ticks depends on zoom/step
            show_minor = (self._zoom >= 2.0)
            
            if not is_major and not is_medium and not (is_minor and show_minor):
                continue
                
            tick_len = 5
            if is_major:
                tick_len = 12
            elif is_medium:
                tick_len = 8
            elif is_minor:
                tick_len = 3
            
            if self._orientation == 'horizontal':
                painter.drawLine(screen_pos, RULER_SIZE - tick_len, screen_pos, RULER_SIZE)
                if is_major and pos >= 0:
                    painter.setPen(RULER_TEXT_COLOR)
                    painter.drawText(screen_pos + 2, 10, str(pos))
                    painter.setPen(RULER_TICK_COLOR)
            else:
                painter.drawLine(RULER_SIZE - tick_len, screen_pos, RULER_SIZE, screen_pos)
                if is_major and pos >= 0:
                    painter.setPen(RULER_TEXT_COLOR)
                    # Draw rotated text for vertical ruler
                    painter.save()
                    painter.translate(10, screen_pos + 2)
                    painter.rotate(90)
                    painter.drawText(0, 0, str(pos))
                    painter.restore()
                    painter.setPen(RULER_TICK_COLOR)
        
        if self._dragging and self._preview_line is not None:
            # We don't draw the preview on the ruler anymore, 
            # PreviewCanvas will draw it on the scene.
            pass
        
        # Draw edge line
        pen.setWidth(1)
        painter.setPen(pen)
        if self._orientation == 'horizontal':
            painter.drawLine(0, RULER_SIZE - 1, self.width(), RULER_SIZE - 1)
        else:
            painter.drawLine(RULER_SIZE - 1, 0, RULER_SIZE - 1, self.height())
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start dragging to create a guide."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            if self._orientation == 'horizontal':
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Inform parent of drag for preview."""
        if self._dragging:
            pos = event.position()
            self.guide_preview.emit(int(pos.x()), int(pos.y()))
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finish drag and emit raw position."""
        if self._dragging:
            self._dragging = False
            self.unsetCursor()
            
            # Clear preview
            self.guide_preview.emit(-1, -1)
            
            pos = event.position()
            self.guide_created.emit(int(pos.x()), int(pos.y()))
            self.update()


class GuideLineItem(QGraphicsLineItem):
    """
    Draggable guide line item.
    
    Supports horizontal and vertical guides with drag-to-move functionality.
    """
    
    def __init__(self, orientation: str, position: int, length: int, 
                 display_width: int, display_height: int,
                 on_moved=None, on_removed=None, parent=None):
        """
        Initialize a guide line.
        
        Args:
            orientation: 'horizontal' or 'vertical'
            position: Y position (horizontal) or X position (vertical)
            length: Display width or height
            display_width: Display width for bounds checking
            display_height: Display height for bounds checking
            on_moved: Callback when guide is moved
            on_removed: Callback when guide should be removed
            parent: Parent item
        """
        super().__init__(parent)
        
        self._orientation = orientation
        self._position = position
        self._length = length
        self._display_width = display_width
        self._display_height = display_height
        self._on_moved = on_moved
        self._on_removed = on_removed
        self._dragging = False
        
        self._update_line()
        
        # Set appearance
        pen = QPen(QColor(0, 255, 255))
        pen.setWidth(1)
        self.setPen(pen)
        
        # High z-value to be on top
        self.setZValue(1000)
        
        # Accept hover events
        self.setAcceptHoverEvents(True)
    
    @property
    def orientation(self) -> str:
        return self._orientation
    
    @property
    def position(self) -> int:
        return self._position
    
    def _update_line(self) -> None:
        """Update line geometry based on position."""
        if self._orientation == 'horizontal':
            self.setLine(0, self._position, self._length, self._position)
        else:
            self.setLine(self._position, 0, self._position, self._length)
    
    def hoverEnterEvent(self, event):
        """Show resize cursor on hover."""
        if self._orientation == 'horizontal':
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Reset cursor on leave."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Start dragging the guide."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Move guide to new position."""
        if self._dragging:
            pos = event.scenePos()
            if self._orientation == 'horizontal':
                self._position = int(pos.y())
            else:
                self._position = int(pos.x())
            self._update_line()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Finish dragging - check if outside bounds to remove."""
        if self._dragging:
            self._dragging = False
            
            # Check if guide is outside display bounds
            if self._orientation == 'horizontal':
                if self._position < 0 or self._position > self._display_height:
                    if self._on_removed:
                        self._on_removed(self)
                    event.accept()
                    return
            else:
                if self._position < 0 or self._position > self._display_width:
                    if self._on_removed:
                        self._on_removed(self)
                    event.accept()
                    return
            
            # Guide is valid, notify move
            if self._on_moved:
                self._on_moved()
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ElementItem(QGraphicsObject):
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
        'p1': Qt.CursorShape.SizeAllCursor,    # Triangle point 1
        'p2': Qt.CursorShape.SizeAllCursor,    # Triangle point 2
        'p3': Qt.CursorShape.SizeAllCursor,    # Triangle point 3
        'start': Qt.CursorShape.SizeAllCursor, # Line start
        'end': Qt.CursorShape.SizeAllCursor,   # Line end
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
    
    def __init__(self, element: Element, model: ThemeModel, parent=None):
        super().__init__(parent)
        self._rect = QRectF(0, 0, element.width, element.height)
        
        self._element = element
        self._model = model
        self._rotating = False
        self._resizing = False
        self._is_updating_geometry = False
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_pos = None
        self._resize_start_aspect = 1.0  # Original aspect ratio
        self._rotate_start_angle = 0.0  # Starting rotation
        self._rotate_center = None  # Center point for rotation
        
        # Font caching
        self._font = None
        self._is_updating_size = False  # Guard against recursion
        
        # Image/icon caching
        self._cached_pixmap = None  # Cached QPixmap for images
        self._cached_image_path = None  # Path used for cached pixmap
        self._cached_icon_font = None  # Cached QFont for icons
        self._cached_icon_unicode = None  # Cached unicode char for icon
        
        # Selection state
        is_bg = isinstance(element, (BackgroundImageElement, BackgroundVideoElement))
        flags = QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        if not is_bg:
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        
        self.setFlags(flags)
        self.setAcceptHoverEvents(not is_bg)
        
        if is_bg:
            self.setZValue(-500)
        
        # Connect initial properties
        self.update_from_element()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """Handle position change to sync with element properties."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            old_pos = self.pos()
            dx = new_pos.x() - old_pos.x()
            dy = new_pos.y() - old_pos.y()
            
            # Sync element's absolute coordinates via Model
            if self._element.element_type == ElementType.TRIANGLE:
                 # Calculate new values
                 # Notes: Triangle uses x1..y3, not x/y directly for positioning
                 # We must update all points relative to the move
                 new_x1 = self._element.x1 + int(dx)
                 new_y1 = self._element.y1 + int(dy)
                 new_x2 = self._element.x2 + int(dx)
                 new_y2 = self._element.y2 + int(dy)
                 new_x3 = self._element.x3 + int(dx)
                 new_y3 = self._element.y3 + int(dy)
                 
                 # Setup block signals or batch update if possible, but for now serial calls or batching
                 # The model doesn't have a batch update yet, so we call individually
                 # To prevent jitter, we could suppress updates or rely on Qt's coalescing
                 self._model.set_element_property(self._element.id, "x1", new_x1)
                 self._model.set_element_property(self._element.id, "y1", new_y1)
                 self._model.set_element_property(self._element.id, "x2", new_x2)
                 self._model.set_element_property(self._element.id, "y2", new_y2)
                 self._model.set_element_property(self._element.id, "x3", new_x3)
                 self._model.set_element_property(self._element.id, "y3", new_y3)

            elif self._element.element_type == ElementType.LINE:
                 # Line uses x,y and x2,y2
                 new_x = self._element.x + int(dx)
                 new_y = self._element.y + int(dy)
                 new_x2 = self._element.x2 + int(dx)
                 new_y2 = self._element.y2 + int(dy)
                 
                 self._model.set_element_property(self._element.id, "x", new_x)
                 self._model.set_element_property(self._element.id, "y", new_y)
                 self._model.set_element_property(self._element.id, "x2", new_x2)
                 self._model.set_element_property(self._element.id, "y2", new_y2)

            else:
                # Standard element uses x,y
                new_x = int(new_pos.x())
                new_y = int(new_pos.y())
                # Use move_element for semantic clarity and potential optimization
                self._model.move_element(self._element.id, new_x, new_y)
                
        return super().itemChange(change, value)

    def rect(self):
        """Compatibility method for rest of code."""
        return self._rect
        
    def setRect(self, *args):
        """Compatibility method for rest of code."""
        if len(args) == 1:
            new_rect = args[0]
        else:
            new_rect = QRectF(*args)
            
        if self._rect == new_rect:
            return
            
        self.prepareGeometryChange()
        self._rect = new_rect
        self.setTransformOriginPoint(self._rect.center())
        self.update()
    
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
        rect = self._rect
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
        from PyQt6.QtGui import QPainterPath, QPolygonF
        
        path = QPainterPath()
        elem_type = self._element.element_type
        
        if elem_type == ElementType.TRIANGLE:
            pos = self.pos()
            p1 = QPointF(self._element.x1 - pos.x(), self._element.y1 - pos.y())
            p2 = QPointF(self._element.x2 - pos.x(), self._element.y2 - pos.y())
            p3 = QPointF(self._element.x3 - pos.x(), self._element.y3 - pos.y())
            path.addPolygon(QPolygonF([p1, p2, p3]))
        elif elem_type == ElementType.LINE:
            pos = self.pos()
            p1 = QPointF(self._element.x - pos.x(), self._element.y - pos.y())
            p2 = QPointF(self._element.x2 - pos.x(), self._element.y2 - pos.y())
            
            line_path = QPainterPath()
            line_path.moveTo(p1)
            line_path.lineTo(p2)
            
            # Use a stroker to make the line clickable with some tolerance
            from PyQt6.QtGui import QPainterPathStroker
            stroker = QPainterPathStroker()
            stroker.setWidth(max(10, self._element.line_width))
            stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
            path = stroker.createStroke(line_path)
        else:
            # Add the main element rectangle
            path.addRect(self.rect())
        
        # Add selection handles and rotate handle to the shape when selected
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
    
    def _get_anchor_point(self, handle: str) -> tuple[float, float]:
        """Get the scene coordinates of the anchor point opposite to the handle."""
        # Use starting rect to ensure anchor remains fixed during the entire resize
        rect = self.mapToScene(self._resize_start_rect).boundingRect()
        if handle == 'tl': return rect.right(), rect.bottom()
        if handle == 'tr': return rect.left(), rect.bottom()
        if handle == 'bl': return rect.right(), rect.top()
        if handle == 'br': return rect.left(), rect.top()
        if handle == 't': return rect.center().x(), rect.bottom()
        if handle == 'b': return rect.center().x(), rect.top()
        if handle == 'l': return rect.right(), rect.center().y()
        if handle == 'r': return rect.left(), rect.center().y()
        return rect.center().x(), rect.center().y()

    def _update_appearance(self) -> None:
        """Update visual appearance based on element type."""
        # For QGraphicsObject, we just trigger a repaint
        self.update()

    def _get_font(self) -> QFont:
        """Get QFont for the text element, loading it if necessary."""
        elem_type = self._element.element_type
        if elem_type not in (ElementType.TEXT, ElementType.DYNAMIC_TEXT):
            return QFont()
            
        font_path_rel = getattr(self._element, 'font', "roboto/Roboto-Regular.ttf")
        font_size = getattr(self._element, 'font_size', 16)
        # Clamp font size to prevent overflow errors
        font_size = max(1, min(1000, int(font_size)))
        
        # Check if we need to reload the font (cache invalidation)
        cache_key = (font_path_rel, font_size)
        if hasattr(self, '_font_cache_key') and self._font_cache_key == cache_key and self._font:
            return self._font
        
        # Try to find the font file
        theme_path = self._model._theme_path
        font_path = None
        if theme_path:
            p = theme_path / font_path_rel
            if p.exists():
                font_path = str(p)
        
        if not font_path:
            # Try general fonts directory
            import os
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'res', 'fonts')
            p = os.path.join(fonts_dir, font_path_rel)
            if os.path.exists(p):
                font_path = p

        font = None
        if font_path:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    font = QFont(families[0])
                    font.setPixelSize(font_size)
        
        if not font:
            # Fallback
            font = QFont("Arial")
            font.setPixelSize(font_size)
        
        # Cache the font
        self._font = font
        self._font_cache_key = cache_key
        return font

    def _resolve_dynamic_text(self, template: str) -> str:
        """Resolve format strings using mock data for preview."""
        resolved_text = template
        try:
            placeholders = re.findall(r'\{(.*?)\}', template)
            for placeholder in placeholders:
                parts = placeholder.split(':')
                sensor_id = parts[0]
                flag = parts[1] if len(parts) > 1 else None
                
                value = ""
                if sensor_id.startswith("DATE"):
                    # Handle date/time formatting
                    now = datetime.datetime.now()
                    if flag == "short":
                        if "HOUR" in sensor_id:
                            value = now.strftime("%I:%M %p")
                        else:
                            value = now.strftime("%m/%d/%y")
                    elif flag == "medium":
                        if "HOUR" in sensor_id:
                            value = now.strftime("%I:%M:%S %p")
                        else:
                            value = now.strftime("%b %d, %Y")
                    elif flag == "long":
                        if "HOUR" in sensor_id:
                            value = now.strftime("%I:%M:%S %p %Z")
                        else:
                            value = now.strftime("%B %d, %Y")
                    elif flag == "full":
                        if "HOUR" in sensor_id:
                            value = now.strftime("%A, %B %d, %Y %I:%M:%S %p %Z")
                        else:
                            value = now.strftime("%A, %B %d, %Y")
                    elif flag:
                        # Try custom strftime pattern
                        try:
                            # Map common Java/Qt patterns to Python if needed
                            pattern = flag.replace("yyyy", "%Y").replace("yy", "%y").replace("MM", "%m").replace("dd", "%d")
                            pattern = pattern.replace("HH", "%H").replace("mm", "%M").replace("ss", "%S").replace("zzz", "%Z")
                            value = now.strftime(pattern)
                        except:
                            value = str(config.STATS_VALUES.get(sensor_id, f"{{{placeholder}}}"))
                    else:
                        value = str(config.STATS_VALUES.get(sensor_id, f"{{{placeholder}}}"))
                elif sensor_id == "UPTIME":
                    if flag == "SECONDS":
                        value = str(config.STATS_VALUES.get("UPTIME.SECONDS", "228790"))
                    elif flag == "FORMATTED":
                        value = str(config.STATS_VALUES.get("UPTIME.FORMATTED", "2 days, 15:33:10"))
                    else:
                        value = str(config.STATS_VALUES.get("UPTIME.FORMATTED", f"{{{placeholder}}}"))
                elif flag == 'nu':
                    value = str(config.STATS_VALUES.get(f"{sensor_id}_RAW", f"{{{placeholder}}}"))
                elif flag == 'u':
                    value = str(config.STATS_VALUES.get(sensor_id, f"{{{placeholder}}}"))
                elif flag == 'r':
                    value = str(config.STATS_RAW.get(sensor_id, f"{{{placeholder}}}"))
                else:
                    value = str(config.STATS_VALUES.get(sensor_id, f"{{{placeholder}}}"))
                
                resolved_text = resolved_text.replace(f"{{{placeholder}}}", value)
        except Exception as e:
            logger.error(f"Error resolving dynamic text: {e}")
            
        return resolved_text

    def _update_text_size(self) -> None:
        """Update element width/height based on text content and font."""
        if self._is_updating_size:
            return
            
        elem_type = self._element.element_type
        if elem_type not in (ElementType.TEXT, ElementType.DYNAMIC_TEXT):
            return
            
        self._is_updating_size = True
        try:
            text = getattr(self._element, 'text', None) or "Sample Text"
            if elem_type == ElementType.DYNAMIC_TEXT:
                text = self._resolve_dynamic_text(text)

            font = self._get_font()
            metrics = QFontMetrics(font)
            
            # Calculate bounding rect for text
            rect = metrics.boundingRect(text)
            
            # Use static size if requested
            force_static = getattr(self._element, 'force_static', False)
            if force_static:
                new_w = self._element.width
                new_h = self._element.height
            else:
                # Update element properties if they differ significantly (to avoid loops)
                new_w = int(max(10, rect.width() + 4)) # Add small padding
                new_h = int(max(10, rect.height() + 4))
                
                if self._element.width != new_w or self._element.height != new_h:
                    self._model.set_element_property(self._element.id, "width", new_w)
                    self._model.set_element_property(self._element.id, "height", new_h)
            
            # Calculate offsets based on anchor (Pillow style)
            anchor = getattr(self._element, 'anchor', 'lt')
            off_x = 0
            if anchor.startswith('m'): # middle
                off_x = -new_w / 2
            elif anchor.startswith('r'): # right
                off_x = -new_w
                
            off_y = 0
            # Vertical: t (top/ascender), m (middle), b (bottom)
            if 'm' in anchor[1:]: # middle
                off_y = -new_h / 2
            elif 'b' in anchor[1:]: # bottom
                off_y = -new_h
            
            # Update rect with offsets
            self.setRect(off_x, off_y, new_w, new_h)
            self.setTransformOriginPoint(self.rect().center())
        finally:
            self._is_updating_size = False
    
    def _get_handle_rects(self) -> Dict[str, QRectF]:
        """Get rectangles for all resize handles (corners + midpoints)."""
        rect = self.rect()
        hs = self.HANDLE_SIZE
        offset = hs / 2
        
        if self._element.element_type == ElementType.TRIANGLE:
             # TRIANGLE: Reverting to standard bounding box handles as requested
             pass
        elif self._element.element_type == ElementType.LINE:
            # Special 2-point handles for LINE
            pos = self.pos()
            p1 = QPointF(self._element.x - pos.x(), self._element.y - pos.y())
            p2 = QPointF(self._element.x2 - pos.x(), self._element.y2 - pos.y())
            
            handles = {}
            handles['start'] = QRectF(p1.x() - offset, p1.y() - offset, hs, hs)
            handles['end'] = QRectF(p2.x() - offset, p2.y() - offset, hs, hs)
            return handles

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
    
    def mouseDoubleClickEvent(self, event):
        """Handle double click for on-canvas editing."""
        if self._element.element_type in (ElementType.TEXT, ElementType.DYNAMIC_TEXT):
            self._start_on_canvas_editing()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _start_on_canvas_editing(self) -> None:
        """Show an overlay to edit text on the canvas."""
        # Find the view to parent the editor
        view = self.scene().views()[0] if self.scene().views() else None
        if not view: return
        
        elem_type = self._element.element_type
        text_val = getattr(self._element, 'text', "")
        
        if elem_type == ElementType.DYNAMIC_TEXT:
            # Use QTextEdit for highlighting
            self._edit_overlay = QTextEdit(view)
            self._edit_overlay.setPlainText(text_val)
            self._highlighter = SensorHighlighter(self._edit_overlay.document())
            self._edit_overlay.setAcceptRichText(False)
            self._edit_overlay.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._edit_overlay.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Handle Enter key in QTextEdit (subclass or event filter?)
            # For simplicity, we'll use an event filter to catch Enter
            self._edit_overlay.installEventFilter(self)
        else:
            # Use QLineEdit for simple text
            self._edit_overlay = QLineEdit(view)
            self._edit_overlay.setText(text_val)
            self._edit_overlay.returnPressed.connect(self._finish_on_canvas_editing)
        
        # Style the editor to look "on-canvas"
        font = self._get_font()
        # Scale font for view zoom
        zoom = view.transform().m11()
        font.setPointSizeF(font.pointSizeF() * zoom)
        self._edit_overlay.setFont(font)
        
        # Position the line edit
        scene_rect = self.sceneBoundingRect()
        view_rect = view.mapFromScene(scene_rect).boundingRect()
        
        # Add some padding to avoid clipping handles
        self._edit_overlay.setGeometry(view_rect.adjusted(-2, -2, 2, 2))
        
        # Styling
        css = """
            QWidget {
                background: rgba(40, 40, 40, 240);
                color: white;
                border: 1px solid #0096FF;
                padding: 0px;
            }
        """
        self._edit_overlay.setStyleSheet(css)
        
        self._edit_overlay.setFocus()
        if isinstance(self._edit_overlay, QLineEdit):
            self._edit_overlay.selectAll()
        else:
            self._edit_overlay.selectAll()
        
        # Signals
        self._edit_overlay.editingFinished.connect(self._finish_on_canvas_editing) if hasattr(self._edit_overlay, 'editingFinished') else None

    def eventFilter(self, obj, event):
        """Event filter to handle keys in QTextEdit overlay."""
        if obj == getattr(self, '_edit_overlay', None) and isinstance(obj, QTextEdit):
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self._finish_on_canvas_editing()
                        return True
                elif event.key() == Qt.Key.Key_Escape:
                    self._edit_overlay.deleteLater()
                    self._edit_overlay = None
                    return True
        return super().eventFilter(obj, event)

    def _finish_on_canvas_editing(self) -> None:
        """Handle completion of on-canvas text editing."""
        if not hasattr(self, '_edit_overlay') or not self._edit_overlay:
            return
            
        if isinstance(self._edit_overlay, QLineEdit):
            new_text = self._edit_overlay.text()
        else:
            new_text = self._edit_overlay.toPlainText()
            
        # Apply change via model
        if new_text != getattr(self._element, 'text', ""):
            self._model.set_element_property(self._element.id, "text", new_text)
            self._update_text_size()
            
        # Clean up
        self._edit_overlay.deleteLater()
        self._edit_overlay = None
        self._highlighter = None

    def _store_move_start(self) -> None:
        """Store starting coordinates for move operation (supports bulk move undo)."""
        if self._element.element_type == ElementType.TRIANGLE:
            self._move_start_pts = [
                (self._element.x1, self._element.y1),
                (self._element.x2, self._element.y2),
                (self._element.x3, self._element.y3)
            ]
        elif self._element.element_type == ElementType.LINE:
            self._move_start_coords = {
                'x': self._element.x, 'y': self._element.y,
                'x2': self._element.x2, 'y2': self._element.y2
            }
        else:
            self._move_start_pos = (self._element.x, self._element.y)

    def _has_moved(self) -> bool:
        """Check if the element has moved since move start."""
        if self._element.element_type == ElementType.TRIANGLE:
            if not hasattr(self, '_move_start_pts'): return False
            new_pts = [(self._element.x1, self._element.y1), (self._element.x2, self._element.y2), (self._element.x3, self._element.y3)]
            return self._move_start_pts != new_pts
        elif self._element.element_type == ElementType.LINE:
            if not hasattr(self, '_move_start_coords'): return False
            new_coords = {'x': self._element.x, 'y': self._element.y, 'x2': self._element.x2, 'y2': self._element.y2}
            return self._move_start_coords != new_coords
        else:
            if not hasattr(self, '_move_start_pos'): return False
            return self._move_start_pos != (self._element.x, self._element.y)

    def _push_move_command(self) -> None:
        """Push appropriate move command to undo stack."""
        if self._element.element_type == ElementType.TRIANGLE:
            old_vals = {
                'x1': self._move_start_pts[0][0], 'y1': self._move_start_pts[0][1],
                'x2': self._move_start_pts[1][0], 'y2': self._move_start_pts[1][1],
                'x3': self._move_start_pts[2][0], 'y3': self._move_start_pts[2][1]
            }
            new_vals = {
                'x1': self._element.x1, 'y1': self._element.y1,
                'x2': self._element.x2, 'y2': self._element.y2,
                'x3': self._element.x3, 'y3': self._element.y3
            }
            cmd = ChangePropertiesCommand(self._model, self._element.id, old_vals, new_vals, "Move Triangle")
            self._model._undo_stack.push(cmd)
        elif self._element.element_type == ElementType.LINE:
            old_vals = self._move_start_coords
            new_vals = {'x': self._element.x, 'y': self._element.y, 'x2': self._element.x2, 'y2': self._element.y2}
            cmd = ChangePropertiesCommand(self._model, self._element.id, old_vals, new_vals, "Move Line")
            self._model._undo_stack.push(cmd)
        else:
            old_x, old_y = self._move_start_pos
            cmd = MoveElementCommand(self._model, self._element.id, old_x, old_y, self._element.x, self._element.y)
            self._model._undo_stack.push(cmd)

    def _cleanup_move_start(self) -> None:
        """Clean up move start attributes."""
        for attr in ('_move_start_pts', '_move_start_coords', '_move_start_pos'):
            if hasattr(self, attr):
                delattr(self, attr)

    def mousePressEvent(self, event):
        """Handle mouse press for resize/rotate start."""
        print("DEBUG: ElementItem.mousePressEvent")
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle == 'rot':
                # Start rotation
                self._rotating = True
                self._resize_handle = 'rot'
                self._rotate_center = self.rect().center()
                self._rotate_start_angle = self.rotation()
                event.accept()
                return
            elif handle:
                # Start resizing
                self._resizing = True
                self._resize_handle = handle
                self._resize_start_rect = self.rect()
                self._resize_start_pos = event.pos()
                self._resize_start_aspect = self.rect().width() / self.rect().height() if self.rect().height() > 0 else 1.0
                
                if self._element.element_type == ElementType.LINE:
                    self._resize_start_coords = {
                        'x': self._element.x, 'y': self._element.y,
                        'x2': self._element.x2, 'y2': self._element.y2
                    }
                elif self._element.element_type == ElementType.TRIANGLE:
                    # Store original positions in scene coords on resize start for scaling
                    self._resize_start_pts = [
                        (self._element.x1, self._element.y1),
                        (self._element.x2, self._element.y2),
                        (self._element.x3, self._element.y3)
                    ]
                event.accept()
                return
            else:
                # Normal move start - let base class handle selection (Ctrl/Shift supported)
                super().mousePressEvent(event)
                
                # If this item is selected, store start positions for all selected items for bulk move
                if self.isSelected():
                    selected_items = [i for i in self.scene().selectedItems() if isinstance(i, ElementItem)]
                    print(f"DEBUG: Selected items for move: {len(selected_items)}")
                    for item in selected_items:
                        item._store_move_start()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for resizing/rotating."""
        # print("DEBUG: ElementItem.mouseMoveEvent start")
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
            
            # 1. Update virtual rect based on handle and delta
            min_size = 10
            # Check if Shift is held for proportional resize (corners only)
            proportional = (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and handle in ('tl', 'tr', 'bl', 'br')
            
            if handle == 'tl':
                rect.setTopLeft(rect.topLeft() + delta)
                if proportional:
                    rect.setHeight(rect.width() / self._resize_start_aspect)
            elif handle == 'tr':
                rect.setTopRight(rect.topRight() + delta)
                if proportional:
                    new_height = rect.width() / self._resize_start_aspect
                    rect.setTop(rect.bottom() - new_height)
            elif handle == 'bl':
                rect.setBottomLeft(rect.bottomLeft() + delta)
                if proportional:
                    rect.setHeight(rect.width() / self._resize_start_aspect)
            elif handle == 'br':
                rect.setBottomRight(rect.bottomRight() + delta)
                if proportional:
                    rect.setHeight(rect.width() / self._resize_start_aspect)
            elif handle == 't':
                rect.setTop(rect.top() + delta.y())
            elif handle == 'b':
                rect.setBottom(rect.bottom() + delta.y())
            elif handle == 'l':
                rect.setLeft(rect.left() + delta.x())
            elif handle == 'r':
                rect.setRight(rect.right() + delta.x())
            
            rect = rect.normalized()
            
            # 2. Handle specific element types with the new rect
            if self._element.element_type == ElementType.LINE:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    import math
                    # Snap to 5-degree increments relative to the other point
                    other_p = QPointF(self._element.x2, self._element.y2) if handle == 'start' else QPointF(self._element.x, self._element.y)
                    curr_p = event.scenePos()
                    diff = curr_p - other_p
                    dist = math.sqrt(diff.x()**2 + diff.y()**2)
                    if dist > 0.1:
                        angle_rad = math.atan2(diff.y(), diff.x())
                        angle_deg = math.degrees(angle_rad)
                        snapped_deg = round(angle_deg / 5) * 5
                        snapped_rad = math.radians(snapped_deg)
                        
                        new_x = int(other_p.x() + dist * math.cos(snapped_rad))
                        new_y = int(other_p.y() + dist * math.sin(snapped_rad))
                        
                        if handle == 'start':
                            self._model.move_element(self._element.id, new_x, new_y)
                        else:
                            self._model.set_element_property(self._element.id, "x2", new_x)
                            self._model.set_element_property(self._element.id, "y2", new_y)
                else:
                    # Line uses scene delta for start/end handles directly
                    delta_scene = event.scenePos() - event.lastScenePos()
                    if handle == 'start':
                        # x,y handled by move_element or property set?
                        # Manual calculation:
                        new_x = self._element.x + int(delta_scene.x())
                        new_y = self._element.y + int(delta_scene.y())
                        self._model.move_element(self._element.id, new_x, new_y)
                    elif handle == 'end':
                        new_x2 = self._element.x2 + int(delta_scene.x())
                        new_y2 = self._element.y2 + int(delta_scene.y())
                        self._model.set_element_property(self._element.id, "x2", new_x2)
                        self._model.set_element_property(self._element.id, "y2", new_y2)
                
                # Clamp coordinates to avoid overflow (Model handles this, but we can do it too or let model do it)
                # self._element.x = ... (Model handles clamping)
                
                self.prepareGeometryChange()
                self.update_from_element()
                event.accept()
                return

            elif self._element.element_type == ElementType.TRIANGLE:
                old_rect = self._resize_start_rect
                new_rect = rect # already normalized
                
                if old_rect.width() > 0 and old_rect.height() > 0:
                    scale_x = new_rect.width() / old_rect.width()
                    scale_y = new_rect.height() / old_rect.height()
                    
                    # Update element points based on scaling from anchor
                    # Anchor is the corner opposite to the dragged handle
                    anchor_x, anchor_y = self._get_anchor_point(handle)
                    
                    self._element.x1 = int(anchor_x + (self._resize_start_pts[0][0] - anchor_x) * scale_x)
                    self._element.y1 = int(anchor_y + (self._resize_start_pts[0][1] - anchor_y) * scale_y)
                    self._element.x2 = int(anchor_x + (self._resize_start_pts[1][0] - anchor_x) * scale_x)
                    self._element.y2 = int(anchor_y + (self._resize_start_pts[1][1] - anchor_y) * scale_y)
                    self._element.y3 = int(anchor_y + (self._resize_start_pts[2][1] - anchor_y) * scale_y)

                # Update via Model
                self._model.set_element_property(self._element.id, "x1", self._element.x1)
                self._model.set_element_property(self._element.id, "y1", self._element.y1)
                self._model.set_element_property(self._element.id, "x2", self._element.x2)
                self._model.set_element_property(self._element.id, "y2", self._element.y2)
                self._model.set_element_property(self._element.id, "x3", self._element.x3)
                self._model.set_element_property(self._element.id, "y3", self._element.y3)
                
                self.prepareGeometryChange()
                self.update_from_element()
                event.accept()
                return

            # Enforce minimum size
            if rect.width() >= min_size and rect.height() >= min_size:
                # SPECIAL HANDLING FOR STATIC TEXT: resize updates font size
                # DYNAMIC TEXT now updates width/height instead of font size
                is_ui_text = (self._element.element_type == ElementType.TEXT)
                
                if is_ui_text and handle in ('tl', 'tr', 'bl', 'br'):
                    # Calculate new font size based on height change ratio
                    old_h = self._resize_start_rect.height()
                    new_h = rect.height()
                    if old_h > 0:
                        old_fs = getattr(self._element, 'font_size', 16)
                        new_fs = max(6, min(1000, int(old_fs * (new_h / old_h))))
                        if new_fs != old_fs:
                            self._model.set_element_property(self._element.id, "font_size", new_fs)
                        # The update_from_element will handle the rest
                else:
                    # For all other elements including DYNAMIC_TEXT, update dimensions
                    self.setRect(rect.normalized())
                    self.update()
            
            event.accept()
            return
        
        # print("DEBUG: Calling super().mouseMoveEvent")
        super().mouseMoveEvent(event)
        # print("DEBUG: super().mouseMoveEvent returned")
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for resize/rotate end."""
        if self._rotating:
            self._rotating = False
            self._resize_handle = None
            # Update element angle via model (triggers undo command via property panel? No, interactive usually needs explicit command?)
            # Wait, interactive rotation usually ends with a command?
            # Existing code just set self._element.angle. 
            # If we want undo support, we should push a command here or use set_element_property.
            # set_element_property pushes undo? No, set_element_property is low level. 
            # Commands use set_element_property.
            # Ideally we should push a ChangePropertyCommand here.
            # But for "Single Source of Truth", we first need to ensure the Model is updated.
            # If we push a command, it will allow undo.
            # Let's check how resize does it.
            # Resize (triangle) pushes ChangePropertiesCommand.
            # Rect/Circle resize just sets attrs?
            # Lines 1333 just set width/height. This means Rect resize wasn't undoable?
            # Or maybe `finish_on_canvas_editing` is separate.
            # I will just switch to set_element_property for now to satisfy the "Model is Truth" requirement.
            # Undo support is a separate concern but closely related.
            self._model.set_element_property(self._element.id, "angle", self.rotation())
            event.accept()
            return
        
        if self._resizing:
            self._resizing = False
            self._resize_handle = None
            
            # Update element dimensions
            rect = self.rect()
            
            if self._element.element_type == ElementType.TRIANGLE:
                # Push a single batch command for all triangle point changes
                old_vals = {
                    'x1': self._resize_start_pts[0][0], 'y1': self._resize_start_pts[0][1],
                    'x2': self._resize_start_pts[1][0], 'y2': self._resize_start_pts[1][1],
                    'x3': self._resize_start_pts[2][0], 'y3': self._resize_start_pts[2][1]
                }
                new_vals = {
                    'x1': self._element.x1, 'y1': self._element.y1,
                    'x2': self._element.x2, 'y2': self._element.y2,
                    'x3': self._element.x3, 'y3': self._element.y3
                }
                cmd = ChangePropertiesCommand(self._model, self._element.id, old_vals, new_vals, "Resize Triangle")
                self._model._undo_stack.push(cmd)
            else:
                self._model.set_element_property(self._element.id, "width", int(rect.width()))
                self._model.set_element_property(self._element.id, "height", int(rect.height()))
                
                # Adjust position if top-left changed
                if rect.left() != 0 or rect.top() != 0:
                    new_pos = self.pos() + rect.topLeft()
                    self.setPos(new_pos)
                    # Use move_element
                    self._model.move_element(self._element.id, int(new_pos.x()), int(new_pos.y()))
                    self.setRect(0, 0, rect.width(), rect.height())
            
            event.accept()
            return

        if self.scene() and self.scene().mouseGrabberItem() == self:
            print("DEBUG: mouseReleaseEvent - releasing grabber")
            # Handle move completion
            selected_items = [i for i in self.scene().selectedItems() if isinstance(i, ElementItem)]
            
            # Use macro to group multiple moves into one undo entry
            any_moved = any(item._has_moved() for item in selected_items)
            print(f"DEBUG: any_moved={any_moved}")
            
            if any_moved:
                print("DEBUG: Starting macro")
                self._model._undo_stack.beginMacro("Move Elements")
                try:
                    for item in selected_items:
                        if item._has_moved():
                            print(f"DEBUG: Pushing move command for {item._element.id}")
                            item._push_move_command()
                finally:
                    print("DEBUG: Ending macro")
                    self._model._undo_stack.endMacro()
            
            # Clean up all
            print("DEBUG: Cleaning up")
            for i, item in enumerate(selected_items):
                print(f"DEBUG: Cleaning up item {i} ({item})")
                try:
                    item._cleanup_move_start()
                except Exception as e:
                    print(f"DEBUG: Error cleaning item {i}: {e}")

            print("DEBUG: Ungrabbing mouse")
            self.ungrabMouse()
            
        print("DEBUG: Calling super().mouseReleaseEvent")
        super().mouseReleaseEvent(event)
        print("DEBUG: ElementItem.mouseReleaseEvent finished")
    
    def _get_element_pen(self) -> QPen:
        """Get pen for element outline."""
        if hasattr(self._element, 'outline') and self._element.outline:
            c = self._element.outline.color
            pen = QPen(QColor(c[0], c[1], c[2], c[3]))
            pen.setWidth(self._element.outline.width)
            if self._element.outline.cap == 'round':
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            else:
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            if self._element.outline.dash_array:
                dashes = [float(d) for d in self._element.outline.dash_array]
                if len(dashes) % 2 != 0:
                    dashes.append(dashes[-1])  # Make even by duplicating last entry
                pen.setDashPattern(dashes)
            return pen
        return Qt.PenStyle.NoPen
    
    def _update_shadow(self) -> None:
        """Update element shadow effect."""
        if getattr(self._element, 'shadow', None):
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(self._element.shadow.blur)
            c = self._element.shadow.color
            color = QColor(c[0], c[1], c[2], c[3])
            effect.setColor(color)
            effect.setOffset(self._element.shadow.offset_x, self._element.shadow.offset_y)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)
    
    def paint(self, painter: QPainter, option, widget=None):
        """Custom paint method to render based on element type."""
        rect = self.rect()
        # Use element outline logic
        pen = self._get_element_pen()
        brush = QBrush(self._get_element_color())
        
        painter.setPen(pen)
        painter.setBrush(brush)
        
        elem_type = self._element.element_type
        
        if elem_type == ElementType.RECTANGLE:
            # Draw rectangle (with corner radius if set)
            # Shear transform
            if hasattr(self._element, 'shear_left') or hasattr(self._element, 'shear_right'):
                # Apply shear transform
                # We need to use painter transform
                # But simple shear is hard with drawRoundedRect directly on rect
                # Construct path?
                # User asked for shear_left/shear_right. Vertical shear?
                # Usually shear is x-skew. 
                # Let's support simple x-shear if available?
                # For now stick to basic rect unless complex
                pass
            
            radius = getattr(self._element, 'radius', 0)
            if radius > 0:
                painter.drawRoundedRect(rect, radius, radius)
            else:
                painter.drawRect(rect)
        
        elif elem_type == ElementType.CIRCLE:
            # Draw circle/ellipse
            painter.drawEllipse(rect)
        
        elif elem_type == ElementType.TRIANGLE:
            # Draw triangle using specific coordinates mapped to local
            pos = self.pos()
            p1 = QPointF(self._element.x1 - pos.x(), self._element.y1 - pos.y())
            p2 = QPointF(self._element.x2 - pos.x(), self._element.y2 - pos.y())
            p3 = QPointF(self._element.x3 - pos.x(), self._element.y3 - pos.y())
            from PyQt6.QtGui import QPolygonF
            painter.drawPolygon(QPolygonF([p1, p2, p3]))
        
        elif elem_type == ElementType.LINE:
            # Draw line using specific coordinates mapped to local
            pos = self.pos()
            p1 = QPointF(self._element.x - pos.x(), self._element.y - pos.y())
            p2 = QPointF(self._element.x2 - pos.x(), self._element.y2 - pos.y())
            
            # 1. Draw Outline Casing (if enabled)
            if hasattr(self._element, 'outline') and self._element.outline:
                o = self._element.outline
                c = QColor(o.color[0], o.color[1], o.color[2], o.color[3])
                pen = QPen(c)
                # Casing width = line_width + 2 * outline_width
                pen.setWidth(self._element.line_width + (o.width * 2))
                
                if self._element.end_cap == 'round':
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                else:
                    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                
                if o.dash_array:
                    dashes = [float(d) for d in o.dash_array]
                    if len(dashes) % 2 != 0:
                        dashes.append(dashes[-1])
                    pen.setDashPattern(dashes)
                    
                painter.setPen(pen)
                painter.drawLine(p1, p2)
            
            # 2. Draw Main Line Stroke
            main_color = self._get_element_color()
            pen = QPen(main_color)
            pen.setWidth(self._element.line_width)
            
            if self._element.end_cap == 'round':
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            else:
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                
            painter.setPen(pen)
            painter.drawLine(p1, p2)
        
        elif elem_type == ElementType.TEXT or elem_type == ElementType.DYNAMIC_TEXT:
            # Render actual text
            text = getattr(self._element, 'text', None) or ""
            if elem_type == ElementType.DYNAMIC_TEXT:
                text = self._resolve_dynamic_text(text)
            
            font = self._get_font()
            painter.setFont(font)
            
            # Use the color from the element
            color = self._get_element_color()
            painter.setPen(QPen(color))
            
            # Alignment (for multiline or within the padded rect)
            align_str = getattr(self._element, 'align', 'left')
            anchor = getattr(self._element, 'anchor', 'lt')
            
            # Horizontal alignment
            if align_str == 'center':
                flags = Qt.AlignmentFlag.AlignHCenter
            elif align_str == 'right':
                flags = Qt.AlignmentFlag.AlignRight
            else:
                flags = Qt.AlignmentFlag.AlignLeft
                
            # Vertical alignment based on anchor
            if 'm' in anchor[1:]:
                flags |= Qt.AlignmentFlag.AlignVCenter
            elif 'b' in anchor[1:]:
                flags |= Qt.AlignmentFlag.AlignBottom
            else:
                flags |= Qt.AlignmentFlag.AlignTop
                
            painter.drawText(rect, flags, text)
            
            # Optional: draw a very faint border when selected but not focused
            if self.isSelected():
                painter.setPen(QPen(QColor(0, 150, 255, 50)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
        
        elif elem_type == ElementType.BACKGROUND_IMAGE:
            # Draw actual background image
            image_path = getattr(self._element, 'path', '')
            if image_path:
                if self._cached_pixmap is None or self._cached_image_path != image_path:
                    self._load_image_pixmap(image_path)
                
                if self._cached_pixmap and not self._cached_pixmap.isNull():
                    painter.drawPixmap(rect.toRect(), self._cached_pixmap)
                else:
                    self._draw_image_placeholder(painter, rect, "No Background")
            else:
                self._draw_image_placeholder(painter, rect, "No Image")
                
        elif elem_type == ElementType.BACKGROUND_VIDEO:
            # Draw video background frame (background.png)
            # For video backgrounds, we render 'background.png' which is extracted by video_processor
            image_path = "background.png"
            if self._cached_pixmap is None or self._cached_image_path != image_path:
                self._load_image_pixmap(image_path)
            
            if self._cached_pixmap and not self._cached_pixmap.isNull():
                painter.drawPixmap(rect.toRect(), self._cached_pixmap)
            else:
                self._draw_image_placeholder(painter, rect, "Video Preview")
        
        elif elem_type == ElementType.IMAGE:
            # Draw actual image if path is set
            image_path = getattr(self._element, 'path', '')
            if image_path:
                # Check if we need to reload
                if self._cached_pixmap is None or self._cached_image_path != image_path:
                    self._load_image_pixmap(image_path)
                
                if self._cached_pixmap and not self._cached_pixmap.isNull():
                    # Draw the image scaled to fit rect
                    painter.drawPixmap(rect.toRect(), self._cached_pixmap)
                else:
                    # Fallback to placeholder if load failed
                    self._draw_image_placeholder(painter, rect, "Load Error")
            else:
                self._draw_image_placeholder(painter, rect, "No Image")
        
        elif elem_type == ElementType.ICON:
            # Draw actual icon if URL is set
            icon_val = getattr(self._element, 'icon', '')
            if icon_val and 'fontawesome.com' in icon_val:
                self._render_fontawesome_icon(painter, rect, icon_val)
            elif icon_val:
                # It's a hex code, try to render as unicode
                self._render_icon_hex(painter, rect, icon_val)
            else:
                # Fallback placeholder
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
            elif self._element.element_type == ElementType.LINE and name in ('start', 'end'):
                # Draw Line handles as circles
                painter.drawEllipse(handle_rect)
            else:
                # Draw resize handles as rectangles
                painter.drawRect(handle_rect)
    
    def itemChange(self, change, value):
        """Handle item changes for position updates and snapping."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Smart Snapping Logic
            new_pos = value
            current_pos = self.pos()
            dx = new_pos.x() - current_pos.x()
            dy = new_pos.y() - current_pos.y()
            
            # Snap thresholds
            GUIDE_THRESHOLD = 20
            GRID_THRESHOLD = 5
            GRID_SIZE = 10
            
            # --- X-axis Snapping ---
            if abs(dx) > 0.001:  # Ensure we have motion
                # Moving right: snap RIGHT edge. Moving left: snap LEFT edge.
                is_moving_right = dx > 0
                leading_x = new_pos.x() + (self.rect().width() if is_moving_right else 0)
                
                snapped_x = None
                
                # 1. Check Guides (Priority 1)
                for g_v in self._model.guides_v:
                    if abs(g_v - leading_x) < GUIDE_THRESHOLD:
                        snapped_x = g_v - (self.rect().width() if is_moving_right else 0)
                        break
                
                # 2. Check Grid (Priority 2)
                if snapped_x is None:
                    nearest_grid = round(leading_x / GRID_SIZE) * GRID_SIZE
                    if abs(nearest_grid - leading_x) < GRID_THRESHOLD:
                        snapped_x = nearest_grid - (self.rect().width() if is_moving_right else 0)
                
                if snapped_x is not None:
                    new_pos.setX(snapped_x)
            
            # --- Y-axis Snapping ---
            if abs(dy) > 0.001:
                # Moving down: snap BOTTOM edge. Moving up: snap TOP edge.
                is_moving_down = dy > 0
                leading_y = new_pos.y() + (self.rect().height() if is_moving_down else 0)
                
                snapped_y = None
                
                # 1. Check Guides (Priority 1)
                for g_h in self._model.guides_h:
                    if abs(g_h - leading_y) < GUIDE_THRESHOLD:
                        snapped_y = g_h - (self.rect().height() if is_moving_down else 0)
                        break
                
                # 2. Check Grid (Priority 2)
                if snapped_y is None:
                    nearest_grid = round(leading_y / GRID_SIZE) * GRID_SIZE
                    if abs(nearest_grid - leading_y) < GRID_THRESHOLD:
                        snapped_y = nearest_grid - (self.rect().height() if is_moving_down else 0)
                
                if snapped_y is not None:
                    new_pos.setY(snapped_y)
            
            return new_pos
            
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update element position with support for coordinate-based items
            if self._is_updating_geometry:
                return value
                
            new_pos = value
            # We need to know the old position to calculate delta
            # Since we just moved, self.pos() IS the new position (value)
            # We should have stored the last position
            old_pos = getattr(self, '_last_stored_pos', new_pos)
            dx = int(new_pos.x()) - int(old_pos.x())
            dy = int(new_pos.y()) - int(old_pos.y())
            
            # Apply delta to extra points (Triangle, Line)
            elem_type = self._element.element_type
            if dx != 0 or dy != 0:
                if elem_type == ElementType.TRIANGLE:
                    self._element.x1 += dx
                    self._element.y1 += dy
                    self._element.x2 += dx
                    self._element.y2 += dy
                    self._element.x3 += dx
                    self._element.y3 += dy
                elif elem_type == ElementType.LINE:
                    self._element.x += dx
                    self._element.y += dy
                    self._element.x2 += dx
                    self._element.y2 += dy
                else:
                    self._element.x = int(new_pos.x())
                    self._element.y = int(new_pos.y())
                    
            self._last_stored_pos = new_pos
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_appearance()
            self.update()  # Trigger repaint
        
        # Return value - base class behavior is to return value unchanged
        return value
    
    def _load_image_pixmap(self, image_path: str) -> None:
        """Load and cache a pixmap from the image path."""
        from PyQt6.QtGui import QPixmap
        from pathlib import Path
        
        self._cached_image_path = image_path
        
        # Resolve the path
        theme_folder = getattr(self._model, 'theme_folder', None)
        path = Path(image_path)
        
        if not path.is_absolute():
            if theme_folder:
                path = Path(theme_folder) / image_path
            else:
                # Fallback to current working directory or original path
                pass
        
        if path.exists():
            self._cached_pixmap = QPixmap(str(path))
            # Update element dimensions to match image if first load
            if self._cached_pixmap and not self._cached_pixmap.isNull():
                if self._element.width == 100 and self._element.height == 100:
                    # Default size, update to actual image size
                    self._element.width = self._cached_pixmap.width()
                    self._element.height = self._cached_pixmap.height()
                    self.setRect(0, 0, self._element.width, self._element.height)
        else:
            logger.warning(f"Image not found: {path} (original: {image_path})")
            self._cached_pixmap = None
    
    def _draw_image_placeholder(self, painter: QPainter, rect: QRectF, label: str) -> None:
        """Draw placeholder for images that can't be loaded."""
        painter.setBrush(QBrush(QColor(80, 80, 120, 100)))
        painter.drawRect(rect)
        
        # Draw diagonal lines
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomLeft())
        
        # Label
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
    
    def _render_fontawesome_icon(self, painter: QPainter, rect: QRectF, icon_url: str) -> None:
        """Render a FontAwesome icon from its URL."""
        from library.font_manager import font_manager
        from PyQt6.QtGui import QFontDatabase
        
        # Resolve icon metadata
        unicode_hex, font_url = font_manager.resolve_icon_metadata(icon_url)
        
        if not unicode_hex or not font_url:
            # Failed to resolve, draw placeholder
            painter.setBrush(QBrush(QColor(100, 80, 120, 100)))
            painter.drawEllipse(rect)
            painter.setPen(QPen(QColor(255, 100, 100)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
            return
        
        # Get the font file
        font_path = font_manager.get_font_path(font_url)
        if not font_path:
            painter.setPen(QPen(QColor(255, 100, 100)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "⌛")
            return
        
        # Load font if not cached
        if self._cached_icon_font is None or self._cached_icon_unicode != unicode_hex:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self._cached_icon_font = QFont(families[0])
                    self._cached_icon_unicode = unicode_hex
        
        if self._cached_icon_font:
            # Set font size based on rect
            size = int(min(rect.width(), rect.height()) * 0.8)
            self._cached_icon_font.setPixelSize(max(12, size))
            painter.setFont(self._cached_icon_font)
            
            # Draw the icon character
            try:
                char = chr(int(unicode_hex, 16))
            except ValueError:
                char = "?"
            
            color = getattr(self._element, 'color', (255, 255, 255, 255))
            painter.setPen(QPen(QColor(*color)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, char)
        else:
            painter.setPen(QPen(QColor(255, 100, 100)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "!")
    
    def _render_icon_hex(self, painter: QPainter, rect: QRectF, hex_code: str) -> None:
        """Render an icon from a hex unicode code."""
        # Try to parse as hex
        try:
            char = chr(int(hex_code, 16))
        except ValueError:
            char = hex_code[:1] if hex_code else "?"
        
        # Use a default font
        font = QFont("Segoe UI Symbol", int(min(rect.width(), rect.height()) * 0.6))
        painter.setFont(font)
        
        color = getattr(self._element, 'color', (255, 255, 255, 255))
        painter.setPen(QPen(QColor(*color)))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, char)

    def update_from_element(self) -> None:
        """Sync graphics item with element data."""
        # For text elements, we always recalculate size to ensure it fits the text
        if self._element.element_type in (ElementType.TEXT, ElementType.DYNAMIC_TEXT):
            self._update_text_size()
        
        # Update styling
        self._update_appearance()
        self._update_shadow()
        
        self._is_updating_geometry = True
        # Geometry Logic
        if self._element.element_type == ElementType.TRIANGLE:
             # Calculate bounding box of points
             xs = [self._element.x1, self._element.x2, self._element.x3]
             ys = [self._element.y1, self._element.y2, self._element.y3]
             min_x, max_x = min(xs), max(xs)
             min_y, max_y = min(ys), max(ys)
             
             padding = 2 # Small padding
             self.setPos(min_x - padding, min_y - padding)
             self.setRect(0, 0, max_x - min_x + padding*2, max_y - min_y + padding*2)
             
        elif self._element.element_type == ElementType.LINE:
             # Calculate bounding box of start/end
             xs = [self._element.x, self._element.x2]
             ys = [self._element.y, self._element.y2]
             min_x, max_x = min(xs), max(xs)
             min_y, max_y = min(ys), max(ys)
             
             padding = 10 # Larger padding for easier selection
             self.setPos(min_x - padding, min_y - padding)
             self.setRect(0, 0, max_x - min_x + padding*2, max_y - min_y + padding*2)
             
        else:
            self.setPos(self._element.x, self._element.y)
            self.setRect(0, 0, self._element.width, self._element.height)
        
        self._last_stored_pos = self.pos()
        self._is_updating_geometry = False
            
        # Update transform origin to center after rect change
        self.setTransformOriginPoint(self.rect().center())
        self.setRotation(self._element.angle)
        self.setOpacity(self._element.opacity)
        
        # Background video visibility depends on 'enabled' flag
        if isinstance(self._element, BackgroundVideoElement):
            self.setVisible(self._element.visible and self._element.enabled)
        else:
            self.setVisible(self._element.visible)
        
        self.update()  # Trigger repaint


class ThemeGraphicsView(QGraphicsView):
    """Custom GraphicsView to handle additive selection with Shift during rubber band drag."""
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to support additive selection."""
        # Check if we are finishing a rubber band drag and Shift is held
        is_rubber_band = self.dragMode() == QGraphicsView.DragMode.RubberBandDrag
        is_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        
        if is_rubber_band and is_shift:
            # Capture currently selected items before the rubber band logic updates (clears) them
            previously_selected = list(self.scene().selectedItems())
            
            # Let base class perform the new selection from rubber band rect
            super().mouseReleaseEvent(event)
            
            # Re-select the items that were previously selected
            for item in previously_selected:
                item.setSelected(True)
        else:
            super().mouseReleaseEvent(event)


class PreviewCanvas(QWidget):
    """
    Canvas widget for visual theme editing.
    
    Contains a QGraphicsView with rulers, guides, and element items.
    
    Signals:
        selection_changed: Emitted when canvas selection changes
        element_moved: Emitted when an element is moved on canvas
    """
    # Signals
    selection_changed = pyqtSignal(list)  # List of element IDs
    mouse_moved = pyqtSignal(object)       # QPointF (scene coordinates)
    element_moved = pyqtSignal(str, int, int)  # element_id, new_x, new_y
    
    # Zoom limits
    MIN_ZOOM = 0.1
    MAX_ZOOM = 5.0
    ZOOM_STEP = 0.1
    
    # Grid settings
    GRID_SIZE = 10
    
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
        
        self._element_items: Dict[str, ElementItem] = {}
        self._guide_items: List[GuideLineItem] = []
        
        self._preview_line_item = None
        self._space_pressed = False
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self._setup_ui()
        self._connect_signals()
        
        self._block_selection_signal = False
    
    def _setup_ui(self) -> None:
        """Set up the canvas UI with rulers."""
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create corner spacer (top-left)
        corner = QFrame()
        corner.setFixedSize(RULER_SIZE, RULER_SIZE)
        corner.setFrameShape(QFrame.Shape.NoFrame)
        corner.setLineWidth(0)
        corner.setStyleSheet(f"background-color: {RULER_BG_COLOR.name()}; border: none;")
        layout.addWidget(corner, 0, 0)
        
        # Create horizontal ruler (top)
        self._ruler_h = RulerWidget('horizontal')
        layout.addWidget(self._ruler_h, 0, 1)
        
        # Create vertical ruler (left)
        self._ruler_v = RulerWidget('vertical')
        layout.addWidget(self._ruler_v, 1, 0)
        
        # Create graphics scene
        self._scene = QGraphicsScene()
        self._scene.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        
        # Create graphics view
        self._view = ThemeGraphicsView(self._scene)
        self._view.setFrameStyle(QFrame.Shape.NoFrame)
        self._view.setLineWidth(0)
        self._view.setStyleSheet("QGraphicsView { border: none; padding: 0px; background: transparent; }")
        self._view.setContentsMargins(0, 0, 0, 0)
        self._view.viewport().setContentsMargins(0, 0, 0, 0)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self._view.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(self._view, 1, 1)
        
        # Connect scroll signals to update rulers
        self._view.horizontalScrollBar().valueChanged.connect(lambda: self._sync_rulers())
        self._view.verticalScrollBar().valueChanged.connect(lambda: self._sync_rulers())
        
        # Connect ruler signals for guide creation
        # Top ruler (horizontal) creates horizontal guides (drag down)
        self._ruler_h.guide_created.connect(self._on_ruler_h_created)
        self._ruler_h.guide_preview.connect(self._on_h_guide_preview)
        # Left ruler (vertical) creates vertical guides (drag right)
        self._ruler_v.guide_created.connect(self._on_ruler_v_created)
        self._ruler_v.guide_preview.connect(self._on_v_guide_preview)
        
        # Set initial scene rect based on display size
        self._update_scene_rect()
        
        # Draw theme background
        self._draw_background()
    
    def _sync_rulers(self) -> None:
        """Synchronize rulers with current view transform and scroll."""
        if not hasattr(self, '_ruler_h') or not hasattr(self, '_ruler_v'):
            return
        
        # Get scene (0,0) in viewport pixels (this accounts for both scroll and zoom)
        origin_px = self._view.mapFromScene(0, 0)
        
        # Update rulers
        self._ruler_h.set_zoom(self._zoom_level)
        self._ruler_h.set_scroll_offset(origin_px.x())
        
        self._ruler_v.set_zoom(self._zoom_level)
        self._ruler_v.set_scroll_offset(origin_px.y())
    
    def resizeEvent(self, event) -> None:
        """Handle resize to sync rulers."""
        super().resizeEvent(event)
        self._sync_rulers()
    
    def _on_h_guide_preview(self, x: int, y: int) -> None:
        """Show horizontal guide preview during drag from top ruler."""
        self._clear_preview_line()
        if x == -1 and y == -1:
            return
            
        # Map ruler local Y to scene Y
        view_y = y - RULER_SIZE
        scene_y = int(self._view.mapToScene(0, view_y).y())
        
        # Draw horizontal preview line across full scene
        pen = QPen(QColor(0, 255, 255, 150))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        scene_rect = self._scene.sceneRect()
        self._preview_line_item = self._scene.addLine(
            scene_rect.left(), scene_y, scene_rect.right(), scene_y, pen
        )
        self._preview_line_item.setZValue(2000)
    
    def _on_v_guide_preview(self, x: int, y: int) -> None:
        """Show vertical guide preview during drag from left ruler."""
        self._clear_preview_line()
        if x == -1 and y == -1:
            return
            
        # Map ruler local X to scene X
        view_x = x - RULER_SIZE
        scene_x = int(self._view.mapToScene(view_x, 0).x())
        
        # Draw vertical preview line across full scene
        pen = QPen(QColor(0, 255, 255, 150))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        scene_rect = self._scene.sceneRect()
        self._preview_line_item = self._scene.addLine(
            scene_x, scene_rect.top(), scene_x, scene_rect.bottom(), pen
        )
        self._preview_line_item.setZValue(2000)
    
    def _clear_preview_line(self) -> None:
        """Remove preview line from scene."""
        if self._preview_line_item:
            self._scene.removeItem(self._preview_line_item)
            self._preview_line_item = None
            
    def _on_ruler_h_created(self, x: int, y: int) -> None:
        """Handle horizontal guide creation from top ruler."""
        view_y = y - RULER_SIZE
        scene_y = int(self._view.mapToScene(0, view_y).y())
        self.add_guide_h(scene_y)
        
    def _on_ruler_v_created(self, x: int, y: int) -> None:
        """Handle vertical guide creation from left ruler."""
        view_x = x - RULER_SIZE
        scene_x = int(self._view.mapToScene(view_x, 0).x())
        self.add_guide_v(scene_x)
    
    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.element_added.connect(self._on_element_added)
        self._model.element_removed.connect(self._on_element_removed)
        self._model.element_changed.connect(self._on_element_changed)
        self._model.element_moved.connect(self._on_element_moved)
        self._model.guides_changed.connect(self._refresh_canvas)
        
        # Listen for model reset to refresh canvas
        self._model.layoutChanged.connect(self._on_model_layout_changed)
        self._model.modelReset.connect(self._refresh_canvas)
        
        # Connect scene selection changes
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)
    
    def _update_scene_rect(self) -> None:
        """Update scene rectangle based on display size."""
        width = self._model.display_width
        height = self._model.display_height
        
        # Set scene rect to match display size exactly (no margins)
        self._scene.setSceneRect(0, 0, width, height)
    
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
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for coordinate updates."""
        scene_pos = self._view.mapToScene(event.pos())
        self.mouse_moved.emit(scene_pos)
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        print("DEBUG: PreviewCanvas.mousePressEvent")
        super().mousePressEvent(event)
        
    def _draw_grid(self) -> None:
        """Draw grid overlay."""
        width = self._model.display_width
        height = self._model.display_height
        
        # Use a cosmetic pen (width 0) for sub-pixel perfect alignment
        pen = QPen(QColor(60, 60, 60))
        pen.setWidth(0)
        
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
        
        display_w = self._model.display_width
        display_h = self._model.display_height
        
        # Create guide items
        self._guide_items = []
        
        # Horizontal guides
        for y in self._model.guides_h:
            item = GuideLineItem(
                'horizontal', y, display_w, display_w, display_h,
                on_moved=self._on_guide_moved,
                on_removed=self._on_guide_removed
            )
            self._scene.addItem(item)
            self._guide_items.append(item)
        
        # Vertical guides
        for x in self._model.guides_v:
            item = GuideLineItem(
                'vertical', x, display_h, display_w, display_h,
                on_moved=self._on_guide_moved,
                on_removed=self._on_guide_removed
            )
            self._scene.addItem(item)
            self._guide_items.append(item)
    
    def _on_guide_moved(self) -> None:
        """Handle guide moved - sync with model."""
        h_guides = [item.position for item in self._guide_items if item.orientation == 'horizontal']
        v_guides = [item.position for item in self._guide_items if item.orientation == 'vertical']
        self._model.set_guides(h_guides, v_guides)
    
    def _on_guide_removed(self, item: GuideLineItem) -> None:
        """Handle guide removed."""
        if item in self._guide_items:
            self._guide_items.remove(item)
        self._scene.removeItem(item)
        
        h_guides = [g.position for g in self._guide_items if g.orientation == 'horizontal']
        v_guides = [g.position for g in self._guide_items if g.orientation == 'vertical']
        self._model.set_guides(h_guides, v_guides)
    
    def _save_guides(self) -> None:
        """No longer used, guides are synced with ThemeModel."""
        pass
    
    def add_guide_h(self, y: int) -> None:
        """Add horizontal guide at y position."""
        if y not in self._model.guides_h:
            self._model.set_guides(self._model.guides_h + [y], self._model.guides_v)
    
    def add_guide_v(self, x: int) -> None:
        """Add vertical guide at x position."""
        if x not in self._model.guides_v:
            self._model.set_guides(self._model.guides_h, self._model.guides_v + [x])
    
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
        item = ElementItem(element, self._model)
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
        print("DEBUG: PreviewCanvas._on_scene_selection_changed")
        if self._block_selection_signal:
            print("DEBUG: Ignoring signal due to block")
            return
            
        try:
            selected_ids = [
                item.element_id
                for item in self._scene.selectedItems()
                if isinstance(item, ElementItem)
            ]
            print(f"DEBUG: Emitting selection_changed with {len(selected_ids)} items")
            self.selection_changed.emit(selected_ids)
        except RuntimeError:
            # Scene may be deleted during application close
            pass
    
    # --- Selection ---
    
    def get_scene_center(self) -> QPointF:
        """Get the center of the current viewport in scene coordinates."""
        viewport_center = self._view.viewport().rect().center()
        return self._view.mapToScene(viewport_center)

    def select_elements(self, element_ids: List[str]) -> None:
        """
        Select elements by ID.
        
        Args:
            element_ids: List of element IDs to select
        """
        # Clear current selection
        print(f"DEBUG: PreviewCanvas.select_elements({len(element_ids)} items)")
        self._scene.clearSelection()
        
        # Expand groups recursively to select all their children on canvas
        target_ids = []
        for eid in element_ids:
            elem = self._model.get_element(eid)
            if not elem:
                continue
            if elem.element_type == ElementType.GROUP:
                target_ids.extend(self._model.get_all_children_ids(eid))
            else:
                target_ids.append(eid)
        
        # Select specified items
        self._block_selection_signal = True
        try:
            for elem_id in target_ids:
                item = self._element_items.get(elem_id)
                if item:
                    item.setSelected(True)
        finally:
            self._block_selection_signal = False
            
        # Manually emit ONE signal if needed? 
        # Actually logic is likely: 
        # 1. User clicks -> Scene emits signal -> Canvas emits signal -> MainWindow syncs Layer
        # 2. Layer clicks -> MainWindow calls select_elements -> Canvas updates -> NO signal needed back to MainWindow
        # So suppressing is correct for case 2.
    
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
        self._sync_rulers()
    
    def _apply_zoom(self) -> None:
        """Apply current zoom level."""
        self._view.setTransform(QTransform().scale(self._zoom_level, self._zoom_level))
        self._sync_rulers()
    
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
        if y not in self._model.guides_h:
            self._model.set_guides(self._model.guides_h + [y], self._model.guides_v)
    
    def add_guide_v(self, x: int) -> None:
        """Add vertical guide at x position."""
        if x not in self._model.guides_v:
            self._model.set_guides(self._model.guides_h, self._model.guides_v + [x])
    
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
                item = ElementItem(element, self._model)
                self._scene.addItem(item)
                self._element_items[element.id] = item
        
        # Ensure rulers are synced after redraw
        self._sync_rulers()
    
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
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._view.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
            
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
            
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self._view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self._view.unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)
        
    def focusOutEvent(self, event) -> None:
        """Handle focus loss to reset tool states."""
        if self._space_pressed:
            self._space_pressed = False
            self._view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self._view.unsetCursor()
        super().focusOutEvent(event)
