import os
import sys
from PIL import Image

# Add root to path
sys.path.append(os.getcwd())

from library.ui_renderer import UiRenderer
import yaml

def render_theme():
    theme_path = os.path.join("res", "themes", "NZXT_color_ui")
    yaml_path = os.path.join(theme_path, "theme.yaml")
    
    print(f"Loading {yaml_path}...")
    with open(yaml_path, 'r') as f:
        theme_data = yaml.safe_load(f)
        
    renderer = UiRenderer(theme_data, theme_path)
    print("Generating overlay...")
    overlay = renderer.generate_overlay()
    
    output_path = os.path.join(theme_path, "preview.png")
    overlay.save(output_path)
    print(f"Saved render to {output_path}")
    print(f"Size: {overlay.size}")

if __name__ == "__main__":
    render_theme()
