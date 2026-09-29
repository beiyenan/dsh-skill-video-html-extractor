---
name: video-html-extractor
description: 从用户上传的视频/音频文件提取文案（语音转文字），把转写内容结构化后生成两版单文件 HTML——阅读版（浅色、长文、可搜索逐字稿）与数据看板版（亮/暗主题、指标卡/逻辑链/时间线/对比表），并按文案主题自动命名产物文件。适用于用户上传 .mp4/.mov/.mkv/.mp3/.wav/.m4a/.flac/.ogg 等音视频文件并要求「提取文案」「转成文字」「做成网页/HTML」「可视化」「整理一下内容」的场景。
---

# 视频文案提取 → 双版可视化 HTML

把用户上传的音视频文件转成：
1. 纯文本转写稿（`transcript.txt`）
2. **阅读版** HTML（`render_html.py`）：浅色长文风，适合细读，逐字稿可搜索
3. **看板版** HTML（`viz_render.py`）：数据看板风，指标卡/逻辑链/事件卡/时间线/对比表/结论区；默认亮色（`--theme=light`），可暗色（dark）或一次两版（both）

两份结构化数据（`analysis.json` / `dashboard.json`）**共用第 4 步的校正稿与标题**；两个渲染器只负责呈现，不各自为政。

## 何时使用

- 用户上传音视频文件，要求提取语音内容 / 文案 / 字幕 / 转写
- 用户要求把某段音视频「整理成网页」「做成 HTML」「可视化」「方便理解」
- 用户要求产物按内容命名（如「根据讲的主题给文件命名」）

## 前置：环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `SILICONFLOW_API_KEY` | 硅基流动 API key（ASR） | 未设置时 `asr_transcribe.py` 自动读 `~/.dsh/secrets/siliconflow_api_key`（已配置，**无需向用户询问**）；两处都没有才向用户索取，且**不要写入任何持久文件** |
| `SILICONFLOW_BASE_URL` | ASR 端点 | `https://api.siliconflow.cn/v1` |
| `ZHIPU_API_KEY` | 智谱 API key（机器校正，可选） | 未设置时 `llm_calibrate.py` 自动读 `~/.dsh/secrets/zhipu_api_key`；没有则跳过 3.5 步，校正回退为主模型手工完成 |
| `VIDEO2HTML_OUT` | 输出目录 | 输入文件同目录 |

推荐 ASR 模型：`Qwen/Qwen3-ASR-1.7B`（免费、速度快、中文好）。备选：`XingChenAGI/XingChenASR-V3.2-Ultra`（会输出"嗯"等语气词，适合口语化内容）、`XingChenAGI/XingChenASR-Diarize-V3.0`（带说话人分离）。

## 工作流

### 第 1 步：确认输入文件

用户「上传」的文件通常落在工作区（`/data/data/.../workspaces/incoming/` 或用户指明路径）。确认文件存在、可读、大小合理（>50MB 时提醒会分块转写）。

### 第 2 步：提取/准备音频

```bash
python3 <skill_dir>/scripts/extract_audio.py <输入文件> <输出.wav>
```

脚本把音频重采样为 16kHz mono 16bit WAV（ASR 要求，且必须带 RIFF 头——裸 PCM 会 500）。

| 输入格式 | 本环境（Android/DSH 工具链）表现 |
|----------|--------------------------------------|
| `.wav` | ✅ 纯 Python 重采样，直接可用 |
| `.mp4/.mov`（含 AAC 音频） | ✅ 工具链 ffmpeg（`usr/bin/ffmpeg`）精确提取为 16k mono WAV；脚本自动注入 `LD_LIBRARY_PATH`+`LD_PRELOAD`（Android 直跑会缺 so/preload，已实测解决）。AAC 直传 ASR 不通（500），必须先解码 |
| `.mp3/.m4a/.aac/.flac/.ogg` | ✅ 同样走工具链 ffmpeg 精确解码 |
| `.mkv/.avi/.webm` | ✅ 同样走工具链 ffmpeg（`usr/bin/ffmpeg`）|

