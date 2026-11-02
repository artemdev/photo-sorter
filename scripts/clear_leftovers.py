#!/usr/bin/env python3
"""Kept so older commands and the Claude Code agent keep working; see photo_sorter/leftovers.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from photo_sorter.leftovers import main  # noqa: E402

main()
