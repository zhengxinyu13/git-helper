#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图形界面入口（PyInstaller 用这个文件打 GUI 版 exe）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitcore import DEFAULT_REPO, load_config
from gui_qt import run_gui

if __name__ == "__main__":
    cfg = load_config()
    sys.exit(run_gui(cfg.get("lastRepo") or DEFAULT_REPO))
