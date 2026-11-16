#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-dev-sop 质量体检的检查项实现。

四组：secrets（敏感信息）、debug/markers（调试与遗留标记）、
redundancy（冗余）、structure（结构完整性）、style（代码规范）。
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from sop_common import (
    DOC_KINDS, GENERATED_DIR_NAMES, NODE_BUILTINS, PY_DIST_ALIAS, SEVERITY_ORDER,
    SEVERITY_TAG, STDLIB_FALLBACK, finding, clip, is_test_path, iter_files, lang_of,
    read_text, rel,
)

CHECK_NAMES = ["secrets", "debug", "markers", "redundancy", "structure", "style"]
CHECK_LABELS = {
    "secrets": "敏感信息", "debug": "调试残留", "markers": "遗留标记",
    "redundancy": "冗余", "structure": "结构完整性", "style": "代码规范",
}


# ---------------------------------------------------------------- 敏感信息

def check_secrets(files, rules):
    out = []
    for rule in rules.get("secrets", []):
        pattern = re.compile(rule["pattern"])
        allow = re.compile(rule["allow_pattern"]) if rule.get("allow_pattern") else None
        globs = rule.get("exclude_glob", [])
        for path, rpath, text in files:
            if any(fnmatch.fnmatch(rpath, g) or fnmatch.fnmatch(path.name, g) for g in globs):
                continue
            for no, line in enumerate(text.splitlines(), 1):
                if allow and allow.search(line):
                    continue
                if pattern.search(line):
                    msg = clip(rule.get("message", "疑似敏感信息")) + " → " + clip(line, 80)
                    out.append(finding("secrets", rule.get("severity", "blocker"),
                                       rpath, no, rule["id"], msg))
    return out


# ---------------------------------------------------------------- 调试与标记

def check_debug(files, rules):
    out = []
    for rule in rules.get("debug", []):
        langs = rule.get("langs")
        pattern = re.compile(rule["pattern"])
        allow = re.compile(rule["allow_pattern"]) if rule.get("allow_pattern") else None
        globs = rule.get("exclude_glob", [])
        for path, rpath, text in files:
            if langs and lang_of(path) not in langs:
                continue
            if rule.get("skip_tests") and is_test_path(rpath):
                continue
            if any(fnmatch.fnmatch(rpath, g) for g in globs):
                continue
            for no, line in enumerate(text.splitlines(), 1):
                if allow and allow.search(line):
                    continue
                if pattern.search(line):
                    msg = clip(rule.get("message", "调试残留")) + " → " + clip(line, 80)
                    out.append(finding("debug", rule.get("severity", "warning"),
                                       rpath, no, rule["id"], msg))
    return out


def check_markers(files, rules):
    out = []
    for rule in rules.get("markers", []):
        pattern = re.compile(rule["pattern"])
        globs = rule.get("exclude_glob", [])
        for path, rpath, text in files:
            if any(fnmatch.fnmatch(rpath, g) or fnmatch.fnmatch(path.name, g) for g in globs):
                continue
            for no, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    msg = clip(rule.get("message", "遗留标记")) + " → " + clip(line, 80)
                    out.append(finding("markers", rule.get("severity", "info"),
                                       rpath, no, rule["id"], msg))
    return out


# ---------------------------------------------------------------- 冗余

COMMENT_PREFIXES = ("#", "//", "/*", "*", "--")
CODE_HINT_RE = re.compile(
    r"(=>|==|!=|:=|\+=|-=|\bfunction\b|\bdef\b|\bclass\b|\bimport\b|\breturn\b|"
    r"\bconst\b|\bvar\b|\blet\b|\bself\.|\bawait\b|\bnew\s+\w|\w+\(.*\)|"
    r"^\s*\w+\s*[+\-*/]?=\s*\S|"
    r"^(if|elif|else|for|while|with|try|except|finally|match|case|switch)\b.*:\s*$)"
)
COMMENT_NOISE_RE = re.compile(r"^\s*(type|@|eslint|noqa|type:|pylint|pragma)")


def _strip_comment(line: str) -> str:
    stripped = line.strip()
    for prefix in COMMENT_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return ""


