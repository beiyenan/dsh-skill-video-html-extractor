---
name: video-html-extractor
description: 从用户上传的音/视频文件提取文案（语音转文字），转成结构化后生成两版单文件 HTML——摘要版（8 种视觉组件混合排版）与阅读版（分段排版、字号/字体/主题可调），并按文案主题自动命名。适用用户上传 .mp4/.mov/.mkv/.mp3/.wav/.m4a/.flac/.ogg 并要求「提取文案」「转成文字」「做成网页/HTML」「可视化」「整理内容」的场景。
---

# 视频文案提取 → 两版可视化 HTML

**一条 skill，一套流程，任何模型都能跑出一致的产物。** 你不需要自己编排步骤，也不要去读渲染器源码。

## 你要做的只有两件事

1. 运行一次 `prepare`（脚本自动完成：提取音频 → ASR 转写 → 机器校正 → 生成骨架 `analysis.json` 和任务单 `TASK.md`）。
2. 按 `TASK.md` 把 `analysis.json` 从骨架填成完整文档，跑 `validate_analysis.py` 自检到 **0 error**，再运行 `finish`（脚本自动校验 + 渲染两版 HTML）。

除此之外的转写、校正、渲染、校验、清理，全部由脚本完成。**不要手改 transcript 或 HTML。**

## 环境变量 / 密钥

已配置，无需向用户询问，也不要写进任何持久文件：

| 用途 | 自动读取 |
|------|---------|
| ASR（硅基流动） | `~/.dsh/secrets/siliconflow_api_key` |
| 机器校正（智谱） | `~/.dsh/secrets/zhipu_api_key` |

默认 ASR 模型：`XingChenAGI/XingChenASR-V3.2-Ultra`（免费，适合口语化）。

## 工作流（就这三步）

### 第 1 步：确认输入文件

确认文件存在、可读。>50MB 时脚本会自动分块，无需你做任何事。

### 第 2 步：prepare（全自动）

```bash
python3 <skill_dir>/scripts/run_pipeline.py prepare <输入文件> [--workers 3]
```

脚本依次做：提取 16k mono WAV → ASR 分块转写 → 智谱机器校正 → 生成骨架 + 任务单。**若工作区已有 `transcript.txt`/`transcript_calibrated.txt` 缓存会直接跳过对应步骤（命中缓存近零成本），且绝不覆盖已有的 `analysis.json`。** 退出码 `0` 成功；`1` 提取失败（看上方输出，若为解码问题走文末降级方案）；`3/4` 校正 key 不可用（跳过校正，你在填 analysis.json 时手工完成即可）。

完成后它会打印：骨架路径、任务单路径、以及低置信度校正项清单。骨架未填完时 validate 报 ERROR 是**预期现象**，不要慌。

### 第 3 步：填 analysis.json（这是你唯一要动的）

1. **读** `TASK.md`（任务单）+ `transcript.txt`（内容来源）+ `transcript_calibrated.txt`（校正稿，正文以它为准）+ `examples/analysis.example.json`（**结构照抄它，别猜字段名**）。
2. 用 write 工具**整体覆盖** `analysis.json`，保留骨架里的正确键名，只填内容：
   - `title`：具体、可检索、≤30 字。禁用泛词（转写/文案/内容整理/transcript/未命名/原始文件名）。例：「耶鲁死亡课：直面死亡才能活明白」。
   - `tone` / `summary` / `hero_facts`(3–6 个记忆点数字) / `sections`(6–10) / `key_takeaways`(5–10，带 [mm:ss] 引用) / `conclusion` / `entities` / `footer.calibration`。
   - `sections` 的 `type` 按内容本质选并配对该字段：`timeline`(时序)/`compare`(对比)/`pair`(痛点解法)/`architecture`(结构)/`flow`(流向)/`quote`(金句)/`list`(清单)/`default`(论述)。**不要全堆成 default。** 具体字段形状看 `examples/analysis.example.json` 与 TASK.md。
3. **红线**：只改高置信度错；不改观点/数字量级/不加事实；金句原样加引号；**所有数字必须能在 transcript.txt 找到出处，禁止编造**。
4. **自检到 0 error**（照 TASK.md 末尾的命令）：
   ```bash
   python3 <skill_dir>/scripts/validate_analysis.py analysis.json --transcript transcript.txt
   ```
   它只报 ERROR（不让过）和 WARN（建议修）。照提示改，重跑，直到 ERROR 全消。

### 第 4 步：finish（全自动）

```bash
python3 <skill_dir>/scripts/run_pipeline.py finish <输入文件> [--theme light|dark]
```

先校验（0 error 才渲染），再生成两版 HTML（文件名自动 = title）：
- **摘要版** `<title>.html`：8 种视觉组件混合，内嵌可搜索逐字稿（ASR 原稿，存证）。
- **阅读版** `<title>_阅读版.html`：校正稿分段排版，A-/A+ 字号、4 款字体、亮暗主题，偏好存 localStorage。

### 第 5 步：交付 + 清理

用 `present` 交付摘要版 + 阅读版 + `transcript.txt`（用户只要部分则按需）。然后删除本次中间产物，只留交付物：`*.html`、`transcript.txt`、`analysis.json`。要删的：`*.wav`、`*.chunks/`、`*_calibrated.txt.calib_cache/`、日志、调试脚本、为装 ffmpeg 下载的 `.deb` 与临时目录。**保留**已装进 `usr/bin/ffmpeg` 的工具链本身。

**红线**：只删本次任务产生的文件；删前用 `ls`/文件名特征确认归属，拿不准就问用户；绝不删输出目录里的历史文件。

## 交付前自查清单（照抄，过一遍即可）

- 校验器已 0 error（title 非泛词、字段名/类型/枚举正确、数字能回溯到原文）。
- 阅读版可正常打开、字号/主题按钮可用；两版均为单文件、无外部依赖。
- 术语校正说明已写在 `footer.calibration`。

## 降级方案（提取失败时）

1. 告知用户无法解码该容器音频轨。
2. 给三个选择：a. 用户手动导成 `.wav`/`.mp3` 再传（从第 2 步起）；b. 有外挂字幕（.srt/.vtt）直接读字幕跳过 ASR；c. 放弃转写，只整理已有文本。
3. **不要**在拿不到真实语音时假装完成转写。

## 边界

- 只处理用户提供的本地文件；不做需登录/付费墙的 URL。
- 不做语音合成、视频剪辑。转写语言以音频实际语言为准；中文效果最好，小语种可能不准需告知用户。
- 所有数字/引语必须能在 `transcript.txt` 找到出处。