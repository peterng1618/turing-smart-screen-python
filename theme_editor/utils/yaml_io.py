# SPDX-License-Identifier: GPL-3.0-or-later
"""
YAML I/O utilities for Theme Editor v2.

Handles reading and writing theme YAML files:
- theme-v2.yaml (new format)
- theme.yaml (legacy format, read-only support)

Uses ruamel.yaml to preserve comments and formatting where possible.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from PyQt6.QtCore import QTemporaryFile, QIODevice

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
            "ui_elements": [],
            "dynamic_elements": [],
        }
        
        # Extract author
        author = v1.get("author")
        if not author:
            # check INFO.AUTHOR
            info = v1.get("INFO", {})
            author = info.get("AUTHOR", "")
        v2["author"] = author
        
        # Handle video background (v1)
        video_bg = v1.get("video_background", {})
        eb_video = {
            "type": "background_video",
            "name": "Background Video",
            "enabled": video_bg.get("ENABLE", False),
            "source_path": video_bg.get("SOURCE_PATH", ""),
            "x": video_bg.get("x", 0),
            "y": video_bg.get("y", 0),
            "width": video_bg.get("width", 0),
            "height": video_bg.get("height", 0),
            "angle": video_bg.get("ROTATE", 0),
            "start_offset": video_bg.get("START_OFFSET", "00:00"),
            "duration": video_bg.get("DURATION", ""),
            "loop_fade_duration": video_bg.get("LOOP_FADE_DURATION", 1.0),
            "locked": True,
            "z_order": -500
        }
        v2["ui_elements"].append(eb_video)
        
        # Handle background image (v1)
        static_images = v1.get("static_images", {})
        bg_path = "background.png"
        if "BACKGROUND" in static_images:
            bg_path = static_images["BACKGROUND"].get("PATH", "background.png")
            
        eb_img = {
            "type": "background_image",
            "name": "Background Image",
            "path": bg_path,
            "locked": True,
            "z_order": -99
        }
        v2["ui_elements"].append(eb_img)
        
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
            
            element["align"] = text_data.get("ALIGN", "left").lower()
            element["anchor"] = text_data.get("ANCHOR", "lt").lower()
            
            v2["ui_elements"].append(element)
        
        # Convert ui_elements (already in new format)
        for elem in v1.get("ui_elements", []):
            v2["ui_elements"].append(elem)
        
        # Convert STAT sections to dynamic_elements
        stats = v1.get("STAT", v1.get("STATS", {}))
        for sensor_type, sensor_data in stats.items():
            if not isinstance(sensor_data, dict):
                continue
            
            # Special case: DATE might be at the top level or under STATS
            self._convert_stat_section(v2["dynamic_elements"], sensor_type, sensor_data)
        
        # Also check for DATE at top level (some themes do this)
        if "DATE" in v1 and "DATE" not in stats:
             self._convert_stat_section(v2["dynamic_elements"], "DATE", v1["DATE"])
        
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
            
            # Handle variations of TEXT sub-element
            text_keys = ["TEXT", "PERCENT_TEXT", "DATA_TEXT", "NAME_TEXT", "VALUE_TEXT"]
            for t_key in text_keys:
                if t_key in metric_data:
                    text_cfg = metric_data[t_key]
                    if text_cfg.get("SHOW", False):
                        # Construct appropriate sensor path and label
                        sensor_path = f"{sensor_type}.{metric}"
                        if t_key == "PERCENT_TEXT":
                            sensor_path = f"{sensor_type}.{metric}" # Usually already points to percentage
                        
                        # Check if width/height are explicitly set (forced)
                        width = text_cfg.get("WIDTH")
                        height = text_cfg.get("HEIGHT")
                        force_static = (width is not None or height is not None)
                        
                        element = {
                            "type": "dynamic_text",
                            "name": f"{sensor_type}_{metric}_{t_key}",
                            "text": f"{{{sensor_path}:u}}",
                            "sensor": sensor_path,
                            "x": text_cfg.get("X", 0),
                            "y": text_cfg.get("Y", 0),
                            "width": width if width is not None else 0,
                            "height": height if height is not None else 0,
                            "force_static": force_static,
                            "font": text_cfg.get("FONT", "roboto-mono/RobotoMono-Bold.ttf"),
                            "font_size": text_cfg.get("FONT_SIZE", 16),
                            "show_unit": text_cfg.get("SHOW_UNIT", True),
                            "interval": interval,
                            "align": text_cfg.get("ALIGN", "left"),
                            "anchor": text_cfg.get("ANCHOR", "lt"),
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
    
    def save(self, theme_name: str, data: Dict[str, Any], source_theme_path: Optional[Path] = None) -> None:
        """
        Save theme data to theme-editor.yaml (editor format only).
        
        For saving both editor format and engine-compatible format,
        use save_all() instead.
        
        Args:
            theme_name: Name of theme folder
            data: Theme data dictionary
            source_theme_path: Optional original path to resolve existing relative assets
        """
        theme_path = self.THEMES_DIR / theme_name
        theme_path.mkdir(parents=True, exist_ok=True)
        
        # Copy external assets to theme folder
        self._copy_external_assets(data, theme_path, source_theme_path)
        
        editor_file = theme_path / "theme-editor.yaml"
        
        logger.info(f"Saving editor format: {editor_file}")
        
        self._atomic_write(editor_file, data)
    
    def save_all(self, theme_name: str, data: Dict[str, Any], source_theme_path: Optional[Path] = None) -> None:
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
            source_theme_path: Optional original path to resolve existing relative assets
        """
        self.save(theme_name, data, source_theme_path)  # Save theme-editor.yaml
        self.export_v1(theme_name, data)                # Export theme.yaml

    def _atomic_write(self, target_path: Path, data: Dict[str, Any]) -> None:
        """
        Write data to target_path atomically using QTemporaryFile.
        
        Args:
            target_path: Destination path
            data: Data to write (serialized via yaml)
        """
        logger.info(f"Atomic write start for {target_path}")
        # Create temporary file in the same directory as target to ensure atomic move
        # template: name.XXXXXX.tmp
        temp_file = QTemporaryFile(str(target_path.parent / "temp_save.XXXXXX.yaml"))
        temp_file.setAutoRemove(False) # We will handle removal/move
        
        if not temp_file.open():
            logger.error(f"Failed to create temp file for saving {target_path}")
            raise IOError("Could not create temporary save file")
        
        try:
            # Get the path now, because sometimes it's tricky after close depending on OS?
            # actually fileName() works as long as object lives.
            temp_path = Path(temp_file.fileName())
            logger.info(f"Temp file created at {temp_path}")
            
            # Serialize data to string first
            import io
            stream = io.StringIO()
            if self._yaml:
                self._yaml.dump(data, stream)
            else:
                yaml.dump(
                    data, stream,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True
                )
            
            content = stream.getvalue().encode('utf-8')
            
            # Write bytes
            bytes_written = temp_file.write(content)
            if bytes_written == -1:
                 raise IOError(f"Failed to write to temp file: {temp_file.errorString()}")
            
            # Flush and Close
            temp_file.flush()
            temp_file.close()
            
            # Check if write was successful (size?)
            if temp_path.stat().st_size == 0 and len(content) > 0:
                raise IOError("Temp file is empty after write!")
            
            # Backup original if exists
            backup_path = None
            if target_path.exists():
                logger.info(f"Target exists, creating backup...")
                backup_path = target_path.with_suffix(target_path.suffix + ".bak")
                # Remove old backup if exists
                if backup_path.exists():
                    logger.info(f"Removing old backup {backup_path}")
                    backup_path.unlink()
                # Rename current to backup
                logger.info(f"Moving {target_path} to {backup_path}")
                shutil.move(target_path, backup_path)
            else:
                logger.info(f"Target {target_path} does not exist, no backup needed.")
            
            # Rename temp to target using QTemporaryFile.rename to handle locks/lifecycle correctly
            # This promotes the temporary file to a permanent file and detaches auto-deletion.
            logger.info(f"Renaming temp file to {target_path}")
            if not temp_file.rename(str(target_path)):
                error_msg = f"Failed to rename temp file to {target_path}: {temp_file.errorString()}"
                logger.error(error_msg)
                # Fallback? If rename fails, maybe use shutil if we close? 
                # But rename should work if target (which we just backed up) is gone.
                # If target wasn't backed up (didn't exist), it should also work.
                
                # If rename failed, valid reason could be target exists (race condition?)
                # or still open? rename() closes it implicitly or requires close?
                # "The file is closed before it is renamed." - Qt Docs
                
                # Retrying with shutil after ensuring destruction of QObject?
                # But we are in the middle of using it.
                
                raise IOError(error_msg)
                
            logger.info(f"Successfully saved to {target_path}")
            
        except Exception as e:
            logger.error(f"Atomic save failed: {e}")
            # Try to restore backup if we moved it
            if 'backup_path' in locals() and backup_path and backup_path.exists() and not target_path.exists():
                 logger.info("Restoring backup...")
                 shutil.move(backup_path, target_path)
            
            if 'temp_path' in locals() and temp_path.exists():
                 try:
                     temp_path.unlink()
                 except: pass

            raise e
    
    def _copy_external_assets(self, data: Dict[str, Any], theme_path: Path, source_theme_path: Optional[Path] = None) -> None:
        """
        Copy external assets (images, videos) to theme folder and update paths.
        
        Assets are renamed to [name]_source.[ext] if localized.
        
        Args:
            data: Theme data dictionary (modified in place)
            theme_path: Path to theme folder (destination)
            source_theme_path: Optional original path to resolve relative assets
        """
        # 1. Top-level assets (BACKGROUND)
        static_imgs = data.get("static_images", {})
        bg_info = static_imgs.get("BACKGROUND")
        if bg_info:
            path_str = bg_info.get("PATH", "")
            if path_str:
                src_path = self._resolve_source_path(path_str, theme_path, source_theme_path)
                if src_path:
                    localized_path = self._localize_asset(src_path, theme_path, theme_path) # backgrounds in root
                    bg_info["PATH"] = localized_path
        
        # 2. Top-level assets (Video Background)
        video_bg = data.get("video_background")
        if video_bg:
            path_str = video_bg.get("SOURCE_PATH", "")
            if path_str:
                src_path = self._resolve_source_path(path_str, theme_path, source_theme_path)
                if src_path:
                    localized_path = self._localize_asset(src_path, theme_path, theme_path) # videos in root
                    video_bg["SOURCE_PATH"] = localized_path

        # 3. Elements (UI & Dynamic)
        images_dir = theme_path / "images"
        for elements_key in ["ui_elements", "dynamic_elements"]:
            elements = data.get(elements_key, [])
            for elem in elements:
                etype = elem.get("type")
                path_key = "path"
                dest_dir = images_dir
                
                if etype == "background_image":
                    # Skip as handled above, but technically might still be in list
                    path_key = "path"
                    dest_dir = theme_path
                elif etype == "image":
                    path_key = "path"
                    dest_dir = images_dir
                elif etype == "background_video":
                    # Skip as handled above
                    path_key = "source_path"
                    dest_dir = theme_path
                else:
                    continue
                
                path_str = elem.get(path_key, "")
                if not path_str:
                    continue
                
                src_path = self._resolve_source_path(path_str, theme_path, source_theme_path)
                if src_path:
                    localized_path = self._localize_asset(src_path, theme_path, dest_dir)
                    elem[path_key] = localized_path
                else:
                    logger.warning(f"Could not resolve asset path: {path_str}")

    def _resolve_source_path(self, path_str: str, theme_path: Path, source_theme_path: Optional[Path]) -> Optional[Path]:
        """Helper to resolve a source path from various locations."""
        raw_path = Path(path_str)
        if raw_path.is_absolute():
            return raw_path if raw_path.exists() else None
        
        # Try current theme folder
        if (theme_path / raw_path).exists():
            return theme_path / raw_path
            
        # Try source theme folder (Save As)
        if source_theme_path and (source_theme_path / raw_path).exists():
            return source_theme_path / raw_path
            
        return None

    def _localize_asset(self, src_path: Path, theme_path: Path, dest_dir: Path) -> str:
        """Helper to copy and rename an asset to _source, returns local relative path."""
        import shutil
        try:
            rel_in_dest = src_path.relative_to(theme_path)
        except ValueError:
            rel_in_dest = None
            
        stem = src_path.stem
        suffix = src_path.suffix
        
        if not stem.endswith("_source") and not stem.endswith("_exported"):
            new_filename = f"{stem}_source{suffix}"
        else:
            new_filename = src_path.name
            
        dest_path = dest_dir / new_filename
        
        if rel_in_dest is None or src_path.name != new_filename or src_path.parent != dest_dir:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if not dest_path.exists() or dest_path.stat().st_mtime < src_path.stat().st_mtime:
                logger.info(f"Localizing asset: {src_path} -> {dest_path}")
                shutil.copy2(src_path, dest_path)
                
        return os.path.relpath(dest_path, theme_path).replace('\\', '/')

    
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
        
        self._atomic_write(v1_file, v1_data)
    
    def _convert_v2_to_v1(self, v2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert v2 (editor) theme data to v1 (display engine) format.
        
        Strict Order:
        1. author
        2. display
        3. static_images (BACKGROUND first)
        4. video_background
        5. STATS
        6. dynamic_text
        
        Note: All UI elements (shapes, text, baked images) are EXCLUDED.
        """
        # Use child classes of dict or just careful insertion order to preserve order for yaml.dump(sort_keys=False)
        v1 = {}
        
        # 1. Author
        v1["author"] = v2.get("author", "Unknown")
        
        # 2. Display
        v1["display"] = v2.get("display", {})
        
        # 3. Static Images (BACKGROUND MUST BE FIRST)
        v1["static_images"] = {}
        
        # Check v2 static_images for BACKGROUND
        v2_static_imgs = v2.get("static_images", {})
        bg_info = v2_static_imgs.get("BACKGROUND")
        
        if bg_info:
            # Point to _exported.png
            src_path = Path(bg_info.get("PATH", "background_source.png"))
            # Rename stem from _source to _exported
            stem = src_path.stem.replace("_source", "")
            exported_name = f"{stem}_exported.png"
            
            # Standard dimensions from display settings
            w, h = self._get_v1_display_dimensions(v1["display"])
            
            v1["static_images"]["BACKGROUND"] = {
                "PATH": exported_name,
                "X": 0,
                "Y": 0,
                "WIDTH": w,
                "HEIGHT": h
            }
        
        # 4. Video Background
        v2_video_bg = v2.get("video_background")
        if v2_video_bg:
            v1["video_background"] = {
                "ENABLE": v2_video_bg.get("ENABLE", True),
                "SOURCE_PATH": v2_video_bg.get("SOURCE_PATH", ""),
                "x": v2_video_bg.get("x", 0), # Editor uses lowercase x,y? Let's check model
                "y": v2_video_bg.get("y", 0),
                "width": v2_video_bg.get("width", 0),
                "height": v2_video_bg.get("height", 0),
                "START_OFFSET": v2_video_bg.get("START_OFFSET", "00:00"),
                "DURATION": v2_video_bg.get("DURATION", ""),
                "LOOP_FADE_DURATION": v2_video_bg.get("LOOP_FADE_DURATION", 1.0),
            }
            # Add _exported path
            src_path = Path(v2_video_bg.get("SOURCE_PATH", "video_source.mp4"))
            stem = src_path.stem.replace("_source", "")
            exported_video = f"{stem}_exported.mp4"
            v1["video_background"]["LOCAL_PATH"] = exported_video
            v1["video_background"]["REMOTE_PATH"] = f"/mnt/SDCARD/video/{exported_video}"

        # 5. STATS & 6. dynamic_text
        v1["STATS"] = {}
        v1["dynamic_text"] = {}
        
        dynamic_elements = v2.get("dynamic_elements", [])
        for elem in dynamic_elements:
            etype = elem.get("type")
            name = elem.get("name", "Dynamic")
            
            if etype == "dynamic_text":
                text = elem.get("text", "")
                sensor_path = elem.get("sensor", "")
                parts = sensor_path.split(".")
                
                if len(parts) >= 2 and text == f"{{{sensor_path}:u}}":
                    # Place into STATS
                    sensor_type = parts[0]
                    metric = ".".join(parts[1:])
                    
                    if sensor_type not in v1["STATS"]:
                        v1["STATS"][sensor_type] = {"INTERVAL": elem.get("interval", 1)}
                    
                    curr = v1["STATS"][sensor_type]
                    for p in parts[1:-1]:
                        if p not in curr: curr[p] = {}
                        curr = curr[p]
                    
                    last_metric = parts[-1]
                    if last_metric not in curr:
                        curr[last_metric] = {}
                    
                    text_cfg = {
                        "SHOW": True,
                        "X": elem.get("x", 0), "Y": elem.get("y", 0),
                        "FONT": elem.get("font", ""),
                        "FONT_SIZE": elem.get("font_size", 16),
                        "FONT_COLOR": elem.get("color", "255, 255, 255, 255").rsplit(",", 1)[0],
                        "ALIGN": elem.get("align", "left"),
                        "ANCHOR": elem.get("anchor", "lt"),
                        "SHOW_UNIT": elem.get("show_unit", True),
                    }
                    if elem.get("force_static"):
                        text_cfg["WIDTH"] = elem.get("width")
                        text_cfg["HEIGHT"] = elem.get("height")
                    
                    curr[last_metric]["TEXT"] = text_cfg
                else:
                    # Place into dynamic_text
                    v1["dynamic_text"][name] = {
                        "TEXT": text,
                        "X": elem.get("x", 0), "Y": elem.get("y", 0),
                        "FONT": elem.get("font", ""),
                        "FONT_SIZE": elem.get("font_size", 16),
                        "FONT_COLOR": elem.get("color", "255, 255, 255, 255").rsplit(",", 1)[0],
                        "ALIGN": elem.get("align", "left"),
                        "ANCHOR": elem.get("anchor", "lt"),
                        "INTERVAL": elem.get("interval", 1),
                    }
                    if elem.get("force_static"):
                        v1["dynamic_text"][name]["WIDTH"] = elem.get("width")
                        v1["dynamic_text"][name]["HEIGHT"] = elem.get("height")

        # Clean up empty sections
        if not v1["static_images"]: del v1["static_images"]
        if not v1["STATS"]: del v1["STATS"]
        if not v1["dynamic_text"]: del v1["dynamic_text"]
        
        return v1

    def _get_v1_display_dimensions(self, display: Dict[str, Any]) -> tuple:
        """Helper to get width, height from display settings."""
        size = display.get("DISPLAY_SIZE", "5\"")
        orientation = display.get("DISPLAY_ORIENTATION", "landscape")
        
        sizes = {
            "2.1\"": (480, 480),
            "3.5\"": (320, 480),
            "5\"": (480, 800),
            "8.8\"": (480, 1920),
        }
        w, h = sizes.get(size, (480, 800))
        if orientation == "landscape":
            return max(w, h), min(w, h)
        return min(w, h), max(w, h)
    
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