def check_commented_code(files, rules):
    min_lines = rules.get("redundancy", {}).get("min_commented_block", 4)
    out = []
    for path, rpath, text in files:
        if lang_of(path) not in {"python", "js"}:
            continue
        if any(part in GENERATED_DIR_NAMES for part in Path(rpath).parts):
            continue
        run, run_start = [], 0
        rows = list(enumerate(text.splitlines(), 1)) + [(0, "")]
        for idx, line in rows:
            body = _strip_comment(line)
            if body and CODE_HINT_RE.search(body) and not COMMENT_NOISE_RE.match(body):
                if not run:
                    run_start = idx
                run.append(body)
                continue
            if len(run) >= min_lines:
                out.append(finding("redundancy", "warning", rpath, run_start, "commented-code",
                                   f"连续 {len(run)} 行被注释掉的代码，应删除（版本库已有历史）"))
            run = []
    return out


TRIVIAL_LINE_RE = re.compile(
    r"^[\s{}()\[\];,]*$|^(else|try|finally|end|pass|return|break|continue)\s*[:{]?$"
)


def check_duplicate_blocks(files, rules):
    cfg = rules.get("redundancy", {})
    window = cfg.get("dup_window", 6)
    min_chars = cfg.get("dup_min_chars", 120)
    buckets = {}
    for path, rpath, text in files:
        if lang_of(path) not in {"python", "js"}:
            continue
        if any(part in GENERATED_DIR_NAMES for part in Path(rpath).parts):
            continue
        norm = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines()]
        for i in range(len(norm) - window + 1):
            block = norm[i:i + window]
            meaningful = [b for b in block if not TRIVIAL_LINE_RE.match(b)]
            if len(meaningful) < window - 1 or sum(len(b) for b in meaningful) < min_chars:
                continue
            key = hashlib.sha1("\n".join(block).encode("utf-8")).hexdigest()
            buckets.setdefault(key, []).append((rpath, i + 1))

    out, seen = [], set()
    for hits in buckets.values():
        if len(hits) < 2:
            continue
        sig = tuple(sorted({h[0] for h in hits}))
        if sig in seen:
            continue
        seen.add(sig)
        others = ", ".join(f"{h[0]}:{h[1]}" for h in hits[1:4])
        out.append(finding("redundancy", "warning", hits[0][0], hits[0][1], "duplicate-block",
                           f"{window} 行代码重复出现于 {others}，可提取公共函数"))
    return out


PY_IMPORT_SKIP_NAMES = {"annotations", "*"}


def _unused_python_imports(rpath, text):
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [finding("structure", "blocker", rpath, exc.lineno or 1,
                        "syntax-error", f"Python 语法错误：{exc.msg}")]
    lines = text.splitlines()
    spans, candidates = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
            for alias in node.names:
                candidates.append((alias.asname or alias.name.split(".")[0], alias.name,
                                   node.lineno))
        elif isinstance(node, ast.ImportFrom):
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
            if node.level and Path(rpath).name == "__init__.py":
                continue
            for alias in node.names:
                if alias.name in PY_IMPORT_SKIP_NAMES:
                    continue
                candidates.append((alias.asname or alias.name, alias.name, node.lineno))
    if not candidates:
        return []
    skip = set()
    for start, end in spans:
        for i in range(start, end + 1):
            if lines[i - 1].strip().startswith(("import ", "from ")):
                skip.add(i)
    body_parts = []
    for i, line in enumerate(lines, 1):
        if i in skip:
            if ";" in line:
                body_parts.append(line.split(";", 1)[1])
            continue
        body_parts.append(line)
    body = "\n".join(body_parts)
    out = []
    for local, original, lineno in candidates:
        if not local or local in PY_IMPORT_SKIP_NAMES:
            continue
        if re.search(rf"\b{re.escape(local)}\b", body):
            continue
        out.append(finding("redundancy", "warning", rpath, lineno, "unused-import",
                           f"导入了 {original} 但正文未使用"))
    return out


JS_IMPORT_RE = re.compile(
    r"^[ \t]*import\s+(?:(?P<clause>[^'\"]+?)\s+from\s+)?['\"](?P<mod>[^'\"]+)['\"]", re.M
)
JS_KEYWORDS = {"import", "from", "as", "default", "type", "of"}


