#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 提交助手 —— 统一入口

用法:
    不带参数   → 打开图形界面（Qt 版）
    带子命令   → 命令行模式，输出 JSON，供 AI Agent 调用

Git 逻辑全部在 gitcore.py，界面在 gui_qt.py，这里只做分发。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

from gitcore import (DEFAULT_REPO, create_backup, create_branch, delete_branch,
                     discard_all, do_commit, get_branches, get_diff, get_log,
                     get_status, git, init_repo, is_repo, load_config,
                     abort_merge, merge_branch, remember_repo, reset_to,
                     restore_file, revert_commit, save_config, switch_branch)

CLI_HELP = """Git 提交助手（命令行）

常用:
  status                        查看工作区变更
  log -n 20                     查看提交历史
  commit -m "说明" [-p 文件...]  提交（不给 -p 则提交全部）
  diff --type commit --hash H   查看某次提交改了什么
  revert <hash>                 反向撤销（推荐，历史完整保留）
  reset <hash> --mode mixed     硬回退 soft|mixed|hard
  restore <路径>                还原单个文件
  init <目录>                   该目录 git init 并首次提交
  use <目录>                    设为默认仓库
  branch --list|--create|--switch|--delete
  merge <分支>|--abort
  schedule --on|--off --hours N --run-now

全部命令输出 JSON：成功 {"ok": true, ...} 退出码 0；失败 {"ok": false, "error": ...} 退出码 1。
"""


def build_parser():
    p = argparse.ArgumentParser(
        prog="git_helper.py",
        description="Git 提交助手命令行接口（输出 JSON，供 AI Agent 调用）")
    p.add_argument("-C", "--repo", default=None,
                   help="目标仓库路径；省略则用上次打开的仓库")
    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("status", help="查看工作区变更")
    sp = sub.add_parser("log", help="查看提交历史")
    sp.add_argument("-n", type=int, default=20)
    sp = sub.add_parser("commit", help="提交（不指定 paths 则提交全部）")
    sp.add_argument("-m", "--message", default="")
    sp.add_argument("-p", "--paths", nargs="*", default=None)
    sp = sub.add_parser("diff")
    sp.add_argument("--type", default="unstaged", choices=["unstaged", "staged", "commit"])
    sp.add_argument("--hash", default=None)
    sub.add_parser("discard", help="撤销全部未提交改动（危险）")
    sp = sub.add_parser("revert", help="反向撤销某次提交")
    sp.add_argument("hash")
    sp = sub.add_parser("reset", help="回退到某次提交")
    sp.add_argument("hash")
    sp.add_argument("--mode", default="mixed", choices=["soft", "mixed", "hard"])
    sp = sub.add_parser("restore", help="还原单个文件")
    sp.add_argument("path")
    sp.add_argument("--hash", default="HEAD")
    sp = sub.add_parser("schedule", help="定时自动提交")
    sp.add_argument("--on", action="store_true")
    sp.add_argument("--off", action="store_true")
    sp.add_argument("--hours", type=int, default=None)
    sp.add_argument("--run-now", action="store_true")
    sp = sub.add_parser("init", help="在指定目录 git init 并首次提交")
    sp.add_argument("path")
    sp = sub.add_parser("branch", help="分支：列表 / 新建 / 切换 / 删除")
    sp.add_argument("--list", action="store_true")
    sp.add_argument("--create", default=None, metavar="NAME")
    sp.add_argument("--no-switch", action="store_true", help="只创建，不切换")
    sp.add_argument("--switch", default=None, metavar="NAME")
    sp.add_argument("--delete", default=None, metavar="NAME")
    sp.add_argument("--force", action="store_true")
    sp = sub.add_parser("merge", help="合并分支")
    sp.add_argument("name", nargs="?", default=None, help="要合并进来的分支；--abort 时可省略")
    sp.add_argument("--abort", action="store_true", help="中止进行中的合并")
    sp = sub.add_parser("use", help="设定默认仓库，之后所有命令都针对它")
    sp.add_argument("path")
    sub.add_parser("repos", help="列出最近打开过的仓库")
    return p