> 判断：看退出码。0 = 拿到精确的 16k mono WAV；1 = 提取失败，必须走降级方案。
> 历史备注：若 `usr/bin/ffmpeg` 缺失，按 install-clang.sh 同款思路安装（apt download-only + dpkg-deb 解包平移）。

### 第 3 步：ASR 分块转写

```bash
SILICONFLOW_API_KEY=... python3 <skill_dir>/scripts/asr_transcribe.py <wav文件> <输出txt> \
    [--model Qwen/Qwen3-ASR-1.7B] [--chunk-seconds 120] [--workers 2]
```

脚本把 WAV 按 `chunk-seconds`（默认 120s）切片，**每片重包 RIFF 头**（已验证：裸 PCM 会 500，带才行），逐片 POST 硅基流动 `/audio/transcriptions`，拼接为带时间戳的纯文本：
```
[00:00] 这是开头说的话
[02:03] 第二段内容
```
输出 `transcript.txt`。每片原始 JSON 落盘到 `<wav>.chunks/`，支持断点重跑；单片失败重试 3 次，全失败则退出码 2（已有结果仍写出）。

**`--workers`（默认 2）**：块级并发。实测 15.8 分钟视频（8 块）串行约 2 分钟，并发 2 约 1 分钟；免费档限流紧，不建议 >4。缓存机制与串行完全一致（已完成的块直接命中，重跑免费）。

### 第 3.5 步：机器校正预筛（可选，建议执行——省下 4a 的大部分时间）

```bash
python3 <skill_dir>/scripts/llm_calibrate.py <transcript.txt> <transcript_calibrated.txt> \
    [--model glm-4.7] [--workers 2] [--max-chars 2500] [--report report.json]
```

用智谱 `glm-4.7`（2025-09 实测的免费档；key 读 `~/.dsh/secrets/zhipu_api_key`）对转写稿做**高置信度预校正**，产出：
- `transcript_calibrated.txt`——校正稿（保留 `[mm:ss]` 行结构，头部标注"预筛"）
- `*.report.json`——逐条 `changes`（含 reason 与 high/low 置信度）+ 跨块术语表 `glossary`

脚本内建防线（均实测过）：校正红线写死在 prompt（只改同音字/专名/数字规范/行内碎句，不改观点与数量级；不确定标 low 且正文保持原文）；**行级时间戳校验**——LLM 合并跨行碎句时会吞掉 `[mm:ss]`，校验失败自动进入单行修复二次调用；429/1302 限流长退避（默认并发 2）；**双泳道调度**（workers 条泳道内按块序号顺序执行，术语表沿泳道前滚，修复纯并发下专名前后不一致的竞态）；每块缓存可断点重跑，收尾自动清理旧 prompt 版本的残留缓存；模型不支持 `thinking` 字段时 400 自动去掉再试。15 分钟视频约 1-2 分钟跑完。

`--max-chars`（默认 1500）：块越小失败粒度越小、并发利用率高、缓存复用多；`--workers`（默认 2）：免费档限流紧，不建议 >4。

退出码：`0` 成功｜`2` 个别块失败（该块保留原文，不影响使用）｜`3` 无余额/无资源包｜`4` 鉴权失败。**退出码 3/4 不要死磕**：告知用户 key 不可用，4a 回到纯手工流程。

### 第 4 步：文案校正 + 结构化理解

**由你（agent）负责校正与理解**，分两阶段工作。

#### 4a. 校正终审（优先基于 3.5 的产物）

**有 3.5 产物时**：只需读 `report.json` 逐条终审 `changes`——accept（保留）/ reject（按原文从校正稿回改），low 条目重点核对，`glossary` 并入 `entities` 候选。实体 grep 自检仍要做（对象改为校正稿）。主模型不再逐字重写全文。

**没有 3.5 产物时**（key 不可用或用户未配置）：读取 `transcript.txt` 全文，按下表逐段手工修正，在脑内/笔记完成即可（`transcript.txt` 原文保持不动作为存证）。

ASR 原始输出常见问题：

