---
name: video-html-extractor
description: 从用户上传的音/视频文件提取文案（语音转文字），转成结构化后生成两版单文件 HTML——摘要版（8 种视觉组件混合排版）与阅读版（分段排版、字号/字体/主题可调），并按文案主题自动命名。适用用户上传 .mp4/.mov/.mkv/.mp3/.wav/.m4a/.flac/.ogg 并要求「提取文案」「转成文字」「做成网页/HTML」「可视化」「整理内容」的场景。
---

# 视频文案提取 → 两版可视化 HTML

**一条 skill，一套流程，任何模型都能跑出一致的产物。** 你不需要自己编排步骤，也不要去读渲染器源码。

## 最短路径速查（照抄这 6 条命令即可）

```bash
# 1. 输入（推荐免 cp 用法）：脚本支持附件绝对路径 + --out 指定工作区，产物落 --out 目录，无需复制
python3 <skill>/scripts/run_pipeline.py prepare <附件绝对路径> --out /storage/emulated/0/DSH/<工作区>
#    仅当想保留本地 input.mp4 副本时才手动复制（附件目录只读）：
#    cp <附件路径> /workspace/input.mp4

# 2. prepare（全自动：提取 → ASR → 机器校正 → GLM 起草 analysis.json）
#    用免 cp 用法时省略第 1 步，直接到第 3 步终审草稿；用副本则跑：
python3 <skill>/scripts/run_pipeline.py prepare input.mp4

# 3. 终审 GLM 草稿 analysis.json（读校正稿核对事实/数字/高亮，edit 修订；草稿缺失时才按 TASK.md 手填）
#    + 网络校准：python3 <skill>/scripts/run_pipeline.py calibrate <输入文件> --out <工作区>
#      （Tavily 自动批量核实 entities；无 key 时静默跳过，可改用 web_search 手动核实）

# 4. 自检到 0 error（不带 --transcript 时自动探测校正稿做溯源基准）
python3 <skill>/scripts/validate_analysis.py analysis.json

# 5. finish（自动渲染两版 HTML；路径须与 prepare 一致）
#    免 cp 用法：python3 <skill>/scripts/run_pipeline.py finish <附件绝对路径> --out /storage/emulated/0/DSH/<工作区>
#    副本用法：python3 <skill>/scripts/run_pipeline.py finish input.mp4

# 6. 交付 + 清理（finish 已自动删中间产物）。仅当用了 input.mp4 副本时，才手动删该副本（见 SKILL.md 第 5 节清理说明）
```

任何一步卡住、想看细节，再回 SKILL.md 对应小节。

## 你要做的只有三件事

1. 运行一次 `prepare`（脚本自动完成：提取音频 → ASR 转写 → 机器校正 → **GLM 起草 `analysis.json`** → 生成任务单 `TASK.md`）。起草把最重的生成钉在固定的 glm-4.7 上，**会话模型切换不影响主耗时**；起草失败/无 key 时自动回退为空骨架，由你手填。
2. **终审草稿**（不是从零写）：按 `TASK.md` 读校正稿；**先跑 `run_pipeline.py calibrate` 做一轮网络校准**（Tavily API 自动批量核实 entities，会自动回填 footer，见「网络校准」）；再核对事实/数字/高亮逐字性、edit 修订；跑 `validate_analysis.py` 自检到 **0 error**（仅 WARN 可留，不阻塞渲染），再运行 `finish`（脚本自动校验 + 按 DESIGN-SPEC 渲染两版 HTML + 按 title 重命名校正稿 + 自动清理中间产物，原始逐字稿 `transcript.txt` 一并删除，仅保留校正稿）。
   - **快路径**：若视频 < 2 分钟且 `entities` 里全是常见中文名（抖音/今日头条/小红书等，ASR 误写率极低），web_search 可以只做 1 次验证搜索（确认没把「快手」写成「头条」这类近义混用），不必逐条查；有英文音译词或冷门人名/产品名才需要批量搜索。
