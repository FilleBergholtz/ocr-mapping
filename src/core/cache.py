"""
Cache - Caching av PDF-bilder och extraherad text för performance.
"""

from typing import Optional, Dict, Tuple
from pathlib import Path
from PIL import Image
import hashlib
import pickle
import os
from .logger import get_logger

logger = get_logger()


class Cache:
    """Hanterar caching av PDF-bilder och extraherad text."""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory cache för snabb åtkomst
        self._image_cache: Dict[str, Image.Image] = {}
        self._text_cache: Dict[str, str] = {}
        self._max_memory_items = 50  # Max antal objekt i minnet
    
    def _get_cache_key(self, pdf_path: str, page_num: int = 0, dpi: int = 200) -> str:
        """Skapar en cache-nyckel baserat på PDF-sökväg, sidnummer och DPI."""
        # Använd filens modificeringstid för att detektera ändringar
        try:
            mtime = os.path.getmtime(pdf_path)
            key_data = f"{pdf_path}:{page_num}:{dpi}:{mtime}"
            return hashlib.md5(key_data.encode()).hexdigest()
        except OSError:
            # Om filen inte finns, använd bara sökvägen
            key_data = f"{pdf_path}:{page_num}:{dpi}"
            return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_cached_image(
        self,
        pdf_path: str,
        page_num: int = 0,
        dpi: int = 200
    ) -> Optional[Image.Image]:
        """Hämtar en cachad PDF-bild."""
        cache_key = self._get_cache_key(pdf_path, page_num, dpi)
        
        # Kolla in-memory cache först
        if cache_key in self._image_cache:
            logger.debug(f"Cache hit (memory): {pdf_path} sid {page_num}")
            return self._image_cache[cache_key]
        
        # Kolla disk cache
        cache_file = self.cache_dir / f"image_{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    image = pickle.load(f)
                # Lägg till i minnet om det finns plats
                if len(self._image_cache) < self._max_memory_items:
                    self._image_cache[cache_key] = image
                logger.debug(f"Cache hit (disk): {pdf_path} sid {page_num}")
                return image
            except Exception as e:
                logger.warning(f"Fel vid laddning av cache: {e}")
                # Ta bort korrupt cache-fil
                cache_file.unlink()
        
        return None
    
    def cache_image(
        self,
        pdf_path: str,
        page_num: int,
        image: Image.Image,
        dpi: int = 200
    ):
        """Cachar en PDF-bild."""
        cache_key = self._get_cache_key(pdf_path, page_num, dpi)
        
        # Lägg till i minnet
        if len(self._image_cache) >= self._max_memory_items:
            # Ta bort äldsta (FIFO)
            oldest_key = next(iter(self._image_cache))
            del self._image_cache[oldest_key]
        self._image_cache[cache_key] = image
        
        # Spara till disk
        cache_file = self.cache_dir / f"image_{cache_key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(image, f)
            logger.debug(f"Cachad bild: {pdf_path} sid {page_num}")
        except Exception as e:
            logger.warning(f"Fel vid caching av bild: {e}")
    
    def get_cached_text(self, pdf_path: str) -> Optional[str]:
        """Hämtar cachad extraherad text."""
        cache_key = self._get_cache_key(pdf_path, 0, 0)
        
        # Kolla in-memory cache
        if cache_key in self._text_cache:
            logger.debug(f"Cache hit (memory): text från {pdf_path}")
            return self._text_cache[cache_key]
        
        # Kolla disk cache
        cache_file = self.cache_dir / f"text_{cache_key}.txt"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                # Lägg till i minnet
                if len(self._text_cache) < self._max_memory_items:
                    self._text_cache[cache_key] = text
                logger.debug(f"Cache hit (disk): text från {pdf_path}")
                return text
            except Exception as e:
                logger.warning(f"Fel vid laddning av text-cache: {e}")
                cache_file.unlink()
        
        return None
    
    def cache_text(self, pdf_path: str, text: str):
        """Cachar extraherad text."""
        cache_key = self._get_cache_key(pdf_path, 0, 0)
        
        # Lägg till i minnet
        if len(self._text_cache) >= self._max_memory_items:
            oldest_key = next(iter(self._text_cache))
            del self._text_cache[oldest_key]
        self._text_cache[cache_key] = text
        
        # Spara till disk
        cache_file = self.cache_dir / f"text_{cache_key}.txt"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.debug(f"Cachad text: {pdf_path}")
        except Exception as e:
            logger.warning(f"Fel vid caching av text: {e}")
    
    def clear_cache(self):
        """Rensar all cache."""
        self._image_cache.clear()
        self._text_cache.clear()
        
        # Rensa disk cache
        for cache_file in self.cache_dir.glob("*"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Fel vid borttagning av cache-fil {cache_file}: {e}")
        
        logger.info("Cache rensad")


# Global cache-instans
_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """Hämtar global cache-instans."""
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache
