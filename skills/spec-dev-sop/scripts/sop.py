#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-dev-sop 工具集。

子命令：
    status                       阶段体检
    scaffold <feature>           生成 docs/dev/<feature>/ 文档骨架
    audit                        质量扫描（敏感信息 / 冗余 / 结构 / 规范）
    test                         探测并运行单测

仅依赖标准库，Python 3.8+。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_checks import CHECK_NAMES, run_audit  # noqa: E402
from sop_common import (  # noqa: E402
    DOC_KINDS, LANG_BY_EXT, LEGACY_DOC_NAMES, SKIP_DIR_NAMES, TEMPLATE_DIR,
    find_root, load_rules, read_text, rel,
)

DEFAULT_TEMPLATES = {
    "需求方案.md": "# {{FEATURE}} · 需求方案\n",
    "开发文档.md": "# {{FEATURE}} · 开发文档\n",
    "测试记录.md": "# {{FEATURE}} · 测试记录\n",
    "质量体检.md": "# {{FEATURE}} · 质量体检\n",
}
def _doc_path(feature_dir: Path, kind: str) -> Path:
    """优先取新命名 <feature>.<类型>.md，回退到旧的 plan.md/design.md 等。"""
    path = feature_dir / f"{feature_dir.name}.{kind}.md"
    if path.exists():
        return path
    legacy = feature_dir / LEGACY_DOC_NAMES[kind]
    return legacy if legacy.exists() else path



# ---------------------------------------------------------------- scaffold

def cmd_scaffold(root: Path, feature: str, force: bool) -> int:
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", feature):
        print(f"[error] feature 名必须是 kebab-case 英文数字：{feature}", file=sys.stderr)
        return 2
    target = root / "docs" / "dev" / feature
    target.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    created = []
    for kind in DOC_KINDS:
        dest = target / f"{feature}.{kind}.md"
        if dest.exists() and not force:
            print(f"   跳过（已存在）: {rel(dest, root)}")
            continue
        template = f"{kind}.md"
        src = TEMPLATE_DIR / template
        text = read_text(src) if src.exists() else DEFAULT_TEMPLATES[template]
        text = (text or "").replace("{{FEATURE}}", feature).replace("{{DATE}}", today)
        dest.write_text(text, encoding="utf-8")
        created.append(rel(dest, root))
    print(f"已创建 {len(created)} 个文件于 docs/dev/{feature}/")
    for item in created:
        print(f"   + {item}")
    print("\n下一步：按 references/discovery-questions.md 澄清需求，"
          f"填 {feature}.需求方案.md，确认后再写开发文档。")
    return 0


# ---------------------------------------------------------------- status

STATUS_RE = re.compile(r"状态[：:]\s*(\S+)")
CONFIRMED_TOKENS = ("已确认", "已批准", "confirmed", "approved")


def _doc_status(path: Path) -> str:
    if not path.exists():
        return "缺失"
    text = read_text(path) or ""
    m = STATUS_RE.search(text)
    if not m:
        return "无状态行"
    value = m.group(1)
    if any(tok in value for tok in CONFIRMED_TOKENS):
        return "已确认"
    if "待确认" in value or "草稿" in value or "draft" in value.lower():
        return "待确认"
    return value


def _disp_len(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _disp_len(text))


def _latest_code_mtime(root: Path) -> float:
    latest = 0.0
    for sub in ("backend", "frontend/src", "src", "app"):
        base = root / sub
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                if Path(name).suffix.lower() in LANG_BY_EXT:
                    try:
                        latest = max(latest, (Path(dirpath) / name).stat().st_mtime)
                    except OSError:
                        continue
    return latest


def _verdict(feat: Path, states: dict, code_mtime: float) -> str:
    design = _doc_path(feat, "开发文档")
    design_mtime = design.stat().st_mtime if design.exists() else 0
    if design_mtime and code_mtime > design_mtime + 60 and states["开发文档"] != "已确认":
        return "文档未确认但代码已改动，属跳关，应倒补文档"
    if states["开发文档"] == "已确认" and states["质量体检"] == "已确认":
        return "已收尾"
    if states["开发文档"] == "已确认":
        return "可开发 / 待补测试与体检"
    if states["需求方案"] == "已确认":
        return "方案已定，待开发文档确认"
    return "方案阶段，禁止写业务代码"


def cmd_status(root: Path) -> int:
    dev_dir = root / "docs" / "dev"
    if not dev_dir.is_dir():
        print("docs/dev/ 不存在：这是新需求，从阶段 1 开始。")
        print("  运行 python skills/spec-dev-sop/scripts/sop.py scaffold <feature>")
        return 0
    features = sorted(p for p in dev_dir.iterdir() if p.is_dir())
    if not features:
        print("docs/dev/ 下没有需求目录，从阶段 1 开始。")
        return 0

    code_mtime = _latest_code_mtime(root)
    widths = (24, 12, 12, 12, 12)
    header = "".join(_pad(t, w) for t, w in zip(("feature",) + DOC_KINDS, widths))
    print(f"== 需求阶段体检（{len(features)} 个需求）==")
    print(header + "结论")
    print("-" * 100)
    exit_code = 0
    for feat in features:
        states = {kind: _doc_status(_doc_path(feat, kind)) for kind in DOC_KINDS}
        verdict = _verdict(feat, states, code_mtime)
        if verdict.startswith("文档未确认"):
            exit_code = 1
        cells = (feat.name,) + tuple(states[kind] for kind in DOC_KINDS)
        print("".join(_pad(c, w) for c, w in zip(cells, widths)) + verdict)
    return exit_code