3. 交付前按「交付前自查清单」过一遍。

除此之外的转写、校正、渲染、校验、清理，全部由脚本完成。**不要手改 transcript 或 HTML。**

## 环境变量 / 密钥

已配置，无需向用户询问，也不要写进任何持久文件：

| 用途 | 自动读取 |
|------|---------|
| ASR（硅基流动） | `~/.dsh/secrets/siliconflow_api_key` |
| 机器校正（智谱） | `~/.dsh/secrets/zhipu_api_key` |

默认 ASR 模型：`XingChenAGI/XingChenASR-V3.2-Ultra`（免费，适合口语化）。

## 工作流（详细版；已走最短路径可跳过本节）

### 第 1 步：确认输入文件

确认文件存在、可读。>50MB 时脚本会自动分块，无需你做任何事。

### 第 2 步：prepare（全自动）

```bash
python3 <skill_dir>/scripts/run_pipeline.py prepare <输入文件> [--workers 3] [--out 输出目录]
```

脚本依次做：提取 16k mono WAV → ASR 分块转写 → 智谱机器校正 → **交叉验证（检查 changes 清单中的修正是否真的应用到了校正稿文本，未应用的自动补全）** → 生成骨架 + 任务单 → **GLM 起草完整 analysis.json**（`llm_draft_analysis.py`，自带限流退避与 2 轮校验回喂修复；已有非空 title 的 analysis.json 不覆盖；`--no-draft` 可关闭）。**若工作区已有 `transcript.txt`/`transcript_calibrated.txt` 缓存会直接跳过对应步骤（命中缓存近零成本），且绝不覆盖已有内容的 `analysis.json`。** 退出码 `0` 成功；`1` 提取失败（看上方输出，若为解码问题走文末降级方案）；`3/4` 校正 key 不可用（跳过校正与起草，你手工完成）。

完成后它会打印：草稿路径、任务单路径、以及低置信度校正项清单。

### 第 3 步：终审 analysis.json（草稿已就绪，这是你唯一要动的）

1. **读** `TASK.md`（任务单）+ `transcript_calibrated.txt`（校正稿，正文以它为准）。`analysis.json` 通常已是 GLM 草稿；**只有草稿是空骨架时**才需要照 `examples/analysis.example.json` 从零填。
2. **先跑网络校准，再动手编辑**（顺序重要：calibrate 会自动回填 footer.calibration，之后脚本在 finish 前不再写 analysis.json，你的 edit 就不会撞上脚本写入）：
   ```bash
   python3 <skill>/scripts/run_pipeline.py calibrate <输入文件> [--out 输出目录]
   ```
   脚本（`network_calibrate.py`）自动把 entities 按类别分组批量调 **Tavily API**（Key 读 skill 根目录 `.tavily_key`，其次 `~/.dsh/secrets/tavily_api_key`、环境变量 `TAVILY_API_KEY`），写 `calibration_report.json`；若 `footer.calibration` 还是骨架占位符则自动回填核实摘要（**已有人工内容则不覆盖**）。**之后你只需审读报告里的「未确认」项**（脚本只确认不改写）：确实写错的按「『ASR 原文』→『官方写法』（出处：URL）」补进 `footer.calibration` 并同步替换正文。**校准只改名词写法，不改观点、数字量级。** 若无 Tavily key 或搜索失败，脚本静默跳过（exit 0），此时回退为旧路径——用 web_search 手动核实（按类别分组、一次 2–4 条 queries）。注：`finish` 会再跑一次 calibrate（`--reuse` 复用报告，不重复扣次数），所以忘记单独跑也不漏。**生活/教程类视频的 entities 多为口语称谓（菜名、料名、俗称），搜不到官方写法是常态——未确认项保留原文即可，不必逐条深究。**
