# SPDX-License-Identifier: GPL-3.0-or-later
import math
from typing import List, Tuple, Optional
from PyQt6.QtCore import QPointF, QRectF

def calculate_rotation(
    center: QPointF, 
    start_pos: QPointF, 
    current_pos: QPointF, 
    start_angle: float, 
    snap: bool = False,
    snap_increment: float = 15.0
) -> float:
    """Calculate new rotation angle based on mouse movement."""
    start_vec = start_pos - center
    curr_vec = current_pos - center
    
    start_rad = math.atan2(start_vec.y(), start_vec.x())
    curr_rad = math.atan2(curr_vec.y(), curr_vec.x())
    
    delta_degrees = math.degrees(curr_rad - start_rad)
    new_rotation = start_angle + delta_degrees
    
    if snap:
        new_rotation = round(new_rotation / snap_increment) * snap_increment
        
    return new_rotation

def get_anchor_point(rect: QRectF, handle: str) -> Tuple[float, float]:
    """Get the anchor point (opposite of handle) for scaling."""
    if handle == 'tl': return rect.right(), rect.bottom()
    if handle == 'tr': return rect.left(), rect.bottom()
    if handle == 'bl': return rect.right(), rect.top()
    if handle == 'br': return rect.left(), rect.top()
    if handle == 't': return 0, rect.bottom()
    if handle == 'b': return 0, rect.top()
    if handle == 'l': return rect.right(), 0
    if handle == 'r': return rect.left(), 0
    return rect.center().x(), rect.center().y()

def scale_point(point: Tuple[float, float], anchor: Tuple[float, float], scale_x: float, scale_y: float) -> Tuple[int, int]:
    """Scale a point relative to an anchor."""
    x, y = point
    ax, ay = anchor
    new_x = int(ax + (x - ax) * scale_x)
    new_y = int(ay + (y - ay) * scale_y)
    return new_x, new_y

def snap_angle(angle_deg: float, increment: float = 15.0) -> float:
    """Snap angle to nearest increment."""
    return round(angle_deg / increment) * increment

def calculate_snapped_line_end(start_p: QPointF, end_p: QPointF, increment_deg: float = 5.0) -> Tuple[int, int]:
    """Calculate end point for a line snapped to angular increments."""
    diff = end_p - start_p
    dist = math.sqrt(diff.x()**2 + diff.y()**2)
    if dist < 0.1:
        return int(end_p.x()), int(end_p.y())
        
    angle_rad = math.atan2(diff.y(), diff.x())
    angle_deg = math.degrees(angle_rad)
    snapped_deg = round(angle_deg / increment_deg) * increment_deg
    snapped_rad = math.radians(snapped_deg)
    
    new_x = int(start_p.x() + dist * math.cos(snapped_rad))
    new_y = int(start_p.y() + dist * math.sin(snapped_rad))
    return new_x, new_y
