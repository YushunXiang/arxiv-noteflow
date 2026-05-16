#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATE_LINE_RE = re.compile(r"^\S+\s+(\d{4}-\d{2}-\d{2})\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a daily-arxiv reading manifest.")
    parser.add_argument("--repo", default=".", help="Path to the daily-arxiv repository.")
    parser.add_argument("--category", default="cs.RO", help="arXiv recent category.")
    parser.add_argument("--date", help="Visible arXiv recent date in YYYY-MM-DD format.")
    parser.add_argument("--download-output", default="downloads", help="daily-arxiv download output root.")
    parser.add_argument("--notes-output", default="papers", help="Root directory for generated notes.")
    parser.add_argument("--manifest", help="Manifest path. Defaults to <date-dir>/daily-arxiv-manifest.json.")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay passed to daily-arxiv download.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout passed to daily-arxiv download.")
    parser.add_argument("--keep-going", action="store_true", help="Continue after individual paper failures.")
    parser.add_argument("--skip-download", action="store_true", help="Use an existing downloads/<date>/metadata.jsonl.")
    parser.add_argument("--max-papers", type=int, help="Limit manifest papers after reading metadata.")
    return parser.parse_args()


def resolve_repo(path: str) -> Path:
    repo = Path(path).expanduser().resolve()
    if not (repo / "src" / "daily_arxiv" / "cli.py").exists():
        raise SystemExit(f"daily-arxiv repo not found or missing src/daily_arxiv/cli.py: {repo}")
    return repo


def resolve_under_repo(repo: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def run_download(args: argparse.Namespace, repo: Path, output_root: Path) -> str:
    cmd = [
        "uv",
        "run",
        "daily-arxiv",
        "download",
        args.category,
        "--output",
        str(output_root),
        "--delay",
        str(args.delay),
        "--timeout",
        str(args.timeout),
    ]
    if args.date:
        cmd.extend(["--date", args.date])
    if args.keep_going:
        cmd.append("--keep-going")

    completed = subprocess.run(cmd, cwd=repo, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, file=sys.stderr, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")

    if completed.returncode != 0:
        print(f"daily-arxiv exited with status {completed.returncode}; trying to use metadata if available.", file=sys.stderr)
    return completed.stdout + "\n" + completed.stderr


def parse_date_from_output(category: str, output: str) -> str | None:
    prefix = f"{category} "
    for line in output.splitlines():
        if not line.startswith(prefix):
            continue
        match = DATE_LINE_RE.match(line)
        if match:
            return match.group(1)
    return None


def latest_date_dir(output_root: Path) -> Path:
    candidates = [
        path
        for path in output_root.iterdir()
        if path.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and (path / "metadata.jsonl").exists()
    ]
    if not candidates:
        raise SystemExit(f"No dated metadata directories found under {output_root}")
    return sorted(candidates, key=lambda path: path.name)[-1]


def load_metadata(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
    return records


def read_toplevel_tex(source_dir: Path) -> list[str]:
    readme = source_dir / "00README.json"
    if not readme.exists():
        return []
    try:
        data = json.loads(readme.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    result: list[str] = []
    for item in data.get("sources", []):
        if item.get("usage") != "toplevel":
            continue
        filename = item.get("filename")
        if isinstance(filename, str):
            tex_path = source_dir / filename
            result.append(str(tex_path.resolve() if tex_path.exists() else tex_path))
    return result


def resolve_metadata_path(repo: Path, value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path
    return str(path.resolve())


def build_manifest(
    args: argparse.Namespace,
    repo: Path,
    output_root: Path,
    notes_root: Path,
    date_dir: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    records = load_metadata(metadata_path)
    if args.max_papers is not None:
        records = records[: args.max_papers]

    papers: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    suggested_notes_root = notes_root / date_dir.name
    for record in records:
        source_dir = Path(record.get("source_dir", ""))
        if not source_dir.is_absolute():
            source_dir = repo / source_dir
        source_dir = source_dir.resolve()

        paper = {
            "id": record.get("id"),
            "metadata_title": record.get("title"),
            "authors": record.get("authors", []),
            "subjects": record.get("subjects", []),
            "category": record.get("category", args.category),
            "date": record.get("date", date_dir.name),
            "abs_url": record.get("abs_url"),
            "src_url": record.get("src_url"),
            "pdf_url": f"https://arxiv.org/pdf/{record.get('id')}.pdf",
            "source_dir": str(source_dir),
            "toplevel_tex": read_toplevel_tex(source_dir),
            "status": record.get("status"),
            "error": record.get("error"),
            "suggested_notes_root": str(suggested_notes_root.resolve()),
        }
        papers.append(paper)
        if record.get("status") == "failed":
            failed.append(paper)

    return {
        "repo": str(repo),
        "category": args.category,
        "date": date_dir.name,
        "download_output": str(output_root),
        "notes_output": str(notes_root),
        "metadata_path": str(metadata_path),
        "papers": papers,
        "failed": failed,
    }


def main() -> int:
    args = parse_args()
    repo = resolve_repo(args.repo)
    output_root = resolve_under_repo(repo, args.download_output)
    notes_root = resolve_under_repo(repo, args.notes_output)

    cli_output = ""
    if not args.skip_download:
        cli_output = run_download(args, repo, output_root)

    selected_date = args.date or parse_date_from_output(args.category, cli_output)
    date_dir = output_root / selected_date if selected_date else latest_date_dir(output_root)
    metadata_path = date_dir / "metadata.jsonl"
    if not metadata_path.exists():
        raise SystemExit(f"metadata.jsonl not found: {metadata_path}")

    manifest = build_manifest(args, repo, output_root, notes_root, date_dir, metadata_path)
    manifest_path = Path(args.manifest).expanduser() if args.manifest else date_dir / "daily-arxiv-manifest.json"
    if not manifest_path.is_absolute():
        manifest_path = repo / manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest["manifest_path"] = str(manifest_path.resolve())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
