#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 提交助手 —— 核心逻辑层（纯标准库，无任何 GUI 依赖）

这一层被两处共用：
    - 命令行接口（git_helper.py），供 AI Agent 调用
    - Qt 图形界面（gui_qt.py）

改这里等于同时改两边，不要把 git 逻辑复制到 GUI 里。
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime

# ---------------------------------------------------------------- 路径
# 打成单文件 exe 后，__file__ 指向 PyInstaller 的临时解压目录，程序一退出就没了。
# 所以：配置/日志这类要持久化的东西放 exe 所在目录；图标等只读资源从解压目录取。
def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _res_dir():
    base = getattr(sys, "_MEIPASS", None)
    return base or os.path.dirname(os.path.abspath(__file__))


def _user_dir():
    """个人配置目录：%APPDATA%\\Git 提交助手（仅打包后的 exe 用）。

    为什么不放程序目录：程序目录会被安装/卸载/覆盖安装反复改写，
    配置放那儿迟早被带走（用户反馈过：升级后最近仓库记录和定时设置全没了）。
    挪到用户目录后，升级、覆盖安装、卸载都不会碰它 —— 重装回来设置还在。

    源码模式返回 None（继续用源码目录，保持「拎着文件夹就能跑」的便携性）。
    """
    if not getattr(sys, "frozen", False):
        return None
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    try:
        d = os.path.join(base, "Git 提交助手")
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".writetest")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
        return d
    except Exception:
        return None          # 用户目录不可写就回退到程序目录，别因此崩掉


def _is_self_dir(d):
    """这个目录是不是「Git 提交助手自己的源码目录」。

    助手现在可以整个搬离工作区（比如放到 ~/Desktop/git-helper 并自建仓库），
    这时往上找仓库会先撞见它自己 —— 得跳过，否则默认仓库变成助手源码而不是用户的工作区。
    """
    if os.path.isfile(os.path.join(d, "gitcore.py")):
        return True
    return os.path.basename(d) == "git-helper"


def _guess_default_repo():
    """没配置过仓库时用哪个目录。

    从起点往上找最近的 Git 仓库，最多找 5 层 ——
    这样 exe 放在 git-helper/dist/ 或工作区任意子目录都能认出来；
    遇到助手自己的目录就跳过；找不到就回落到起点，让用户手动选一次。

    起点：源码模式是 git-helper/ 的上一级（工作区），exe 模式是 exe 所在目录。
    """
    d = os.path.dirname(HERE) if not getattr(sys, "frozen", False) else HERE
    for _ in range(5):
        if os.path.isdir(os.path.join(d, ".git")) and not _is_self_dir(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return HERE


HERE = _app_dir()          # 可写：程序所在目录
RES = _res_dir()           # 只读资源：app.ico
USER_DIR = _user_dir()     # 个人配置目录（打包后为 %APPDATA%，源码模式为 None）
DEFAULT_REPO = _guess_default_repo()
# 配置与日志一律落在用户目录（拿不到就退回程序目录）
_CONFIG_HOME = USER_DIR or HERE
CONFIG_PATH = os.path.join(_CONFIG_HOME, "config.json")
ERROR_LOG = os.path.join(_CONFIG_HOME, "error.log")
CREDIT = "This software was written by Grayson Zheng."


def _migrate_legacy_config():
    """把旧版留在程序目录里的 config.json 搬到用户目录（只搬一次）。

    老版本（<=1.0.3）把配置写在 exe 旁边。升级到新版后如果不管，
    用户会发现"最近仓库记录没了"，所以启动时静默搬一次。
    """
    if not USER_DIR:
        return
    legacy = os.path.join(HERE, "config.json")
    if not os.path.isfile(legacy) or os.path.isfile(CONFIG_PATH):
        return
    try:
        shutil.copy2(legacy, CONFIG_PATH)
    except Exception:
        pass


_migrate_legacy_config()

DEFAULT_CONFIG = {
    "autoEnabled": True,
    "intervalHours": 1,
    "lastRunAt": 0,          # 毫秒时间戳
    "maxLog": 200,
    "lastRepo": "",
    "recentRepos": [],
    # 背景毛玻璃。注意：Windows 的 DWM 亚克力接口（SetWindowCompositionAttribute）
    # 会让窗口内容不可见、且截图/录屏得到空白，Qt 版改用「抓桌面 + 模糊」实现，
    # 不再走那个接口。这里只是开这个自绘效果的开关。
    "blurBackground": True,
    # 玻璃浓度档位：通透 / 标准 / 沉稳 / 实底。壁纸花、累眼时调沉。
    "glassLevel": "沉稳",
    # 自动提交时跳过「正在写入」的文件（Office 锁文件 / 刚改过还没稳定 /
    # 云盘正在同步）。关掉就回到原来「add -A 全交」的行为。
    "skipUnstable": True,
    # 文件改完后多久算「稳定」。云盘上传 + Office 保存都可能要几十秒。
    "stableSeconds": 120,
    # 已经提示过「此仓库在云盘目录里」的路径，避免每次启动都弹一次。
    "cloudWarnedFor": "",
}


# ---------------------------------------------------------------- 云盘目录
# 仓库落在云同步目录里时，git 每写一次 .git 都要触发一轮同步，
# 云盘也可能在 git 读取的同一瞬间改写工作区文件 —— 两边抢同一批文件。
# 这里只做「识别 + 提醒 + 提交时保守处理」，不去动用户的云盘设置。
CLOUD_MARKERS = (
    ("坚果云", "坚果云"),
    ("nutstore", "坚果云"),
    ("onedrive", "OneDrive"),
    ("dropbox", "Dropbox"),
    ("icloud", "iCloud"),
    ("百度网盘", "百度网盘"),
    ("baidunetdisk", "百度网盘"),
    ("google drive", "Google Drive"),
    ("seafile", "Seafile"),
    ("syncthing", "Syncthing"),
    ("群晖", "群晖 Drive"),
)


def is_cloud_dir(path):
    """判断目录是否在已知云同步盘里。返回云盘名称，不在则返回 None。"""
    if not path:
        return None
    low = os.path.abspath(path).lower()
    for key, label in CLOUD_MARKERS:
        if key.lower() in low:
            return label
    return None

STATUS_LABEL = {
    "??": "新增", "A ": "新增", "AM": "新增",
    "M ": "修改", " M": "修改", "MM": "修改",
    "D ": "删除", " D": "删除",
    "R ": "重命名", "T ": "类型变更",
}


# ---------------------------------------------------------------- 基础工具
def log_exception(exc, val, tb):
    """GUI 进程没有控制台，异常一律落到 error.log"""
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            traceback.print_exception(exc, val, tb, file=f)
            f.write("-" * 70 + "\n")
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass          # exe 放在只读目录时不能因为存配置失败就崩掉


def remember_repo(cfg, path):
    cfg["lastRepo"] = path
    rec = [p for p in cfg.get("recentRepos", []) if p != path]
    rec.insert(0, path)
    cfg["recentRepos"] = rec[:10]
    save_config(cfg)


# ---------------------------------------------------------------- git 封装
# 无控制台的 GUI 进程若不指定 CREATE_NO_WINDOW，每次调用 git.exe
# 都会被 Windows 分配一个新控制台窗口 → 屏幕上不停闪 cmd 黑框
CREATE_NO_WINDOW = 0x08000000


def _run(repo, *args):
    cmd = ["git", "-c", "core.quotepath=false", "-c", "core.safecrlf=false", *args]
    kwargs = {}
    if platform.system() == "Windows":
        # 双保险：CREATE_NO_WINDOW 抑制控制台分配，
        # STARTF_USESHOWWINDOW + SW_HIDE 抑制窗口显示
        kwargs["creationflags"] = CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    return subprocess.run(
        cmd, cwd=repo, capture_output=True,
        text=True, encoding="utf-8", errors="replace", **kwargs,
    )


def git(repo, *args, check=True):
    p = _run(repo, *args)
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "git 执行失败").strip())
    return p.stdout


