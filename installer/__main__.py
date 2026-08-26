#!/usr/bin/env python3
"""Windows XP Setup Wizard -- entry point.

A real standalone installer: it fetches winxp itself from GitHub, so this
directory has no static dependency on the winxp package existing on disk.
Only PyQt6 and the stdlib are required, which is deliberate -- this is the
thing that eventually gets Nuitka-compiled into a native binary shipped via
GitHub Releases, and fewer dependencies means a smaller, more reliable build.

Usage:
    python3 -m installer
    python3 installer/__main__.py    # also works, same entry point
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wizard import main

if __name__ == "__main__":
    main()