3. 用 edit 工具**针对性修订**草稿（不要无脑整体重写）：
   - `title`：具体、可检索、≤30 字。禁用泛词（转写/文案/内容整理/transcript/未命名/原始文件名）。例：「耶鲁死亡课：直面死亡才能活明白」。
   - `tone` / `summary` / `hero_facts`(3–6 个记忆点数字) / `sections`(6–10) / `key_takeaways`(5–10，带 [mm:ss] 引用) / `conclusion` / `entities` / `footer.calibration`。
   - `reader_highlights`：8–15 条阅读版金色高亮短语，**逐字摘自校正稿**（4–30 字）。只挑含金量最高的：核心概念定义、关键结论、金句、重要数字表述；禁止「首先/所以/但是」类过渡词。每条全文仅在首次出现处高亮。校验器会 WARN 报原文找不到的条目。
   - **`summary` 必须写「核心观点」，不是「内容摘要」**。3–5 句话，只保留：① 文案的中心论点（1 句，可加引号原文）；② 支撑论点的 2–3 个关键数字/数据；③ 一句行动指令或结论。**不要写「博主用 X 经历切入」「后来他读到 Y」「由此他给出 Z」「结尾邀请观众 W」这类叙事流水账**——视频讲了什么、谁说的、怎么转折的，全都不进 summary，这些留给 `sections` 和 `key_takeaways` 去讲。读者打开 HTML 第一眼看到的 summary 是「文案本身在讲什么」，不是「视频怎么讲的」。例：原文核心是「人是需要间歇性堕落的，精力管理比时间管理更重要」，那 summary 就写「间歇性堕落是自救：人就像弹簧……老教授 5+2 / 6+1……有效工作时间只有 4 小时，用 20% 有效时间干 20% 最重要的事」，不写「博主傻白用高三经历切入、崩溃后读了一篇文章」。
   - `sections` 的 `type` 按内容本质选并配对该字段：`timeline`(时序)/`compare`(对比)/`pair`(痛点解法)/`architecture`(结构)/`flow`(流向)/`quote`(金句)/`list`(清单)/`default`(论述)。**不要全堆成 default。** 具体字段形状看 `examples/analysis.example.json` 与 TASK.md。**v2 选择指引（R 系列）**：
     - **R1 叙事钩子前置**：原稿若含真实人物事件/案例故事，必须在 Hero 之后、理论章节之前用 `timeline` 呈现"开篇故事"（让读者先产生疑问再进机制）；无叙事素材可跳过。这是 v1 产出最常漏用的——强叙事被压进 list/default，丢了故事钩子。
     - **R2 数据支撑独立成节**：支撑中心论点的调查/研究数据（非首屏 hero_facts）集中一个 `default` 或 `compare` 章节；强对比数据（如长期 61% vs 一次性 19%）用 `compare` 呈现，**不得拆成两张平铺卡**。
     - **R3 量化机制可视化**：原文带倍数/参照点/增减对比等"可计算"机制时，用 section 的 `bars` 字段（`[{label,value,text?,tone?}]` + `bar_note?`）渲染纯 CSS 条形图（`.bar-chart`），数字仍须可回溯原文。
     - **R4 全文去重**：同一金句/数据/结论全页只出现一次。sections 讲"机制与故事"，takeaways 只留一句式"结论条目"（带时间戳但不复述细节）。校验器对重复金句/重复数据点/sections↔takeaways 逐字复述给 WARN。
     - **R5 解法与机制挂钩**：若解法从机制推导，解法区显式标注对应机制（如"帮急不帮穷 ← 享乐适应/参照点"），形成"机制→解法"闭环。
     - **pair 使用前提收紧**：仅当痛与解真实一一对应时用 `pair`；纯解释性内容不得伪装成"解法"（v1 的痛点3条+伪解法3条平铺即反例）。