def is_repo(path):
    return bool(path) and os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git"))


def init_repo(path):
    """在一个普通文件夹里初始化仓库，并做首次提交。返回 (ok, 说明)"""
    if not path:
        raise RuntimeError("路径为空")
    if is_repo(path):
        raise RuntimeError("该目录已经是 Git 仓库：%s" % path)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "add", "-A")
    if has_staged(path):
        git(path, "commit", "-m", "chore: 初始化仓库，纳入现有文件")
        h = git(path, "rev-parse", "HEAD").strip()
        return True, "已初始化并提交首次 commit %s" % h[:7]
    return True, "已初始化（目录为空，暂无文件可提交）"


def has_staged(repo):
    # diff --quiet：有差异时退出码为 1
    return _run(repo, "diff", "--cached", "--quiet").returncode != 0


def get_status(repo):
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or "—"
    out = git(repo, "status", "--porcelain=v1", "-uall", check=False)
    files = []
    for line in out.splitlines():
        if len(line.strip()) < 3:
            continue
        xy = line[:2]
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append({"status": STATUS_LABEL.get(xy, "变更"), "path": path})
    return branch, files


def get_branches(repo):
    sep = "\x1f"
    out = git(repo, "branch", "--list", "--format=%(refname:short)" + sep + "%(HEAD)",
              "--sort=-committerdate", check=False)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        name, _, head = line.partition(sep)
        rows.append({"name": name.strip(), "current": head.strip() == "*"})
    return rows


def create_branch(repo, name, switch=True):
    if switch:
        git(repo, "checkout", "-b", name)
        return "已创建并切换到分支 %s" % name
    git(repo, "branch", name)
    return "已创建分支 %s（未切换）" % name


def switch_branch(repo, name):
    git(repo, "checkout", name)
    return "已切换到分支 %s" % name


def delete_branch(repo, name, force=False):
    git(repo, "branch", "-d" if not force else "-D", name)
    return "已删除分支 %s" % name


