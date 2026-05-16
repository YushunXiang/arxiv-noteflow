from __future__ import annotations

from pathlib import Path
import os
import time

import httpx

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
