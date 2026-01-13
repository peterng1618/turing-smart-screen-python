# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Dict, List, Type, Optional
from theme_editor.models.element import (
    ElementType, BackgroundImageElement, BackgroundVideoElement,
    TextElement, DynamicTextElement, ImageElement, IconElement, ThemeInfoElement
)
from theme_editor.panels.property_sections.base import PropertySection
from theme_editor.panels.property_sections.identity_section import IdentitySection
from theme_editor.panels.property_sections.transform_section import TransformSection
from theme_editor.panels.property_sections.appearance_section import AppearanceSection
from theme_editor.panels.property_sections.outline_section import OutlineSection
from theme_editor.panels.property_sections.shadow_section import ShadowSection
from theme_editor.panels.property_sections.typography_section import TypographySection
from theme_editor.panels.property_sections.image_section import ImageSection
from theme_editor.panels.property_sections.icon_section import IconSection
from theme_editor.panels.property_sections.sensor_section import SensorSection
from theme_editor.panels.property_sections.background_section import BackgroundSection
from theme_editor.panels.property_sections.theme_info_section import ThemeInfoSection

# Using None as key for common sections
SECTION_REGISTRY: Dict[Optional[ElementType], List[Type[PropertySection]]] = {
    None: [IdentitySection, TransformSection, AppearanceSection, ShadowSection],
    ElementType.RECTANGLE: [OutlineSection],
    ElementType.CIRCLE: [OutlineSection],
    ElementType.TRIANGLE: [OutlineSection],
    ElementType.LINE: [OutlineSection],
    ElementType.IMAGE: [ImageSection, OutlineSection],
    ElementType.TEXT: [TypographySection],
    ElementType.DYNAMIC_TEXT: [TypographySection, SensorSection],
    ElementType.ICON: [IconSection],
    ElementType.BACKGROUND_IMAGE: [BackgroundSection],
    ElementType.BACKGROUND_VIDEO: [BackgroundSection],
    ElementType.THEME_INFO: [ThemeInfoSection],
}

def get_sections_for_element_type(element_type: ElementType) -> List[Type[PropertySection]]:
    """Get the list of property sections for a given element type."""
    sections = SECTION_REGISTRY.get(None, []).copy()
    if element_type in SECTION_REGISTRY:
        sections.extend(SECTION_REGISTRY[element_type])
    return sections