4. **红线**：只改高置信度错；不改观点/数字量级/不加事实；金句原样加引号；**所有数字必须能在 transcript.txt 找到出处，禁止编造**（校验器兼容中文数字：原文「二零一九」= JSON「2019」，「三家」= 3，不会误报）；**不要把原文说法「雅化」成原文没有的短语**（校验器查不出，交差前人工抽查 `summary`/`key_takeaways`/`quote` 里的短语，拿不准回 `transcript.txt` 搜）。
5. **通顺度**：转写稿可能含 ASR 把开场音乐/噪音误输出的句首杂字（如「等」）。终审校正稿时若该字使句首不通且无实义，应删除以恢复通顺。这与「拒绝雅化」不冲突——雅化是改写实义措辞，删除句首无义杂字仅是修正 ASR 噪音。
6. **自检到 0 error**（照 TASK.md 末尾的命令；不带 --transcript 时自动探测校正稿做溯源基准）：
   ```bash
   python3 <skill_dir>/scripts/validate_analysis.py analysis.json
   ```
   它只报 ERROR（不让过）和 WARN（建议修，不阻塞渲染）。照提示改，重跑，直到 ERROR 全消。

**失败退出码对照表**（`validate_analysis.py` 单独跑）：

| 退出码 | 含义 | 怎么办 |
|---|---|---|
| `0` | 校验通过（0 error） | 直接进 finish |
| `1` | 有 ERROR（硬伤：字段/类型/枚举/泛词标题等） | 按输出逐条修，重跑直到 0；ERROR 会拦住 finish，不修好不出网页 |
| `2` | 仅 WARN（小建议，如要点条数略少） | 可修可不修；**不阻塞 finish，照常渲染** |

**无 key 时的降级路径**（完整分支，别懵）：

- **没有硅基流动 key**：ASR 转写跑不了。让用户手动提供文字稿（文件名任意，格式 `[mm:ss] 文本`），放到工作目录后重命名为 `transcript.txt`，从「机器校正」步骤继续。
- **没有智谱 key**（prepare 报 exit 3/4）：机器校正与 GLM 起草都跳过，**不影响后续**——你在第 3 步手填 analysis.json 时把校正工作手工完成（对照 transcript 把明显错别字/音译词改对，写进 `footer.calibration`）。
- 两条 key 都缺：手动文字稿 + 手工填 analysis.json + 手工自检，流程仍可走完，只是转写与校正质量取决于人工。

**已知盲区（校验器查不出来，需人工抽查）**：数字出处会校验（兼容中文数字写法，原文「二零一九」与 JSON「2019」互认），但**术语/口诀/短语是否原文存在不校验**。写 analysis.json 时偶发把原文说法「雅化」成原文没有的短语（例：原文「不饿就不吃」被写成「过六不食」）。交差前扫一眼 `summary`、`key_takeaways`、`quote` 卡片里的中文短语，拿不准的就去 `transcript.txt` 里搜一下，搜不到就别用。

### 第 4 步：finish（全自动）

```bash
python3 <skill_dir>/scripts/run_pipeline.py finish <输入文件> [--theme dark|light] [--out 输出目录]
```

先校验（仅 ERROR 拒渲染，WARN 放行），再按 `DESIGN-SPEC.md` 的设计规范生成两版 HTML：
- **摘要版** `<title>_摘要版.html`：8 种视觉组件混合（可挂 `.bar-chart` 条形图，R3）。**不含逐字稿**（校正稿以 `<title>_校正稿.txt` 独立文件交付，不再内嵌到 HTML）。**默认深色主题**（DESIGN-SPEC 核心目标：深色主题 + 渐变红金强调 + 毛玻璃卡片 + 入场/悬浮/背景粒子动效 + 响应式网格）。**导航栏右上角带明暗主题切换按钮**（太阳/月亮图标，点一下换主题，偏好存 `localStorage` 键 `dsh_theme`，下次打开沿用）。**导航为每个主要章节提供锚点**（v2 导航完整性），**页脚校正说明与实体列表默认折叠**（`<details><summary>`，点开可见；生成声明不折叠）。
- **阅读版** `<title>_阅读版.html`：校正稿分段排版，A-/A+ 字号、4 款字体、亮暗主题，偏好存 localStorage。**默认深色**；`finish` 的 `--theme light` 同时作用于摘要版与阅读版（两版初始主题一致），页内按钮仍可随时切换。**阅读版高亮（`.para strong`）颜色：暗色主题金黄色 `#f5c518`，亮色主题天蓝色 `#00a6e6`**（CSS 用 `html[data-theme="light"] .para strong{color:#00a6e6}` 覆盖；只改高亮文字，不改标题/分隔线的 `--grad-b` 渐变）。

