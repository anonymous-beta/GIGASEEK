"""
GIGASEEK Logging System
Structured logging with demon aesthetic
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console
from .colors import demon_theme


def setup_logger(
    name: str = "gigaseek",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    rich_output: bool = True
) -> logging.Logger:
    """Setup and configure GIGASEEK logger"""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Rich console handler
    if rich_output:
        console = Console(theme=demon_theme, stderr=True)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True
        )
        rich_handler.setLevel(level)
        logger.addHandler(rich_handler)
    else:
        # Standard handler
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(level)
        logger.addHandler(stream_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    
    return logger


class DemonLogger:
    """Custom logger with demon-themed output"""
    
    def __init__(self, name: str = "gigaseek"):
        self.logger = logging.getLogger(name)
        self.console = Console(theme=demon_theme)
    
    def info(self, msg: str, *args, **kwargs):
        self.logger.info(f"[demon]⛧[/demon] {msg}", *args, **kwargs)
    
    def success(self, msg: str, *args, **kwargs):
        self.logger.info(f"[success]✓[/success] {msg}", *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(f"[warning]⚠[/warning] {msg}", *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self.logger.error(f"[error]✗[/error] {msg}", *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(f"[dim]◆[/dim] {msg}", *args, **kwargs)
    
    def crawl(self, msg: str, *args, **kwargs):
        self.logger.info(f"[fire]🕸[/fire] {msg}", *args, **kwargs)
    
    def find(self, msg: str, *args, **kwargs):
        self.logger.info(f"[highlight]⛧ FOUND ⛧[/highlight] {msg}", *args, **kwargs)
