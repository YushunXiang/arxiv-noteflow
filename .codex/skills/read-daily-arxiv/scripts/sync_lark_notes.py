#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from typing import Any


DEFAULT_PARENT_FOLDER_TOKEN_ENV = "LARK_PARENT_FOLDER_TOKEN"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class FolderResolution:
    token: str
    created: bool
    duplicate_tokens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SyncSummary:
    parent_folder_token_configured: bool
    date_folder_token: str
    imported_markdown: int
    synced_assets: int
    duplicate_folder_tokens: dict[str, list[str]]


Runner = Callable[[list[str], Path], CommandResult]


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def parent_folder_token_from_env() -> str | None:
    return os.environ.get(DEFAULT_PARENT_FOLDER_TOKEN_ENV)


def run_command(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def strip_search_highlight(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON output from lark-cli, got: {raw.strip()}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from lark-cli, got: {raw.strip()}")
    return data


def token_from_stdout(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise RuntimeError("lark-cli did not return a folder token")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, dict):
        token = parsed.get("data", {}).get("folder_token") or parsed.get("folder_token")
        if isinstance(token, str) and token:
            return token
    raise RuntimeError(f"Could not parse folder token from lark-cli output: {stripped}")


def check_result(result: CommandResult, command: list[str]) -> None:
    if result.returncode == 0:
        return
    command_text = " ".join(command)
    raise RuntimeError(
        f"Command failed with exit code {result.returncode}: {command_text}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def result_token(item: dict[str, Any]) -> str:
    meta = item.get("result_meta", {})
    token = meta.get("token") or item.get("token")
    return token if isinstance(token, str) else ""


def result_create_time(item: dict[str, Any]) -> str:
    meta = item.get("result_meta", {})
    value = meta.get("create_time", "")
    return str(value)


def result_title(item: dict[str, Any]) -> str:
    highlighted = item.get("title_highlighted")
    if isinstance(highlighted, str):
        return strip_search_highlight(highlighted)
    title = item.get("title")
    return title if isinstance(title, str) else ""


def find_or_create_folder(
    repo: Path,
    parent_token: str,
    folder_name: str,
    runner: Runner = run_command,
) -> FolderResolution:
    search_command = [
        "lark-cli",
        "drive",
        "+search",
        "--as",
        "user",
        "--query",
        folder_name,
        "--doc-types",
        "folder",
        "--only-title",
        "--folder-tokens",
        parent_token,
        "--page-size",
        "20",
    ]
    search_result = runner(search_command, repo)
    check_result(search_result, search_command)
    data = load_json_object(search_result.stdout)
    results = data.get("data", {}).get("results", [])
    if not isinstance(results, list):
        results = []

    exact_matches = [
        item
        for item in results
        if isinstance(item, dict) and result_title(item) == folder_name and result_token(item)
    ]
    if exact_matches:
        exact_matches.sort(key=result_create_time)
        tokens = [result_token(item) for item in exact_matches]
        return FolderResolution(token=tokens[0], created=False, duplicate_tokens=tokens if len(tokens) > 1 else [])

    create_command = [
        "lark-cli",
        "drive",
        "+create-folder",
        "--as",
        "user",
        "--folder-token",
        parent_token,
        "--name",
        folder_name,
        "--jq",
        ".data.folder_token",
    ]
    create_result = runner(create_command, repo)
    check_result(create_result, create_command)
    return FolderResolution(token=token_from_stdout(create_result.stdout), created=True)


def markdown_notes(date_dir: Path) -> list[Path]:
    return sorted(path for path in date_dir.glob("**/*.md") if path.is_file())


def has_asset_files(assets_dir: Path) -> bool:
    return assets_dir.is_dir() and any(path.is_file() for path in assets_dir.rglob("*"))


def relative_to_repo(path: Path, repo: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError as exc:
        raise RuntimeError(f"Path must be inside repo for lark-cli drive +push --local-dir: {path}") from exc


def import_markdown(repo: Path, note_path: Path, date_folder_token: str, runner: Runner) -> None:
    command = [
        "lark-cli",
        "drive",
        "+import",
        "--as",
        "user",
        "--type",
        "docx",
        "--folder-token",
        date_folder_token,
        "--file",
        str(note_path),
    ]
    result = runner(command, repo)
    check_result(result, command)


def push_assets(repo: Path, assets_dir: Path, assets_folder_token: str, runner: Runner) -> None:
    command = [
        "lark-cli",
        "drive",
        "+push",
        "--as",
        "user",
        "--local-dir",
        relative_to_repo(assets_dir, repo),
        "--folder-token",
        assets_folder_token,
        "--if-exists",
        "smart",
    ]
    result = runner(command, repo)
    check_result(result, command)


def sync_date(
    repo: Path,
    papers_root: Path,
    date: str,
    parent_folder_token: str | None = None,
    lark_date_folder_name: str | None = None,
    sync_assets: bool = False,
    runner: Runner = run_command,
) -> SyncSummary:
    repo = repo.expanduser().resolve()
    parent_folder_token = parent_folder_token or parent_folder_token_from_env()
    if not parent_folder_token:
        raise ValueError(
            "Missing Lark parent folder token. Set LARK_PARENT_FOLDER_TOKEN in .env "
            "or pass --parent-folder-token."
        )

    papers_root = papers_root.expanduser()
    if not papers_root.is_absolute():
        papers_root = repo / papers_root
    papers_root = papers_root.resolve()
    date_dir = papers_root / date
    if not date_dir.exists():
        raise FileNotFoundError(f"Date directory does not exist: {date_dir}")

    duplicate_folder_tokens: dict[str, list[str]] = {}

    date_folder_name = lark_date_folder_name or date
    date_folder = find_or_create_folder(repo, parent_folder_token, date_folder_name, runner)
    if date_folder.duplicate_tokens:
        duplicate_folder_tokens[date_folder_name] = date_folder.duplicate_tokens

    notes = markdown_notes(date_dir)
    for note_path in notes:
        import_markdown(repo, note_path, date_folder.token, runner)

    synced_assets = 0
    if sync_assets:
        for paper_dir in sorted({note_path.parent for note_path in notes}):
            assets_dir = paper_dir / "assets"
            if not has_asset_files(assets_dir):
                continue
            paper_folder = find_or_create_folder(repo, date_folder.token, paper_dir.name, runner)
            paper_key = f"{date_folder_name}/{paper_dir.name}"
            if paper_folder.duplicate_tokens:
                duplicate_folder_tokens[paper_key] = paper_folder.duplicate_tokens

            assets_folder = find_or_create_folder(repo, paper_folder.token, "assets", runner)
            assets_key = f"{paper_key}/assets"
            if assets_folder.duplicate_tokens:
                duplicate_folder_tokens[assets_key] = assets_folder.duplicate_tokens

            push_assets(repo, assets_dir, assets_folder.token, runner)
            synced_assets += 1

    return SyncSummary(
        parent_folder_token_configured=True,
        date_folder_token=date_folder.token,
        imported_markdown=len(notes),
        synced_assets=synced_assets,
        duplicate_folder_tokens=duplicate_folder_tokens,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync arxiv-noteflow Markdown notes to Lark Drive.")
    parser.add_argument("--repo", default=".", type=Path, help="Path to the arxiv-noteflow repository.")
    parser.add_argument("--date", required=True, help="Local papers date folder, e.g. 2026-05-18.")
    parser.add_argument("--papers-root", default=Path("papers"), type=Path)
    parser.add_argument(
        "--parent-folder-token",
        default=parent_folder_token_from_env(),
        help="Lark Drive parent folder token. Defaults to LARK_PARENT_FOLDER_TOKEN from the environment.",
    )
    parser.add_argument("--lark-date-folder-name")
    parser.add_argument("--sync-assets", action="store_true", help="Upload each paper assets/ directory to Lark.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    load_env_file(Path.cwd() / ".env")
    args = parse_args(argv)
    repo_env = args.repo.expanduser() / ".env"
    if not args.parent_folder_token and repo_env.resolve() != (Path.cwd() / ".env").resolve():
        load_env_file(repo_env)
        args.parent_folder_token = parent_folder_token_from_env()
    summary = sync_date(
        repo=args.repo,
        papers_root=args.papers_root,
        date=args.date,
        parent_folder_token=args.parent_folder_token,
        lark_date_folder_name=args.lark_date_folder_name,
        sync_assets=args.sync_assets,
    )
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