def _unused_js_imports(rpath, text):
    spans, candidates = [], []
    for m in JS_IMPORT_RE.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        spans.append((line_no, line_no + m.group(0).count("\n")))
        clause = m.group("clause")
        if not clause:
            continue
        for name in re.findall(r"[A-Za-z_$][\w$]*", clause):
            if name not in JS_KEYWORDS:
                candidates.append((name, m.group("mod"), line_no))
    if not candidates:
        return []
    keep = set()
    for start, end in spans:
        keep.update(range(start, end + 1))
    body = "\n".join(line for i, line in enumerate(text.splitlines(), 1) if i not in keep)
    out = []
    for name, mod, lineno in candidates:
        if re.search(rf"(?<![\w$.]){re.escape(name)}(?![\w$])", body):
            continue
        out.append(finding("redundancy", "warning", rpath, lineno, "unused-import",
                           f"从 {mod} 导入的 {name} 未使用"))
    return out


def check_long_signatures(files, rules):
    max_lines = rules.get("redundancy", {}).get("max_function_lines", 60)
    out = []
    for path, rpath, text in files:
        if lang_of(path) != "python" or is_test_path(rpath):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = getattr(node, "end_lineno", None)
            if end and end - node.lineno + 1 > max_lines:
                size = end - node.lineno + 1
                out.append(finding("redundancy", "warning", rpath, node.lineno, "long-function",
                                   f"函数 {node.name} 有 {size} 行（阈值 {max_lines}），建议拆分"))
    return out


def check_empty_bodies(files, rules):
    cfg = rules.get("redundancy", {})
    out = []
    for path, rpath, text in files:
        if lang_of(path) != "python":
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [
                stmt for stmt in node.body
                if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str))
            ]
            if len(body) != 1 or not isinstance(body[0], ast.Pass):
                continue
            out.append(finding("redundancy", "info", rpath, node.lineno, "empty-body",
                               f"函数 {node.name} 只有 pass，是否写完了？"))
    return out


def check_long_files(files, rules):
    cfg = rules.get("redundancy", {})
    max_lines = cfg.get("max_file_lines", 800)
    exempt = cfg.get("file_exempt_glob", [])
    out = []
    for path, rpath, text in files:
        if lang_of(path) not in {"python", "js"}:
            continue
        if any(fnmatch.fnmatch(rpath, g) for g in exempt):
            continue
        count = text.count("\n") + 1
        if count > max_lines:
            out.append(finding("redundancy", "info", rpath, 1, "long-file",
                               f"文件 {count} 行（阈值 {max_lines}），考虑按职责拆分"))
    return out


# ---------------------------------------------------------------- 结构完整性

def _parse_requirements(root: Path):
    deps = []
    for name in ("requirements.txt", "requirements/base.txt", "backend/requirements.txt"):
        path = root / name
        if not path.exists():
            continue
        for line in (read_text(path) or "").splitlines():
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            dep = re.split(r"[=<>!~\[; ]", line)[0].strip().lower()
            if dep:
                deps.append(dep.replace("_", "-"))
    return deps


def check_python_deps(root: Path, files, rules):
    if not rules.get("structure", {}).get("check_python_deps", True):
        return []
    dep_set = set(_parse_requirements(root))
    if not dep_set:
        return []
    stdlib = set(getattr(sys, "stdlib_module_names", ())) or STDLIB_FALLBACK
    local = set()
    bases = [root] + [root / sub for sub in ("backend", "src", "app")]
    for base in bases:
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                local.add(child.name)
    for path, rpath, _text in files:
        if lang_of(path) == "python" and not is_test_path(rpath):
            local.add(path.stem)
    used = {}
    for path, rpath, text in files:
        if lang_of(path) != "python" or is_test_path(rpath):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [(node.module or "").split(".")[0]]
            for name in names:
                if not name or name in stdlib or name in local:
                    continue
                used.setdefault(name.lower(), (rpath, node.lineno))
    out = []
    for name, (rpath, lineno) in sorted(used.items()):
        dist = PY_DIST_ALIAS.get(name, name).replace("_", "-")
        if dist in dep_set or name.replace("_", "-") in dep_set:
            continue
        out.append(finding("structure", "warning", rpath, lineno, "undeclared-dependency",
                           f"import 了第三方包 {name}，但 requirements.txt 未声明（应写 {dist}）"))
    return out


