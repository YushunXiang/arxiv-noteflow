from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "read-daily-arxiv"
    / "scripts"
    / "sync_lark_notes.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location("sync_lark_notes", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sync_date_imports_markdown_and_pushes_assets(tmp_path: Path) -> None:
    module = load_script()
    assert module.DEFAULT_PARENT_FOLDER_TOKEN_ENV == "LARK_PARENT_FOLDER_TOKEN"

    papers_root = tmp_path / "papers"
    paper_dir = papers_root / "2026-05-18" / "a-kinematic-metric-for-fine-manipulation-ability-in-robotic-hands"
    assets_dir = paper_dir / "assets"
    assets_dir.mkdir(parents=True)
    note_path = paper_dir / "a-kinematic-metric-for-fine-manipulation-ability-in-robotic-hands.md"
    note_path.write_text("# note\n", encoding="utf-8")
    (assets_dir / "pipeline.png").write_bytes(b"png")

    commands: list[list[str]] = []
    folder_tokens = {
        ("root_token", "2026-05-18"): "date_token",
        (
            "date_token",
            "a-kinematic-metric-for-fine-manipulation-ability-in-robotic-hands",
        ): "paper_token",
        ("paper_token", "assets"): "assets_token",
    }

    def runner(command: list[str], cwd: Path) -> module.CommandResult:
        commands.append(command)
        if command[:3] == ["lark-cli", "drive", "+search"]:
            parent = command[command.index("--folder-tokens") + 1]
            query = command[command.index("--query") + 1]
            return module.CommandResult(0, '{"data":{"results":[]}}', "")
        if command[:3] == ["lark-cli", "drive", "+create-folder"]:
            parent = command[command.index("--folder-token") + 1]
            name = command[command.index("--name") + 1]
            return module.CommandResult(0, folder_tokens[(parent, name)], "")
        if command[:3] == ["lark-cli", "drive", "+import"]:
            assert command[command.index("--folder-token") + 1] == "date_token"
            assert command[command.index("--file") + 1] == str(note_path)
            return module.CommandResult(0, '{"ticket":"ok"}', "")
        if command[:3] == ["lark-cli", "drive", "+push"]:
            assert command[command.index("--folder-token") + 1] == "assets_token"
            assert command[command.index("--local-dir") + 1] == str(assets_dir.relative_to(tmp_path))
            assert command[command.index("--if-exists") + 1] == "smart"
            return module.CommandResult(0, '{"summary":{"uploaded":1}}', "")
        raise AssertionError(f"Unexpected command: {command}")

    summary = module.sync_date(
        repo=tmp_path,
        papers_root=papers_root,
        date="2026-05-18",
        parent_folder_token="root_token",
        sync_assets=True,
        runner=runner,
    )

    assert summary.imported_markdown == 1
    assert summary.synced_assets == 1
    assert summary.parent_folder_token_configured is True
    assert "parent_folder_token" not in summary.__dict__
    assert summary.date_folder_token == "date_token"
    search_queries = [
        command[command.index("--query") + 1]
        for command in commands
        if command[:3] == ["lark-cli", "drive", "+search"]
    ]
    assert "papers" not in search_queries
    assert [command[:3] for command in commands].count(["lark-cli", "drive", "+push"]) == 1


def test_sync_date_requires_parent_folder_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_script()
    monkeypatch.delenv("LARK_PARENT_FOLDER_TOKEN", raising=False)
    date_dir = tmp_path / "papers" / "2026-05-18"
    date_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="LARK_PARENT_FOLDER_TOKEN"):
        module.sync_date(
            repo=tmp_path,
            papers_root=tmp_path / "papers",
            date="2026-05-18",
            runner=lambda command, cwd: module.CommandResult(0, "", ""),
        )


def test_parse_args_reads_parent_folder_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_script()
    monkeypatch.setenv("LARK_PARENT_FOLDER_TOKEN", "env_parent_token")

    args = module.parse_args(["--date", "2026-05-18"])

    assert args.parent_folder_token == "env_parent_token"


def test_load_env_file_sets_missing_values_without_overriding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LARK_PARENT_FOLDER_TOKEN=from_env_file",
                "EXISTING_VALUE=from_env_file",
                "QUOTED_VALUE=\"quoted value\"",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("LARK_PARENT_FOLDER_TOKEN", raising=False)
    monkeypatch.setenv("EXISTING_VALUE", "from_shell")

    module.load_env_file(env_file)

    assert os.environ["LARK_PARENT_FOLDER_TOKEN"] == "from_env_file"
    assert os.environ["EXISTING_VALUE"] == "from_shell"
    assert os.environ["QUOTED_VALUE"] == "quoted value"


def test_find_or_create_folder_reuses_oldest_exact_duplicate() -> None:
    module = load_script()

    def runner(command: list[str], cwd: Path) -> module.CommandResult:
        assert command[:3] == ["lark-cli", "drive", "+search"]
        return module.CommandResult(
            0,
            """
            {
              "data": {
                "results": [
                  {
                    "title_highlighted": "<em>papers</em>",
                    "result_meta": {"token": "new_token", "create_time": "20"}
                  },
                  {
                    "title_highlighted": "<em>papers</em>",
                    "result_meta": {"token": "old_token", "create_time": "10"}
                  }
                ]
              }
            }
            """,
            "",
        )

    resolved = module.find_or_create_folder(
        repo=Path("/tmp/project"),
        parent_token="root_token",
        folder_name="papers",
        runner=runner,
    )

    assert resolved.token == "old_token"
    assert resolved.created is False
    assert resolved.duplicate_tokens == ["old_token", "new_token"]
