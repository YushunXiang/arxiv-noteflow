import json
import tarfile
from io import BytesIO

import httpx
import pytest

from daily_arxiv.downloader import DownloadError, archive_path_for, download_group, download_source_archive, source_dir_for
from daily_arxiv.models import DateGroup, Paper


def _paper() -> Paper:
    return Paper(
        id="2605.15157",
        title="Hand-in-the-Loop",
        authors=["Zhuohang Li"],
        subjects=["Robotics (cs.RO)"],
        category="cs.RO",
        date="2026-05-15",
        abs_url="https://arxiv.org/abs/2605.15157",
        src_url="https://arxiv.org/src/2605.15157",
    )


def _old_style_paper() -> Paper:
    return Paper(
        id="math/0309136",
        title="Old-Style Arxiv ID",
        authors=["Example Author"],
        subjects=["Mathematics"],
        category="math",
        date="2003-09-13",
        abs_url="https://arxiv.org/abs/math/0309136",
        src_url="https://arxiv.org/src/math/0309136",
    )


def _tar_bytes() -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = b"content"
        info = tarfile.TarInfo("main.tex")
        info.size = len(data)
        tar.addfile(info, BytesIO(data))
    return buffer.getvalue()


def test_archive_path_for_normalizes_old_style_arxiv_id(tmp_path) -> None:
    assert archive_path_for(_old_style_paper(), tmp_path) == tmp_path / "archives" / "math-0309136.tar.gz"


def test_source_dir_for_normalizes_old_style_arxiv_id(tmp_path) -> None:
    assert source_dir_for(_old_style_paper(), tmp_path) == tmp_path / "sources" / "math-0309136"


def test_download_source_archive_writes_temp_then_final_file(tmp_path) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, content=b"archive-bytes")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    archive_path, status = download_source_archive(_paper(), tmp_path, client)

    assert status == "downloaded"
    assert archive_path == tmp_path / "archives" / "2605.15157.tar.gz"
    assert archive_path.read_bytes() == b"archive-bytes"
    assert seen_urls == ["https://arxiv.org/src/2605.15157"]
    assert not list(archive_path.parent.glob("*.tmp"))


def test_download_source_archive_skips_existing_non_empty_file(tmp_path) -> None:
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archive_path = archive_dir / "2605.15157.tar.gz"
    archive_path.write_bytes(b"existing")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called when archive exists")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result_path, status = download_source_archive(_paper(), tmp_path, client)

    assert status == "skipped"
    assert result_path == archive_path
    assert archive_path.read_bytes() == b"existing"


def test_download_source_archive_raises_for_http_error(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"missing")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(DownloadError) as exc_info:
        download_source_archive(_paper(), tmp_path, client)

    assert "Failed to download https://arxiv.org/src/2605.15157: HTTP 404" in str(exc_info.value)


def test_download_group_downloads_extracts_and_writes_metadata(tmp_path) -> None:
    paper = _paper()
    group = DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[paper])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_tar_bytes())

    client = httpx.Client(transport=httpx.MockTransport(handler))

    results = download_group(group, tmp_path, client=client, delay=0, keep_going=False)

    date_dir = tmp_path / "2026-05-15"
    assert results[0].status == "downloaded"
    assert (date_dir / "archives" / "2605.15157.tar.gz").exists()
    assert (date_dir / "sources" / "2605.15157" / "main.tex").read_text() == "content"
    records = [json.loads(line) for line in (date_dir / "metadata.jsonl").read_text().splitlines()]
    assert records == [
        {
            "id": "2605.15157",
            "title": "Hand-in-the-Loop",
            "authors": ["Zhuohang Li"],
            "subjects": ["Robotics (cs.RO)"],
            "date": "2026-05-15",
            "category": "cs.RO",
            "abs_url": "https://arxiv.org/abs/2605.15157",
            "src_url": "https://arxiv.org/src/2605.15157",
            "archive_path": str(date_dir / "archives" / "2605.15157.tar.gz"),
            "source_dir": str(date_dir / "sources" / "2605.15157"),
            "status": "downloaded",
            "error": None,
        }
    ]


def test_download_group_keep_going_records_failure(tmp_path) -> None:
    group = DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[_paper()])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    results = download_group(group, tmp_path, client=client, delay=0, keep_going=True)

    assert results[0].status == "failed"
    assert "HTTP 500" in str(results[0].error)
    records = [json.loads(line) for line in (tmp_path / "2026-05-15" / "metadata.jsonl").read_text().splitlines()]
    assert records[0]["status"] == "failed"
    assert "HTTP 500" in records[0]["error"]
