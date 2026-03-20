"""
TahtLang Language Server Protocol implementation.

Provides IDE features like autocomplete, diagnostics, go-to-definition.
"""

from .server import main, server

__all__ = ["server", "main"]
