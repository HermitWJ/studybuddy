#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把仓库根 skills/ 下的技能同步到 .codebuddy/skills/。

skills/          唯一源码，随仓库提交、可评审
.codebuddy/skills/   CodeBuddy 的项目级技能加载目录，被 .gitignore 忽略，属派生产物

用法：
  python skills/sync_skills.py            同步（覆盖变化文件）
  python skills/sync_skills.py --check    只检查是否一致，不一致返回 1（可用于 CI）
  python skills/sync_skills.py --clean    同步并删除目标中多余的旧文件
  python skills/sync_skills.py --list     列出发现的技能
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "skills"
DST = ROOT / ".codebuddy" / "skills"

EXCLUDE_DIRS = {"dist", "__pycache__", ".git", ".pytest_cache", "node_modules"}
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIXES = {".pyc", ".zip"}


def discover_skills():
    """只有包含 SKILL.md 的子目录才算技能。"""
    if not SRC.is_dir():
        raise SystemExit(f"[FAIL] 找不到技能源目录：{SRC}")
    skills = []
    for child in sorted(SRC.iterdir()):
        if child.is_dir() and child.name not in EXCLUDE_DIRS and (child / "SKILL.md").is_file():
            skills.append(child)
    return skills


def iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path, rel


def normalized(path: Path) -> bytes:
    """按行尾无关的方式读取内容。

    仓库 .gitattributes 指定 eol=lf，签出后是 LF；而历史副本可能是 CRLF。
    直接字节比较会把这种差异误判成「内容变更」，导致每次都提示不同步。
    """
    return path.read_bytes().replace(b"\r\n", b"\n")


def same_content(a: Path, b: Path) -> bool:
    return normalized(a) == normalized(b)


def diff_skill(skill_dir: Path):
    added, changed, same = [], [], []
    target = DST / skill_dir.name
    for src_file, rel in iter_files(skill_dir):
        dst_file = target / rel
        if not dst_file.exists():
            added.append(rel)
        elif same_content(src_file, dst_file):
            same.append(rel)
        else:
            changed.append(rel)
    return added, changed, same


def extra_files(skill_dir: Path):
    target = DST / skill_dir.name
    if not target.is_dir():
        return []
    keep = {rel for _, rel in iter_files(skill_dir)}
    return [
        path.relative_to(target)
        for path in sorted(target.rglob("*"))
        if path.is_file() and path.relative_to(target) not in keep
    ]


def prune_empty_dirs(base: Path) -> None:
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def command_list() -> int:
    skills = discover_skills()
    if not skills:
        print("[WARN] skills/ 下没有任何技能")
        return 0
    print(f"发现 {len(skills)} 个技能（源目录 {SRC}）：")
    for item in skills:
        target = DST / item.name
        state = "已同步" if target.is_dir() else "未部署"
        print(f"  - {item.name:<28} {state}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 skills/ 到 .codebuddy/skills/")
    parser.add_argument("--check", action="store_true", help="只检查差异，不写文件")
    parser.add_argument("--clean", action="store_true", help="同步时删除目标中多余的旧文件")
    parser.add_argument("--list", action="store_true", help="列出发现的技能")
    args = parser.parse_args(argv)

    if args.list:
        return command_list()

    skills = discover_skills()
    if not skills:
        print("[WARN] skills/ 下没有任何技能，无需同步")
        return 0

    total_changed = 0
    for skill in skills:
        added, changed, same = diff_skill(skill)
        removed = extra_files(skill) if args.clean else []
        target = DST / skill.name
        drift = len(added) + len(changed) + len(removed)

        if args.check:
            if drift:
                total_changed += drift
                print(f"[WARN] {skill.name}：新增 {len(added)} / 变更 {len(changed)} / 多余 {len(removed)}")
                for rel in added:
                    print(f"          + {rel}")
                for rel in changed:
                    print(f"          ~ {rel}")
                for rel in removed:
                    print(f"          - {rel}")
            else:
                print(f"[ OK ] {skill.name}：与 .codebuddy 一致")
            continue

        if not drift:
            print(f"[ OK ] {skill.name}：已是最新（{len(same)} 个文件）")
            continue

        target.mkdir(parents=True, exist_ok=True)
        for rel in added + changed:
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill / rel, dst)
        for rel in removed:
            (target / rel).unlink()
        prune_empty_dirs(target)
        total_changed += drift
        print(f"[ OK ] {skill.name}：新增 {len(added)} / 更新 {len(changed)} / 删除 {len(removed)}")

    if args.check:
        if total_changed:
            print(f"\n[FAIL] 有 {total_changed} 个文件未同步，执行 python skills/sync_skills.py 修复")
            return 1
        print("\n[ OK ] 全部技能均已同步")
        return 0

    print(f"\n[ OK ] 同步完成，目标目录：{DST}")
    print("[INFO] 修改技能请只改 skills/<name>/，再执行本脚本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
