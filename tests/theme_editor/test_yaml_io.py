# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for theme_editor.utils.yaml_io module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import tempfile
import shutil

from theme_editor.utils.yaml_io import ThemeYamlIO


class TestThemeYamlIOInit:
    """Tests for ThemeYamlIO initialization."""
    
    def test_init(self):
        """Test basic initialization."""
        io = ThemeYamlIO()
        assert io is not None
    
    def test_themes_dir_exists(self):
        """Test that THEMES_DIR path is valid."""
        io = ThemeYamlIO()
        # Path should end with res/themes
        assert io.THEMES_DIR.name == "themes"
        assert io.THEMES_DIR.parent.name == "res"


class TestV1ToV2Conversion:
    """Tests for v1 to v2 format conversion."""
    
    def test_convert_display_settings(self):
        """Test converting display settings."""
        io = ThemeYamlIO()
        v1 = {
            "display": {
                "DISPLAY_SIZE": '5"',
                "DISPLAY_ORIENTATION": "landscape",
                "DISPLAY_RGB_LED": "255, 0, 128",
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert v2["display"]["DISPLAY_SIZE"] == '5"'
        assert v2["display"]["DISPLAY_ORIENTATION"] == "landscape"
    
    def test_convert_background_image(self):
        """Test converting static background image."""
        io = ThemeYamlIO()
        v1 = {
            "static_images": {
                "BACKGROUND": {
                    "PATH": "bg.png",
                    "X": 0,
                    "Y": 0,
                }
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert v2["background"]["type"] == "image"
        assert v2["background"]["path"] == "bg.png"
    
    def test_convert_video_background(self):
        """Test converting video background."""
        io = ThemeYamlIO()
        v1 = {
            "video_background": {
                "ENABLE": True,
                "LOCAL_PATH": "video.mp4",
                "REMOTE_PATH": "/mnt/SDCARD/video/video.mp4",
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert v2["background"]["type"] == "video"
        assert "video" in v2["background"]
    
    def test_convert_static_images(self):
        """Test converting static images to ui_elements."""
        io = ThemeYamlIO()
        v1 = {
            "static_images": {
                "BACKGROUND": {"PATH": "bg.png", "X": 0, "Y": 0},
                "LOGO": {"PATH": "logo.png", "X": 10, "Y": 20, "WIDTH": 50, "HEIGHT": 50},
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        # BACKGROUND should not be in ui_elements (it's the background)
        assert len(v2["ui_elements"]) == 1
        
        logo = v2["ui_elements"][0]
        assert logo["type"] == "image"
        assert logo["name"] == "LOGO"
        assert logo["path"] == "logo.png"
        assert logo["x"] == 10
        assert logo["y"] == 20
    
    def test_convert_static_text(self):
        """Test converting static text to ui_elements."""
        io = ThemeYamlIO()
        v1 = {
            "static_text": {
                "TITLE": {
                    "TEXT": "Hello World",
                    "X": 100,
                    "Y": 50,
                    "FONT": "roboto/Roboto-Bold.ttf",
                    "FONT_SIZE": 24,
                    "FONT_COLOR": "255, 255, 255",
                }
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert len(v2["ui_elements"]) == 1
        
        text = v2["ui_elements"][0]
        assert text["type"] == "text"
        assert text["name"] == "TITLE"
        assert text["text"] == "Hello World"
        assert text["font_size"] == 24
    
    def test_convert_ui_elements_passthrough(self):
        """Test that ui_elements are passed through unchanged."""
        io = ThemeYamlIO()
        v1 = {
            "ui_elements": [
                {"type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50},
                {"type": "circle", "x": 100, "y": 100, "radius": 30},
            ]
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert len(v2["ui_elements"]) == 2
        assert v2["ui_elements"][0]["type"] == "rectangle"
        assert v2["ui_elements"][1]["type"] == "circle"
    
    def test_convert_stats_text(self):
        """Test converting STAT text elements."""
        io = ThemeYamlIO()
        v1 = {
            "STAT": {
                "CPU": {
                    "INTERVAL": 1,
                    "PERCENTAGE": {
                        "TEXT": {
                            "SHOW": True,
                            "X": 100,
                            "Y": 50,
                            "FONT": "roboto-mono/RobotoMono-Bold.ttf",
                            "FONT_SIZE": 20,
                            "FONT_COLOR": "255, 255, 255",
                            "SHOW_UNIT": True,
                        }
                    }
                }
            }
        }
        
        v2 = io._convert_v1_to_v2(v1)
        
        assert len(v2["dynamic_elements"]) == 1
        
        elem = v2["dynamic_elements"][0]
        assert elem["type"] == "dynamic_text"
        assert elem["sensor"] == "CPU.PERCENTAGE"
        assert elem["x"] == 100
        assert elem["y"] == 50


class TestV2ToV1Conversion:
    """Tests for v2 to v1 format conversion."""
    
    def test_convert_display(self):
        """Test converting display settings."""
        io = ThemeYamlIO()
        v2 = {
            "display": {
                "DISPLAY_SIZE": '5"',
                "DISPLAY_ORIENTATION": "portrait",
            }
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        assert v1["display"]["DISPLAY_SIZE"] == '5"'
    
    def test_convert_background_to_static_images(self):
        """Test converting image background to static_images."""
        io = ThemeYamlIO()
        v2 = {
            "background": {
                "type": "image",
                "path": "bg.png",
            }
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        assert "BACKGROUND" in v1["static_images"]
        assert v1["static_images"]["BACKGROUND"]["PATH"] == "bg.png"
    
    def test_convert_image_elements(self):
        """Test converting image ui_elements to static_images."""
        io = ThemeYamlIO()
        v2 = {
            "ui_elements": [
                {"type": "image", "name": "LOGO", "path": "logo.png", "x": 10, "y": 20}
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        assert "LOGO" in v1["static_images"]
    
    def test_convert_text_elements(self):
        """Test converting text ui_elements to static_text."""
        io = ThemeYamlIO()
        v2 = {
            "ui_elements": [
                {
                    "type": "text",
                    "name": "TITLE",
                    "text": "Test",
                    "x": 50,
                    "y": 100,
                    "font": "roboto/Roboto.ttf",
                    "font_size": 16,
                }
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        assert "TITLE" in v1["static_text"]
        assert v1["static_text"]["TITLE"]["TEXT"] == "Test"


class TestListThemes:
    """Tests for listing themes."""
    
    def test_list_themes_returns_list(self):
        """Test that list_themes returns a list."""
        io = ThemeYamlIO()
        themes = io.list_themes()
        
        assert isinstance(themes, list)
    
    def test_list_themes_excludes_special_dirs(self):
        """Test that special directories are excluded."""
        io = ThemeYamlIO()
        themes = io.list_themes()
        
        # Check that no theme starts with "--"
        for theme in themes:
            assert not theme.startswith("--")


class TestGetThemePath:
    """Tests for get_theme_path."""
    
    def test_get_theme_path(self):
        """Test getting theme path."""
        io = ThemeYamlIO()
        path = io.get_theme_path("TestTheme")
        
        assert path.name == "TestTheme"
        assert path.parent == io.THEMES_DIR
