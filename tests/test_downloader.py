import httpx
import pytest

from daily_arxiv.downloader import DownloadError, archive_path_for, download_source_archive, source_dir_for
from daily_arxiv.models import Paper


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
