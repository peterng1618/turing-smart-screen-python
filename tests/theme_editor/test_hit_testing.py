# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for hit-testing in ElementItem.
"""

import pytest
import sys
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF
from theme_editor.models.element import create_element, ElementType
from theme_editor.models.theme_model import ThemeModel
from theme_editor.canvas.preview_canvas import ElementItem

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_triangle_hit_testing(qapp):
    """Test that Triangles use their actual shape for hit-testing."""
    model = ThemeModel(MagicMock())
    # Create a triangle with points (0,0), (100,0), (50,100)
    # The default rectangle would be (0,0,100,100)
    triangle = create_element(
        ElementType.TRIANGLE, 
        x1=0, y1=0, 
        x2=100, y2=0, 
        x3=50, y3=100
    )
    item = ElementItem(triangle, model)
    item.setPos(0, 0)
    
    # Local coordinates of points
    p_inside = QPointF(50, 50)
    p_outside_bottom_left = QPointF(5, 95) # Inside (0,0,100,100) but outside triangle
    p_outside_bottom_right = QPointF(95, 95) # Inside (0,0,100,100) but outside triangle
    
    assert item.shape().contains(p_inside), "Point inside triangle should be hit"
    
    # These currently FAIL (return True) because it's using a rectangle
    assert not item.shape().contains(p_outside_bottom_left), "Point outside triangle should NOT be hit"
    assert not item.shape().contains(p_outside_bottom_right), "Point outside triangle should NOT be hit"

def test_line_hit_testing(qapp):
    """Test that Lines use their actual shape for hit-testing."""
    model = ThemeModel(MagicMock())
    # Create a line from (0,0) to (100,100)
    # Default rectangle would be (0,0,100,100)
    line = create_element(
        ElementType.LINE, 
        x=0, y=0, 
        x2=100, y2=100, 
        line_width=10
    )
    item = ElementItem(line, model)
    item.setPos(0, 0)
    
    # Midpoint of the line
    p_on_line = QPointF(50, 50)
    # Point off the line but inside (0,0,100,100)
    p_off_line = QPointF(100, 0)
    
    assert item.shape().contains(p_on_line), "Point on line should be hit"
    
    # This currently FAILS (returns True) because it's using a rectangle
    assert not item.shape().contains(p_off_line), "Point off line should NOT be hit"
