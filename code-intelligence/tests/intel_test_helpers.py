from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "-c", "core.hooksPath=/dev/null", *args],
        text=True,
    ).strip()


def commit(path: Path, message: str = "fixture") -> str:
    git(path, "add", ".")
    git(
        path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        message,
    )
    return git(path, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "target"
    root.mkdir()
    git(root, "init", "-q")
    sources = {
        "app/__init__.py": "",
        "app/auth.py": (
            'def current_user():\n    """Must authenticate the current tenant."""\n    return 1\n'
        ),
        "app/payments.py": '''from .auth import current_user
from fastapi import FastAPI, Depends
app = FastAPI()

def refund(amount, paid):
    """A refund must never exceed the amount paid."""
    return min(amount, paid)

@app.get("/payments/{payment_id}")
def read_payment(payment_id, user=Depends(current_user)):
    """A customer can only read payments they own."""
    return refund(10, 20)

def dynamic(callback):
    return callback()
''',
        "tests/test_payments.py": """from app.payments import refund

def test_refund_bounds():
    assert refund(30, 20) == 20
""",
        "README.md": "# Payments fixture\nA customer must only access their own payments.\n",
        "pyproject.toml": '[project]\nname="fixture"\ndependencies=["fastapi>=0.110"]\n',
    }
    for name, content in sources.items():
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    return root, commit(root)
