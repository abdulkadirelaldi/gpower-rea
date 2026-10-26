"""The submission rules are a test, not a promise."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compliance_check_passes():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "compliance_check.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "COMPLIANCE: PASS" in proc.stdout


def test_vector_file_is_up_to_date():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_vectors.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_engine_has_no_runtime_dependencies():
    """The engine + CLI must import with nothing but the standard library."""
    code = (
        "import sys\n"
        "blocked = ('numpy', 'scipy', 'pandas', 'mcp', 'anthropic')\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name.split('.')[0] in blocked: return self\n"
        "    def load_module(self, name):\n"
        "        raise ImportError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "from gpower_rea.cli import main\n"
        "assert main(['-t','indep','-a','0.05','-p','0.95','-e','0.5','--json']) == 0\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT)
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_required_documents_exist():
    required = [
        "README.md",
        "LICENSE",
        "SPEC.md",
        "ETHICS.md",
        "docs/REA-METHOD.md",
        "docs/CLI-CONTRACT.md",
        "docs/ARCHITECTURE.md",
        "docs/VALIDATION.md",
        "docs/CLEANROOM-PROTOCOL.md",
        "docs/SESSION-LOG.md",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    assert not missing, f"missing documents: {missing}"


def test_every_spec_finding_is_cited_somewhere_in_code_or_tests():
    import re

    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    findings = sorted(set(re.findall(r"^### (F-\d{2})", spec, re.MULTILINE)))
    assert len(findings) >= 8, "SPEC.md should enumerate the family's findings"
    haystack = ""
    for path in list((ROOT / "src").rglob("*.py")) + list(
        (ROOT / "tests").rglob("*.py")
    ):
        haystack += path.read_text(encoding="utf-8")
    uncited = [f for f in findings if f not in haystack]
    assert not uncited, f"findings never referenced from code or tests: {uncited}"
