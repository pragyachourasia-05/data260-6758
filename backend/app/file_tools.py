"""HW7 Part 6: file tools confined to a sandbox directory, plus a pure-Python bash safety gate.

Tools: read_file, write_file, edit_file, glob_files, search_in_files, bash.
Every path is resolved inside SANDBOX; anything that escapes it is refused.

Safety gate
  SAFE_PREFIXES               allow-list of command prefixes that may run without asking
  is_destructive(command)     independent deny-list check (returns bool)
  confirm_bash(command, auto_approve=False) -> {"allowed": bool, "reason": str}
A destructive command is blocked unless explicit confirmation (auto_approve=True) is supplied,
even when it starts with a SAFE_PREFIXES entry (e.g. "ls && rm -rf ~").
"""
from __future__ import annotations

import difflib
import fnmatch
import re
import subprocess
from pathlib import Path

SANDBOX = Path.cwd()  # set_sandbox() points this at a temporary course directory

# Read-only commands only. ("python -c" was removed in v2: it can run arbitrary code.)
SAFE_PREFIXES = (
    "ls", "dir", "pwd", "echo", "cat", "type", "head", "tail", "wc", "grep", "find",
    "python --version", "git status", "git log", "git diff",
)

# (reason, pattern) - each matched anywhere in the command, including after ; && || | and $( ) or ` `
DESTRUCTIVE_PATTERNS = [
    ("recursive deletion", r"\brm\s+(-[a-z]*[rf][a-z]*\s+)*-[a-z]*r|\brm\s+-[a-z]*\s*-r|\brmdir\s+/s\b|\bdel\s+/s\b|"
                           r"\bremove-item\b.*-recurse|\bshutil\.rmtree\b|\bfind\b.*(-delete\b|-exec\s+rm\b)"),
    ("privilege escalation", r"(^|[;&|(`\s])(sudo|su|doas|runas)\b|\bstart-process\b.*-verb\s+runas"),
    ("permission/ownership change", r"\b(chmod|chown|chgrp|icacls|takeown|setfacl)\b"),
    ("raw-device write", r"\bdd\b.*\bof=/dev/|>\s*/dev/(sd|nvme|hd|disk|xvd)|\\\\\.\\physicaldrive"),
    ("filesystem creation", r"\b(mkfs(\.\w+)?|mke2fs|mkswap|format(\.com)?\s+[a-z]:|diskpart|fdisk|parted|wipefs)\b"),
    ("redirection to a root path", r">>?\s*(/(etc|bin|sbin|usr|boot|lib|dev|root|sys|proc|var)\b|/\s*$|/[^\s]*\s*$(?<=/)|"
                                   r"[a-z]:\\(windows|program files)|c:\\\s*$)"),
]


def set_sandbox(path: str | Path) -> Path:
    global SANDBOX
    SANDBOX = Path(path).resolve()
    SANDBOX.mkdir(parents=True, exist_ok=True)
    return SANDBOX


def _inside(path: str) -> Path:
    p = (SANDBOX / path).resolve()
    if p != SANDBOX and SANDBOX not in p.parents:
        raise PermissionError(f"path escapes the sandbox: {path}")
    return p


def _rel(p: Path) -> str:
    return p.relative_to(SANDBOX).as_posix()


def ok(data) -> dict:
    return {"success": True, "data": data}


def fail(error: str) -> dict:
    return {"success": False, "error": error}


# ---------------------------------------------------------------- file tools

def read_file(path: str, max_lines: int | None = None) -> dict:
    try:
        lines = _inside(path).read_text(encoding="utf-8").splitlines()
    except (OSError, PermissionError) as exc:
        return fail(str(exc))
    shown = lines[:max_lines] if max_lines else lines
    return ok({"path": path, "content": "\n".join(shown), "lines_shown": len(shown), "total_lines": len(lines),
               "truncated": len(shown) < len(lines)})


