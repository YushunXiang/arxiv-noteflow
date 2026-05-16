from __future__ import annotations

from pathlib import Path
import tarfile


class UnsafeArchiveError(RuntimeError):
    pass


def extract_archive(archive_path: Path, target_dir: Path) -> Path:
    archive_path = Path(archive_path)
    target_dir = Path(target_dir)
    if target_dir.exists() and any(target_dir.iterdir()):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = (target_root / member.name).resolve()
            if not _is_relative_to(member_path, target_root):
                raise UnsafeArchiveError(f"Archive member escapes target directory: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(f"Archive member has unsafe type: {member.name}")
        tar.extractall(target_root, filter="data")
    return target_dir


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
