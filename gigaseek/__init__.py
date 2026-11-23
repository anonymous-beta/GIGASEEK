"""
GIGASEEK OSINT Framework
Creator: Anonymous-beta
"""

__version__ = "1.0.0"
__author__ = "Anonymous-beta"
__description__ = "Demon-themed OSINT framework with super crawler capabilities"

from .core.engine import GigaseekEngine
from .config import Config

__all__ = ["GigaseekEngine", "Config", "__version__", "__author__"]
