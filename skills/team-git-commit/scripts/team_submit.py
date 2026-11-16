#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""团队协作提交助手。

强制把代码提交并推送到个人分支 feat/<用户名>：
  1. 分支必须从 origin/main 迁出；
  2. 推送前必须 fetch + rebase 到最新 origin/main，冲突解决完才允许推送；
  3. 永不推送远程 main / master。

子命令：
  check                 只读体检，不修改任何状态
  submit [-m MSG]       完整流程：确保分支 -> 同步 -> 提交 -> rebase -> 推送
  sync                  只做 fetch + rebase（不提交、不推送）
  set-user <NAME>       写入团队用户名配置（git config team.username）

示例：
  python team_submit.py check
  python team_submit.py submit -m "feat: 新增登录接口"
  python team_submit.py submit -m "fix: 修正时区" --dry-run
  python team_submit.py set-user HermitWJ
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROTECTED_BRANCHES = ("main", "master")
DEFAULT_PREFIX = "feat/"
DEFAULT_UPSTREAM = "origin/main"
REMOTE = "origin"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NEED_CONFIRM = 2
EXIT_CONFLICT = 3


class GitError(RuntimeError):
    """可预期的流程错误，直接展示给用户。"""


class BranchDecisionRequired(GitError):
    """目标分支不存在，必须先与用户确认后才能新建。"""


# --------------------------------------------------------------------------- #
# 基础命令封装
# --------------------------------------------------------------------------- #
JSON_MODE = False


def emit(tag: str, message: str) -> None:
    # JSON 模式下把日志导向 stderr，保证 stdout 是纯 JSON
    stream = sys.stderr if JSON_MODE else sys.stdout
    print(f"[{tag:<4}] {message}", file=stream)