def cli_main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_parser().parse_args(argv)
    if not args.cmd:
        print(CLI_HELP)
        return 0

    cfg = load_config()
    repo = os.path.normpath(args.repo) if args.repo else (cfg.get("lastRepo") or DEFAULT_REPO)
    out = {}

    def need_repo():
        if not is_repo(repo):
            raise RuntimeError("不是 Git 仓库：%s（可用 init 命令初始化）" % repo)

    try:
        if args.cmd == "init":
            ok, msg = init_repo(os.path.normpath(args.path))
            remember_repo(cfg, os.path.normpath(args.path))
            out = {"ok": ok, "repo": cfg["lastRepo"], "message": msg}

        elif args.cmd == "use":
            path = os.path.normpath(args.path)
            if not os.path.isdir(path):
                raise RuntimeError("目录不存在：%s" % path)
            remember_repo(cfg, path)
            out = {"ok": True, "repo": path, "isRepo": is_repo(path),
                   "message": "默认仓库已设为：%s" % path}

        elif args.cmd == "repos":
            out = {"ok": True, "current": cfg.get("lastRepo", ""),
                   "recent": cfg.get("recentRepos", [])}

        elif args.cmd == "status":
            need_repo()
            branch, files = get_status(repo)
            out = {"ok": True, "repo": repo, "branch": branch,
                   "count": len(files), "files": files}

        elif args.cmd == "log":
            need_repo()
            logs = get_log(repo, args.n)
            out = {"ok": True, "repo": repo, "count": len(logs), "log": logs}

        elif args.cmd == "commit":
            need_repo()
            h, msg = do_commit(repo, args.message, args.paths)
            out = {"ok": True, "committed": bool(h), "hash": h, "message": msg}

        elif args.cmd == "diff":
            need_repo()
            if args.type == "commit" and not args.hash:
                raise RuntimeError("type=commit 时必须提供 --hash")
            out = {"ok": True, "diff": get_diff(repo, args.type, args.hash)}

        elif args.cmd == "discard":
            need_repo()
            backup = discard_all(repo)
            out = {"ok": True, "message": "已撤销所有未提交的改动", "backup": backup}

        elif args.cmd == "revert":
            need_repo()
            out = {"ok": True, "message": revert_commit(repo, args.hash)}

        elif args.cmd == "reset":
            need_repo()
            backup = reset_to(repo, args.hash, args.mode)
            out = {"ok": True,
                   "message": "已回退到 %s（%s）" % (args.hash[:7], args.mode),
                   "backup": backup}

        elif args.cmd == "restore":
            need_repo()
            out = {"ok": True, "message": restore_file(repo, args.path, args.hash)}

        elif args.cmd == "branch":
            need_repo()
            if args.create:
                out = {"ok": True,
                       "message": create_branch(repo, args.create, not args.no_switch)}
            elif args.switch:
                out = {"ok": True, "message": switch_branch(repo, args.switch)}
            elif args.delete:
                out = {"ok": True, "message": delete_branch(repo, args.delete, args.force)}
            else:
                out = {"ok": True, "branches": get_branches(repo)}

        elif args.cmd == "merge":
            need_repo()
            if args.abort:
                out = {"ok": True, "message": abort_merge(repo)}
            elif not args.name:
                raise RuntimeError("缺少要合并的分支名")
            else:
                r = merge_branch(repo, args.name)
                out = {"ok": r["merged"], "merged": r["merged"],
                       "message": r["message"], "conflicts": r["conflicts"]}

        elif args.cmd == "schedule":
            if args.on:
                cfg["autoEnabled"] = True
            if args.off:
                cfg["autoEnabled"] = False
            if args.hours:
                cfg["intervalHours"] = max(1, args.hours)
            if args.run_now:
                cfg["lastRunAt"] = 0
            save_config(cfg)
            h = msg = None
            if args.run_now and is_repo(repo):
                h, msg = do_commit(repo, None, None)
            out = {"ok": True,
                   "config": {"autoEnabled": cfg["autoEnabled"],
                              "intervalHours": cfg["intervalHours"]},
                   "committed": bool(h), "hash": h, "message": msg}
    except Exception as e:
        out = {"ok": False, "error": str(e)}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


def main():
    if len(sys.argv) > 1:
        return cli_main()

    # 无参数 → 图形界面。打包成 console 版 exe 时没有 GUI 意义，给出提示。
    if getattr(sys, "frozen", False):
        print(CLI_HELP)
        return 0

    from gui_qt import run_gui
    cfg = load_config()
    return run_gui(cfg.get("lastRepo") or DEFAULT_REPO)


if __name__ == "__main__":
    sys.exit(main())
