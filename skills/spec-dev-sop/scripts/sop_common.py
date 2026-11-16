#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-dev-sop 公共常量与工具函数。"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "templates"
RULES_PATH = SCRIPT_DIR / "audit_rules.json"

SEVERITY_ORDER = {"blocker": 0, "warning": 1, "info": 2}
SEVERITY_TAG = {"blocker": "BLOCKER", "warning": "WARNING", "info": "INFO"}

LANG_BY_EXT = {
    ".py": "python",
    ".pyi": "python",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".ts": "js",
    ".tsx": "js",
    ".vue": "js",
    ".scss": "css",
    ".css": "css",
}

CONFIG_EXTS = {".env", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml", ".properties"}

SKIP_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".codebuddy",
    ".idea", ".vscode", "coverage", ".nyc_output", "site-packages", ".tox",
}

GENERATED_DIR_NAMES = {"migrations", "dist", "build", "vendor", "assets"}

CODE_EXTS = set(LANG_BY_EXT) | CONFIG_EXTS | {".html", ".json", ".txt", ".sh", ".ps1", ".bat"}

TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|.*_test\.py$|.*\.test\.(js|ts)$|.*\.spec\.(js|ts)$|^conftest\.py$)"
)

# import 名 -> PyPI 发行包名
PY_DIST_ALIAS = {
    "django": "django",
    "rest_framework": "djangorestframework",
    "corsheaders": "django-cors-headers",
    "dotenv": "python-dotenv",
    "mysqldb": "mysqlclient",
    "pil": "pillow",
    "yaml": "pyyaml",
    "jwt": "pyjwt",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "crypto": "pycryptodome",
    "openssl": "pyopenssl",
    "dateutil": "python-dateutil",
    "decouple": "python-decouple",
    "psycopg2": "psycopg2-binary",
    "drf_spectacular": "drf-spectacular",
    "rest_framework_simplejwt": "djangorestframework-simplejwt",
    "allauth": "django-allauth",
    "debug_toolbar": "django-debug-toolbar",
    "pytest_django": "pytest-django",
    "faker": "faker",
}

NODE_BUILTINS = {
    "fs", "path", "os", "http", "https", "url", "util", "crypto", "stream", "events",
    "child_process", "buffer", "zlib", "net", "tty", "assert", "querystring", "readline",
}

STDLIB_FALLBACK = {
    "abc", "argparse", "ast", "asyncio", "base64", "binascii", "bisect", "calendar", "codecs",
    "collections", "concurrent", "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "email", "enum", "errno", "functools", "gc", "getpass", "glob", "gzip",
    "hashlib", "hmac", "html", "http", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "logging", "math", "mimetypes", "multiprocessing", "operator", "os", "pathlib",
    "pickle", "platform", "pprint", "queue", "random", "re", "secrets", "shutil", "signal",
    "socket", "sqlite3", "ssl", "statistics", "string", "struct", "subprocess", "sys", "tempfile",
    "textwrap", "threading", "time", "timeit", "traceback", "types", "typing", "unicodedata",
    "unittest", "urllib", "uuid", "venv", "warnings", "weakref", "xml", "zipfile", "zlib",
}

DOC_KINDS = ("需求方案", "开发文档", "测试记录", "质量体检")
LEGACY_DOC_NAMES = {
    "需求方案": "plan.md", "开发文档": "design.md",
    "测试记录": "test.md", "质量体检": "review.md",
}

DEFAULT_RULES = {
    "version": 1,
    "scan": {"exclude_glob": [], "max_file_kb": 512},
    "secrets": [],
    "debug": [],
    "markers": [],
    "redundancy": {},
    "structure": {},
    "style": {},
}


def find_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def eprint(*args) -> None:
    print(*args, file=sys.stderr)


def read_text(path: Path):
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def lang_of(path: Path):
    return LANG_BY_EXT.get(path.suffix.lower())


def is_test_path(rpath: str) -> bool:
    return bool(TEST_FILE_RE.search(Path(rpath).name))


def finding(check, severity, path, line, code, message):
    return {
        "check": check,
        "severity": severity,
        "path": path,
        "line": line,
        "code": code,
        "message": message,
    }


def clip(text: str, width: int = 100) -> str:
    text = text.strip().replace("\t", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def iter_files(root: Path, rules: dict, only_paths=None):
    excludes = rules.get("scan", {}).get("exclude_glob", [])
    max_bytes = rules.get("scan", {}).get("max_file_kb", 512) * 1024
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            r = rel(path, root)
            if only_paths is not None and r not in only_paths:
                continue
            if any(fnmatch.fnmatch(r, pat) or fnmatch.fnmatch(name, pat) for pat in excludes):
                continue
            if path.suffix.lower() not in CODE_EXTS and name != ".env":
                continue
            try:
                if path.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            yield path, r


def load_rules(path=None) -> dict:
    path = Path(path) if path else RULES_PATH
    rules = json.loads(json.dumps(DEFAULT_RULES))
    if not path.exists():
        return rules
    try:
        user = json.loads(read_text(path) or "{}")
    except json.JSONDecodeError as exc:
        eprint(f"[warn] 规则文件解析失败，改用内置默认：{exc}")
        return rules
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(rules.get(key), dict):
            rules[key].update(value)
        else:
            rules[key] = value
    return rules
