import io
import tarfile

import pytest

from daily_arxiv.extractor import UnsafeArchiveError, extract_archive


def _write_tar(path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_extract_archive_creates_target_directory(tmp_path) -> None:
    archive = tmp_path / "paper.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    _write_tar(archive, {"main.tex": b"\\documentclass{article}"})

    result = extract_archive(archive, target)

    assert result == target
    assert (target / "main.tex").read_bytes() == b"\\documentclass{article}"


def test_extract_archive_skips_existing_non_empty_directory(tmp_path) -> None:
    archive = tmp_path / "paper.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    target.mkdir(parents=True)
    (target / "main.tex").write_text("existing")
    _write_tar(archive, {"main.tex": b"new"})

    result = extract_archive(archive, target)

    assert result == target
    assert (target / "main.tex").read_text() == "existing"


def test_extract_archive_rejects_path_traversal(tmp_path) -> None:
    archive = tmp_path / "bad.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    _write_tar(archive, {"../escape.tex": b"bad"})

    with pytest.raises(UnsafeArchiveError):
        extract_archive(archive, target)

    assert not (tmp_path / "escape.tex").exists()