def check_django_apps(root: Path, files, rules):
    if not rules.get("structure", {}).get("check_django_apps", True):
        return []
    out = []
    for path, rpath, _text in files:
        if path.name != "apps.py":
            continue
        app_dir = path.parent
        app = rel(app_dir, root)
        if not (app_dir / "__init__.py").exists():
            out.append(finding("structure", "warning", rpath, 1, "django-app",
                               f"{app} 缺少 __init__.py，可能不被识别为 Python 包"))
        if (app_dir / "models.py").exists() and not (app_dir / "migrations").is_dir():
            out.append(finding("structure", "warning", rpath, 1, "django-app",
                               f"{app} 有 models.py 但没有 migrations/，确认是否要 makemigrations"))
        if not (app_dir / "tests.py").exists() and not (app_dir / "tests").is_dir():
            out.append(finding("structure", "warning", rpath, 1, "django-app",
                               f"{app} 没有 tests.py 或 tests/，改动此 app 必须补测试"))
    return out


def check_django_settings(files, rules):
    if not rules.get("structure", {}).get("check_django_settings", True):
        return []
    out = []
    for path, rpath, text in files:
        if path.name != "settings.py":
            continue
        for no, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if re.match(r"^DEBUG\s*=\s*True", s):
                out.append(finding("structure", "warning", rpath, no, "django-debug",
                                   "DEBUG=True 硬编码，生产环境会泄露堆栈与配置"))
            elif re.match(r"^ALLOWED_HOSTS\s*=\s*\[['\"]\*", s):
                out.append(finding("structure", "warning", rpath, no, "django-hosts",
                                   "ALLOWED_HOSTS 含通配符 *，建议改为具体域名"))
            elif re.search(r"CORS_(ORIGIN|ALLOW)_[A-Z_]*ALL", s) and "True" in s:
                out.append(finding("structure", "info", rpath, no, "django-cors",
                                   "CORS 全放开，确认是否只用于本地调试"))
    return out


def _module_name(mod: str) -> str:
    if mod.startswith("@"):
        return "/".join(mod.split("/")[:2])
    return mod.split("/")[0]


def _collect_js_imports(pkg_dir: Path, files):
    imported = {}
    for path, rpath, text in files:
        if lang_of(path) != "js" or is_test_path(rpath):
            continue
        if pkg_dir not in path.parents:
            continue
        for m in JS_IMPORT_RE.finditer(text):
            mod = m.group("mod")
            if mod.startswith((".", "/", "node:", "@/", "~/")):
                continue
            lineno = text[: m.start()].count("\n") + 1
            imported.setdefault(_module_name(mod), (rpath, lineno))
    return imported


def check_frontend_deps(root: Path, files, rules, all_files=None):
    """文件改动模式下，判断「依赖是否被引用」必须看整个 src，否则会把未改动的引用算成未使用。"""
    cfg = rules.get("structure", {})
    if not cfg.get("check_frontend_deps", True):
        return []
    out = []
    for cand in ("package.json", "frontend/package.json"):
        pkg_path = root / cand
        if not pkg_path.exists():
            continue
        try:
            data = json.loads(read_text(pkg_path) or "{}")
        except json.JSONDecodeError:
            out.append(finding("structure", "blocker", rel(pkg_path, root), 1,
                               "bad-package-json", "package.json 不是合法 JSON"))
            continue
        declared = dict(data.get("dependencies") or {}, **(data.get("devDependencies") or {}))
        pkg_dir = pkg_path.parent
        imported = _collect_js_imports(pkg_dir, files)
        imported_all = imported if all_files is None else _collect_js_imports(pkg_dir, all_files)

        for name, (rpath, lineno) in sorted(imported.items()):
            if name in declared or name in NODE_BUILTINS:
                continue
            out.append(finding("structure", "warning", rpath, lineno, "undeclared-dependency",
                               f"import 了 {name}，但 package.json 未声明依赖"))

        ignore = cfg.get("frontend_ignore_deps", [])
        for name in sorted(declared):
            if name in imported_all or name in ignore:
                continue
            if name.startswith(("@types/", "eslint", "prettier", "sass")):
                continue
            out.append(finding("structure", "info", rel(pkg_path, root), 1, "unused-dependency",
                               f"package.json 声明的 {name} 未被 src 引用，确认是否可移除"))
    return out


