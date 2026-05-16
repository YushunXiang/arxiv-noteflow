from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    id: str
    title: str
    authors: list[str]
    subjects: list[str]
    category: str
    date: str
    abs_url: str
    src_url: str


@dataclass(frozen=True)
class DateGroup:
    date: str
    heading: str
    category: str
    papers: list[Paper]


@dataclass(frozen=True)
class PaperResult:
    paper: Paper
    archive_path: str
    source_dir: str
    status: str
    error: str | None = None