**render 后自动重命名**：`finish` 渲染完两版 HTML 后，将 `transcript_calibrated.txt` 重命名为 `<title>_校正稿.txt`（文件名与 HTML 保持同一前缀）。原始逐字稿 `transcript.txt` 不重命名，而是由清理步骤自动删除。

`--theme light` 可回落亮色（CSS 变量切换，结构不变；摘要版渲染出的 HTML 仍可点按钮随时切回深色）。

### 第 5 步：交付 + 清理

用 `present` 交付摘要版 + 阅读版 + `<title>_校正稿.txt`（用户只要部分则按需）。**注意：`present` 每次调用最多渲染 4 张卡，3 件交付物必须放同一次调用里传完整**（漏传会被静默吞掉，用户看不到第 3 件）。

**规则：交付物自动复制到系统 Download 目录**。`finish` 渲染完成后，脚本会把本次 `<title>_摘要版.html`、`<title>_阅读版.html`、`<title>_校正稿.txt` 复制一份到 `/storage/emulated/0/Download`（目录不存在则自动创建；复制失败仅警告，不影响主流程）。工作区与 Download 各存一份，用户用系统文件管理器或分享入口可直接找到。

**清理（默认自动）**：`finish` 渲染完成后，**默认自动删除本次任务产生的中间产物**（含原始逐字稿 `transcript.txt`），只留交付物。脚本只按精确路径删自己生成的东西（不 glob 通配），自动满足「不碰历史文件」的红线：

| 自动删除（精确路径） | 说明 |
|---|---|
| `<输入名>.wav` | 音频中间件 |
| `<输入名>.wav.chunks/` | ASR 分块目录 |
| `transcript.txt` | ASR 原始逐字稿（仅保留校正稿） |
| `transcript_calibrated.txt.calib_cache/` | 校正缓存 |
| `report.json` | 机器预筛报告（填完 analysis.json 后已无用） |
| `TASK.md` | 任务单（填完 analysis.json 后已无用） |
| `analysis.json` | 渲染配置（HTML 渲染完成后已无用） |

保留交付物：`<title>_摘要版.html`、`<title>_阅读版.html`、`<title>_校正稿.txt`。若想保留缓存以便断点重跑（重跑 `prepare` 时命中缓存跳过 ASR），用 `finish --keep-cache`。

**仍需人工处理的两件事**：
- 若 `cp` 了输入文件到工作区（如 `input.mp4`），手动删掉这份副本——脚本不知道副本叫什么名字（用户附件目录里的原件**绝不动**）。
- 为装 ffmpeg 下载的 `.deb` 与临时目录（若有）手动清理。

**保留**已装进 `usr/bin/ffmpeg` 的工具链本身。

**红线**：脚本自动清理只删它自己生成的精确路径；若你手动删，只删本次任务产生的文件，删前用 `ls`/文件名特征确认归属，拿不准就问用户；绝不删输出目录里的历史文件。

## 交付前自查清单（照抄，过一遍即可）

