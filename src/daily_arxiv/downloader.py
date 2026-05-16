from __future__ import annotations

import json
from pathlib import Path
import os
import time

import httpx

from daily_arxiv.extractor import extract_archive
from daily_arxiv.models import DateGroup, Paper, PaperResult

USER_AGENT = "daily-arxiv/0.1.0 (+https://arxiv.org)"


class DownloadError(RuntimeError):
    pass


def _safe_paper_id(paper: Paper) -> str:
    return paper.id.replace("/", "-")


def archive_path_for(paper: Paper, output_dir: Path) -> Path:
    return Path(output_dir) / "archives" / f"{_safe_paper_id(paper)}.tar.gz"


def source_dir_for(paper: Paper, output_dir: Path) -> Path:
    return Path(output_dir) / "sources" / _safe_paper_id(paper)


def download_source_archive(paper: Paper, output_dir: Path, client: httpx.Client) -> tuple[Path, str]:
    archive_path = archive_path_for(paper, output_dir)
    if archive_path.exists() and archive_path.stat().st_size > 0:
        return archive_path, "skipped"

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = archive_path.with_suffix(archive_path.suffix + ".tmp")
    headers = {"User-Agent": USER_AGENT}
    try:
        with client.stream("GET", paper.src_url, headers=headers) as response:
            if response.status_code != 200:
                raise DownloadError(f"Failed to download {paper.src_url}: HTTP {response.status_code}")
            with tmp_path.open("wb") as file:
                for chunk in response.iter_bytes():
                    if chunk:
                        file.write(chunk)
    except httpx.HTTPError as exc:
        raise DownloadError(f"Failed to download {paper.src_url}: {exc}") from exc

    os.replace(tmp_path, archive_path)
    return archive_path, "downloaded"


def download_group(
    group: DateGroup,
    output_root: Path,
    client: httpx.Client | None = None,
    delay: float = 3.0,
    keep_going: bool = False,
    timeout: float = 30.0,
) -> list[PaperResult]:
    date_dir = Path(output_root) / group.date
    date_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout)

    results: list[PaperResult] = []
    try:
        for index, paper in enumerate(group.papers):
            try:
                archive_path, status = download_source_archive(paper, date_dir, client)
                source_dir = source_dir_for(paper, date_dir)
                extract_archive(archive_path, source_dir)
                archive_path.unlink(missing_ok=True)
                results.append(PaperResult(paper, str(archive_path), str(source_dir), status))
            except Exception as exc:
                result = PaperResult(
                    paper,
                    str(archive_path_for(paper, date_dir)),
                    str(source_dir_for(paper, date_dir)),
                    "failed",
                    str(exc),
                )
                results.append(result)
                if not keep_going:
                    _write_metadata(date_dir / "metadata.jsonl", results)
                    raise
            if delay > 0 and index < len(group.papers) - 1:
                time.sleep(delay)
    finally:
        if owns_client:
            client.close()

    _write_metadata(date_dir / "metadata.jsonl", results)
    return results


def _write_metadata(path: Path, results: list[PaperResult]) -> None:
    lines = [json.dumps(_metadata_record(result), ensure_ascii=False) for result in results]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _metadata_record(result: PaperResult) -> dict[str, object]:
    paper = result.paper
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "subjects": paper.subjects,
        "date": paper.date,
        "category": paper.category,
        "abs_url": paper.abs_url,
        "src_url": paper.src_url,
        "archive_path": result.archive_path,
        "source_dir": result.source_dir,
        "status": result.status,
        "error": result.error,
    }