def check_env_management(root: Path, files, rules):
    if not rules.get("structure", {}).get("check_env", True):
        return []
    out = []
    gitignore = root / ".gitignore"
    ignore_text = (read_text(gitignore) or "") if gitignore.exists() else ""
    if (root / ".env").exists():
        tracked = False
        try:
            res = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"],
                                 cwd=root, capture_output=True, text=True, check=False)
            tracked = res.returncode == 0
        except (OSError, subprocess.SubprocessError):
            tracked = False
        if tracked:
            out.append(finding("secrets", "blocker", ".env", 1, "tracked-env",
                               ".env 已进版本库，密钥全部泄露：git rm --cached .env"))
        elif not re.search(r"^\s*(\.env|\*\.env|\.env\.\*)\s*$", ignore_text, re.M):
            out.append(finding("structure", "warning", ".gitignore", 1, "env-not-ignored",
                               ".gitignore 未忽略 .env，存在误提交风险"))
        if not (root / ".env.example").exists():
            out.append(finding("structure", "info", ".env", 1, "no-env-example",
                               "有 .env 却没有 .env.example，新成员不知道要配哪些变量"))
    used = set()
    for path, rpath, text in files:
        if lang_of(path) != "python":
            continue
        pattern = r"(?:os\.environ\.get|os\.getenv|os\.environ\[)\s*\(?\s*['\"]([A-Z][A-Z0-9_]{2,})"
        used.update(re.findall(pattern, text))
    example = root / ".env.example"
    if used and example.exists():
        declared = set(re.findall(r"^\s*([A-Z][A-Z0-9_]*)", read_text(example) or "", re.M))
        missing = sorted(used - declared)
        if missing:
            out.append(finding("structure", "info", ".env.example", 1, "env-example-incomplete",
                               "代码读取但 .env.example 未列出：" + ", ".join(missing[:8])))
    return out


def check_doc_names(root: Path, rules):
    """docs/dev/ 下的文档名必须是 <feature>.<文档类型>.md。"""
    if not rules.get("structure", {}).get("check_doc_names", True):
        return []
    dev = root / "docs" / "dev"
    if not dev.is_dir():
        return []
    out = []
    kinds = "/".join(DOC_KINDS)
    for feat in sorted(p for p in dev.iterdir() if p.is_dir()):
        for md in sorted(feat.glob("*.md")):
            parts = md.name.split(".")
            valid = (
                len(parts) >= 3
                and parts[0] == feat.name
                and parts[-1] == "md"
                and ".".join(parts[1:-1]) in DOC_KINDS
            )
            if not valid:
                out.append(finding("structure", "warning", rel(md, root), 1, "doc-name",
                                   f"文档名看不出属于哪个需求，应为 {feat.name}.<类型>.md，"
                                   f"类型取 {kinds}"))
    return out


def check_orphan_files(files, rules):
    cfg = rules.get("structure", {})
    if not cfg.get("check_orphans", False):
        return []
    out = []
    modules = {}
    for path, rpath, _text in files:
        if lang_of(path) != "python" or path.stem in {"__init__", "manage", "settings", "conftest"}:
            continue
        if is_test_path(rpath) or any(p in GENERATED_DIR_NAMES for p in Path(rpath).parts):
            continue
        modules[path.stem] = rpath
    if not modules:
        return out
    corpus = "\n".join(text for _p, _r, text in files)
    for stem, rpath in sorted(modules.items()):
        body = corpus.replace(rpath, "")
        if not re.search(rf"\b{re.escape(stem)}\b", body):
            out.append(finding("structure", "info", rpath, 1, "orphan-file",
                               f"{rpath} 未被任何文件 import 或引用，确认是否遗留"))
    return out


# ---------------------------------------------------------------- 代码规范

def check_style(files, rules):
    cfg = rules.get("style", {})
    max_len = cfg.get("max_line_length", 120)
    out = []
    for path, rpath, text in files:
        if lang_of(path) not in {"python", "js"}:
            continue
        lines = text.splitlines()
        trailing, long_lines = [], 0
        for no, line in enumerate(lines, 1):
            if cfg.get("check_trailing_whitespace", True) and line != line.rstrip():
                trailing.append(no)
            if max_len and len(line) > max_len:
                long_lines += 1
                out.append(finding("style", "info", rpath, no, "long-line",
                                   f"行宽 {len(line)} 超过 {max_len}"))
        if trailing:
            out.append(finding("style", "info", rpath, trailing[0], "trailing-whitespace",
                               f"{len(trailing)} 行存在行尾空白，首个在第 {trailing[0]} 行"))
        if cfg.get("check_final_newline", True) and text and not text.endswith("\n"):
            out.append(finding("style", "info", rpath, len(lines), "no-final-newline",
                               "文件末尾缺少换行"))
        if cfg.get("check_mixed_indent", True) and lang_of(path) == "python":
            has_tab = any(re.match(r"^\t+\S", line) for line in lines)
            has_space = any(re.match(r"^ {2,}\S", line) for line in lines)
            if has_tab and has_space:
                out.append(finding("style", "warning", rpath, 1, "mixed-indent",
                                   "同时使用 Tab 和空格缩进，统一为 4 空格"))
        if text[:3].startswith("\ufeff"):
            out.append(finding("style", "info", rpath, 1, "bom", "文件带 UTF-8 BOM"))
    return out