# ---------------------------------------------------------------- test

def _detect_targets(root: Path, extra: list):
    targets = []
    py_dir = root / "backend" if (root / "backend" / "manage.py").exists() else root
    has_manage = (py_dir / "manage.py").exists()
    py_tests = [p for p in py_dir.glob("**/test*.py") if "node_modules" not in p.parts]
    has_cfg = any((py_dir / n).exists() for n in ("pytest.ini", "conftest.py", "tox.ini", "setup.cfg"))
    pyproject = py_dir / "pyproject.toml"
    if pyproject.exists() and "pytest" in (read_text(pyproject) or ""):
        has_cfg = True
    settings_arg = []
    for cand, module in (("config/settings_test.py", "config.settings_test"),
                         ("settings_test.py", "settings_test")):
        if (py_dir / cand).exists():
            settings_arg = [f"--settings={module}"]
            break

    if has_cfg:
        targets.append(("pytest", [sys.executable, "-m", "pytest", "-q", *extra], py_dir))
    elif has_manage:
        cmd = [sys.executable, "manage.py", "test", *settings_arg, *extra]
        targets.append(("django-test", cmd, py_dir))
    elif py_tests:
        targets.append(("pytest", [sys.executable, "-m", "pytest", "-q", *extra], py_dir))

    npm, npx, node = shutil.which("npm"), shutil.which("npx"), shutil.which("node")
    for pkg in (root / "package.json", root / "frontend" / "package.json"):
        if not pkg.exists():
            continue
        try:
            data = json.loads(read_text(pkg) or "{}")
        except json.JSONDecodeError:
            continue
        probe = dict(data.get("devDependencies") or {}, **(data.get("dependencies") or {}))
        scripts = data.get("scripts") or {}
        cwd = pkg.parent
        node_test_files = sorted(
            p.relative_to(cwd).as_posix() for p in (cwd / "tests").glob("*.test.js")
        ) if (cwd / "tests").is_dir() else []

        if "vitest" in probe and npx:
            targets.append((f"vitest({cwd.name})", [npx, "vitest", "run", *extra], cwd))
        elif "jest" in probe and npx:
            targets.append((f"jest({cwd.name})", [npx, "jest", *extra], cwd))
        elif node_test_files and node:
            cmd = [node, "--test", *node_test_files, *extra]
            targets.append((f"node-test({cwd.name})", cmd, cwd))
        elif scripts.get("test") and npm:
            targets.append((f"npm-test({cwd.name})", [npm, "test", *extra], cwd))
    return targets


def _run_targets(targets) -> int:
    failed = 0
    for name, cmd, cwd in targets:
        print(f"\n===== 运行 {name} =====")
        try:
            code = subprocess.run(cmd, cwd=cwd, shell=False).returncode
        except FileNotFoundError as exc:
            print(f"   命令不存在：{exc}")
            failed += 1
            continue
        if code != 0:
            failed += 1
            print(f"   {name} 失败（退出码 {code}）")
        else:
            print(f"   {name} 通过")
    return failed


def cmd_test(root: Path, dry_run: bool, extra: list) -> int:
    targets = _detect_targets(root, extra)
    if not targets:
        print("未探测到测试框架。")
        print("  后端：装 pytest，或在 backend/<app>/tests.py 写 Django TestCase")
        print("  前端：npm i -D vitest @vue/test-utils jsdom")
        return 0

    print(f"探测到 {len(targets)} 个测试入口：")
    for name, cmd, cwd in targets:
        print(f"   [{name}] {' '.join(cmd)}  (cwd={cwd})")
    if dry_run:
        print("\n--dry-run：不执行。")
        return 0

    failed = _run_targets(targets)
    if failed:
        print(f"\n{failed} 个测试入口失败。修好再进阶段 6。")
        return 1
    print("\n全部通过。继续 audit 做质量体检。")
    return 0


# ---------------------------------------------------------------- CLI

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sop.py", description="规范开发 SOP 工具")
    parser.add_argument("--root", help="项目根目录，默认取 git 顶层或当前目录")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="阶段体检")

    scaffold = sub.add_parser("scaffold", help="生成文档骨架")
    scaffold.add_argument("feature", help="kebab-case 需求名")
    scaffold.add_argument("--force", action="store_true", help="覆盖已存在文件")

    audit = sub.add_parser("audit", help="质量扫描")
    audit.add_argument("--diff", action="store_true", help="只扫描未提交的改动")
    audit.add_argument("--only", choices=CHECK_NAMES, action="append", help="只跑某类检查")
    audit.add_argument("--json", dest="as_json", action="store_true", help="JSON 输出")
    audit.add_argument("--strict", action="store_true", help="warning 也返回非零")
    audit.add_argument("--rules", help="自定义规则文件路径")

    test = sub.add_parser("test", help="探测并运行单测")
    test.add_argument("--dry-run", action="store_true", help="只显示命令")
    test.add_argument("extra", nargs="*", help="透传给测试框架的参数")
    return parser


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    args = _build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else find_root()

    if args.command == "status":
        return cmd_status(root)
    if args.command == "scaffold":
        return cmd_scaffold(root, args.feature, args.force)
    if args.command == "audit":
        rules = load_rules(Path(args.rules).resolve() if args.rules else None)
        return run_audit(root, rules, args.only, args.diff, args.strict, args.as_json)
    if args.command == "test":
        return cmd_test(root, args.dry_run, args.extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
