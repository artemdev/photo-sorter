#!/usr/bin/env python3
"""Kept so older commands and the Claude Code agent keep working; see photo_sorter/importer.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from photo_sorter.importer import main  # noqa: E402

main()
