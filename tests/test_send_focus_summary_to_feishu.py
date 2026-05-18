from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "send_focus_summary_to_feishu.py"


def load_script():
    spec = importlib.util.spec_from_file_location("send_focus_summary_to_feishu", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_note(root: Path, slug: str, title: str, arxiv_id: str, body: str) -> Path:
    note_dir = root / slug
    note_dir.mkdir()
    note_path = note_dir / f"{slug}.md"
    note_path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                f'arxiv_id: "{arxiv_id}"',
                f'arxiv_url: "https://arxiv.org/abs/{arxiv_id}"',
                f'pdf_url: "https://arxiv.org/pdf/{arxiv_id}.pdf"',
                "published: 2026-05-18",
                "updated: 2026-05-18",
                'categories: ["cs.RO"]',
                "---",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return note_path


def test_build_summary_prioritizes_requested_focus_areas(tmp_path: Path) -> None:
    module = load_script()
    date_dir = tmp_path / "papers" / "2026-05-18"
    date_dir.mkdir(parents=True)

    vla_note = write_note(
        date_dir,
        "vla-long-horizon",
        "Learning Bilevel Policies over Symbolic World Models for Long-Horizon Planning",
        "2605.10000",
        """
## 简短总结
- We tackle the challenge of building embodied AI agents that can solve long-horizon planning tasks with VLA policies.
## 方法
- 使用 Vision-Language-Action 模型处理语言目标，并通过层级规划执行长时程任务。
## 可落地实现想法
- 可作为 VLA 长程任务调度的候选基线。
""",
    )
    write_note(
        date_dir,
        "umi-egocentric",
        "Learning Sim-Grounded Policies for Bimanual Rope Manipulation from Human Teleoperation",
        "2605.10001",
        """
## 简短总结
- 使用 UMI-style human teleoperation data 和 egocentric camera observations 学习双臂操作策略。
## 方法
- 从第一视角演示抽取动作轨迹，再做仿真落地。
""",
    )
    write_note(
        date_dir,
        "unrelated",
        "Optimizing Line Segment Inspection with Limited Range Drones",
        "2605.10002",
        """
## 简短总结
- 讨论有限航程无人机巡检路径优化。
""",
    )

    lark_report = tmp_path / "downloads" / "2026-05-18" / "lark-import-report.json"
    lark_report.parent.mkdir(parents=True)
    lark_report.write_text(
        """
        {
          "successes": [
            {
              "file": "%s",
              "url": "https://example.feishu.cn/docx/exampledoc"
            }
          ]
        }
        """
        % vla_note,
        encoding="utf-8",
    )

    notes = module.load_notes(date_dir, module.load_lark_doc_refs(lark_report))
    summary = module.build_summary("2026-05-18", notes, max_items=5)

    assert "2026-05-18 论文重点摘要" in summary
    assert "Long-horizon" in summary
    assert "Egocentric" in summary
    assert "UMI" in summary
    assert "VLA" in summary
    assert "Learning Bilevel Policies" in summary
    assert "Learning Sim-Grounded Policies" in summary
    assert "Optimizing Line Segment Inspection" not in summary
    assert "We tackle the challenge" not in summary
    assert "https://arxiv.org/abs/2605.10000" in summary
    assert "飞书文档：https://example.feishu.cn/docx/exampledoc" in summary


def test_feishu_payload_and_chunking() -> None:
    module = load_script()
    chunks = module.chunk_text("abc\n\n" + ("x" * 12), max_chars=10)

    assert chunks == ["abc", "xxxxxxxxxx", "xx"]
    assert module.build_feishu_text_payload("hello") == {
        "msg_type": "text",
        "content": {"text": "hello"},
    }


def test_send_chunks_waits_between_messages() -> None:
    module = load_script()
    posted: list[str] = []
    slept: list[float] = []

    module.send_feishu_chunks(
        "https://example.test/hook",
        ["first", "second"],
        send_interval=1.5,
        post_func=lambda _url, text: posted.append(text),
        sleep_func=lambda seconds: slept.append(seconds),
    )

    assert posted == ["[1/2]\nfirst", "[2/2]\nsecond"]
    assert slept == [1.5]


def test_lark_report_refs_keep_first_report_when_duplicates(tmp_path: Path) -> None:
    module = load_script()
    note_path = tmp_path / "paper.md"
    first_report = tmp_path / "lark-reimport-report.json"
    second_report = tmp_path / "lark-import-report.json"

    first_report.write_text(
        '{"successes":[{"file":"%s","url":"https://example.feishu.cn/docx/new"}]}'
        % note_path,
        encoding="utf-8",
    )
    second_report.write_text(
        '{"successes":[{"file":"%s","url":"https://example.feishu.cn/docx/old"}]}'
        % note_path,
        encoding="utf-8",
    )

    refs = module.load_lark_doc_refs_from_reports([first_report, second_report])

    assert refs[module.normalize_path_key(note_path)] == "https://example.feishu.cn/docx/new"


def test_load_env_file_sets_missing_webhook_without_overriding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "FEISHU_WEBHOOK_URL=https://example.test/from-env",
                "EXISTING_VALUE=from_env_file",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("EXISTING_VALUE", "from_shell")

    module.load_env_file(env_file)

    assert os.environ["FEISHU_WEBHOOK_URL"] == "https://example.test/from-env"
    assert os.environ["EXISTING_VALUE"] == "from_shell"


def test_main_loads_webhook_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script()
    date_dir = tmp_path / "papers" / "2026-05-18"
    date_dir.mkdir(parents=True)
    write_note(
        date_dir,
        "vla",
        "Vision-Language-Action Policy",
        "2605.10000",
        "## 简短总结\n- VLA policy for robot manipulation.\n",
    )
    (tmp_path / ".env").write_text(
        "FEISHU_WEBHOOK_URL=https://example.test/from-dotenv\n",
        encoding="utf-8",
    )
    sent: list[tuple[str, list[str]]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        module,
        "send_feishu_chunks",
        lambda webhook_url, chunks, **_kwargs: sent.append((webhook_url, chunks)),
    )

    result = module.main(["--date", "2026-05-18", "--max-chars", "18000"])

    assert result == 0
    assert sent
    assert sent[0][0] == "https://example.test/from-dotenv"