def run_git(args, cwd=None, check=True):
    env = dict(os.environ)
    # 关键：避免 rebase/commit 打开编辑器导致进程挂起
    env.setdefault("GIT_EDITOR", "true")
    env.setdefault("GIT_SEQUENCE_EDITOR", "true")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    try:
        proc = subprocess.run(
            ["git"] + [str(a) for a in args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise GitError("未找到 git 命令，请先安装 Git 并确保它在 PATH 中。") from exc
    if check and proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise GitError(f"git {' '.join(str(a) for a in args)} 执行失败：\n{detail}")
    return proc


def git_text(args, cwd=None, default=""):
    proc = run_git(args, cwd=cwd, check=False)
    if proc.returncode != 0:
        return default
    return proc.stdout.strip()


def git_ok(args, cwd=None):
    return run_git(args, cwd=cwd, check=False).returncode == 0


def config_get(cwd, key, default=""):
    return git_text(["config", "--get", key], cwd=cwd, default=default) or default


# --------------------------------------------------------------------------- #
# 环境解析
# --------------------------------------------------------------------------- #
def repo_root():
    proc = run_git(["rev-parse", "--show-toplevel"], check=False)
    if proc.returncode != 0:
        raise GitError("当前目录不在 Git 仓库内，请先进入仓库目录再执行本脚本。")
    return Path(proc.stdout.strip()).resolve()


def sanitize_username(raw: str) -> str:
    """把任意输入清洗成合法的分支名片段（仅保留字母数字与 . _ -）。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", (raw or "").strip())
    return cleaned.strip(".-_")


def gh_login() -> str:
    if not shutil.which("gh"):
        return ""
    try:
        proc = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def resolve_username(root: Path, explicit: str = "") -> str:
    if explicit:
        name = sanitize_username(explicit)
        if not name:
            raise GitError(f"用户名 {explicit!r} 清洗后为空，请只用字母、数字、. _ - 组成。")
        return name

    for key in ("team.username", "github.user"):
        value = config_get(root, key)
        if value:
            name = sanitize_username(value)
            if name:
                emit("INFO", f"用户名取自 git config {key}：{name}")
                return name

    login = sanitize_username(gh_login())
    if login:
        emit("INFO", f"用户名取自 GitHub CLI：{login}")
        return login

    name = sanitize_username(config_get(root, "user.name"))
    if name:
        emit("WARN", f"未配置团队用户名，回退使用 git user.name：{name}")
        emit("WARN", "建议固定下来：python skills/team-git-commit/scripts/team_submit.py set-user <你的用户名>")
        return name

    raise GitError(
        "无法确定团队用户名。请显式指定：\n"
        "  python scripts/team_submit.py set-user <你的用户名>\n"
        "  或 python scripts/team_submit.py submit --user <你的用户名> -m \"...\""
    )


def current_branch(root: Path) -> str:
    return git_text(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)


def branch_exists(root: Path, name: str) -> bool:
    return git_ok(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], cwd=root)


def state_in_progress(root: Path, kind: str) -> bool:
    path = git_text(["rev-parse", "--git-path", kind], cwd=root)
    if not path:
        return False
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    return p.exists()


def is_dirty(root: Path) -> bool:
    return bool(git_text(["status", "--porcelain"], cwd=root))


def pr_link(root: Path, branch: str) -> str:
    url = git_text(["remote", "get-url", REMOTE], cwd=root)
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", url)
    if not match:
        return ""
    return (
        f"https://github.com/{match.group('owner')}/{match.group('repo')}"
        f"/compare/main...{branch}?expand=1"
    )


# --------------------------------------------------------------------------- #
# 核心步骤
# --------------------------------------------------------------------------- #
def valid_branch_name(name: str, prefix: str) -> bool:
    return bool(re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9._-]+", name or ""))


def ensure_branch(root: Path, goal: str, upstream: str, prefix: str, create: bool = False) -> str:
    """切换到目标分支并返回分支名。

    目标分支不存在时，只有显式 create=True 才新建；否则抛出
    BranchDecisionRequired，要求先与用户确认分支选择。
    """
    cur = current_branch(root)

    if cur in ("HEAD", ""):
        raise GitError(f"当前处于 detached HEAD 状态。请先切回分支：git checkout {goal}")

    if not valid_branch_name(goal, prefix):
        raise GitError(
            f"分支 {goal} 不符合团队规范 {prefix}<用户名>。\n"
            f"请改用 {prefix}<用户名> 形式，例如 {prefix}HermitWJ。"
        )

    if cur == goal:
        emit("OK", f"当前分支符合规范：{goal}")
        return goal

    if branch_exists(root, goal):
        run_git(["checkout", goal], cwd=root)
        emit("OK", f"已从 {cur} 切换到现有本地分支 {goal}")
        return goal

    remote_ref = f"{REMOTE}/{goal}"
    if git_ok(["rev-parse", "--verify", "--quiet", remote_ref], cwd=root):
        run_git(["checkout", "-b", goal, "--track", remote_ref], cwd=root)
        emit("OK", f"已从远程分支 {remote_ref} 检出本地分支 {goal}")
        return goal

    if not create:
        raise BranchDecisionRequired(
            f"本地和远程都没有分支 {goal}。\n"
            "新建分支会改变当前工作位置，必须先和用户确认，脚本不会自行创建。\n"
            f"  • 用户同意新建 {goal}：加 --create 重跑\n"
            "  • 用户想用别的已有分支：加 --branch <分支名>\n"
            "  • 先列出可选分支给用户看：team_submit.py branches"
        )

    run_git(["checkout", "-b", goal, "--no-track", upstream], cwd=root)
    emit("OK", f"已从 {upstream} 新建分支 {goal}")
    return goal


def fetch_remote(root: Path) -> None:
    emit("INFO", f"同步远程仓库：git fetch {REMOTE} --prune")
    proc = run_git(["fetch", REMOTE, "--prune"], cwd=root, check=False)
    if proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise GitError(f"拉取远程失败，请检查网络或仓库权限：\n{detail}")
    emit("OK", "远程引用已更新")


def verify_base_on_main(root: Path, upstream: str) -> None:
    """校验当前分支确实是从 main 迁出的（分支起点提交的父提交在 main 历史中）。"""
    upstream_sha = git_text(["rev-parse", upstream], cwd=root)
    if not upstream_sha:
        raise GitError(f"找不到 {upstream}，请先执行 git fetch {REMOTE}。")

    revs = git_text(
        ["rev-list", "--reverse", "--max-parents=1", f"{upstream}..HEAD"], cwd=root
    )
    if not revs:
        emit("OK", f"分支与 {upstream} 无差异")
        return

    first = revs.splitlines()[0].strip()
    parents = git_text(["rev-list", "--parents", "-n", "1", first], cwd=root).split()
    if len(parents) < 2:
        emit("WARN", f"无法确定首个提交 {first[:8]} 的父提交，跳过基线校验")
        return

    parent = parents[1]
    if git_ok(["merge-base", "--is-ancestor", parent, upstream], cwd=root):
        emit("OK", f"分支基线正确：首个独有提交 {first[:8]} 的父提交在 {upstream} 历史中")
    else:
        raise GitError(
            f"分支 {current_branch(root)} 不是从 {upstream} 迁出的"
            f"（提交 {first[:8]} 的父提交 {parent[:8]} 不在 main 历史中）。\n"
            "处理方式（二选一）：\n"
            "  1) 把独有提交摘出来重放到 main 上：\n"
            f"     git branch backup/{current_branch(root)}-$(date +%s)\n"
            f"     git rebase --onto {upstream} {parent} {current_branch(root)}\n"
            f"  2) 重新从 {upstream} 建分支，再 cherry-pick 需要的提交。"
        )


def commit_worktree(root: Path, message: str) -> None:
    if not is_dirty(root):
        emit("OK", "工作区干净，无需新建提交")
        return
    if not message:
        raise GitError(
            "工作区有未提交改动。请二选一：\n"
            "  1) 加 -m \"提交说明\" 让脚本自动 add + commit；\n"
            "  2) 先手动 git commit，再重跑。"
        )
    run_git(["add", "-A"], cwd=root)
    run_git(["commit", "-m", message], cwd=root)
    emit("OK", f"已创建本地提交：{message}")


def rebase_onto_upstream(root: Path, upstream: str) -> int:
    behind = git_text(["rev-list", "--count", f"HEAD..{upstream}"], cwd=root, default="0")
    if behind == "0":
        emit("OK", f"已是最新，无需 rebase（{upstream} 无新提交）")
        return EXIT_OK

    emit("INFO", f"落后 {upstream} {behind} 个提交，开始 rebase")
    proc = run_git(["rebase", upstream], cwd=root, check=False)
    if proc.returncode == 0:
        emit("OK", f"rebase 完成，代码已基于最新 {upstream}")
        return EXIT_OK

    conflicts = git_text(["diff", "--name-only", "--diff-filter=U"], cwd=root)
    emit("FAIL", f"rebase 到 {upstream} 发生冲突，已阻止本次推送")
    if conflicts:
        print("  冲突文件：")
        for item in conflicts.splitlines():
            print(f"    - {item}")
    print("  解决步骤：")
    print("    1) 打开上面列出的文件，处理 <<<<<<< / ======= / >>>>>>> 标记")
    print("    2) git add <已解决的文件>")
    print("    3) git rebase --continue   （如需修改提交说明：git commit --no-edit 后继续）")
    print("    4) 冲突全部解决后重跑：python scripts/team_submit.py submit -m \"...\"")
    print("    放弃本次 rebase：git rebase --abort")
    return EXIT_CONFLICT


def push_branch(root: Path, branch: str, dry_run: bool, allow_force: bool) -> str:
    if branch in PROTECTED_BRANCHES or branch.startswith("refs/heads/main"):
        raise GitError(f"拒绝推送受保护分支 {branch}。团队禁止直接向 main 提交。")

    remote_ref = f"{REMOTE}/{branch}"
    needs_force = False
    if git_ok(["rev-parse", "--verify", "--quiet", remote_ref], cwd=root):
        if not git_ok(["merge-base", "--is-ancestor", remote_ref, "HEAD"], cwd=root):
            needs_force = True

    args = ["push"]
    if dry_run:
        args.append("--dry-run")
    if needs_force:
        if not allow_force:
            raise GitError(
                f"远程 {remote_ref} 与本地历史分叉（rebase 后属正常现象）。\n"
                "已按 --no-force 中止。确认这是你自己的分支后，去掉 --no-force 重跑，"
                "脚本会使用 --force-with-lease。"
            )
        args.append("--force-with-lease")
        emit("WARN", f"历史已分叉，使用 --force-with-lease 更新你自己的分支 {branch}")

    args += ["-u", REMOTE, f"{branch}:{branch}"]
    emit("INFO", f"推送：git {' '.join(args)}")
    proc = run_git(args, cwd=root, check=False)
    if proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise GitError(f"推送失败：\n{detail}")
    return proc.stdout + proc.stderr


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
KIND_LABEL = {
    "protected": "受保护",
    "recommended": "推荐（你的分支）",
    "mine": "feat 分支",
    "other": "非规范分支",
}


def branch_rows(root: Path, upstream: str, target: str, prefix: str):
    """收集本地与远程分支，标注类型及相对 upstream 的领先/落后提交数。"""
    rows = []
    local_names = git_text(["for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=root).splitlines()
    remote_names = git_text(["for-each-ref", "--format=%(refname:short)", "refs/remotes"], cwd=root).splitlines()

    def add(name: str, scope: str) -> None:
        if scope == "remote":
            if not name.startswith(REMOTE + "/"):
                return
            short = name[len(REMOTE) + 1:]
        else:
            short = name
        if not short or short == "HEAD":
            return

        if short in PROTECTED_BRANCHES:
            kind = "protected"
        elif short == target:
            kind = "recommended"
        elif valid_branch_name(short, prefix):
            kind = "mine"
        else:
            kind = "other"

        rows.append({
            "name": name,
            "short": short,
            "scope": scope,
            "kind": kind,
            "label": KIND_LABEL[kind],
            "recommended": short == target,
            "ahead": git_text(["rev-list", "--count", f"{upstream}..{name}"], cwd=root, default="?"),
            "behind": git_text(["rev-list", "--count", f"{name}..{upstream}"], cwd=root, default="?"),
        })

    for name in local_names:
        add(name.strip(), "local")
    for name in remote_names:
        add(name.strip(), "remote")
    return rows


def cmd_branches(args) -> int:
    global JSON_MODE
    JSON_MODE = bool(args.json)
    root = repo_root()
    username = resolve_username(root, args.user)
    prefix = args.branch_prefix or config_get(root, "team.branchPrefix", DEFAULT_PREFIX)
    upstream = args.upstream or config_get(root, "team.upstream", DEFAULT_UPSTREAM)
    target = f"{prefix}{username}"

    try:
        fetch_remote(root)
    except GitError as exc:
        emit("WARN", f"拉取远程失败，改用本地已有引用：{str(exc).splitlines()[0]}")

    cur = current_branch(root)
    rows = branch_rows(root, upstream, target, prefix)

    has_local = any(r["scope"] == "local" and r["short"] == target for r in rows)
    has_remote = any(r["scope"] == "remote" and r["short"] == target for r in rows)
    if has_local and has_remote:
        state = "本地和远程都已存在"
    elif has_remote:
        state = "仅远程存在，可直接检出"
    elif has_local:
        state = "仅本地存在，远程还没有"
    else:
        state = "不存在，需要新建"

    if args.json:
        print(json.dumps({
            "current": cur,
            "username": username,
            "target": target,
            "target_state": state,
            "target_exists": has_local or has_remote,
            "upstream": upstream,
            "branches": rows,
        }, ensure_ascii=False, indent=2))
        return EXIT_OK

    print(f"当前分支：{cur}")
    print(f"推荐分支：{target}  ——  {state}")
    print()
    for scope, title in (("local", "本地分支"), ("remote", "远程分支")):
        items = [r for r in rows if r["scope"] == scope]
        print(f"{title}（相对 {upstream}，+领先 / -落后）")
        if not items:
            print("  （无）")
        for r in items:
            mark = "*" if (scope == "local" and r["name"] == cur) else " "
            line = f"  {mark} {r['name']:<34} +{r['ahead']}/-{r['behind']:<4} {r['label']}"
            if scope == "remote" and has_local and r["short"] == target:
                line += "  [本地已有同名]"
            print(line.rstrip())
        print()

    print("下一步：先把上面的清单给用户看，确认用哪个分支，再执行")
    print(f"  • 用已有分支：  team_submit.py submit --branch <分支名> -m \"提交说明\"")
    print(f"  • 新建 {target}：  team_submit.py submit --create -m \"提交说明\"")
    return EXIT_OK


def cmd_check(args) -> int:
    root = repo_root()
    emit("OK", f"仓库根目录：{root}")

    remote_url = git_text(["remote", "get-url", REMOTE], cwd=root)
    if not remote_url:
        raise GitError(f"未配置远程仓库 {REMOTE}。")
    emit("OK", f"远程 {REMOTE}：{remote_url}")

    username = resolve_username(root, args.user)
    prefix = args.branch_prefix or config_get(root, "team.branchPrefix", DEFAULT_PREFIX)
    upstream_branch = args.upstream or config_get(root, "team.upstream", DEFAULT_UPSTREAM)
    target = f"{prefix}{username}"
    upstream = upstream_branch
    emit("OK", f"团队用户名：{username}  ->  目标分支：{target}")

    try:
        fetch_remote(root)
    except GitError as exc:
        # check 是只读体检，网络不可用时降级为警告，用本地已有的远程引用继续
        emit("WARN", f"拉取远程失败，改用本地已有的 {upstream} 继续体检：{str(exc).splitlines()[0]}")

    cur = current_branch(root)
    if cur in PROTECTED_BRANCHES:
        emit("WARN", f"当前在受保护分支 {cur} 上，提交前需切到 {target}")
    elif cur == target:
        emit("OK", f"当前分支 {cur} 符合规范")
    else:
        emit("WARN", f"当前分支 {cur} 不符合规范，应为 {target}")

    if state_in_progress(root, "rebase-merge") or state_in_progress(root, "rebase-apply"):
        emit("FAIL", "检测到未完成的 rebase，请先 git rebase --continue 或 --abort")
    if state_in_progress(root, "MERGE_HEAD"):
        emit("FAIL", "检测到未完成的 merge，请先提交或 git merge --abort")

    behind = git_text(["rev-list", "--count", f"HEAD..{upstream}"], cwd=root, default="?")
    ahead = git_text(["rev-list", "--count", f"{upstream}..HEAD"], cwd=root, default="?")
    print(f"[INFO] 相对 {upstream}：领先 {ahead} 个提交，落后 {behind} 个提交")
    if behind not in ("0", "?"):
        emit("WARN", "分支落后于 main，提交前必须 rebase")

    emit("OK" if not is_dirty(root) else "WARN",
         "工作区干净" if not is_dirty(root) else "工作区有未提交改动")

    if current_branch(root) == target:
        try:
            verify_base_on_main(root, upstream)
        except GitError as exc:
            emit("FAIL", str(exc).splitlines()[0])

    link = pr_link(root, target)
    if link:
        print(f"[INFO] 提交后可在此发起 PR：{link}")
    return EXIT_OK


def cmd_sync(args) -> int:
    root = repo_root()
    if state_in_progress(root, "rebase-merge") or state_in_progress(root, "rebase-apply"):
        raise GitError("检测到未完成的 rebase，请先 git rebase --continue 或 git rebase --abort。")
    if is_dirty(root):
        raise GitError("工作区有未提交改动，无法 rebase。请先提交或 git stash。")

    username = resolve_username(root, args.user)
    prefix = args.branch_prefix or config_get(root, "team.branchPrefix", DEFAULT_PREFIX)
    target = f"{prefix}{username}"
    upstream = args.upstream or config_get(root, "team.upstream", DEFAULT_UPSTREAM)

    goal = args.branch or target
    fetch_remote(root)
    ensure_branch(root, goal, upstream, prefix, create=getattr(args, "create", False))
    return rebase_onto_upstream(root, upstream)


def cmd_submit(args) -> int:
    root = repo_root()

    if state_in_progress(root, "rebase-merge") or state_in_progress(root, "rebase-apply"):
        raise GitError(
            "检测到未完成的 rebase。请先解决冲突并 git rebase --continue，"
            "或 git rebase --abort 放弃，然后再重跑 submit。"
        )
    if state_in_progress(root, "MERGE_HEAD"):
        raise GitError("检测到未完成的 merge，请先完成提交或 git merge --abort。")

    username = resolve_username(root, args.user)
    prefix = args.branch_prefix or config_get(root, "team.branchPrefix", DEFAULT_PREFIX)
    upstream = args.upstream or config_get(root, "team.upstream", DEFAULT_UPSTREAM)
    target = f"{prefix}{username}"

    goal = args.branch or target
    if goal in PROTECTED_BRANCHES:
        raise GitError(f"目标分支 {goal} 属于受保护分支，禁止直接提交。请使用 {target} 或 --branch 指定 feat 分支。")
    if not valid_branch_name(goal, prefix):
        raise GitError(
            f"分支 {goal} 不符合团队规范 {prefix}<用户名>，例如 {target}。"
        )

    print("=" * 62)
    print(f" 团队用户名：{username}")
    print(f" 目标分支：{goal}" + ("（新建）" if args.create else ""))
    print(f" 上游基线：{upstream}")
    print("=" * 62)

    fetch_remote(root)
    branch = ensure_branch(root, goal, upstream, prefix, create=args.create)
    verify_base_on_main(root, upstream)
    commit_worktree(root, args.message)

    code = rebase_onto_upstream(root, upstream)
    if code != EXIT_OK:
        return code

    # rebase 后再次确认基线（历史被重写）
    verify_base_on_main(root, upstream)

    output = push_branch(root, branch, args.dry_run, not args.no_force)
    if args.dry_run:
        emit("OK", "演练完成（--dry-run，未真正推送）")
        return EXIT_OK

    emit("OK", f"已推送到 {REMOTE}/{branch}")
    link = pr_link(root, branch)
    if link:
        print(f"[INFO] 发起 Pull Request：{link}")
    if "Everything up-to-date" in output:
        emit("INFO", "远程分支已是最新，本次没有新提交")
    return EXIT_OK


def cmd_set_user(args) -> int:
    root = repo_root()
    name = sanitize_username(args.name)
    if not name:
        raise GitError(f"用户名 {args.name!r} 不合法，只允许字母、数字、. _ -")
    run_git(["config", "team.username", name], cwd=root)
    prefix = config_get(root, "team.branchPrefix", DEFAULT_PREFIX)
    upstream = config_get(root, "team.upstream", DEFAULT_UPSTREAM)
    run_git(["config", "team.branchPrefix", prefix], cwd=root)
    run_git(["config", "team.upstream", upstream], cwd=root)
    emit("OK", f"已写入 git config team.username = {name}")
    emit("OK", f"以后提交将使用分支 {prefix}{name}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", help="显式指定团队用户名（默认读 git config team.username）")
    common.add_argument("--branch-prefix", help=f"分支前缀，默认 {DEFAULT_PREFIX}")
    common.add_argument("--upstream", help=f"上游分支，默认 {DEFAULT_UPSTREAM}")

    parser = argparse.ArgumentParser(
        prog="team_submit.py",
        description="团队协作提交助手：强制 feat/<用户名> 分支、提交前 rebase 最新 main、禁止推送 main。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_branches = sub.add_parser(
        "branches", parents=[common], help="列出可用分支，供用户选择（推荐先运行）"
    )
    p_branches.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序解析")
    p_branches.set_defaults(func=cmd_branches)

    p_check = sub.add_parser("check", parents=[common], help="只读体检当前分支状态")
    p_check.set_defaults(func=cmd_check)

    p_submit = sub.add_parser("submit", parents=[common], help="提交并推送到个人分支")
    p_submit.add_argument("-m", "--message", help="本次提交说明；有未提交改动时必填")
    p_submit.add_argument("--branch", help="指定要使用的分支（默认 feat/<用户名>）")
    p_submit.add_argument("--create", action="store_true", help="分支不存在时新建（须先与用户确认）")
    p_submit.add_argument("--dry-run", action="store_true", help="只演练，不真正推送")
    p_submit.add_argument("--no-force", action="store_true", help="禁止使用 --force-with-lease")
    p_submit.set_defaults(func=cmd_submit)

    p_sync = sub.add_parser("sync", parents=[common], help="仅同步并 rebase 到最新 main")
    p_sync.add_argument("--branch", help="指定要同步的分支（默认 feat/<用户名>）")
    p_sync.add_argument("--create", action="store_true", help="分支不存在时新建（须先与用户确认）")
    p_sync.set_defaults(func=cmd_sync)

    p_user = sub.add_parser("set-user", parents=[common], help="写入团队用户名配置")
    p_user.add_argument("name", help="GitHub 用户名，例如 HermitWJ")
    p_user.set_defaults(func=cmd_set_user)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BranchDecisionRequired as exc:
        print()
        emit("WAIT", str(exc))
        return EXIT_NEED_CONFIRM
    except GitError as exc:
        print()
        emit("FAIL", str(exc))
        return EXIT_FAIL
    except KeyboardInterrupt:
        emit("FAIL", "已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
