"""The secrets files and generated data must never be committable.

Checked with `git check-ignore`, so the test follows the real .gitignore
rules rather than reading the file's text.
"""

import subprocess

import pytest

MUST_BE_IGNORED = [
    ".env",
    ".env.local",
    ".streamlit/secrets.toml",
    "data/patients.csv",
]

MUST_BE_TRACKABLE = [
    ".env.example",
]


def is_ignored(path: str) -> bool:
    # Exit code 0: ignored; 1: not ignored; anything else: git failed.
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path],
        capture_output=True,
        check=False,  # exit code 1 is an answer, not an error
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode())
    return result.returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_secrets_and_data_are_ignored(path):
    assert is_ignored(path), f"{path} could be committed"


@pytest.mark.parametrize("path", MUST_BE_TRACKABLE)
def test_examples_are_not_ignored(path):
    assert not is_ignored(path), f"{path} is ignored but must be committed"
