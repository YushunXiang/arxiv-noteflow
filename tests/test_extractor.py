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


def test_extract_archive_rejects_symlink_escape(tmp_path) -> None:
    archive = tmp_path / "bad-link.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    outside = tmp_path / "outside"
    outside.mkdir()

    with tarfile.open(archive, "w:gz") as tar:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = str(outside)
        tar.addfile(link)

        data = b"bad"
        file_info = tarfile.TarInfo("link/evil.tex")
        file_info.size = len(data)
        tar.addfile(file_info, io.BytesIO(data))

    with pytest.raises(UnsafeArchiveError):
        extract_archive(archive, target)

    assert not (outside / "evil.tex").exists()
