from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import Iterable


FOCUS_AREAS: dict[str, tuple[str, ...]] = {
    "Long-horizon": (
        "long-horizon",
        "long horizon",
        "long-horizon planning",
        "long-horizon task",
        "long-horizon manipulation",
        "long horizon planning",
        "长时程",
        "长程",
        "长周期",
        "长期",
        "长任务",
        "多步",
        "层级",
        "bilevel",
        "hierarchical",
        "symbolic world model",
        "task scheduling",
    ),
    "Egocentric": (
        "egocentric",
        "ego-centric",
        "first-person",
        "first person",
        "onboard",
        "wearable",
        "第一视角",
        "自我中心",
        "机载",
        "头戴",
    ),
    "UMI": (
        "umi",
        "universal manipulation interface",
        "human teleoperation",
        "teleoperation",
        "teleop",
        "demonstration",
        "human demonstration",
        "遥操作",
        "远程操作",
        "人类演示",
        "示教",
    ),
    "VLA": (
        "vla",
        "vision-language-action",
        "vision language action",
        "vision-language action",
        "openvla",
        "visuomotor",
        "visual-language-action",
        "视觉-语言-动作",
        "视觉语言动作",
        "具身",
        "动作模型",
    ),
}

DEFAULT_MAX_ITEMS = 12
DEFAULT_MAX_CHARS = 3600

AREA_CHINESE_HINTS = {
    "Long-horizon": "长时程任务、多步规划或层级决策",
    "Egocentric": "第一视角、自我中心或机载观测",
    "UMI": "人类演示、遥操作或示教数据采集",
    "VLA": "视觉-语言-动作策略或具身动作模型",
}


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


@dataclass(frozen=True)
class PaperNote:
    path: Path
    title: str
    arxiv_id: str
    arxiv_url: str
    lark_doc_url: str
    body: str
    focus_scores: dict[str, int]

    @property
    def total_focus_score(self) -> int:
        return sum(self.focus_scores.values())

    @property
    def matched_areas(self) -> list[str]:
        return [area for area, score in self.focus_scores.items() if score > 0]


def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---", 4)
    if end == -1:
        return {}, text

    raw_frontmatter = text[4:end]
    body_start = text.find("\n", end + 4)
    body = text[body_start + 1 :] if body_start != -1 else ""
    return parse_simple_frontmatter(raw_frontmatter), body


