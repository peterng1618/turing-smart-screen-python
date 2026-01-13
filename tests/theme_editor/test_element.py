# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for theme_editor.models.element module.
"""

import pytest
from theme_editor.models.element import (
    Element, ElementType, Shadow, Outline,
    RectangleElement, CircleElement, TextElement, DynamicTextElement,
    create_element
)


class TestElementType:
    """Tests for ElementType enum."""
    
    def test_all_types_defined(self):
        """Verify all expected element types exist."""
        expected = [
            'GROUP', 'BACKGROUND_IMAGE', 'BACKGROUND_VIDEO', 'RECTANGLE', 'CIRCLE', 'ELLIPSE',
            'TRIANGLE', 'LINE', 'TEXT', 'IMAGE', 'ICON',
            'DYNAMIC_TEXT', 'GRAPH', 'RADIAL', 'LINE_GRAPH'
        ]
        for name in expected:
            assert hasattr(ElementType, name), f"Missing ElementType.{name}"


class TestShadow:
    """Tests for Shadow dataclass."""
    
    def test_default_values(self):
        """Test default shadow values."""
        shadow = Shadow()
        assert shadow.blur == 5
        assert shadow.color == (0, 0, 0, 128)
        assert shadow.offset_x == 3
        assert shadow.offset_y == 3
    
    def test_custom_values(self):
        """Test custom shadow values."""
        shadow = Shadow(blur=10, color=(255, 0, 0, 200), offset_x=5, offset_y=10)
        assert shadow.blur == 10
        assert shadow.color == (255, 0, 0, 200)
        assert shadow.offset_x == 5
        assert shadow.offset_y == 10


class TestOutline:
    """Tests for Outline dataclass."""
    
    def test_default_values(self):
        """Test default outline values."""
        outline = Outline()
        assert outline.width == 1
        assert outline.color == (255, 255, 255, 255)
        assert outline.dash_array is None
        assert outline.cap == "butt"
    
    def test_dashed_outline(self):
        """Test dashed outline configuration."""
        outline = Outline(width=2, dash_array=[5, 3], cap="round")
        assert outline.width == 2
        assert outline.dash_array == [5, 3]
        assert outline.cap == "round"


class TestElement:
    """Tests for base Element class."""
    
    def test_default_values(self):
        """Test default element values."""
        elem = Element()
        assert elem.id is not None
        assert len(elem.id) > 0
        assert elem.name == ""
        assert elem.element_type == ElementType.RECTANGLE
        assert elem.x == 0
        assert elem.y == 0
        assert elem.width == 100
        assert elem.height == 100
        assert elem.visible is True
        assert elem.locked is False
        assert elem.opacity == 1.0
        assert elem.angle == 0.0
        assert elem.shadow is None
    
    def test_unique_ids(self):
        """Test that each element gets unique ID."""
        elem1 = Element()
        elem2 = Element()
        assert elem1.id != elem2.id
    
    def test_to_dict_minimal(self):
        """Test to_dict with minimal values."""
        elem = Element()
        elem.x = 50
        elem.y = 100
        data = elem.to_dict()
        
        assert data["type"] == "rectangle"
        assert data["x"] == 50
        assert data["y"] == 100
        assert "name" not in data  # Empty name not included
    
    def test_to_dict_full(self):
        """Test to_dict with all values set."""
        elem = Element()
        elem.name = "test_elem"
        elem.x = 10
        elem.y = 20
        elem.width = 200
        elem.height = 150
        elem.visible = False
        elem.opacity = 0.5
        elem.angle = 45.0
        elem.shadow = Shadow()
        
        data = elem.to_dict()
        
        assert data["name"] == "test_elem"
        assert data["width"] == 200
        assert data["height"] == 150
        assert data["visible"] is False
        assert data["opacity"] == 0.5
        assert data["angle"] == 45.0
        assert "shadow" in data
    
    def test_from_dict(self):
        """Test creating element from dict."""
        data = {
            "name": "restored_elem",
            "x": 100,
            "y": 200,
            "opacity": 0.8,
            "shadow": {
                "blur": 10,
                "color": "0, 0, 0, 180",
                "offset_x": 5,
                "offset_y": 5
            }
        }
        
        elem = Element.from_dict(data)
        
        assert elem.name == "restored_elem"
        assert elem.x == 100
        assert elem.y == 200
        assert elem.opacity == 0.8
        assert elem.shadow is not None
        assert elem.shadow.blur == 10


class TestRectangleElement:
    """Tests for RectangleElement."""
    
    def test_default_values(self):
        """Test default rectangle values."""
        rect = RectangleElement()
        assert rect.element_type == ElementType.RECTANGLE
        assert rect.color == (255, 0, 0, 255)
        assert rect.radius == 0
        assert rect.shear_left == 0.0
        assert rect.shear_right == 0.0
        assert rect.outline is None
    
    def test_to_dict_with_radius(self):
        """Test rectangle to_dict with corner radius."""
        rect = RectangleElement()
        rect.x = 10
        rect.y = 20
        rect.radius = 15
        rect.color = (0, 255, 0, 200)
        
        data = rect.to_dict()
        
        assert data["type"] == "rectangle"
        assert data["color"] == "0, 255, 0, 200"
        assert data["radius"] == 15
    
    def test_to_dict_with_outline(self):
        """Test rectangle to_dict with outline."""
        rect = RectangleElement()
        rect.outline = Outline(width=2, color=(255, 255, 255, 255), dash_array=[5, 3])
        
        data = rect.to_dict()
        
        assert "outline" in data
        assert data["outline"]["width"] == 2
        assert data["outline"]["dash_array"] == [5, 3]


class TestCircleElement:
    """Tests for CircleElement."""
    
    def test_default_values(self):
        """Test default circle values."""
        circle = CircleElement()
        assert circle.element_type == ElementType.CIRCLE
        assert circle.radius == 50
        assert circle.color == (0, 0, 255, 255)
    
    def test_to_dict_no_width_height(self):
        """Test that circle to_dict excludes width/height."""
        circle = CircleElement()
        circle.x = 100
        circle.y = 100
        circle.radius = 30
        
        data = circle.to_dict()
        
        assert "radius" in data
        assert data["radius"] == 30
        assert "width" not in data
        assert "height" not in data


class TestTextElement:
    """Tests for TextElement."""
    
    def test_default_values(self):
        """Test default text values."""
        text = TextElement()
        assert text.element_type == ElementType.TEXT
        assert text.text == "Text"
        assert text.font == "roboto/Roboto-Regular.ttf"
        assert text.font_size == 16
        assert text.align == "left"
    
    def test_to_dict(self):
        """Test text to_dict."""
        text = TextElement()
        text.x = 50
        text.y = 100
        text.text = "Hello World"
        text.font_size = 24
        text.color = (255, 255, 255, 255)
        
        data = text.to_dict()
        
        assert data["text"] == "Hello World"
        assert data["font_size"] == 24


class TestDynamicTextElement:
    """Tests for DynamicTextElement."""
    
    def test_default_values(self):
        """Test default dynamic text values."""
        dtext = DynamicTextElement()
        assert dtext.element_type == ElementType.DYNAMIC_TEXT
        assert dtext.sensor_type == "CPU"
        assert dtext.sensor_metric == "PERCENTAGE"
        assert dtext.show_unit is True
        assert dtext.interval == 1.0
        assert dtext.force_static is False
    
    def test_to_dict(self):
        """Test dynamic text to_dict."""
        dtext = DynamicTextElement()
        dtext.sensor_type = "GPU"
        dtext.sensor_metric = "TEMPERATURE"
        dtext.interval = 2.0
        dtext.force_static = True
        
        data = dtext.to_dict()
        
        assert data["type"] == "dynamic_text"
        assert data["sensor"] == "GPU.TEMPERATURE"
        assert data["interval"] == 2.0
        assert data["force_static"] is True


class TestCreateElement:
    """Tests for create_element factory function."""
    
    def test_create_rectangle(self):
        """Test creating rectangle via factory."""
        elem = create_element(ElementType.RECTANGLE)
        assert isinstance(elem, RectangleElement)
        assert elem.element_type == ElementType.RECTANGLE
    
    def test_create_with_properties(self):
        """Test creating element with custom properties."""
        elem = create_element(
            ElementType.TEXT,
            x=100,
            y=200,
            text="Custom Text",
            font_size=32
        )
        
        assert isinstance(elem, TextElement)
        assert elem.x == 100
        assert elem.y == 200
        assert elem.text == "Custom Text"
        assert elem.font_size == 32
    
    def test_auto_generate_name(self):
        """Test that name is auto-generated if not provided."""
        elem = create_element(ElementType.CIRCLE)
        assert elem.name.startswith("circle_")
    
    def test_preserve_provided_name(self):
        """Test that provided name is preserved."""
        elem = create_element(ElementType.CIRCLE, name="my_circle")
        assert elem.name == "my_circle"
    
    @pytest.mark.parametrize("element_type", [
        ElementType.RECTANGLE,
        ElementType.CIRCLE,
        ElementType.TRIANGLE,
        ElementType.LINE,
        ElementType.TEXT,
        ElementType.IMAGE,
        ElementType.ICON,
        ElementType.GROUP,
        ElementType.DYNAMIC_TEXT,
        ElementType.GRAPH,
        ElementType.RADIAL,
        ElementType.LINE_GRAPH,
    ])
    def test_create_all_types(self, element_type):
        """Test that all element types can be created."""
        elem = create_element(element_type)
        assert elem.element_type == element_type