# ---------------------------------------------------------------- 编排

def collect_changed_files(root: Path):
    changed = set()
    commands = (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    for args in commands:
        try:
            res = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode == 0:
            changed.update(line.strip().replace("\\", "/")
                           for line in res.stdout.splitlines() if line.strip())
    return changed


def load_corpus(root: Path, rules: dict, only_paths=None):
    corpus = []
    for path, rpath in iter_files(root, rules, only_paths):
        text = read_text(path)
        if text is not None:
            corpus.append((path, rpath, text))
    return corpus


def run_audit(root: Path, rules: dict, only=None, use_diff=False, strict=False,
              as_json=False) -> int:
    only_paths = collect_changed_files(root) if use_diff else None
    if use_diff and not only_paths:
        print("没有检测到未提交改动，改为全项目扫描。")
        only_paths = None

    corpus = load_corpus(root, rules, only_paths)
    if not corpus:
        print("没有可扫描的代码文件，仅检查项目结构与文档命名。")

    def wanted(name):
        return not only or name in only

    results = []
    if wanted("secrets"):
        results += check_secrets(corpus, rules)
        results += check_env_management(root, corpus, rules)
    if wanted("debug"):
        results += check_debug(corpus, rules)
    if wanted("markers"):
        results += check_markers(corpus, rules)
    if wanted("redundancy"):
        for path, rpath, text in corpus:
            if lang_of(path) == "python":
                results += _unused_python_imports(rpath, text)
            elif lang_of(path) == "js":
                results += _unused_js_imports(rpath, text)
        results += check_commented_code(corpus, rules)
        results += check_duplicate_blocks(corpus, rules)
        results += check_long_signatures(corpus, rules)
        results += check_empty_bodies(corpus, rules)
        results += check_long_files(corpus, rules)
    if wanted("structure"):
        full_corpus = corpus if only_paths is None else load_corpus(root, rules)
        results += check_python_deps(root, corpus, rules)
        results += check_django_apps(root, corpus, rules)
        results += check_django_settings(corpus, rules)
        results += check_frontend_deps(root, corpus, rules, full_corpus)
        results += check_orphan_files(corpus, rules)
        results += check_doc_names(root, rules)
    if wanted("style"):
        results += check_style(corpus, rules)

    results.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["check"],
                                f["path"], f["line"] or 0))

    if as_json:
        payload = {"root": str(root), "scanned": len(corpus), "findings": results}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_report(results, len(corpus), only_paths is not None)

    counts = {s: sum(1 for f in results if f["severity"] == s) for s in SEVERITY_ORDER}
    if counts["blocker"] or (strict and counts["warning"]):
        return 1
    return 0


def print_report(results, scanned: int, diff_mode: bool) -> None:
    scope = "本次改动" if diff_mode else "全项目"
    print(f"== 质量体检（{scope}，扫描 {scanned} 个文件）==")
    if not results:
        print("\n未发现问题。别忘了人工复核：冗余抽象、交付一致性、日志敏感信息。")
        return

    by_check = {}
    for f in results:
        by_check.setdefault(f["check"], []).append(f)

    for check in CHECK_NAMES:
        items = by_check.get(check)
        if not items:
            continue
        print(f"\n-- {CHECK_LABELS[check]}（{len(items)}）")
        for f in items[:24]:
            loc = f"{f['path']}:{f['line']}"
            print(f"   [{SEVERITY_TAG[f['severity']]:7}] {loc}  {f['message']}")
        if len(items) > 24:
            print(f"   … 另有 {len(items) - 24} 条同类问题（--json 查看全部）")

    counts = {s: sum(1 for f in results if f["severity"] == s) for s in SEVERITY_ORDER}
    print(f"\n汇总：blocker {counts['blocker']} / warning {counts['warning']} "
          f"/ info {counts['info']}")
    if counts["blocker"]:
        print("有 blocker，必须修复后才能报「完成」。")
    elif counts["warning"]:
        print("无 blocker。warning 逐条判断：真问题就修，"
              "误报就把 allow_pattern 写进 audit_rules.json。")
