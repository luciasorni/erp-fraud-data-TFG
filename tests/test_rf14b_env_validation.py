from __future__ import annotations

import os
import subprocess


def test_rf14b_p05_validate_required_env_pre_langsmith_ok() -> None:
    proc = subprocess.run(
        ["python3", "scripts/validate_required_env.py", "--profile", "pre_langsmith"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "OK env validation profile=pre_langsmith" in proc.stdout


def test_rf14b_p05_validate_required_env_langsmith_fails_when_missing() -> None:
    env = dict(os.environ)
    env.pop("LANGSMITH_API_KEY", None)
    env.pop("LANGSMITH_PROJECT", None)
    proc = subprocess.run(
        ["python3", "scripts/validate_required_env.py", "--profile", "langsmith"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 1
    assert "faltan variables para perfil=langsmith" in proc.stderr
