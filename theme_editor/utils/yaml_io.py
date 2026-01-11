# SPDX-License-Identifier: GPL-3.0-or-later
"""
YAML I/O utilities for Theme Editor v2.

Handles reading and writing theme YAML files:
- theme-v2.yaml (new format)
- theme.yaml (legacy format, read-only support)

Uses ruamel.yaml to preserve comments and formatting where possible.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Try to use ruamel.yaml for better formatting preservation
try:
    from ruamel.yaml import YAML
    HAS_RUAMEL = True
except ImportError:
    HAS_RUAMEL = False
    logger.debug("ruamel.yaml not available, using standard yaml")


class ThemeYamlIO:
    """
    Handles theme YAML file I/O.
    
    Supports both theme-v2.yaml (new format) and theme.yaml (legacy).
    """
    
    THEMES_DIR = Path(__file__).parent.parent.parent / "res" / "themes"
    
    def __init__(self):
        """Initialize the YAML I/O handler."""
        if HAS_RUAMEL:
            self._yaml = YAML()
            self._yaml.preserve_quotes = True
            self._yaml.indent(mapping=2, sequence=4, offset=2)
        else:
            self._yaml = None
    
    def load(self, theme_name: str) -> Dict[str, Any]:
        """
        Load theme data from YAML file.
        
        Tries theme-editor.yaml first (editor format), then falls back to
        theme.yaml (engine format) with automatic conversion.
        
        Args:
            theme_name: Name of theme folder
            
        Returns:
            Theme data dictionary
            
        Raises:
            FileNotFoundError: If no theme file found
        """
        theme_path = self.THEMES_DIR / theme_name
        
        # Try editor format first
        editor_file = theme_path / "theme-editor.yaml"
        if editor_file.exists():
            return self._load_editor_format(editor_file)
        
        # Fall back to engine format (theme.yaml) with conversion
        v1_file = theme_path / "theme.yaml"
        if v1_file.exists():
            return self._load_v1(v1_file)
        
        raise FileNotFoundError(f"No theme file found in {theme_path}")
    
    def _load_editor_format(self, path: Path) -> Dict[str, Any]:
        """Load theme-editor.yaml (editor format)."""
        logger.info(f"Loading editor format theme: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            if self._yaml:
                data = self._yaml.load(f)
            else:
                data = yaml.safe_load(f)
        
        return dict(data) if data else {}
    
    def _load_v1(self, path: Path) -> Dict[str, Any]:
        """
        Load legacy theme.yaml and convert to v2 format.
        
        Args:
            path: Path to theme.yaml
            
        Returns:
            Theme data in editor format
        """
        logger.info(f"Loading engine format theme (converting to editor format): {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            v1_data = yaml.safe_load(f)
        
        if not v1_data:
            return {}
        
        # Convert to v2 format
        v2_data = self._convert_v1_to_v2(v1_data)
        return v2_data
    
    def _convert_v1_to_v2(self, v1: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert v1 theme data to v2 format.
        
        Args:
            v1: Legacy theme data
            
        Returns:
            Theme data in v2 format
        """
        v2 = {
            "display": v1.get("display", {}),
            "background": {},
            "ui_elements": [],
            "dynamic_elements": [],
        }
        
        # Handle video background
        video_bg = v1.get("video_background", {})
        if video_bg.get("ENABLE", False):
            v2["background"] = {
                "type": "video",
                "video": video_bg,
            }
        else:
            # Check for background image in static_images
            static_images = v1.get("static_images", {})
            if "BACKGROUND" in static_images:
                v2["background"] = {
                    "type": "image",
                    "path": static_images["BACKGROUND"].get("PATH", "background.png"),
                }
        
        # Convert static_images to ui_elements (except BACKGROUND)
        for name, img_data in v1.get("static_images", {}).items():
            if name == "BACKGROUND":
                continue
            
            element = {
                "type": "image",
                "name": name,
                "path": img_data.get("PATH", ""),
                "x": img_data.get("X", 0),
                "y": img_data.get("Y", 0),
            }
            if "WIDTH" in img_data:
                element["width"] = img_data["WIDTH"]
            if "HEIGHT" in img_data:
                element["height"] = img_data["HEIGHT"]
            
            v2["ui_elements"].append(element)
        
        # Convert static_text to ui_elements
        for name, text_data in v1.get("static_text", {}).items():
            element = {
                "type": "text",
                "name": name,
                "text": text_data.get("TEXT", ""),
                "x": text_data.get("X", 0),
                "y": text_data.get("Y", 0),
                "font": text_data.get("FONT", "roboto/Roboto-Regular.ttf"),
                "font_size": text_data.get("FONT_SIZE", 16),
            }
            
            # Convert color
            color = text_data.get("FONT_COLOR", "255, 255, 255")
            if isinstance(color, str):
                parts = [int(c.strip()) for c in color.split(",")]
                if len(parts) == 3:
                    parts.append(255)
                element["color"] = f"{parts[0]}, {parts[1]}, {parts[2]}, {parts[3]}"
            
            v2["ui_elements"].append(element)
        
        # Convert ui_elements (already in new format)
        for elem in v1.get("ui_elements", []):
            v2["ui_elements"].append(elem)
        
        # Convert STAT sections to dynamic_elements
        stats = v1.get("STAT", v1.get("STATS", {}))
        for sensor_type, sensor_data in stats.items():
            if not isinstance(sensor_data, dict):
                continue
            
            self._convert_stat_section(v2["dynamic_elements"], sensor_type, sensor_data)
        
        return v2
    
    def _convert_stat_section(
        self,
        elements: list,
        sensor_type: str,
        sensor_data: Dict[str, Any]
    ) -> None:
        """
        Convert a STAT section to dynamic_elements.
        
        Args:
            elements: List to append elements to
            sensor_type: CPU, GPU, MEMORY, etc.
            sensor_data: Sensor configuration data
        """
        interval = sensor_data.get("INTERVAL", 1)
        
        for metric, metric_data in sensor_data.items():
            if metric == "INTERVAL" or not isinstance(metric_data, dict):
                continue
            
            # Handle TEXT sub-element
            if "TEXT" in metric_data:
                text_cfg = metric_data["TEXT"]
                if text_cfg.get("SHOW", False):
                    element = {
                        "type": "dynamic_text",
                        "name": f"{sensor_type}_{metric}_TEXT",
                        "text": f"{{{sensor_type}_{metric}:u}}",
                        "sensor": f"{sensor_type}.{metric}",
                        "x": text_cfg.get("X", 0),
                        "y": text_cfg.get("Y", 0),
                        "font": text_cfg.get("FONT", "roboto-mono/RobotoMono-Bold.ttf"),
                        "font_size": text_cfg.get("FONT_SIZE", 16),
                        "show_unit": text_cfg.get("SHOW_UNIT", True),
                        "interval": interval,
                    }
                    
                    color = text_cfg.get("FONT_COLOR", "255, 255, 255")
                    if isinstance(color, str):
                        element["color"] = color + ", 255"
                    
                    elements.append(element)
            
            # Handle GRAPH sub-element
            if "GRAPH" in metric_data:
                graph_cfg = metric_data["GRAPH"]
                if graph_cfg.get("SHOW", False):
                    element = {
                        "type": "graph",
                        "name": f"{sensor_type}_{metric}_GRAPH",
                        "sensor": f"{sensor_type}.{metric}",
                        "x": graph_cfg.get("X", 0),
                        "y": graph_cfg.get("Y", 0),
                        "width": graph_cfg.get("WIDTH", 100),
                        "height": graph_cfg.get("HEIGHT", 20),
                        "min_value": graph_cfg.get("MIN_VALUE", 0),
                        "max_value": graph_cfg.get("MAX_VALUE", 100),
                        "interval": interval,
                    }
                    elements.append(element)
            
            # Handle RADIAL sub-element
            if "RADIAL" in metric_data:
                radial_cfg = metric_data["RADIAL"]
                if radial_cfg.get("SHOW", False):
                    element = {
                        "type": "radial",
                        "name": f"{sensor_type}_{metric}_RADIAL",
                        "sensor": f"{sensor_type}.{metric}",
                        "x": radial_cfg.get("X", 0),
                        "y": radial_cfg.get("Y", 0),
                        "radius": radial_cfg.get("RADIUS", 40),
                        "width": radial_cfg.get("WIDTH", 10),
                        "angle_start": radial_cfg.get("ANGLE_START", 120),
                        "angle_end": radial_cfg.get("ANGLE_END", 60),
                        "interval": interval,
                    }
                    elements.append(element)
            
            # Handle LINE_GRAPH sub-element
            if "LINE_GRAPH" in metric_data:
                lg_cfg = metric_data["LINE_GRAPH"]
                if lg_cfg.get("SHOW", False):
                    element = {
                        "type": "line_graph",
                        "name": f"{sensor_type}_{metric}_LINE_GRAPH",
                        "sensor": f"{sensor_type}.{metric}",
                        "x": lg_cfg.get("X", 0),
                        "y": lg_cfg.get("Y", 0),
                        "width": lg_cfg.get("WIDTH", 100),
                        "height": lg_cfg.get("HEIGHT", 50),
                        "history_size": lg_cfg.get("HISTORY_SIZE", 10),
                        "interval": interval,
                    }
                    elements.append(element)
    
    def save(self, theme_name: str, data: Dict[str, Any]) -> None:
        """
        Save theme data to theme-editor.yaml (editor format only).
        
        For saving both editor format and engine-compatible format,
        use save_all() instead.
        
        Args:
            theme_name: Name of theme folder
            data: Theme data dictionary
        """
        theme_path = self.THEMES_DIR / theme_name
        theme_path.mkdir(parents=True, exist_ok=True)
        
        # Copy external images to theme folder
        self._copy_external_images(data, theme_path)
        
        editor_file = theme_path / "theme-editor.yaml"
        
        logger.info(f"Saving editor format: {editor_file}")
        
        with open(editor_file, 'w', encoding='utf-8') as f:
            if self._yaml:
                self._yaml.dump(data, f)
            else:
                yaml.dump(
                    data, f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True
                )
    
    def save_all(self, theme_name: str, data: Dict[str, Any]) -> None:
        """
        Save theme data to both editor format and engine format.
        
        This method should be used when saving from the editor to ensure
        the theme is compatible with the theming engine.
        
        Writes:
        - theme-editor.yaml: Full editor state for reopening in editor
        - theme.yaml: Engine-compatible format for the theming engine
        
        Args:
            theme_name: Name of theme folder
            data: Theme data dictionary
        """
        self.save(theme_name, data)       # Save theme-editor.yaml
        self.export_v1(theme_name, data)  # Export theme.yaml
    
    def _copy_external_images(self, data: Dict[str, Any], theme_path: Path) -> None:
        """
        Copy external images to theme folder and update paths.
        
        Checks ui_elements for image elements with paths outside the theme folder.
        Copies them to theme/images/ and updates the path to be relative.
        
        Args:
            data: Theme data dictionary (modified in place)
            theme_path: Path to theme folder
        """
        import shutil
        
        images_dir = theme_path / "images"
        
        for elements_key in ["ui_elements", "dynamic_elements"]:
            elements = data.get(elements_key, [])
            for elem in elements:
                if elem.get("type") != "image":
                    continue
                
                path_str = elem.get("path", "")
                if not path_str:
                    continue
                
                path = Path(path_str)
                
                # Check if it's an external path (absolute or outside theme folder)
                is_external = path.is_absolute()
                if not is_external:
                    # Check if relative path exists within theme
                    full_path = theme_path / path
                    is_external = not full_path.exists()
                
                if is_external and path.exists():
                    # Copy to theme/images/ folder
                    images_dir.mkdir(exist_ok=True)
                    
                    dest_filename = path.name
                    dest_path = images_dir / dest_filename
                    
                    # Handle duplicate filenames
                    counter = 1
                    while dest_path.exists() and dest_path.read_bytes() != path.read_bytes():
                        stem = path.stem
                        suffix = path.suffix
                        dest_filename = f"{stem}_{counter}{suffix}"
                        dest_path = images_dir / dest_filename
                        counter += 1
                    
                    if not dest_path.exists():
                        logger.info(f"Copying external image: {path} -> {dest_path}")
                        shutil.copy2(path, dest_path)
                    
                    # Update the element path to relative
                    elem["path"] = f"images/{dest_filename}"

    
    def export_v1(self, theme_name: str, data: Dict[str, Any]) -> None:
        """
        Export theme data to legacy theme.yaml format.
        
        Args:
            theme_name: Name of theme folder
            data: Theme data in v2 format
        """
        theme_path = self.THEMES_DIR / theme_name
        theme_path.mkdir(parents=True, exist_ok=True)
        
        v1_file = theme_path / "theme.yaml"
        
        # Convert v2 to v1 format
        v1_data = self._convert_v2_to_v1(data)
        
        logger.info(f"Exporting v1 theme: {v1_file}")
        
        with open(v1_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                v1_data, f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
    
    def _convert_v2_to_v1(self, v2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert v2 theme data to legacy v1 format.
        
        Args:
            v2: Theme data in v2 format
            
        Returns:
            Theme data in v1 format
        """
        v1 = {
            "display": v2.get("display", {}),
            "static_images": {},
            "static_text": {},
            "ui_elements": [],
            "STATS": {},
        }
        
        # Handle background
        bg = v2.get("background", {})
        if bg.get("type") == "video":
            v1["video_background"] = bg.get("video", {})
            v1["video_background"]["ENABLE"] = True
        elif bg.get("type") == "image":
            v1["static_images"]["BACKGROUND"] = {
                "PATH": bg.get("path", "background.png"),
                "X": 0,
                "Y": 0,
            }
        
        # Convert ui_elements
        for elem in v2.get("ui_elements", []):
            elem_type = elem.get("type", "")
            
            if elem_type == "image":
                v1["static_images"][elem.get("name", "IMAGE")] = {
                    "PATH": elem.get("path", ""),
                    "X": elem.get("x", 0),
                    "Y": elem.get("y", 0),
                }
            elif elem_type == "text":
                v1["static_text"][elem.get("name", "TEXT")] = {
                    "TEXT": elem.get("text", ""),
                    "X": elem.get("x", 0),
                    "Y": elem.get("y", 0),
                    "FONT": elem.get("font", "roboto/Roboto-Regular.ttf"),
                    "FONT_SIZE": elem.get("font_size", 16),
                    "FONT_COLOR": elem.get("color", "255, 255, 255"),
                }
            else:
                # Keep other elements in ui_elements
                v1["ui_elements"].append(elem)
        
        # Convert dynamic_elements back to STATS structure
        # This is complex and would need full implementation
        # For now, just note that dynamic elements exist
        if v2.get("dynamic_elements"):
            logger.warning("Dynamic elements export to v1 not fully implemented")
        
        return v1
    
    def get_theme_path(self, theme_name: str) -> Path:
        """Get the path to a theme folder."""
        return self.THEMES_DIR / theme_name
    
    def list_themes(self) -> list:
        """List all available themes."""
        themes = []
        if self.THEMES_DIR.exists():
            for path in self.THEMES_DIR.iterdir():
                if path.is_dir() and not path.name.startswith("--"):
                    themes.append(path.name)
        return sorted(themes)
