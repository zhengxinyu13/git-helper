#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 exe（在装有 PyQt6 + PyInstaller 的 venv 里运行）

产出：
    dist/Git提交助手.exe   图形界面，双击即用，带自定义图标
    dist/GitHelper-CLI.exe 命令行版，供 AI Agent / 脚本调用

改完界面代码后重新打包：
    <venv>\\Scripts\\python.exe build_exe.py
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "app.ico")

COMMON = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile",
    "--distpath", os.path.join(HERE, "dist"),
    "--workpath", os.path.join(HERE, "build"),
    "--specpath", os.path.join(HERE, "build"),
    "--icon", ICON,
    "--add-data", ICON + os.pathsep + ".",   # 图标打进包，运行时从 _MEIPASS 取
    "--exclude-module", "PyQt6.QtWebEngineCore",
    "--exclude-module", "PyQt6.QtWebEngineWidgets",
    "--exclude-module", "PyQt6.QtQuick",
    "--exclude-module", "PyQt6.QtQml",
    "--exclude-module", "PyQt6.Qt3DCore",
    "--exclude-module", "PyQt6.QtMultimedia",
    "--exclude-module", "tkinter",
]

# 第三个元素是 extra 参数。
# CLI 版只在「不带参数且非冻结」时才会 import gui_qt，打包成 exe 后走的是
# 纯命令行分支，所以整包排除 PyQt6 —— 体积能从 34MB 降到 ~10MB。
TARGETS = [
    ("Git提交助手", "gui_main.py", True, []),   # GUI：无控制台
    ("GitHelper-CLI", "git_helper.py", False,
     ["--exclude-module", "PyQt6"]),            # CLI：保留控制台，不带 Qt
]


def run(name, script, windowed, extra=()):
    cmd = list(COMMON) + list(extra) + ["--name", name]
    cmd += ["--windowed" if windowed else "--console"]
    cmd += [os.path.join(HERE, script)]
    print("\n>>> 打包 %s（%s）" % (name, script))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        print("!! %s 打包失败，退出码 %s" % (name, r.returncode))
        return False
    return True


def main():
    if not os.path.exists(ICON):
        print("缺少图标 %s，先跑 make_icon.py" % ICON)
        return 1

    # 清理旧产物。注意：exe 是便携式的，用户配置就存在 dist/config.json，
    # 删掉 dist 会连带着把默认仓库、定时设置一起清空，所以先备份再还原。
    dist = os.path.join(HERE, "dist")
    kept = {}
    for fn in ("config.json",):
        fp = os.path.join(dist, fn)
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                kept[fn] = f.read()

    for d in ("dist", "build"):
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    os.makedirs(dist, exist_ok=True)
    for fn, data in kept.items():
        with open(os.path.join(dist, fn), "wb") as f:
            f.write(data)
        print("已保留 %s" % fn)

    ok = True
    for name, script, windowed, extra in TARGETS:
        ok = run(name, script, windowed, extra) and ok

    print("\n==== 产物 ====")
    dist = os.path.join(HERE, "dist")
    if os.path.isdir(dist):
        for f in sorted(os.listdir(dist)):
            fp = os.path.join(dist, f)
            print("  %-24s %8.1f MB" % (f, os.path.getsize(fp) / 1024 / 1024))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
