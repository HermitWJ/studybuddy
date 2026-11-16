#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装团队协作 Git 钩子。

默认安装 pre-push：拦截任何向远程 main / master 的推送（含删除 main），
并对不符合 feat/<用户名> 规范的远程分支给出警告。

用法：
  python install_hooks.py            # 安装到当前仓库
  python install_hooks.py --with-commit-guard
                                     # 额外安装 pre-commit，在 main 上提交时提示

钩子只写入 .git/hooks/，不进版本库；每位成员需要在本地各执行一次。
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HOOK_DIR_NAME = "hooks"
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def run_git(args, cwd=None, check=True):
    proc = subprocess.run(
        ["git"] + [str(a) for a in args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise RuntimeError(f"git {' '.join(str(a) for a in args)} 失败：\n{detail}")
    return proc


def git_path(name: str) -> Path:
    """返回相对 git 目录的路径（如 hooks），已解析为绝对路径。"""
    proc = run_git(["rev-parse", "--git-path", name], check=False)
    if proc.returncode != 0:
        raise RuntimeError("当前目录不在 Git 仓库内，请先进入仓库目录。")
    path = Path(proc.stdout.strip())
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def install_hook(hook_name: str, source: Path, hooks_dir: Path) -> None:
    target = hooks_dir / hook_name
    hooks_dir.mkdir(parents=True, exist_ok=True)

    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak-{int(time.time())}")
        shutil.copy2(target, backup)
        print(f"[INFO] 已备份原有 {hook_name} -> {backup.name}")

    content = source.read_text(encoding="utf-8")
    target.write_text(content, encoding="utf-8", newline="\n")

    # Windows 上 chmod 影响有限，但 Git Bash 需要可执行位
    mode = target.stat().st_mode
    target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if os.name != "nt" and not (mode & stat.S_IXUSR):
        os.chmod(target, 0o755)
    print(f"[ OK ] 已安装 {hook_name} -> {target}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="安装团队协作 Git 钩子（拦截 main 推送）")
    parser.add_argument(
        "--with-commit-guard",
        action="store_true",
        help="同时安装 pre-commit，在受保护分支上提交时给出提示",
    )
    args = parser.parse_args(argv)

    try:
        hooks_dir = git_path(HOOK_DIR_NAME)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1

    pre_push = ASSET_DIR / "pre-push"
    if not pre_push.exists():
        print(f"[FAIL] 找不到钩子模板：{pre_push}")
        return 1

    try:
        install_hook("pre-push", pre_push, hooks_dir)
        if args.with_commit_guard:
            guard = ASSET_DIR / "pre-commit"
            if guard.exists():
                install_hook("pre-commit", guard, hooks_dir)
            else:
                print("[WARN] 未找到 pre-commit 模板，跳过")
    except OSError as exc:
        print(f"[FAIL] 写入钩子失败：{exc}")
        return 1

    print()
    print("[INFO] 钩子已生效。验证方式：在 main 上执行 git push 应被拒绝。")
    print("[INFO] 钩子只作用于当前仓库本地，每位成员需各自执行一次。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