| 问题类型 | 例子（本项目实测） | 处理 |
|----------|------------------|------|
| 专有名词听错 | 《巨翅死亡》→《拒斥死亡》(Becker, *The Denial of Death*) | 有把握就改，并把正确写法记入 `entities` |
| 中文数字混排 | "PHIL幺七六"→PHIL 176、"四百五十五美元"→455 美元 | 结构化稿统一为阿拉伯数字 |
| 跨分块断句 | 块边界把一句话劈成两半、产生"高。出整整九倍"式碎句 | 按上下文缝合 |
| 同音字/口误 | "确知"可能是"怕死"的误听 | **不确定就不改**，保留原文；只有语境+常识双重支持才修正 |
| 重复口癖 | "这个这个"、"就是说"高频重复 | 结构化稿省略，逐字稿保留 |

**校正红线**：
- 只改「高置信度」的错；改错的代价大于不改。
- 修正不改观点、不改数字量级、不添加原文没有的事实。
- 双轨原则：HTML 正文/要点用校正后表述；**逐字稿区永远展示 ASR 原文**，供用户回溯核对。

#### 4b. 结构化理解（基于校正后的理解，写入 `analysis.json`）

- `title`：**必须根据转写全文的实际主题拟定**——读完全部内容后概括「这到底在讲什么」，产出具体、可检索的标题（≤30字），并直接用于产物文件命名。硬要求（`render_html.py` 会强制校验，泛词直接拒绝渲染）：
  - ❌ 禁止泛称：「转写」「视频文案」「内容整理」「transcript」「未命名」及其组合；
  - ❌ 禁止直接拿原始视频文件名当标题；
  - ✅ 正确示例：「耶鲁死亡课：直面死亡才能活明白」「2026 年中端手机选购指南」——有主题词、有观点或范围，别人扫一眼文件名就知道内容；
  - 若内容跨多主题，取占比最大的主线主题，不要罗列。标题同时是 HTML 的 `<title>`/`<h1>` 和输出文件名。
- `summary`：3-5 句话概括全文
- `sections`：按内容逻辑切分，每项 `{heading, content(要点列表), key_points}`
- `key_takeaways`：5-10 条最重要的结论/数字/建议（带引用原文时间戳）
- `entities`：出现的人名/产品/地名/专有名词
- `timeline`（可选）：如果内容有明显时间顺序，给 `{time, event}` 列表
- `tone`：语气判断（教程/访谈/演讲/新闻/…）

#### 4c. 为看板版再整理一份 `dashboard.json`

看板版不吃 `sections` 长文，吃「结构化要素」。把 4b 的成果按下面映射重排（内容、标题、时间戳**复用**，不重新创作）：

| dashboard 字段 | 从哪来 |
|----------------|--------|
| `title` / `subtitle` / `tags` | 与 analysis 同一 `title`；subtitle=summary 压缩成 1-2 句；tags=主题标签 |
| `metrics`（3-10 个大数字卡） | 全文最有冲击力的数字（数字+单位+一句标签），`tone`: acc/red/green/blue/purple |
| `chain`（叙事逻辑链） | 内容推进的因果/步骤顺序，3-7 步 |
| `events`（事件/证据卡） | 支撑论点的实验、案例、事故 |
| `timeline` | 有明显时序或历史案例对照时 |
| `tables`（对比表） | 多方案/多主体横向比较（观点、路径、竞品…） |
| `points`（编号观点卡） | 讲者明确列出的主张/建议 |
| `list`（排名清单+“没有的东西”） | 讲者给的排序清单；`missing` 放「清单里缺席的那些」这类反差句 |
| `framework`（2-4 列行动框架） | 可执行建议归成的维度 |
| `conclusion`（金句收尾） | 原文结语/引语，`quote` 必须是原话 |
| `footer.calibration`（存疑脚注） | 把 4a 的校正表转写成人话：**改了什么、哪些存疑未改、以原视频为准** |
| `entities` | 与 analysis 一致，仍要逐条 grep 自检 |

