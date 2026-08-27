"""MacroHard Office Word 2003 -- Professional Edition.

Public surface is the window class; the app registry imports it by name.
"""
from .window import MWordWindow

__all__ = ["MWordWindow"]