- 校验器已 0 error（title 非泛词、字段名/类型/枚举正确、数字能回溯到原文，中文数字写法互认）。
- **专有名词已网络校准**（`footer.calibration` 里有「网络校准」条目，正文已同步替换）。
- **抽查过「雅化」短语**：`summary`/`key_takeaways`/`quote` 里的中文说法都能在 `transcript.txt` 搜到原文，没有原文没有的「雅词」。
- 阅读版可正常打开、字号/主题按钮可用；两版均为单文件、无外部依赖；`finish --theme light` 时两版初始主题一致。
- **视觉符合 DESIGN-SPEC**：深色主题、毛玻璃卡片、渐变强调、入场动画、背景粒子、响应式网格（摘要版）；阅读版有字号/字体/主题控件。
- **主题切换按钮（§3.1.1）**：两版导航栏最右都有圆形毛玻璃按钮，点一下换明暗、偏好写 localStorage（摘要版 `dsh_theme`、阅读版 `theme`）；深色默认、`--theme light` 回落亮色。切换后不会出现文字消失（渐变标题带 `@supports` fallback）。
- 术语校正说明已写在 `footer.calibration`。
- **compare 组件无双图标**：摘要版里 compare 章节的 `<li>` 不应包含 `ico-mark` span（CSS 已用 `::before` 画 ✕/✓，HTML 里再塞 SVG 会双图标）。grep 验证：`grep -c ico-mark *.html` 应为 0；若 >0 说明渲染器回归，改 render_html.py 的 `render_compare`。
- **全文去重（R4）**：重复金句/重复数据点已消除；`sections` 与 `key_takeaways` 无逐字复述（校验器会 WARN 提示，见 `check_dedup`）。
- **导航完整性 / 死锚点**：导航为每个主要章节提供锚点（hero + 各 section + 要点 + 金句）；渲染后自检所有 `href="#..."` 都有对应 `id`，无死链接（缺失为 ERROR 拒渲染）。section 多时移动端锚点条横向滚动（§5.3），非隐藏。
- **速度自查**：本次流程里 `web_search` 调用 ≤ 2 次（按实体类别分组批量搜）；没有重复 `ls` 确认同一目录；`prepare`/`finish` 各只跑 1 次（命中缓存时跳过）；`present` 只调 1 次、把 3 件交付物一次性传齐。若违反，下次按「最短路径速查」6 条命令直接照抄。

## 设计规范（DESIGN-SPEC）

两版 HTML 的视觉层由 `DESIGN-SPEC.md`（本目录）定义，**不要凭经验自由发挥 CSS**：

| 维度 | 规定 |
|------|------|
| 主题 | 深色默认（底色 `#1a1a2e`）；`--theme light` 回落亮色 |
| 强调色 | 红 `#e94560` + 金 `#f5c518` 渐变；价值/数字用金色 |
| 卡片 | Glassmorphism：`rgba(255,255,255,0.06)` 背景 + `backdrop-filter:blur(10px)` + `rgba(255,255,255,0.1)` 细边框 + `border-radius:16px` + `0 8px 32px rgba(0,0,0,0.3)` 阴影 |
| 动效 | `fadeInUp` 入场（stagger 0.1s 增量）+ `float` 背景粒子（6 个，`z-index:-1`）+ `pulse` 流程箭头 + `bounce` 滚动指示 + `barGrow` 条形生长（R3，`transform:scaleX`） |
| 组件 | 8 种 section + **条形对比 `.bar-chart`（R3）**：挂任意 section 的 `bars` 字段，纯 CSS 色块条形，数值用 `--w` 驱动 `transform:scaleX()`（只用 transform/opacity，遵守 §9.2） |
| 主题切换 | 导航栏最右 38×38 圆形毛玻璃按钮（§3.1.1）：摘要版太阳/月亮 SVG 挂 `body[data-theme]`、localStorage 键 `dsh_theme`；阅读版太阳 SVG 挂 `html[data-theme]`、localStorage 键 `theme`；两版默认深色、`--theme light` 回落亮色 |
| 导航 | **导航完整性（v2）**：为每个主要 section 提供锚点（hero + 各章节 + 要点 + 金句），锚点文字用章节 heading；无死链接（渲染后自检 `href→id`，缺失 ERROR 拒渲染） |
| 响应式 | 768px 断点：卡片单列、流程图纵向（箭头 90°）、**导航链接横向滚动（非隐藏，主题按钮保留贴右）**、条形图标签转上方 |
| 字体 | 系统字体栈（`-apple-system, "PingFang SC", "Microsoft YaHei"…`），零外部加载 |
| 约束 | 单文件零依赖、纯原生 HTML/CSS/JS、语义化标签、动画只用 `transform`/`opacity` |

