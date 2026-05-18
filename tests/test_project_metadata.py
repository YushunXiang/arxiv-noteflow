from __future__ import annotations

import tomllib
from pathlib import Path


def test_project_name_and_console_scripts() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "arxiv-noteflow"
    assert pyproject["project"]["scripts"]["arxiv-noteflow"] == "daily_arxiv.cli:app"
    assert pyproject["project"]["scripts"]["daily-arxiv"] == "daily_arxiv.cli:app"
