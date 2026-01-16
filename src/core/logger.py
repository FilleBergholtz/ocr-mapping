"""
Logger - Centraliserad loggning för applikationen.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "ocr_mapping",
    log_file: Optional[str] = None,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Skapar och konfigurerar en logger.
    
    Args:
        name: Logger-namn
        log_file: Sökväg till loggfil (valfritt)
        level: Loggningnivå (default: INFO)
    
    Returns:
        Konfigurerad logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Undvik att lägga till handlers flera gånger
    if logger.handlers:
        return logger
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (om angivet)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Global logger-instans
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Hämtar global logger-instans."""
    global _logger
    if _logger is None:
        # Skapa logs-katalog om den inte finns
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        _logger = setup_logger(
            log_file=str(logs_dir / "app.log"),
            level=logging.INFO
        )
    return _logger