硬约束（与方案一致）：数字/引语忠实原文，不编造；没有对应素材的字段直接省略（渲染器按缺省跳过模块）。

原则：
- **忠实**：只写转写稿里实际有的内容，不脑补、不扩写。
- **可理解**：`sections` 用平实语言重组逻辑顺序（如散乱口语 → 主题归拢），但观点/数字/例子必须保留。
- `key_takeaways` 每条必须能在 transcript 找到对应原文位置（标 `[mm:ss]`）。
- **实体自检（防幻觉）**：`entities` 里每个人名/书名必须能在 transcript 原文或 4a 校正表中找到依据；凭"这类内容通常还会提到谁"联想出来的一律删除。生成后逐条 grep 核对一遍。

### 第 5 步：生成 HTML（两版）

```bash
# 5.1 阅读版（浅色长文）：沿用 analysis.json；交付默认加 --clean
python3 <skill_dir>/scripts/render_html.py analysis.json transcript.txt --clean

# 5.2 看板版：用 dashboard.json；--theme=light|dark|both（默认 light）；交付默认加 --clean
python3 <skill_dir>/scripts/viz_render.py dashboard.json "" transcript.txt --theme=both --clean
```

- `render_html.py`：标题/摘要/核心要点卡/主题分节/时间轴/可搜索逐字稿；文件名自动 = `title`（校验泛词会拒绝渲染，看板版沿用同一标题即可）。
- `viz_render.py`：单文件、样式全内联、**零 JS 零外部资源**（渲染后自报检查）；亮色为默认交付主题，`--theme=both` 同时输出 `_light` / `_dark` 两个文件。行内语法：`**x**` 金色强调、`[mm:ss]` 自动变溯源徽章（`--clean` 时直接去掉）；不传输出名（或传空串，已修复）时自动命名 `<时间戳>-<标题>_visualization_<主题>.html`，与阅读版同目录同前缀。
- **交付默认加 `--clean`（用户偏好，2026-09 起）**：两版都不内嵌 ASR 原始逐字稿、不输出 `[mm:ss]` 分钟标记；页脚自动注明「逐字稿未收入本页，如需回溯请保留随附 transcript.txt」。双轨原则不变——**transcript.txt 仍作为独立文件一并交付**。两版语义差异：阅读版 `--clean` 同时略过时间线 section 与「N 段转写」meta；看板版保留时间线事件内容，只去掉时间戳 chip（案例本身有信息量）。用户明确要「把逐字稿放进网页」或「保留时间戳跳转」时再去掉 `--clean`。
- 两版都用第 4 步的同一 `title` 命名，保证产物成套。

### 第 6 步：交付

用 `present` 把**两版 HTML（默认 --clean 模式）+ transcript.txt** 一起交付（若用户只要其中一版，按用户要求）。若用户只要文字，直接贴 `transcript.txt`。用户嫌某一版风格不合时：改主题用 `--theme`，改结构只动 `dashboard.json`，不要手改 HTML。用户要「把逐字稿放进网页 / 保留时间戳跳转」时，去掉 `--clean` 重新渲染。

## 降级方案（音频提取失败时）

1. 告知用户：本环境无法解码该容器的音频轨（列出尝试过的格式）。
2. 给用户三个选择：
   a. 手动用任何工具（手机相册自带「录音」转文字、剪映导出音频、在线转码站）把音频导成 `.wav`/`.mp3`，上传后重新走第 3 步起。
   b. 若文件其实有外挂字幕（.srt/.vtt），直接让我读字幕文件，跳过 ASR。
   c. 放弃，只要我帮整理已有文本。
3. **不要**在无法获取真实语音时假装完成了转写。

## 边界

- 不处理需登录/付费墙的视频 URL（本 skill 只接受用户提供的本地文件）。
- 不做语音合成、不做视频剪辑。
- 转写语言以音频实际语言为准；ASR 模型中文效果最好，小语种（藏/彝/苗等）可能不准，需告知用户。
- 看板版不做语音识别、不臆造数据：所有指标/引语必须能在 `transcript.txt` 找到出处。
