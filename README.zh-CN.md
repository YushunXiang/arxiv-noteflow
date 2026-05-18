# arxiv-noteflow

[English](README.md)

从 arXiv 分类 recent 页面下载并解压 LaTeX 源码归档。

`arxiv-noteflow` 是一个面向每日论文处理流程的小型 Python 3.12 CLI。它读取
`https://arxiv.org/list/<category>/recent`，选择页面中可见的日期分组，
从 `https://arxiv.org/src/<id>` 下载每篇论文的源码归档，安全解压，并在
`downloads/<date>/` 下写入确定性的元数据。

本仓库还包含本地自动化辅助脚本，可用于把下载后的论文阅读为 Markdown 笔记、
同步生成的笔记到 Lark/飞书云空间，以及通过飞书 webhook 发送重点摘要。

## 功能

- 列出指定 arXiv 分类 recent 页面中最新可见的日期分组。
- 下载源码归档，并解压到每篇论文独立的源码目录。
- 为每篇下载论文保留 JSON Lines 元数据。
- 使用 `--keep-going` 在单篇论文失败后继续批量下载。
- 生成确定性的阅读 manifest，便于 agent 辅助生成论文笔记。
- 从 `.env` 加载私有 token，将生成的 Markdown 笔记同步到 Lark/飞书云空间。
- 从生成的 Markdown 笔记发送聚焦主题的飞书 webhook 摘要。

## 环境要求

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)

可选工作流工具：

- `lark-cli`，用于 Lark/飞书云空间和文档同步
- 飞书自定义机器人 webhook URL，用于摘要推送

## 安装

```bash
uv sync
```

运行测试：

```bash
uv run pytest
```

## CLI 用法

主 CLI 命令是 `arxiv-noteflow`。旧的 `daily-arxiv` 命令会保留为兼容别名。

列出最新可见日期分组：

```bash
uv run arxiv-noteflow list cs.RO
```

列出指定可见日期分组：

```bash
uv run arxiv-noteflow list cs.RO --date 2026-05-15
```

下载并解压源码归档：

```bash
uv run arxiv-noteflow download cs.RO
uv run arxiv-noteflow download cs.RO --date 2026-05-15
```

使用自定义输出目录：

```bash
uv run arxiv-noteflow download cs.RO --output downloads
```

单篇论文失败后继续处理：

```bash
uv run arxiv-noteflow download cs.RO --keep-going
```

常用网络控制参数：

```bash
uv run arxiv-noteflow download cs.RO --timeout 30 --delay 1.0 --keep-going
```

`--date` 只会选择当前 arXiv recent 页面上可见的日期，不会搜索历史归档。

## 输出结构

```text
downloads/
  2026-05-15/
    metadata.jsonl
    archives/
      2605.15157.tar.gz
    sources/
      2605.15157/
```

生成的论文笔记通常写在下载输出目录之外：

```text
papers/
  2026-05-15/
    paper-slug/
      paper-slug.md
      assets/
```

`downloads/` 和 `papers/` 是运行输出，默认被 git 忽略。

## 环境变量

私有的 Lark/飞书配置从 shell 环境或本地 `.env` 文件读取。先复制模板：

```bash
cp example.env .env
```

然后填写：

```dotenv
LARK_PARENT_FOLDER_TOKEN=
FEISHU_WEBHOOK_URL=
```

不要提交 `.env`。该文件已被 `.gitignore` 忽略。

## Codex Skill

本仓库包含一个本地 Codex skill：
[`.codex/skills/read-daily-arxiv/`](.codex/skills/read-daily-arxiv/)。
它面向端到端的每日论文阅读流程，而不只是原始 CLI 下载。

当你希望 Codex 完成以下任务时，使用这个 skill：

- 下载最新或指定日期的 arXiv recent 页面论文
- 检查每篇论文解压后的 LaTeX 源码树
- 为每篇论文在 `papers/<date>/` 下写一份中文 Markdown 笔记
- 对多篇论文批量阅读时使用并行 agents
- 可选：把生成的 Markdown 笔记同步到 Lark/飞书云空间
- 可选：通过飞书 webhook 发送聚焦摘要

Codex 调用示例：

```text
Use $read-daily-arxiv to download and read today's cs.RO papers.
```

```text
Use $read-daily-arxiv to read cs.RO papers for 2026-05-18, sync the generated notes to Lark, and send the Feishu webhook summary.
```

这个 skill 使用 `arxiv-noteflow` 完成下载，通过 `prepare_daily_batch.py`
写出确定性的阅读 manifest，并按照
[`references/paper-note-spec.md`](.codex/skills/read-daily-arxiv/references/paper-note-spec.md)
控制笔记结构和质量检查。如果需要同步到 Lark/飞书或发送 webhook，请在 `.env`
中配置 `LARK_PARENT_FOLDER_TOKEN` 和 `FEISHU_WEBHOOK_URL`，并确保 `lark-cli`
已完成认证。

## 每日阅读工作流

为最新的 `cs.RO` recent 页面分组准备阅读 manifest：

```bash
python3 .codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo . \
  --category cs.RO \
  --download-output downloads \
  --notes-output papers \
  --keep-going
```

从已经下载好的日期目录准备 manifest：

```bash
python3 .codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo . \
  --category cs.RO \
  --date 2026-05-15 \
  --download-output downloads \
  --notes-output papers \
  --skip-download
```

manifest 会包含每篇论文的元数据路径、解压后的源码目录、顶层 TeX 候选文件、
arXiv URL，以及建议的笔记输出路径。

## Lark/飞书同步

把某个日期的 Markdown 笔记同步到已配置的 Lark 云空间文件夹：

```bash
python3 .codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo . \
  --date 2026-05-18 \
  --papers-root papers
```

同时同步本地笔记资源文件：

```bash
python3 .codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo . \
  --date 2026-05-18 \
  --papers-root papers \
  --sync-assets
```

同步脚本默认从 `.env` 或 shell 环境读取 `LARK_PARENT_FOLDER_TOKEN`；也可以用
`--parent-folder-token` 显式传入。

## 飞书 Webhook 摘要

在生成笔记后，为指定日期发送中文重点摘要：

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --max-chars 18000
```

摘要脚本会读取 `papers/<date>/**/*.md`，优先关注 Long-horizon、Egocentric、
UMI 和 VLA 方向，附带 arXiv 链接，并在存在 Lark 导入报告时加入对应飞书文档链接。

使用 `--dry-run` 可以只预览、不发送：

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --dry-run
```

## 开发说明

- 运行时代码位于 `src/daily_arxiv/`。
- 测试位于 `tests/`。
- 网络行为通过 mock HTTP 响应测试，避免依赖真实 arXiv 请求。
- 不要把生成输出、虚拟环境、缓存或 `.env` 文件加入版本控制。

## 许可证

本项目使用 MIT License。详见 [LICENSE](LICENSE)。
