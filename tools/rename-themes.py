import os
import yaml
import argparse
import re
from pathlib import Path
from PIL import Image
from ruamel.yaml import YAML

# Mapping of (min_dim, max_dim) to screen size string
DIMENSION_TO_SIZE = {
    (80, 160): "0.96",
    (320, 480): "3.5",
    (480, 800): "5.0",
    (480, 1920): "8.8"
}

def normalize_size(size_str):
    """Normalize size string (e.g., '3.5' -> '3.5"', '5.0' -> '5.0"')."""
    if not size_str:
        return None
    # Remove quotes and extra spaces to start fresh
    size = str(size_str).replace('"', '').strip()
    try:
        val = float(size)
        if val == int(val):
            res = f"{val:.1f}"
        else:
            res = f"{val:g}"
        return f'{res}"'
    except ValueError:
        # If it's not a number, just ensure it has the " suffix if it looks like a size
        if size and not size.endswith('"'):
            return f'{size}"'
        return size

def infer_size_from_dimensions(width, height):
    """Infers display size from width and height."""
    dims = tuple(sorted((int(width), int(height))))
    return DIMENSION_TO_SIZE.get(dims)

def normalize_orientation(orientation_str):
    """Normalize orientation (e.g., 'portrait' -> 'V', 'landscape' -> 'H')."""
    if not orientation_str:
        return "U"
    o = str(orientation_str).lower().strip()
    if o == 'portrait':
        return 'V'
    elif o == 'landscape':
        return 'H'
    return o.upper()

def update_theme_yaml(yaml_path, size):
    """Update DISPLAY_SIZE in theme.yaml using ruamel.yaml to preserve comments."""
    ryaml = YAML()
    ryaml.preserve_quotes = True
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = ryaml.load(f)
        
        if 'display' not in data:
            data['display'] = {}
        
        data['display']['DISPLAY_SIZE'] = size
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            ryaml.dump(data, f)
        return True
    except Exception as e:
        print(f"Error updating {yaml_path}: {e}")
        return False

def get_theme_metadata(theme_path, update_yaml=False):
    """Extract or infer size and orientation."""
    yaml_path = theme_path / "theme.yaml"
    size = None
    orientation = None
    inferred = False
    
    needs_update = False
    if not yaml_path.exists():
        return None, "U", False

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data and 'display' in data:
                display = data['display']
                raw_size = display.get('DISPLAY_SIZE')
                size = normalize_size(raw_size)
                # If the size in YAML is different from normalized (e.g. missing quote), we need update
                if raw_size != size:
                    needs_update = True
                orientation = normalize_orientation(display.get('DISPLAY_ORIENTATION'))
            
            # If size is still missing, try to infer
            if not size and data and 'static_images' in data:
                bg = data['static_images'].get('BACKGROUND')
                if bg:
                    w, h = bg.get('WIDTH'), bg.get('HEIGHT')
                    # If dimensions are missing in YAML, try opening the file
                    if (not w or not h) and 'PATH' in bg:
                        img_path = theme_path / bg['PATH']
                        if img_path.exists():
                            try:
                                with Image.open(img_path) as img:
                                    w, h = img.size
                            except Exception as e:
                                print(f"Error opening image {img_path}: {e}")
                    
                    if w and h:
                        size = infer_size_from_dimensions(w, h)
                        if size:
                            size = normalize_size(size)
                            inferred = True
                            needs_update = True

    except Exception as e:
        print(f"Error reading {yaml_path}: {e}")

    if needs_update and update_yaml:
        if update_theme_yaml(yaml_path, size):
            print(f"Updated {yaml_path} with proper size: {size}")

    return size, orientation, inferred

def rename_themes(root_dir, dry_run=True, execute_update=False):
    themes_path = Path(root_dir)
    if not themes_path.exists():
        print(f"Error: Themes path {themes_path} does not exist.")
        return

    # Pattern to check if already renamed: {Size}_{Orientation}_
    # Matches strings like "3.5_V_", "5.0_H_", "0.96_V_" at the start of the name
    rename_pattern = re.compile(r'^\d+(\.\d+)_[VH]_')

    # Iterate only one level below res/themes
    for item in themes_path.iterdir():
        # Condition 2: Skip if theme.yaml doesn't exist at the folder root
        if item.is_dir() and (item / "theme.yaml").exists():
            # Get current metadata, update if execute_update is True
            size, orientation, inferred = get_theme_metadata(item, update_yaml=execute_update and not dry_run)
            
            if not size or orientation == "U":
                print(f"Warning: Could not determine metadata for {item.name}. Skipping.")
                continue

            # I'll strip the quote for the folder name part (safer for OS)
            size_for_folder = size.replace('"', '')

            # Condition 1: If folder already follows proper syntax, we don't need to RENAME it
            # But the YAML might still need an update (already handled by get_theme_metadata above)
            if rename_pattern.match(item.name):
                # Ensure the prefix matches the current normalized metadata
                prefix = f"{size_for_folder}_{orientation}_"
                if item.name.startswith(prefix):
                    print(f"Skipping already properly named folder: {item.name}")
                    continue
                else:
                    print(f"Folder {item.name} has incorrect prefix for detected metadata {prefix}. Will rename.")

            new_name = f"{size_for_folder}_{orientation}_{item.name}"
            new_path = item.parent / new_name

            if new_path.exists():
                print(f"Warning: Destination {new_name} already exists. Skipping.")
                continue

            inf_str = " (Inferred)" if inferred else ""
            print(f"{' [DRY RUN]' if dry_run else ''} Renaming: {item.name} -> {new_name}{inf_str}")
            
            if not dry_run:
                try:
                    os.rename(item, new_path)
                except Exception as e:
                    print(f"Error renaming {item.name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename theme folders based on theme.yaml metadata.")
    parser.add_argument("--path", default="res/themes", help="Path to themes directory")
    parser.add_argument("--execute", action="store_true", help="Actually perform the renaming and YAML updates")
    
    args = parser.parse_args()
    
    rename_themes(args.path, dry_run=not args.execute, execute_update=args.execute)
