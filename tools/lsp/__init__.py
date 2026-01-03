"""
TahtLang Language Server Protocol implementation.

Provides IDE features like autocomplete, diagnostics, go-to-definition.
"""

from .server import server, main

__all__ = ['server', 'main']
