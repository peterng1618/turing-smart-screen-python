
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from theme_editor.models.element import create_element, ElementType, Outline

# Create dummy app
app = QApplication(sys.argv)

def test_outline_save():
    # 1. Create a Rectangle with an Outline
    rect = create_element(ElementType.RECTANGLE, name="RectWithOutline", x=10, y=10)
    rect.outline = Outline(width=5, color=(255, 0, 0, 255), dash_array=[5, 5])
    
    print(f"Created Rect: {rect}")
    print(f"Outline present: {rect.outline is not None}")
    
    # 2. Serialize
    data = rect.to_dict()
    print(f"Serialized Data: {data}")
    
    # 3. Check for outline in data
    if "outline" in data:
        print("SUCCESS: Outline found in to_dict output.")
        print(data["outline"])
    else:
        print("FAILURE: Outline NOT found in to_dict output.")

    # 4. Test Round Trip (loading)
    # We need to simulate how the model loads. The model usually interprets the dict.
    # But Element.from_dict is what we should test.
    # Note: RectangleElement.from_dict is NOT explicitly defined in element.py! 
    # The base Element.from_dict is used, or maybe create_element is effectively used?
    # Let's check if RectangleElement has from_dict.
    
    from theme_editor.models.element import RectangleElement
    
    # If RectangleElement doesn't override from_dict, the base one is used.
    # The base one in lines 130-155 of element.py DOES NOT handle 'outline'.
    # This might be the issue if the system relies on from_dict for loading!
    
    # However, let's see how create_element works, maybe the loader uses that?
    # Because valid loading usually involves iterating keys and setting them.
    
    # Let's try to load it back using create_element logic simulation
    # (Checking if create_element handles 'outline' dict)
    
    rect_loaded = create_element(ElementType.RECTANGLE, **data)
    print(f"Loaded Rect Outline: {rect_loaded.outline}")
    
    if rect_loaded.outline:
        print("SUCCESS: Outline persisted after reload via create_element.")
    else:
        print("FAILURE: Outline lost after reload via create_element.")

if __name__ == "__main__":
    test_outline_save()
