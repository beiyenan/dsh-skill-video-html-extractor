# video-html-extractor

> 从用户上传的音视频文件提取文案（语音转文字），并生成**两版单文件 HTML**：阅读版（浅色长文、可搜索逐字稿）与数据看板版（指标卡/逻辑链/时间线/对比表）。产物按文案主题自动命名。

适用于 `.mp4/.mov/.mkv/.mp3/.wav/.m4a/.flac/.ogg` 等音视频文件，要求「提取文案」「转成文字」「做成网页/HTML」「可视化」「整理内容」的场景。

---

## 工作流（6 步）

| 步骤 | 脚本 | 说明 |
|------|------|------|
| 1. 确认输入 | — | 确认文件存在、可读、大小合理（>50MB 会分块转写） |
| 2. 抽音频 | `extract_audio.py` | 解码为重采样 16kHz mono 16bit WAV（ASR 要求） |
| 3. ASR 转写 | `asr_transcribe.py` | 按 120s 切片调硅基流动，拼接带时间戳的 `transcript.txt` |
| 3.5. 校正预筛 | `llm_calibrate.py` | （可选）调智谱 glm 做高置信度校正，产出 `transcript_calibrated.txt` + `report.json` |
| 4. 结构化 | — | 校正终审 → `analysis.json` + `dashboard.json` |
| 5. 生成 HTML | `render_html.py` / `viz_render.py` | 阅读版 + 看板版（`--theme=light\|dark\|both`） |
| 6. 交付 | `present` | 两版 HTML + `transcript.txt` |

## 依赖

- **Python 3**（仅标准库，无第三方 pip 依赖）
- **ffmpeg**（解码 mp4 等容器音轨；Android 直跑需注入 `LD_LIBRARY_PATH`+`LD_PRELOAD`，`extract_audio.py` 已内置）
- **API 密钥**（只读不写）：
  - `SILICONFLOW_API_KEY` 或 `~/.dsh/secrets/siliconflow_api_key` —— ASR（必须）
  - `ZHIPU_API_KEY` 或 `~/.dsh/secrets/zhipu_api_key` —— 机器校正（可选，缺了退纯手工校正）

## 安装到 DSH（DeepSeek Harness）

本 skill 设计为可被 DSH 的 Agent 一键自动安装，无需人工手敲命令。任何一台装好 DSH 的设备上，对 Agent 说：

> 「帮我从 https://github.com/beiyenan/dsh-skill-video-html-extractor 安装 video-html-extractor 这个 skill，并配置好硅基流动和智谱的密钥。」

Agent 会**自动完成**：
1. `git clone` 本仓库
2. 把 `SKILL.md` + `scripts/` 复制到 `~/.dsh/skills/video-html-extractor/`
3. 检查 ffmpeg（缺失则自动安装）
4. 重启 DSH 使 skill 生效

> ⚠️ **密钥不在仓库里**（安全设计，仓库只含读取逻辑不含 key 值）。Agent 安装时你需要**手动提供**：
> - 硅基流动 key → 写入 `~/.dsh/secrets/siliconflow_api_key`（ASR，必须）
> - 智谱 key → 写入 `~/.dsh/secrets/zhipu_api_key`（机器校正，可选）
>
> 脚本运行时优先读环境变量 `SILICONFLOW_API_KEY` / `ZHIPU_API_KEY`，其次读上述 secrets 文件。

**手动安装方式**（不依赖 Agent 时）：
```bash
git clone https://github.com/beiyenan/dsh-skill-video-html-extractor.git
mkdir -p ~/.dsh/skills/video-html-extractor/scripts
cp dsh-skill-video-html-extractor/SKILL.md ~/.dsh/skills/video-html-extractor/
cp dsh-skill-video-html-extractor/scripts/*.py ~/.dsh/skills/video-html-extractor/scripts/
mkdir -p ~/.dsh/secrets
echo "你的硅基流动key" > ~/.dsh/secrets/siliconflow_api_key
echo "你的智谱key"     > ~/.dsh/secrets/zhipu_api_key
chmod 600 ~/.dsh/secrets/*
```
重启 DSH 后 skill 即被识别。

**更新已有副本**：
```bash
cd ~/.dsh/skills/video-html-extractor && git pull
```

## 双轨原则

HTML 正文用**校正稿**表述；`transcript.txt` 永远保留 **ASR 原始逐字稿**，供用户回溯核对。

## 目录结构

```
.
├── SKILL.md            # skill 说明与工作流
├── README.md           # 本文件
└── scripts/
    ├── extract_audio.py     # 抽音频 -> 16kHz mono WAV（主流程）
    ├── asr_transcribe.py    # 分块转写（调硅基流动，主流程）
    ├── llm_calibrate.py     # 机器校正（调智谱，可选，主流程）
    ├── render_html.py       # 阅读版 HTML（主流程）
    ├── viz_render.py        # 看板版 HTML（light/dark/both，主流程）
    ├── decode_aac.py        # 辅助：纯 Python 解 AAC（降级用）
    └── mp4_extract_aac.py   # 辅助：mp4 抽 AAC（降级用）
```

## 许可

请按需补充（建议 MIT / Apache-2.0）。