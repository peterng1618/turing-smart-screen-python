import os
import requests
import hashlib
import json
import re
from library.log import logger
from library import config

class FontManager:
    """Manages downloading and caching of external fonts and icon metadata."""
    
    METADATA_URL = "https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/metadata/icons.json"
    
    CDN_FONTS = {
        'solid': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.ttf',
        'brands': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.ttf',
        'regular': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.ttf'
    }

    def __init__(self):
        self.cache_dir = os.path.join(config.FONTS_DIR, 'cache')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.metadata_path = os.path.join(self.cache_dir, 'icons.json')
        self._metadata = None
            
    def _load_metadata(self):
        """Lazy load and cache Font Awesome metadata."""
        if self._metadata: return self._metadata
        
        # If the file exists but we want to ensure we have the right version, 
        # normally we'd check headers, but here we'll just check if it's empty or invalid.
        if not os.path.exists(self.metadata_path) or os.path.getsize(self.metadata_path) < 1000:
            try:
                logger.info("Downloading Font Awesome 6.x metadata...")
                r = requests.get(self.METADATA_URL, timeout=15)
                r.raise_for_status()
                with open(self.metadata_path, 'w', encoding='utf-8') as f:
                    f.write(r.text)
            except Exception as e:
                logger.error(f"Failed to download icon metadata: {e}")
                return {}
        
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self._metadata = json.load(f)
            return self._metadata
        except Exception as e:
            logger.error(f"Failed to parse icon metadata: {e}")
            # If parse fails, delete the file so it retries next time
            if os.path.exists(self.metadata_path): os.remove(self.metadata_path)
            return {}

    def resolve_icon_metadata(self, icon_val):
        """
        Resolve an icon name or URL to its unicode and recommended font link.
        
        :param icon_val: "house", "f015", or FA URL.
        :return: (unicode_hex, font_link)
        """
        # 1. Check if it's a URL
        is_url = 'fontawesome.com/icons/' in icon_val
        name = icon_val
        style_hint = None
        
        if is_url:
            # Extract name: https://fontawesome.com/icons/arrows-to-circle?f=classic&s=solid
            # Match until ? # or end
            match = re.search(r'icons/([^/?#\s]+)', icon_val)
            if match:
                name = match.group(1)
            
            # Extract parameters using simple logic
            if 'f=brands' in icon_val: style_hint = 'brands'
            if 's=solid' in icon_val: style_hint = 'solid'
            elif 's=regular' in icon_val: style_hint = 'regular'
            elif 's=light' in icon_val or 's=thin' in icon_val:
                # We don't have free TTFs for light/thin usually on CDNJS
                # regular is closer than solid
                style_hint = 'regular'

        # 2. Lookup in metadata
        meta = self._load_metadata()
        icon_data = meta.get(name)
        
        if not icon_data:
            if is_url:
                # If lookup failed for a URL, definitely don't return the URL as unicode
                return None, None
            # Maybe it's already a hex or a direct char
            return icon_val, None
            
        unicode_hex = icon_data.get('unicode')
        available_styles = icon_data.get('styles', [])
        
        # Decide which font to use
        # If it's a brand icon, use brands font regardless of style hint usually
        if 'brands' in available_styles:
            return unicode_hex, self.CDN_FONTS.get('brands')
            
        selected_style = 'solid' # Default
        if style_hint and style_hint in available_styles:
            selected_style = style_hint
        elif 'solid' in available_styles:
            selected_style = 'solid'
        elif 'regular' in available_styles:
            selected_style = 'regular'
        elif available_styles:
            selected_style = available_styles[0]
            
        return unicode_hex, self.CDN_FONTS.get(selected_style)

    def get_font_path(self, url):
        """
        Get the local path for a font URL. Downloads if not cached.
        """
        if not url: return None
            
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = os.path.splitext(url.split('?')[0])[1] or '.ttf'
        filename = f"{url_hash}{ext}"
        local_path = os.path.join(self.cache_dir, filename)
        
        if os.path.exists(local_path):
            return local_path
            
        try:
            logger.info(f"Downloading font from {url}...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return local_path
        except Exception as e:
            logger.error(f"Failed to download font from {url}: {e}")
            return None

# Global instance
font_manager = FontManager()