def merge_branch(repo, name):
    """返回 dict：merged / message / conflicts"""
    p = _run(repo, "merge", "--no-edit", name)
    if p.returncode == 0:
        return {"merged": True, "message": (p.stdout or "已合并 %s" % name).strip(),
                "conflicts": []}
    conflicts = []
    for line in git(repo, "status", "--porcelain", check=False).splitlines():
        if len(line) >= 2 and ("U" in line[:2] or line[:2] in ("AA", "DD")):
            conflicts.append(line[3:].strip())
    return {"merged": False,
            "message": (p.stderr or p.stdout or "合并未完成").strip(),
            "conflicts": conflicts}


def abort_merge(repo):
    p = _run(repo, "merge", "--abort")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "没有进行中的合并").strip())
    return "已中止合并，恢复到合并前的状态"


def get_log(repo, limit=200):
    sep = "\x1f"
    fmt = sep.join(["%H", "%h", "%an", "%ad", "%s"])
    out = git(repo, "log", "--pretty=format:" + fmt,
              "--date=format:%Y-%m-%d %H:%M:%S", "-n", str(limit), check=False)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split(sep)
        if len(parts) < 5:
            continue
        rows.append({"hash": parts[0], "short": parts[1], "author": parts[2],
                     "date": parts[3], "subject": parts[4]})
    return rows


def unstable_reason(repo, rel, stable_seconds=None):
    """这个文件现在能不能安全提交。返回 None = 可以，否则返回跳过原因。

    三种情况不交：
      1. Office/WPS 打开文档时生成的 ~$xxx 锁文件（临时文件，本就不该入库）；
      2. 同目录里有 ~$ 开头、名字能对上的锁文件 —— 说明文档正开着，
         用户可能还在改，此时提交的是半成品；
      3. 文件最后修改时间距今太近（默认 120 秒）—— 云盘可能还没同步完，
         也可能用户下一秒还要保存。
    """
    base = os.path.basename(rel)
    if base.startswith("~$"):
        return "Office 临时锁文件"
    secs = DEFAULT_CONFIG["stableSeconds"] if stable_seconds is None else stable_seconds
    full = os.path.join(repo, rel)
    # 已删除的文件不在磁盘上，删掉是明确动作，不该被"稳定性"拦住
    if not os.path.exists(full):
        return None
    try:
        age = time.time() - os.path.getmtime(full)
    except OSError:
        return None
    if age < secs:
        return "刚改动 %d 秒" % int(age)
    d = os.path.dirname(full) or repo
    try:
        for n in os.listdir(d):
            if n.startswith("~$") and base.startswith(n[2:]):
                return "文件正被 Office 打开"
    except OSError:
        pass
    return None


def filter_stable(repo, files, stable_seconds=None):
    """把待提交列表拆成「可交」和「跳过」两部分。"""
    kept, skipped = [], []
    for f in files:
        reason = unstable_reason(repo, f["path"], stable_seconds)
        if reason:
            skipped.append({"status": f["status"], "path": f["path"],
                            "reason": reason})
        else:
            kept.append(f)
    return kept, skipped


def _add_paths(repo, paths, batch=200):
    """分批 add，避免文件过多时命令行超长（Windows 上限约 3.2 万字符）。"""
    for i in range(0, len(paths), batch):
        git(repo, "add", "-A", "--", *paths[i:i + batch])


def do_commit(repo, message=None, paths=None, skip_unstable=True):
    """提交。返回 (hash, 提交说明, 被跳过的文件列表)。

    hash 为 None 表示这次没提交成（无变更，或变更都还在写入中）。
    """
    _, files = get_status(repo)
    if paths:
        wanted = set(paths)
        files = [f for f in files if f["path"] in wanted]

    kept, skipped = files, []
    if skip_unstable:
        kept, skipped = filter_stable(repo, files)

    if not kept:
        if skipped:
            return None, "%d 个文件仍在写入中，本次跳过" % len(skipped), skipped
        return None, "没有需要提交的变更", skipped

    _add_paths(repo, [f["path"] for f in kept])
    if not has_staged(repo):
        return None, "没有需要提交的变更", skipped
    msg = (message or "").strip() or "chore: 自动提交 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    git(repo, "commit", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip(), msg, skipped


def create_backup(repo):
    name = "backup/before-rollback-" + datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        git(repo, "branch", name)
        return name
    except Exception:
        return None


def get_diff(repo, kind="unstaged", hash_=None):
    if kind == "commit" and hash_:
        return git(repo, "show", "--stat", "--patch", hash_, check=False)
    if kind == "staged":
        return git(repo, "diff", "--cached", check=False)
    return git(repo, "diff", check=False)


def restore_file(repo, path, ref="HEAD"):
    try:
        git(repo, "checkout", ref, "--", path)
    except Exception:
        git(repo, "clean", "-fd", "--", path)      # 未跟踪的新文件 → 删除
    return "已还原 " + path


def discard_all(repo):
    backup = create_backup(repo)
    git(repo, "reset", "--hard", "HEAD")
    git(repo, "clean", "-fd")
    return backup


def revert_commit(repo, hash_):
    git(repo, "revert", "--no-edit", hash_)
    return "已生成反向提交，撤销了 " + hash_[:7]


def reset_to(repo, hash_, mode="mixed"):
    backup = create_backup(repo)
    git(repo, "reset", "--" + mode, hash_)
    return backup
