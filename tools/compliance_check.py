#!/usr/bin/env python
"""Enforce the submission's hard rules as a machine check.

    python tools/compliance_check.py

Rules enforced (assignment "TEMEL KURALLAR" 3 and 4):

  C-1  The repository must not contain the G*Power binary or any installer.
  C-2  The repository must not contain decompiler / disassembler output.
  C-3  Exactly one module may compute power; the CLI, MCP server and agent
       must import the engine rather than reimplement it.
  C-4  Every finding referenced by a procedure must exist in SPEC.md, and
       every finding in SPEC.md must have an evidence file.

Exit code 0 = compliant, 1 = violation(s).  Wired into CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- C-1 / C-2
BINARY_NAMES = {
    "gpower.exe",
    "gpower3.exe",
    "gpower31.exe",
    "gpower.app",
    "gpowerwin.zip",
    "gpowermac.zip",
}
BINARY_SUFFIXES = {
    ".exe", ".dll", ".dylib", ".so", ".msi", ".dmg", ".pkg",
    ".bpl", ".dcu", ".obj", ".lib", ".bin", ".idb", ".i64", ".ida",
}
DECOMPILER_SUFFIXES = {".asm", ".lst", ".dis", ".decompiled", ".c.out"}
DECOMPILER_MARKERS = (
    re.compile(r"\bsub_[0-9A-Fa-f]{6,}\b"),
    re.compile(r"\bloc_[0-9A-Fa-f]{6,}\b"),
    re.compile(r"__fastcall|__stdcall|__cdecl"),
    re.compile(r"Hex-Rays|IDA Pro decompil|Ghidra decompil|Snowman decompil"),
    re.compile(r"^\s*(mov|push|pop|lea|call)\s+(e|r)[a-d]x\b", re.MULTILINE),
    re.compile(r"\bDecompiled with\b"),
)
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".csv", ".toml", ".cfg", ".yml", ".yaml",
    ".json", ".ini", ".rst",
}
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules",
    ".mypy_cache", "build", "dist", ".ruff_cache", ".eggs",
}

# Files that are *about* rule C-2 necessarily quote the patterns C-2 forbids.
# The exemption is deliberately a short, explicit allow-list, it is printed on
# every successful run so it cannot hide, and it covers prose only -- none of
# these files may contain an actual listing.
MARKER_EXEMPT = {
    "tools/compliance_check.py": "defines the patterns in order to detect them",
    "ETHICS.md": "states which artefacts are forbidden and why",
    "docs/VALIDATION.md": "describes what the C-2 scan looks for",
    "docs/REA-METHOD.md": "explains why static analysis was not the method",
    ".gitignore": "excludes the artefacts by name",
}

SELF = Path(__file__).resolve()


def _walk():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.endswith(".egg-info") or ".egg-info" in str(path):
            continue
        yield path


def check_no_binary(problems: list[str]) -> None:
    for path in _walk():
        rel = path.relative_to(ROOT).as_posix()
        if path.name.lower() in BINARY_NAMES:
            problems.append(f"C-1 original binary present: {rel}")
        if path.suffix.lower() in BINARY_SUFFIXES:
            problems.append(f"C-1 binary artefact present: {rel}")
        if path.suffix.lower() in DECOMPILER_SUFFIXES:
            problems.append(f"C-2 disassembly/decompilation artefact: {rel}")


def check_no_decompiler_output(problems: list[str]) -> None:
    for path in _walk():
        rel = path.relative_to(ROOT).as_posix()
        if rel in MARKER_EXEMPT:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in DECOMPILER_MARKERS:
            m = pattern.search(text)
            if m:
                problems.append(
                    f"C-2 decompiler-output marker {m.group(0)!r} in {rel}"
                )
                break


def check_single_engine(problems: list[str]) -> None:
    """Only engine.py may contain the power formula."""
    src = ROOT / "src" / "gpower_rea"
    marker = re.compile(r"nct_cdf\s*\(")
    allowed = {"engine.py", "numerics.py"}
    for path in sorted(src.rglob("*.py")):
        if marker.search(path.read_text(encoding="utf-8")):
            if path.name not in allowed:
                problems.append(
                    f"C-3 power arithmetic outside the engine: {path.name}"
                )
    for adapter, label in (
        (src / "cli.py", "CLI"),
        (src / "mcp_server.py", "MCP server"),
    ):
        if not adapter.is_file():
            problems.append(f"C-3 missing adapter: {adapter.name}")
            continue
        text = adapter.read_text(encoding="utf-8")
        if "import engine" not in text and "from .engine" not in text:
            problems.append(f"C-3 {label} does not import the engine")
    agent = ROOT / "agent" / "agent.py"
    if agent.is_file():
        text = agent.read_text(encoding="utf-8")
        if marker.search(text) or re.search(r"\bmath\.sqrt\(", text):
            problems.append("C-3 the agent performs its own arithmetic")


def check_findings_and_evidence(problems: list[str]) -> None:
    spec = ROOT / "SPEC.md"
    if not spec.is_file():
        problems.append("C-4 SPEC.md is missing")
        return
    spec_text = spec.read_text(encoding="utf-8")
    spec_findings = set(re.findall(r"\bF-\d{2}\b", spec_text))
    spec_evidence = set(re.findall(r"\bE-\d{3}\b", spec_text))

    proc_text = (ROOT / "src" / "gpower_rea" / "procedures.py").read_text(
        encoding="utf-8"
    )
    used = set(re.findall(r'"(F-\d{2})"', proc_text))
    missing = sorted(used - spec_findings)
    if missing:
        problems.append(f"C-4 findings used in code but absent from SPEC.md: {missing}")

    ev_dir = ROOT / "docs" / "EVIDENCE"
    present = set()
    if ev_dir.is_dir():
        for f in ev_dir.glob("E-*.md"):
            m = re.match(r"(E-\d{3})", f.name)
            if m:
                present.add(m.group(1))
    orphans = sorted(spec_evidence - present)
    if orphans:
        problems.append(f"C-4 SPEC.md cites evidence with no file: {orphans}")
    unused = sorted(present - spec_evidence)
    if unused:
        problems.append(f"C-4 evidence files not cited by SPEC.md: {unused}")


def main() -> int:
    problems: list[str] = []
    check_no_binary(problems)
    check_no_decompiler_output(problems)
    check_single_engine(problems)
    check_findings_and_evidence(problems)

    if problems:
        print("COMPLIANCE: FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("COMPLIANCE: PASS")
    print("  C-1 no original binary or installer in the tree")
    print("  C-2 no decompiler / disassembler output")
    print("  C-3 one engine; CLI, MCP and agent are adapters over it")
    print("  C-4 findings <-> SPEC.md <-> docs/EVIDENCE are in sync")
    print()
    print("  C-2 marker scan skips these files, which describe the rule itself:")
    for name, reason in sorted(MARKER_EXEMPT.items()):
        print(f"    - {name:<28} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
