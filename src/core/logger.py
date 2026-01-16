"""
Logger - Centraliserad loggning för applikationen.

Förbättrad loggning med strukturerad information, rotation och helper-metoder
för vanliga loggings-scenarion.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import traceback


def setup_logger(
    name: str = "ocr_mapping",
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console_level: Optional[int] = None,
    file_level: Optional[int] = None
) -> logging.Logger:
    """
    Skapar och konfigurerar en logger med förbättrad funktionalitet.
    
    Logger stödjer:
    - Strukturerad loggning med extra fields
    - Rotation av log-filer (max 10MB, 5 backups)
    - Skillnad mellan console (INFO) och fil (DEBUG)
    - Detaljerade formatters med kontext
    
    Args:
        name: Logger-namn
        log_file: Sökväg till loggfil (valfritt)
        level: Standard loggningnivå (default: INFO)
        console_level: Loggningnivå för console (default: INFO)
        file_level: Loggningnivå för fil (default: DEBUG)
    
    Returns:
        Konfigurerad logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Sätt till DEBUG för att tillåta filtrering per handler
    
    # Undvik att lägga till handlers flera gånger
    if logger.handlers:
        return logger
    
    # Console formatter (enklare format)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File formatter (mer detaljerad med fil och funktion)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (INFO-nivå för att undvika spam)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level or level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler med rotation (om angivet)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # RotatingFileHandler: max 10MB per fil, 5 backups
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(file_level or logging.DEBUG)  # DEBUG för fil för mer detaljer
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# Global logger-instans
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """
    Hämtar global logger-instans.
    
    Logger loggar till både console (INFO) och fil (DEBUG) med rotation.
    Log-filnamn inkluderar datum för lättare hantering.
    """
    global _logger
    if _logger is None:
        # Skapa logs-katalog om den inte finns
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Log-filnamn med datum (app-2026-01-16.log)
        log_filename = f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
        log_file = str(logs_dir / log_filename)
        
        _logger = setup_logger(
            log_file=log_file,
            level=logging.INFO,
            console_level=logging.INFO,  # Console: INFO och högre
            file_level=logging.DEBUG     # Fil: DEBUG och högre
        )
    return _logger


def log_error_with_context(
    logger: logging.Logger,
    error: Exception,
    context: Dict[str, Any],
    message: str = "Error occurred"
) -> None:
    """
    Loggar ett fel med kontextuell information och stack trace.
    
    Args:
        logger: Logger-instans
        error: Exception som inträffade
        context: Dict med kontextuell information (t.ex. filnamn, funktion, etc.)
        message: Meddelande att logga (default: "Error occurred")
    """
    # Bygg strukturerat meddelande med kontext
    context_str = ", ".join(f"{k}={v}" for k, v in context.items())
    full_message = f"{message} - Context: {context_str}"
    
    # Logga med stack trace
    logger.error(full_message, exc_info=error)


def log_function_call(
    logger: logging.Logger,
    func_name: str,
    args: tuple = (),
    kwargs: Dict[str, Any] = None
) -> None:
    """
    Loggar funktionsanrop med argument för debugging.
    
    Args:
        logger: Logger-instans
        func_name: Funktionsnamn
        args: Positionella argument (tuple)
        kwargs: Nyckelordsargument (dict)
    """
    if kwargs is None:
        kwargs = {}
    
    # Bygg argumentsträng (begränsa längd för långa värden)
    args_str = ", ".join(str(arg)[:100] for arg in args[:5])  # Max 5 args, 100 chars each
    kwargs_str = ", ".join(f"{k}={str(v)[:100]}" for k, v in list(kwargs.items())[:5])
    
    call_str = f"{func_name}({args_str}"
    if kwargs_str:
        call_str += f", {kwargs_str}"
    call_str += ")"
    
    logger.debug(f"Calling: {call_str}")


def log_performance(
    logger: logging.Logger,
    operation: str,
    duration: float,
    context: Dict[str, Any] = None
) -> None:
    """
    Loggar prestandamätning för en operation.
    
    Args:
        logger: Logger-instans
        operation: Beskrivning av operationen
        duration: Varaktighet i sekunder
        context: Ytterligare kontextuell information (valfritt)
    """
    context_str = ""
    if context:
        context_str = f" - Context: {', '.join(f'{k}={v}' for k, v in context.items())}"
    
    # Formatera varaktighet (visa ms om < 1s, annars sekunder)
    if duration < 1.0:
        duration_str = f"{duration * 1000:.1f}ms"
    else:
        duration_str = f"{duration:.2f}s"
    
    logger.info(f"Performance: {operation} took {duration_str}{context_str}")