def parse_simple_frontmatter(raw: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        metadata[key.strip()] = value
    return metadata


def score_focus_areas(text: str) -> dict[str, int]:
    lower = text.lower()
    scores: dict[str, int] = {}
    for area, keywords in FOCUS_AREAS.items():
        score = 0
        for keyword in keywords:
            score += lower.count(keyword.lower())
        scores[area] = score
    return scores


def normalize_path_key(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def load_lark_doc_refs(report_path: Path) -> dict[str, str]:
    if not report_path.exists():
        return {}

    data = json.loads(report_path.read_text(encoding="utf-8"))
    successes = data.get("successes", [])
    if not isinstance(successes, list):
        return {}

    refs: dict[str, str] = {}
    for item in successes:
        if not isinstance(item, dict):
            continue
        file_path = item.get("file")
        url = item.get("url")
        if isinstance(file_path, str) and isinstance(url, str) and url:
            refs[normalize_path_key(file_path)] = url
    return refs


def default_lark_report_paths(date: str, papers_root: Path) -> list[Path]:
    if papers_root.is_absolute():
        repo = papers_root.parent
    else:
        repo = Path.cwd()
    downloads_date = repo / "downloads" / date
    return [
        downloads_date / "lark-reimport-report.json",
        downloads_date / "lark-import-report.json",
    ]


def load_lark_doc_refs_from_reports(report_paths: Iterable[Path]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for report_path in report_paths:
        for file_path, url in load_lark_doc_refs(report_path).items():
            refs.setdefault(file_path, url)
    return refs


def load_notes(date_dir: Path, lark_doc_refs: dict[str, str] | None = None) -> list[PaperNote]:
    if not date_dir.exists():
        raise FileNotFoundError(f"Date directory does not exist: {date_dir}")

    lark_doc_refs = lark_doc_refs or {}
    notes: list[PaperNote] = []
    for path in sorted(date_dir.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        metadata, body = strip_frontmatter(text)
        title = metadata.get("title") or path.stem.replace("-", " ")
        arxiv_id = metadata.get("arxiv_id", "")
        arxiv_url = metadata.get("arxiv_url") or (
            f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        )
        scores = score_focus_areas(f"{title}\n{body}")
        notes.append(
            PaperNote(
                path=path,
                title=title,
                arxiv_id=arxiv_id,
                arxiv_url=arxiv_url,
                lark_doc_url=lark_doc_refs.get(normalize_path_key(path), ""),
                body=body,
                focus_scores=scores,
            )
        )
    return notes


def summarize_note(note: PaperNote) -> str:
    hints = [AREA_CHINESE_HINTS[area] for area in note.matched_areas]
    keyword_evidence = ", ".join(extract_matched_keywords(note)[:6]) or "未提取到关键词"
    focus_text = "、".join(hints) if hints else "指定重点方向"
    return (
        f"这篇与{focus_text}相关。"
        f"Markdown 命中的关键线索包括：{keyword_evidence}。"
        "建议优先精读其任务定义、数据来源、策略接口和真实/仿真评估。"
    )


def extract_matched_keywords(note: PaperNote) -> list[str]:
    text = f"{note.title}\n{note.body}".lower()
    matched: list[str] = []
    for area in note.matched_areas:
        for keyword in FOCUS_AREAS[area]:
            if keyword.lower() in text and keyword not in matched:
                matched.append(keyword)
    return matched


def rank_notes(notes: Iterable[PaperNote]) -> list[PaperNote]:
    return sorted(
        notes,
        key=lambda note: (
            note.total_focus_score,
            len(note.matched_areas),
            note.title.lower(),
        ),
        reverse=True,
    )


def format_area_counts(notes: Iterable[PaperNote]) -> str:
    note_list = list(notes)
    parts = []
    for area in FOCUS_AREAS:
        count = sum(1 for note in note_list if note.focus_scores.get(area, 0) > 0)
        parts.append(f"{area} {count} 篇")
    return "，".join(parts)


def build_summary(date: str, notes: list[PaperNote], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    focused = [note for note in rank_notes(notes) if note.total_focus_score > 0]
    selected = focused[:max_items]

    lines = [
        f"{date} 论文重点摘要",
        "",
        f"共读取 {len(notes)} 篇 Markdown；重点方向命中：{format_area_counts(notes)}。",
        "筛选优先级：Long-horizon、Egocentric、UMI、VLA。",
        "",
    ]

    if not selected:
        lines.extend(
            [
                "未在今日笔记中发现明显匹配 Long-horizon / Egocentric / UMI / VLA 的论文。",
                "建议后续扩大关键词或人工复核标题与方法部分。",
            ]
        )
        return "\n".join(lines)

    lines.append("高相关论文：")
    for index, note in enumerate(selected, start=1):
        areas = "、".join(note.matched_areas)
        url_suffix = f" {note.arxiv_url}" if note.arxiv_url else ""
        lines.append(f"{index}. {note.title}")
        lines.append(f"   方向：{areas}；相关性分数：{note.total_focus_score}。")
        lines.append(f"   要点：{summarize_note(note)}")
        if url_suffix:
            lines.append(f"   链接：{url_suffix.strip()}")
        if note.lark_doc_url:
            lines.append(f"   飞书文档：{note.lark_doc_url}")

    lines.extend(["", "方向观察："])
    lines.append(
        "- VLA 相关工作主要集中在把视觉、语言目标和动作生成合到策略或世界模型里，适合继续跟踪泛化能力、训练数据来源和真实机器人验证。"
    )
    lines.append(
        "- Long-horizon 相关工作更依赖层级规划、符号世界模型或任务调度模块，后续可重点比较任务分解接口和失败恢复机制。"
    )
    lines.append(
        "- Egocentric 与 UMI 线索通常和人类演示、遥操作、第一视角观测绑定，值得关注是否能迁移到低成本数据采集和双臂操作。"
    )
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.extend(textwrap.wrap(paragraph, width=max_chars, replace_whitespace=False))
            continue

        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.rstrip())
            current = paragraph

    if current:
        chunks.append(current.rstrip())
    return chunks


def build_feishu_text_payload(text: str) -> dict[str, object]:
    return {"msg_type": "text", "content": {"text": text}}


def post_feishu_text(webhook_url: str, text: str, timeout: float = 10.0) -> None:
    data = json.dumps(build_feishu_text_payload(text), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"Feishu webhook returned HTTP {response.status}: {response_body}")
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError:
            return
        if parsed.get("StatusCode", 0) not in (0, None) or parsed.get("code", 0) not in (0, None):
            raise RuntimeError(f"Feishu webhook rejected message: {response_body}")


def send_feishu_chunks(
    webhook_url: str,
    chunks: list[str],
    send_interval: float,
    rate_limit_retries: int = 3,
    post_func: Callable[[str, str], None] = post_feishu_text,
    sleep_func: Callable[[float], None] = time.sleep,
) -> None:
    for index, chunk in enumerate(chunks, start=1):
        if index > 1 and send_interval > 0:
            sleep_func(send_interval)

        prefix = f"[{index}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        message = f"{prefix}{chunk}"

        for attempt in range(rate_limit_retries + 1):
            try:
                post_func(webhook_url, message)
                break
            except RuntimeError as exc:
                is_rate_limited = "11232" in str(exc) or "frequency limited" in str(exc)
                if not is_rate_limited or attempt >= rate_limit_retries:
                    raise
                sleep_func(send_interval * (attempt + 2))


def split_webhook_urls(values: Iterable[str] | None) -> list[str]:
    urls: list[str] = []
    for value in values or []:
        urls.extend(part.strip() for part in value.split(",") if part.strip())
    return urls


def resolve_webhook_urls(cli_values: list[str] | None) -> list[str]:
    cli_urls = split_webhook_urls(cli_values)
    if cli_urls:
        return cli_urls

    env_urls = os.environ.get("FEISHU_WEBHOOK_URLS")
    if env_urls:
        return split_webhook_urls([env_urls])

    return split_webhook_urls([os.environ.get("FEISHU_WEBHOOK_URL", "")])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize daily paper Markdown notes and send a focused summary to Feishu."
    )
    parser.add_argument("--date", required=True, help="Date folder under papers/, e.g. 2026-05-18.")
    parser.add_argument("--papers-root", default="papers", type=Path)
    parser.add_argument(
        "--webhook-url",
        action="append",
        dest="webhook_urls",
        help=(
            "Feishu custom bot webhook URL. May be passed multiple times; each value may also be "
            "comma-separated. Defaults to FEISHU_WEBHOOK_URLS, then FEISHU_WEBHOOK_URL."
        ),
    )
    parser.add_argument(
        "--lark-report",
        action="append",
        type=Path,
        help=(
            "JSON report from Lark import/reimport containing successes[].file and successes[].url. "
            "May be passed multiple times. Defaults to downloads/<date>/lark-reimport-report.json "
            "and lark-import-report.json when present."
        ),
    )
    parser.add_argument("--max-items", default=DEFAULT_MAX_ITEMS, type=int)
    parser.add_argument("--max-chars", default=DEFAULT_MAX_CHARS, type=int)
    parser.add_argument("--send-interval", default=2.0, type=float)
    parser.add_argument("--rate-limit-retries", default=3, type=int)
    parser.add_argument("--dry-run", action="store_true", help="Print the summary without sending.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_env_file(Path.cwd() / ".env")
    args = parse_args(argv if argv is not None else sys.argv[1:])
    date_dir = args.papers_root / args.date
    report_paths = args.lark_report or default_lark_report_paths(args.date, args.papers_root)
    lark_doc_refs = load_lark_doc_refs_from_reports(report_paths)
    notes = load_notes(date_dir, lark_doc_refs)
    summary = build_summary(args.date, notes, max_items=args.max_items)

    if args.dry_run:
        print(summary)
        return 0

    webhook_urls = resolve_webhook_urls(args.webhook_urls)
    if not webhook_urls:
        print(
            "Missing webhook URL. Pass --webhook-url or set FEISHU_WEBHOOK_URLS/FEISHU_WEBHOOK_URL.",
            file=sys.stderr,
        )
        return 2

    chunks = chunk_text(summary, max_chars=args.max_chars)
    for webhook_url in webhook_urls:
        send_feishu_chunks(
            webhook_url,
            chunks,
            send_interval=args.send_interval,
            rate_limit_retries=args.rate_limit_retries,
        )

    print(f"Sent {len(chunks)} Feishu message(s) to {len(webhook_urls)} webhook(s) for {args.date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