改渲染器时：`render_html.py`（摘要版）与 `read_render.py`（阅读版）的 CSS 块必须与 `DESIGN-SPEC.md` 同步；新增视觉组件先查 spec §7 片段库。

## 工具链复装（ffmpeg，模型无关）

当 `prepare` 报「本机工具链 ffmpeg 缺失或损坏」时，**不要再让模型手写解包配方**
（过去多次 1 小时卡在这）。正确做法：

1. 若当前会话**已有 dsh-backup 包**（任意一个 `dsh-backup-*.zip`），直接：
   ```bash
   unzip dsh-backup-*.zip -d /tmp/dsh-rest
   sh /tmp/dsh-rest/install-deps.sh install-ffmpeg
   # 无 apt 的机器离线即可；有 apt 且允许联网时:
   sh /tmp/dsh-rest/install-deps.sh install-ffmpeg --net
   ```
   脚本会自动读包内 `toolchain-deps/TARGET_PREFIX`（备份机实测过的 usr 前缀），
   注入 `LD_LIBRARY_PATH` + `LD_PRELOAD`，解包平移全部 `.deb`，跑 `ffmpeg -version` 自检。

2. 若没有现成备份包，按 `TOOLCHAIN_HINT`（脚本 stderr 自动打印）手工走：
   在目标机 usr 前缀下 `apt-get install -y --download-only ffmpeg`，
   再把 `var/cache/apt/archives/*.deb` 逐个 `dpkg-deb -x` 解包，
   把其中 `data/data/com.termux/files/usr/.` 整树 cp 到 `<usr前缀>/`，
   执行/验证必须注入 `LD_LIBRARY_PATH=<前缀>/lib` 与 `LD_PRELOAD=<前缀>/lib/libtermux-exec-ld-preload.so`。

**恢复备份包时（README-RESTORE.md 第 3 节）一律用包内 `install-deps.sh`，**
不要手写 ffmpeg 安装步骤。

## 降级方案（提取失败时）

1. 告知用户无法解码该容器音频轨。
2. 给三个选择：a. 用户手动导成 `.wav`/`.mp3` 再传（从第 2 步起）；b. 有外挂字幕（.srt/.vtt）直接读字幕跳过 ASR；c. 放弃转写，只整理已有文本。
3. **不要**在拿不到真实语音时假装完成转写。

## 边界

- 只处理用户提供的本地文件；不做需登录/付费墙的 URL。
- 不做语音合成、视频剪辑。转写语言以音频实际语言为准；中文效果最好，小语种可能不准需告知用户。
- 所有数字/引语必须能在 `transcript.txt` 找到出处。

## 推送到 GitHub（token 已预配，随时可推）

本 skill 的 Git 仓库：https://github.com/beiyenan/dsh-skill-video-html-extractor（分支 `main`）。

**推送方式（一条命令，无需再要 token）：**
```bash
bash <skill>/scripts/git_push.sh            # 推当前分支到 main
bash <skill>/scripts/git_push.sh main       # 指定分支
```

**安全约定（改推送相关代码务必遵守）：**
- GitHub PAT 存在 **`~/.dsh/secrets/github_token`**（chmod 600，位于 git 仓库树**之外**，`git ls-files` 永远看不到它），由 `git_push.sh` 在推送瞬间读取，**绝不写进 `.git/config`、不写进任何 commit、不留在工作区**。
- `remote origin` 只存**无 token** 的干净 HTTPS 地址（`https://github.com/...`）。
- 推送脚本 `git_push.sh` 内部用一次性带 token 的 URL 调 `git push`，推完即弃；`main` 是跟踪分支。
- `.gitignore` 已忽略 `*_token`/`*_key`/`*.pem` 等敏感模式作兜底；任何情况下都不应把 secrets 内容提交进仓库。