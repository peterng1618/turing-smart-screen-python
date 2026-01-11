# SPDX-License-Identifier: GPL-3.0-or-later
"""
Element classes for Theme Editor v2.

Defines the base Element class and all specific element types that can be
used in themes (shapes, text, images, icons, sensors).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
import uuid


class ElementType(Enum):
    """Types of elements that can be added to a theme."""
    # Container types
    GROUP = auto()
    BACKGROUND_IMAGE = auto()
    BACKGROUND_VIDEO = auto()
    
    # Shape types
    RECTANGLE = auto()
    CIRCLE = auto()
    ELLIPSE = auto()
    TRIANGLE = auto()
    LINE = auto()
    
    # Content types
    TEXT = auto()
    IMAGE = auto()
    ICON = auto()
    
    # Dynamic types (sensor-bound)
    DYNAMIC_TEXT = auto()
    GRAPH = auto()
    RADIAL = auto()
    LINE_GRAPH = auto()


@dataclass
class Shadow:
    """Shadow configuration for elements."""
    blur: int = 5
    color: Tuple[int, int, int, int] = (0, 0, 0, 128)
    offset_x: int = 3
    offset_y: int = 3


@dataclass
class Outline:
    """Outline configuration for elements."""
    width: int = 1
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    dash_array: Optional[List[int]] = None
    cap: str = "butt"  # "butt" or "round"


@dataclass
class Element:
    """
    Base class for all theme elements.
    
    Every element has common properties like position, visibility, and
    optional styling (shadow, opacity, rotation).
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    element_type: ElementType = ElementType.RECTANGLE
    
    # Hierarchy
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    
    # Position and size
    x: int = 0
    y: int = 0
    width: int = 100
    height: int = 100
    
    # Common styling
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    angle: float = 0.0
    shadow: Optional[Shadow] = None
    
    # Z-order (lower = further back)
    z_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert element to dictionary for serialization."""
        data = {
            "type": self.element_type.name.lower(),
            "x": self.x,
            "y": self.y,
        }
        
        # Add non-default values
        if self.name:
            data["name"] = self.name
        if self.width != 100:
            data["width"] = self.width
        if self.height != 100:
            data["height"] = self.height
        if not self.visible:
            data["visible"] = False
        if self.opacity != 1.0:
            data["opacity"] = self.opacity
        if self.angle != 0.0:
            data["angle"] = self.angle
        if self.shadow:
            data["shadow"] = {
                "blur": self.shadow.blur,
                "color": f"{self.shadow.color[0]}, {self.shadow.color[1]}, {self.shadow.color[2]}, {self.shadow.color[3]}",
                "offset_x": self.shadow.offset_x,
                "offset_y": self.shadow.offset_y,
            }
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], element_id: Optional[str] = None) -> "Element":
        """Create element from dictionary."""
        element = cls()
        element.id = element_id or str(uuid.uuid4())
        element.name = data.get("name", "")
        element.x = data.get("x", 0)
        element.y = data.get("y", 0)
        element.width = data.get("width", 100)
        element.height = data.get("height", 100)
        element.visible = data.get("visible", True)
        element.opacity = data.get("opacity", 1.0)
        element.angle = data.get("angle", 0.0)
        
        # Parse shadow
        if "shadow" in data:
            shadow_data = data["shadow"]
            color_str = shadow_data.get("color", "0, 0, 0, 128")
            color = tuple(int(c.strip()) for c in color_str.split(","))
            element.shadow = Shadow(
                blur=shadow_data.get("blur", 5),
                color=color,
                offset_x=shadow_data.get("offset_x", 3),
                offset_y=shadow_data.get("offset_y", 3),
            )
        
        return element


@dataclass
class RectangleElement(Element):
    """Rectangle shape element."""
    element_type: ElementType = field(default=ElementType.RECTANGLE, init=False)
    color: Tuple[int, int, int, int] = (255, 0, 0, 255)
    radius: int = 0
    shear_left: float = 0.0
    shear_right: float = 0.0
    outline: Optional[Outline] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        if self.radius > 0:
            data["radius"] = self.radius
        if self.shear_left != 0:
            data["shear_left"] = self.shear_left
        if self.shear_right != 0:
            data["shear_right"] = self.shear_right
        if self.outline:
            data["outline"] = {
                "width": self.outline.width,
                "color": f"{self.outline.color[0]}, {self.outline.color[1]}, {self.outline.color[2]}, {self.outline.color[3]}",
            }
            if self.outline.dash_array:
                data["outline"]["dash_array"] = self.outline.dash_array
            if self.outline.cap != "butt":
                data["outline"]["cap"] = self.outline.cap
        return data


@dataclass
class CircleElement(Element):
    """Circle shape element."""
    element_type: ElementType = field(default=ElementType.CIRCLE, init=False)
    radius: int = 50
    color: Tuple[int, int, int, int] = (0, 0, 255, 255)
    outline: Optional[Outline] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["radius"] = self.radius
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        # Remove width/height for circles (use radius instead)
        data.pop("width", None)
        data.pop("height", None)
        if self.outline:
            data["outline"] = {
                "width": self.outline.width,
                "color": f"{self.outline.color[0]}, {self.outline.color[1]}, {self.outline.color[2]}, {self.outline.color[3]}",
            }
        return data


@dataclass
class TriangleElement(Element):
    """Triangle shape element defined by three points."""
    element_type: ElementType = field(default=ElementType.TRIANGLE, init=False)
    x1: int = 0
    y1: int = 0
    x2: int = 100
    y2: int = 0
    x3: int = 50
    y3: int = 100
    radius: int = 0  # Corner radius
    color: Tuple[int, int, int, int] = (255, 165, 0, 255)
    outline: Optional[Outline] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["x1"] = self.x1
        data["y1"] = self.y1
        data["x2"] = self.x2
        data["y2"] = self.y2
        data["x3"] = self.x3
        data["y3"] = self.y3
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        if self.radius > 0:
            data["radius"] = self.radius
        # Remove standard x/y (use x1,y1 instead)
        data.pop("x", None)
        data.pop("y", None)
        data.pop("width", None)
        data.pop("height", None)
        return data


@dataclass
class LineElement(Element):
    """Line element between two points."""
    element_type: ElementType = field(default=ElementType.LINE, init=False)
    x2: int = 100
    y2: int = 0
    line_width: int = 2
    color: Tuple[int, int, int, int] = (0, 255, 0, 255)
    end_cap: str = "butt"  # "butt" or "round"
    outline: Optional[Outline] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["x2"] = self.x2
        data["y2"] = self.y2
        data["width"] = self.line_width
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        if self.end_cap != "butt":
            data["end_cap"] = self.end_cap
        return data


@dataclass
class TextElement(Element):
    """Static text element."""
    element_type: ElementType = field(default=ElementType.TEXT, init=False)
    text: str = "Text"
    font: str = "roboto/Roboto-Regular.ttf"
    font_size: int = 16
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    align: str = "left"  # "left", "center", "right"
    anchor: str = "lt"  # Pillow anchor
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["text"] = self.text
        data["font"] = self.font
        data["font_size"] = self.font_size
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        if self.align != "left":
            data["align"] = self.align
        if self.anchor != "lt":
            data["anchor"] = self.anchor
        return data


@dataclass
class ImageElement(Element):
    """Image element."""
    element_type: ElementType = field(default=ElementType.IMAGE, init=False)
    path: str = ""
    outline: Optional[Outline] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["path"] = self.path
        return data


@dataclass
class IconElement(Element):
    """Font Awesome icon element."""
    element_type: ElementType = field(default=ElementType.ICON, init=False)
    icon: str = "f015"  # Hex code or FontAwesome URL
    link: Optional[str] = None  # Direct font URL
    size: int = 24
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["icon"] = self.icon
        if self.link:
            data["link"] = self.link
        data["size"] = self.size
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        return data


@dataclass
class GroupElement(Element):
    """Group container element."""
    element_type: ElementType = field(default=ElementType.GROUP, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        # Groups are represented as a list of child elements
        return {
            "type": "group",
            "name": self.name,
            "children": self.children,
        }


@dataclass
class DynamicTextElement(Element):
    """Dynamic text element bound to sensor value(s)."""
    element_type: ElementType = field(default=ElementType.DYNAMIC_TEXT, init=False)
    text: str = "{CPU_PERCENTAGE:u}"  # Format string with {SENSOR_ID:flag}
    # legacy fields
    sensor_type: str = "CPU"
    sensor_metric: str = "PERCENTAGE"
    show_unit: bool = True
    font: str = "roboto-mono/RobotoMono-Bold.ttf"
    font_size: int = 16
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    align: str = "left"
    anchor: str = "lt"
    interval: float = 1.0
    force_static: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = "dynamic_text"
        data["text"] = self.text
        # For backward compatibility with older viewers, we can still provide 'sensor'
        # but the new implementation looks for 'text'
        data["sensor"] = f"{self.sensor_type}.{self.sensor_metric}"
        data["show_unit"] = self.show_unit
        data["font"] = self.font
        data["font_size"] = self.font_size
        data["color"] = f"{self.color[0]}, {self.color[1]}, {self.color[2]}, {self.color[3]}"
        data["align"] = self.align
        data["anchor"] = self.anchor
        data["interval"] = self.interval
        data["force_static"] = self.force_static
        return data


@dataclass
class GraphElement(Element):
    """Bar graph element bound to a sensor value."""
    element_type: ElementType = field(default=ElementType.GRAPH, init=False)
    sensor_type: str = "CPU"
    sensor_metric: str = "PERCENTAGE"
    min_value: float = 0
    max_value: float = 100
    bar_color: Tuple[int, int, int, int] = (0, 255, 0, 255)
    background_color: Tuple[int, int, int, int] = (50, 50, 50, 255)
    horizontal: bool = True
    interval: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = "graph"
        data["sensor"] = f"{self.sensor_type}.{self.sensor_metric}"
        data["min_value"] = self.min_value
        data["max_value"] = self.max_value
        data["bar_color"] = f"{self.bar_color[0]}, {self.bar_color[1]}, {self.bar_color[2]}, {self.bar_color[3]}"
        data["background_color"] = f"{self.background_color[0]}, {self.background_color[1]}, {self.background_color[2]}, {self.background_color[3]}"
        data["horizontal"] = self.horizontal
        data["interval"] = self.interval
        return data


@dataclass
class RadialElement(Element):
    """Radial gauge element bound to a sensor value."""
    element_type: ElementType = field(default=ElementType.RADIAL, init=False)
    sensor_type: str = "CPU"
    sensor_metric: str = "PERCENTAGE"
    radius: int = 50
    bar_width: int = 10
    angle_start: float = 120
    angle_end: float = 60
    min_value: float = 0
    max_value: float = 100
    bar_color: Tuple[int, int, int, int] = (0, 255, 0, 255)
    background_color: Tuple[int, int, int, int] = (50, 50, 50, 255)
    clockwise: bool = True
    interval: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = "radial"
        data["sensor"] = f"{self.sensor_type}.{self.sensor_metric}"
        data["radius"] = self.radius
        data["width"] = self.bar_width
        data["angle_start"] = self.angle_start
        data["angle_end"] = self.angle_end
        data["min_value"] = self.min_value
        data["max_value"] = self.max_value
        data["bar_color"] = f"{self.bar_color[0]}, {self.bar_color[1]}, {self.bar_color[2]}, {self.bar_color[3]}"
        data["clockwise"] = self.clockwise
        data["interval"] = self.interval
        # Remove width/height for radial (use radius instead)
        data.pop("width", None)
        data.pop("height", None)
        return data


@dataclass
class LineGraphElement(Element):
    """Line graph element showing sensor history."""
    element_type: ElementType = field(default=ElementType.LINE_GRAPH, init=False)
    sensor_type: str = "CPU"
    sensor_metric: str = "PERCENTAGE"
    min_value: float = 0
    max_value: float = 100
    history_size: int = 60
    line_color: Tuple[int, int, int, int] = (0, 255, 0, 255)
    background_color: Tuple[int, int, int, int] = (30, 30, 30, 200)
    line_width: int = 2
    fill: bool = False
    fill_color: Tuple[int, int, int, int] = (0, 255, 0, 100)
    interval: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = "line_graph"
        data["sensor"] = f"{self.sensor_type}.{self.sensor_metric}"
        data["min_value"] = self.min_value
        data["max_value"] = self.max_value
        data["history_size"] = self.history_size
        data["line_color"] = f"{self.line_color[0]}, {self.line_color[1]}, {self.line_color[2]}, {self.line_color[3]}"
        data["background_color"] = f"{self.background_color[0]}, {self.background_color[1]}, {self.background_color[2]}, {self.background_color[3]}"
        data["line_width"] = self.line_width
        data["fill"] = self.fill
        if self.fill:
            data["fill_color"] = f"{self.fill_color[0]}, {self.fill_color[1]}, {self.fill_color[2]}, {self.fill_color[3]}"
        data["interval"] = self.interval
        return data


@dataclass
class BackgroundImageElement(Element):
    """Background image element (always locked, non-selectable on canvas)."""
    element_type: ElementType = field(default=ElementType.BACKGROUND_IMAGE, init=False)
    path: str = "background.png"
    
    def __post_init__(self):
        # Always locked and visible
        self.locked = True
        self.visible = True
        if not self.name:
            self.name = "Background Image"
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "type": "background_image",
            "path": self.path,
        })
        return data
        return data


@dataclass
class BackgroundVideoElement(Element):
    """Background video element (always locked, non-selectable on canvas)."""
    element_type: ElementType = field(default=ElementType.BACKGROUND_VIDEO, init=False)
    enabled: bool = False
    source_path: str = ""  # Original video path
    # Video processing options
    start_offset: str = "00:00"  # mm:ss format
    duration: str = ""  # Empty = full video
    loop_fade_duration: float = 0.0  # Seconds for crossfade loop
    
    def __post_init__(self):
        # Always locked and visible
        self.locked = True
        self.visible = True
        if not self.name:
            self.name = "Background Video"
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "type": "background_video",
            "enabled": self.enabled,
            "source_path": self.source_path,
            "start_offset": self.start_offset,
            "loop_fade_duration": self.loop_fade_duration,
        })
        if self.duration:
            data["duration"] = self.duration
        return data


# Factory function to create elements from type
ELEMENT_CLASSES = {
    ElementType.RECTANGLE: RectangleElement,
    ElementType.CIRCLE: CircleElement,
    ElementType.TRIANGLE: TriangleElement,
    ElementType.LINE: LineElement,
    ElementType.TEXT: TextElement,
    ElementType.IMAGE: ImageElement,
    ElementType.ICON: IconElement,
    ElementType.GROUP: GroupElement,
    ElementType.DYNAMIC_TEXT: DynamicTextElement,
    ElementType.GRAPH: GraphElement,
    ElementType.RADIAL: RadialElement,
    ElementType.LINE_GRAPH: LineGraphElement,
    ElementType.BACKGROUND_IMAGE: BackgroundImageElement,
    ElementType.BACKGROUND_VIDEO: BackgroundVideoElement,
}


def create_element(element_type: ElementType, **kwargs) -> Element:
    """
    Factory function to create an element of the specified type.
    
    Args:
        element_type: Type of element to create
        **kwargs: Properties to set on the element
        
    Returns:
        New element instance
    """
    element_class = ELEMENT_CLASSES.get(element_type, Element)
    element = element_class()
    
    # Apply kwargs with type conversion
    for key, value in kwargs.items():
        if not hasattr(element, key):
            continue
            
        # Handle Shadow object conversion
        if key == "shadow" and isinstance(value, dict):
            color = value.get("color", "0, 0, 0, 128")
            parsed_color = (0, 0, 0, 128) # Default
            
            if isinstance(color, str):
                try:
                    parts = tuple(int(c.strip()) for c in color.split(","))
                    parsed_color = parts + (255,) if len(parts) == 3 else parts
                except ValueError:
                    pass
            elif isinstance(color, (list, tuple)):
                parsed_color = tuple(color)
                if len(parsed_color) == 3:
                    parsed_color = parsed_color + (255,)
                
            shadow = Shadow(
                blur=value.get("blur", 5),
                color=parsed_color,
                offset_x=value.get("offset_x", 3),
                offset_y=value.get("offset_y", 3),
            )
            setattr(element, key, shadow)
            continue
            
        # Handle Outline object conversion
        if key == "outline" and isinstance(value, dict):
            color = value.get("color", "255, 255, 255, 255")
            parsed_color = (255, 255, 255, 255) # Default
            
            if isinstance(color, str):
                try:
                    parts = tuple(int(c.strip()) for c in color.split(","))
                    parsed_color = parts + (255,) if len(parts) == 3 else parts
                except ValueError:
                    pass
            elif isinstance(color, (list, tuple)):
                parsed_color = tuple(color)
                if len(parsed_color) == 3:
                    parsed_color = parsed_color + (255,)
                
            outline = Outline(
                width=value.get("width", 1),
                color=parsed_color,
                dash_array=value.get("dash_array"),
                cap=value.get("cap", "butt"),
            )
            setattr(element, key, outline)
            continue
            
        # Handle color conversion (str/list -> tuple)
        if (key == "color" or key.endswith("_color")) and value is not None:
            if isinstance(value, str):
                try:
                    # Parse "R, G, B, A" string
                    value = tuple(int(c.strip()) for c in value.split(","))
                    if len(value) == 3:
                        value = value + (255,)
                except ValueError:
                    # Keep original value if parsing fails (e.g. invalid format)
                    pass
            elif isinstance(value, list):
                value = tuple(value)
        
        # General assignment
        setattr(element, key, value)
    
    # Auto-generate name if not provided
    if not element.name:
        element.name = f"{element_type.name.lower()}_{element.id[:8]}"
    
    return element