def write_file(path: str, content: str) -> dict:
    try:
        p = _inside(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except (OSError, PermissionError) as exc:
        return fail(str(exc))
    return ok({"path": path, "bytes": len(content.encode("utf-8"))})


def edit_file(path: str, old: str, new: str) -> dict:
    """Replace exactly one occurrence of `old` and return a short unified diff."""
    try:
        p = _inside(path)
        before = p.read_text(encoding="utf-8")
    except (OSError, PermissionError) as exc:
        return fail(str(exc))
    count = before.count(old)
    if count != 1:
        return fail(f"'old' must occur exactly once (found {count})")
    after = before.replace(old, new, 1)
    p.write_text(after, encoding="utf-8")
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", lineterm="", n=1)
    return ok({"path": path, "diff": "\n".join(list(diff)[:20])})


def glob_files(pattern: str) -> dict:
    try:
        matches = sorted(_rel(p) for p in SANDBOX.glob(pattern) if p.is_file() and SANDBOX in p.resolve().parents)
    except (ValueError, NotImplementedError) as exc:
        return fail(f"bad pattern: {exc}")
    return ok({"pattern": pattern, "files": matches})


def search_in_files(pattern: str, file_pattern: str = "*", max_results: int = 50) -> dict:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return fail(f"bad regex: {exc}")
    hits = []
    for p in sorted(SANDBOX.rglob("*")):
        if not p.is_file() or not fnmatch.fnmatch(p.name, file_pattern):
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if rx.search(line):
                hits.append({"path": _rel(p), "line": n, "text": line.strip()[:200]})
                if len(hits) >= max_results:
                    return ok({"pattern": pattern, "file_pattern": file_pattern, "matches": hits, "truncated": True})
    return ok({"pattern": pattern, "file_pattern": file_pattern, "matches": hits, "truncated": False})


# ---------------------------------------------------------------- safety gate

def destructive_reasons(command: str) -> list[str]:
    cmd = " ".join(command.strip().lower().split())
    return [reason for reason, rx in DESTRUCTIVE_PATTERNS if re.search(rx, cmd)]


def is_destructive(command: str) -> bool:
    return bool(destructive_reasons(command))


def confirm_bash(command: str, auto_approve: bool = False) -> dict:
    cmd = " ".join(command.strip().split())
    reasons = destructive_reasons(cmd)
    if reasons:  # checked first and independently of SAFE_PREFIXES
        if auto_approve:
            return {"allowed": True, "reason": f"destructive ({', '.join(reasons)}) - explicit confirmation supplied"}
        return {"allowed": False, "reason": f"blocked: destructive ({', '.join(reasons)}) needs explicit confirmation"}
    # v2: every chained/piped segment must be allow-listed, and command substitution never is.
    segments = [s.strip() for s in re.split(r"&&|\|\||;|\||\n", cmd) if s.strip()]
    substitution = "$(" in cmd or "`" in cmd
    if segments and not substitution and all(
        any(seg.lower() == p or seg.lower().startswith(p + " ") for p in SAFE_PREFIXES) for seg in segments
    ):
        return {"allowed": True, "reason": "every segment matches SAFE_PREFIXES and none is destructive"}
    if auto_approve:
        return {"allowed": True, "reason": "not in SAFE_PREFIXES - explicit confirmation supplied"}
    return {"allowed": False, "reason": "blocked: not in SAFE_PREFIXES (needs confirmation)"}


def bash(command: str, auto_approve: bool = False, timeout: int = 20) -> dict:
    gate = confirm_bash(command, auto_approve)
    if not gate["allowed"]:
        return fail(gate["reason"])
    try:
        proc = subprocess.run(command, shell=True, cwd=SANDBOX, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return fail(f"timed out after {timeout}s")
    return ok({"command": command, "exit_code": proc.returncode, "stdout": proc.stdout[-2000:],
               "stderr": proc.stderr[-1000:], "gate": gate["reason"]})
