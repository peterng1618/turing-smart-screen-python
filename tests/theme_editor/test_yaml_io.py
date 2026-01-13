# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for theme_editor.utils.yaml_io module.
"""

from pathlib import Path
import tempfile

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
        
        # Background image is now in static_images
        assert "static_images" in v2
        assert "BACKGROUND" in v2["static_images"]
        assert v2["static_images"]["BACKGROUND"]["PATH"] == "bg.png"
    
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
        
        # Video background is now in video_background dict
        assert "video_background" in v2
        bv = v2["video_background"]
        assert bv["ENABLE"] is True
    
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
        
        # 1 element: LOGO in ui_elements. Background is in static_images.
        # Note: ui_elements might be empty list or contain just LOGO
        assert len(v2["ui_elements"]) == 1
        
        logo = v2["ui_elements"][0]
        assert logo["type"] == "image"
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
        
        # 1 element: TITLE. Backgrounds stored separately now.
        assert len(v2["ui_elements"]) == 1
        
        text = next(e for e in v2["ui_elements"] if e["name"] == "TITLE")
        assert text["type"] == "text"
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
        
        # 2 passed through. Backgrounds stored separately now.
        assert len(v2["ui_elements"]) == 2
        assert any(e["type"] == "rectangle" for e in v2["ui_elements"])
        assert any(e["type"] == "circle" for e in v2["ui_elements"])
    
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
        """Test converting background_image element to BACKGROUND image."""
        io = ThemeYamlIO()
        v2 = {
            "static_images": {
                "BACKGROUND": {
                    "PATH": "custom_bg.png",
                    "X": 0, "Y": 0
                }
            }
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        # Background path in v1 export points to _exported.png
        assert "BACKGROUND" in v1["static_images"]
        assert v1["static_images"]["BACKGROUND"]["PATH"] == "custom_bg_exported.png"
    
    def test_ui_elements_exclusion(self):
        """Test that non-background ui_elements are EXCLUDED from v1 export."""
        io = ThemeYamlIO()
        v2 = {
            "ui_elements": [
                {"type": "image", "name": "LOGO", "path": "logo.png", "x": 10, "y": 20},
                {"type": "text", "name": "TITLE", "text": "Test", "x": 50, "y": 100}
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        # Neither should be in v1 since they are baked
        assert "static_images" not in v1
        assert "static_text" not in v1
    
    def test_dynamic_text_exported(self):
        """Test that dynamic_text IS exported to theme.yaml (as STATS or dynamic_text)."""
        io = ThemeYamlIO()
        v2 = {
            "dynamic_elements": [
                {
                    "type": "dynamic_text",
                    "name": "CPU Usage",
                    "sensor": "CPU.PERCENTAGE",
                    "text": "{CPU.PERCENTAGE:u}",
                    "x": 10, "y": 10,
                    "interval": 1.0
                }
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        # Should be in STATS because it matches the {SENSOR:u} pattern
        assert "STATS" in v1
        assert "CPU" in v1["STATS"]
        assert v1["STATS"]["CPU"]["PERCENTAGE"]["TEXT"]["SHOW"] is True
    
    def test_dynamic_text_custom_pattern_exported(self):
        """Test that custom pattern dynamic text goes into dynamic_text section."""
        io = ThemeYamlIO()
        v2 = {
            "dynamic_elements": [
                {
                    "type": "dynamic_text",
                    "name": "Combined",
                    "text": "C: {CPU.PERCENTAGE:u} G: {GPU.PERCENTAGE:u}",
                    "x": 10, "y": 10
                }
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2)
        
        assert "dynamic_text" in v1
        assert "Combined" in v1["dynamic_text"]
        assert v1["dynamic_text"]["Combined"]["TEXT"] == "C: {CPU.PERCENTAGE:u} G: {GPU.PERCENTAGE:u}"


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

class TestCopyExternalAssets:
    """Tests for copying external assets."""
    
    def test_copy_external_backgrounds(self):
        """Test that background_image and background_video assets are copied."""
        io = ThemeYamlIO()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_theme_path = Path(tmp_dir) / "NewTheme"
            dest_theme_path.mkdir()
            
            source_theme_path = Path(tmp_dir) / "OldTheme"
            source_theme_path.mkdir()
            
            # Create dummy source assets
            old_bg = source_theme_path / "background.png"
            old_bg.write_bytes(b"old background")
            
            old_ui_img = source_theme_path / "images" / "logo.png"
            old_ui_img.parent.mkdir()
            old_ui_img.write_bytes(b"old logo")
            
            # Absolute external asset
            ext_img = Path(tmp_dir) / "external.png"
            ext_img.write_bytes(b"external")
            
            data = {
                "ui_elements": [
                    {
                        "type": "background_image",
                        "path": "background.png"  # Relative to OldTheme
                    },
                    {
                        "type": "image",
                        "path": "images/logo.png" # Relative to OldTheme
                    },
                    {
                        "type": "image",
                        "path": str(ext_img)      # Absolute
                    }
                ]
            }
            
            io._copy_external_assets(data, dest_theme_path, source_theme_path)
            
            # Verify background was copied to root and renamed to _source
            assert (dest_theme_path / "background_source.png").exists()
            assert (dest_theme_path / "background_source.png").read_bytes() == b"old background"
            assert data["ui_elements"][0]["path"] == "background_source.png"
            
            # Verify logo was copied to images/ and renamed to _source
            assert (dest_theme_path / "images" / "logo_source.png").exists()
            assert (dest_theme_path / "images" / "logo_source.png").read_bytes() == b"old logo"
            assert data["ui_elements"][1]["path"] == "images/logo_source.png"
            
            # Verify external image was copied to images/ and renamed to _source
            assert (dest_theme_path / "images" / "external_source.png").exists()
            assert data["ui_elements"][2]["path"] == "images/external_source.png"

    def test_v1_export_order(self):
        """Test that v1 export follows strict section ordering and excludes UI elements."""
        io = ThemeYamlIO()
        
        v2_data = {
            "author": "Peter",
            "display": {"DISPLAY_SIZE": "5\""},
            "static_images": {
                "BACKGROUND": {"PATH": "test_source.png"}
            },
            "ui_elements": [
                {"type": "image", "name": "BakeMe", "path": "images/bake_source.png"},
                {"type": "text", "name": "StaticText", "text": "Hello"}
            ],
            "dynamic_elements": [
                {
                    "type": "dynamic_text",
                    "name": "CPU_Temp",
                    "sensor": "CPU.TEMPERATURE",
                    "text": "{CPU.TEMPERATURE:u}"
                }
            ]
        }
        
        v1 = io._convert_v2_to_v1(v2_data)
        
        # Verify order of keys
        keys = list(v1.keys())
        expected_order = ["author", "display", "static_images", "STATS"]
        assert keys == expected_order
        
        # Verify BACKGROUND is first in static_images
        static_keys = list(v1["static_images"].keys())
        assert static_keys[0] == "BACKGROUND"
        assert v1["static_images"]["BACKGROUND"]["PATH"] == "test_exported.png"
        
        # Verify exclusion of BakeMe and StaticText
        assert "BakeMe" not in v1["static_images"]
        assert "static_text" not in v1
        assert len(v1["static_images"]) == 1
