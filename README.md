# Git 提交助手

Windows 上的 Git 图形化小工具：毛玻璃界面，能一键提交、按文件回退、管理分支，
也提供命令行接口供 AI Agent 或脚本调用。

> This software was written by Grayson Zheng.

## 前置条件

本工具是 `git` 的图形外壳，**必须先安装 Git for Windows**：<https://git-scm.com/download/win>
（一路下一步即可）。没装 Git 的话所有功能都不可用，安装程序会给出提示。

## 安装

两种方式，任选其一：

1. **安装包**（推荐）：下载 `Git提交助手-Setup-<版本>.exe` 双击运行，按向导走完即可。
   卸载走「控制面板 → 程序和功能」，或用安装目录下的 `unins000.exe`。
2. **免安装**：直接取 `dist/Git提交助手.exe` 双击运行，不需要装 Python。
   程序配置（默认仓库、自动提交开关、玻璃浓度）保存在
   `%APPDATA%\Git 提交助手\config.json`，升级或重装都不会丢。

## 功能

- **提交**：勾选文件后提交，或定时自动提交（默认 1 小时，可在界面开关）
- **提交保护**：默认跳过 `~$` 锁文件、正被 Office 打开的文档、2 分钟内刚改过的文件；
  按 `Office 锁文件 / 临时文件 / 云盘冲突副本` 等 14 条默认规则过滤，
  点「忽略规则」可在已有仓库里一键补齐 `.gitignore`
- **云盘提示**：仓库落在坚果云 / OneDrive / Dropbox 等同步目录里时会提醒，
  并自动开启上面的提交保护
- **后台常驻**：关闭窗口默认缩到系统托盘，定时自动提交继续生效；
  可选开机自启（写在「当前用户」启动项里，不需要管理员权限）
- **回退**：反向撤销某个 commit、回退到指定 commit（soft / mixed / hard）、单文件还原、
  撤销全部未提交改动 —— 破坏性操作前会自动创建 `backup/before-rollback-<时间戳>` 分支
- **分支**：新建 / 切换 / 合并（带冲突检测）/ 删除 / 中止合并
- **多仓库**：任意目录都能用，输入路径或浏览选择；目录还不是仓库时可一键
  `git init` 并完成首次提交；记住最近 10 个仓库
- **界面**：真玻璃拟态（抓桌面后模糊作为背景）、无边框、自绘标题栏

## 命令行（给 AI / 脚本用）

`GitHelper-CLI.exe` 或源码模式下的 `git_helper.py`，输入输出都是 JSON，
成功退出码 0、失败 1：

```bash
GitHelper-CLI.exe status                      # 查看工作区变更
GitHelper-CLI.exe log -n 20                   # 查看提交历史
GitHelper-CLI.exe commit -m "说明" [-p 文件]   # 提交（-p 指定文件，省略则全部）
GitHelper-CLI.exe revert <hash>               # 反向撤销某个提交
GitHelper-CLI.exe reset <hash> --mode mixed   # 回退到某个提交
GitHelper-CLI.exe branch --list               # 分支列表
GitHelper-CLI.exe branch --create feature/x   # 建分支并切换
GitHelper-CLI.exe merge feature/x             # 合并分支
GitHelper-CLI.exe init <路径>                 # 初始化仓库并首次提交
GitHelper-CLI.exe ignore                      # 生成/补齐 .gitignore 默认忽略规则
GitHelper-CLI.exe use <路径>                  # 设为默认仓库
GitHelper-CLI.exe -C <路径> status            # 临时对某个仓库操作
```

## 从源码构建

打包环境需要 Python + PyQt6 + PyInstaller + Pillow：

```bash
python make_icon.py        # 生成 app.ico（已有则跳过）
python build_exe.py        # 产出 dist/Git提交助手.exe 与 dist/GitHelper-CLI.exe
```

安装包用 Inno Setup 编译：

```bash
ISCC.exe installer.iss     # 产出 installer/Git提交助手-Setup-<版本>.exe
```

改界面或逻辑后必须重新打包，exe 里的代码是打包那一刻的快照。

## 分支约定

- `main`：开发主线
- `feature/<名字>`：新功能一律开分支开发，完成后合回 `main`
- `release`：长期保留，承载发布相关改动与版本 tag
