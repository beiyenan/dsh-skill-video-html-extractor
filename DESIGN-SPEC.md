# 文案转可视化网页 — 设计与实现方法论

> 本文档记录了一套将纯文案内容转化为**美观、结构化、易理解**的可视化单页网页的完整方法论。其他 Agent 可据此方法，从零搭建同等品质的网页。

---

## 一、设计总纲

### 1.1 核心目标

将一段纯文本（如演讲稿、转写稿、文章）转化为一个**单页滚动式网页**，要求：

- **视觉冲击力强**：深色主题 + 渐变配色 + 动效点缀
- **信息层级清晰**：通过分区、卡片、流程图等视觉元素降低认知负荷
- **移动端友好**：响应式布局，手机/平板/桌面端均可流畅浏览
- **零外部依赖**：所有 CSS/JS 内联在一个 HTML 文件中，无需框架、无需构建工具

### 1.2 设计语言定义

| 维度 | 选择 | 说明 |
|------|------|------|
| 主题 | 深色模式 | 底色 #1a1a2e，降低视觉疲劳，突出内容 |
| 强调色 | 红色 #e94560 + 金色 #f5c518 | 红色用于 CTA/高亮，金色用于价值/价格信息 |
| 卡片风格 | Glassmorphism（毛玻璃） | backdrop-filter: blur() + 半透明背景 + 细边框 |
| 字体 | 系统字体栈 | -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC"...，零加载延迟 |
| 圆角 | 16px 统一 | 卡片、按钮、徽章统一使用 border-radius: 16px |
| 阴影 | 多层柔和阴影 | 0 8px 32px rgba(0,0,0,0.3) 营造悬浮感 |

### 1.3 配色方案（CSS 变量定义）

```
:root {
    --primary: #1a1a2e;       /* 主背景：深蓝黑 */
    --secondary: #16213e;     /* 次级背景 */
    --accent: #0f3460;        /* 强调深蓝色 */
    --highlight: #e94560;     /* 高亮色：红 */
    --gold: #f5c518;          /* 金色：价值/价格 */
    --text-light: #f0f0f0;    /* 主文字 */
    --text-muted: #b0b0b0;    /* 次要文字 */
    --card-bg: rgba(255,255,255,0.06);  /* 卡片背景 */
    --card-border: rgba(255,255,255,0.1); /* 卡片边框 */
    --radius: 16px;           /* 统一圆角 */
    --shadow: 0 8px 32px rgba(0,0,0,0.3); /* 统一阴影 */
}
```

**关键原则**：所有颜色通过 CSS 变量统一管理，修改 `:root` 即可全局换肤。

---

## 二、页面结构方法论

### 2.1 标准页面区块清单

一套完整的文案→网页转换，通常包含以下区块（按阅读顺序）：

| 区块 | 作用 | 视觉形式 |
|------|------|----------|
| **导航栏** | 快速跳转锚点 | 固定顶部 + 毛玻璃背景 |
| **Hero 首屏** | 一句话概括主题 + CTA | 全屏居中 + 大标题渐变 + 按钮 |
| **概念解释区** | 核心概念阐述 | 单卡片 + 左侧渐变条 + 图标 |
| **内容卡片区** | 分类展示要点 | CSS Grid 卡片网格 |
| **逻辑流程图** | 展示流程/关系 | Flex 横向排列 + 箭头连接 |
| **金句引用区** | 突出打动人的句子 | 居中引用块 + 左引号装饰 |
| **行动建议区** | 给出可操作步骤 | 编号卡片网格 |
| **Footer** | 页脚信息 | 简洁居中 |

### 2.2 内容映射规则

将文案内容映射到页面区块的规则：

1. **标题/主题句** → Hero 区域的大标题
2. **核心定义/概念解释** → 概念解释区
3. **分类列举的内容**（如"五类技能"）→ 卡片网格区
4. **流程/步骤/因果关系** → 逻辑流程图
5. **金句/感悟/总结性语句** → 金句引用区
6. **行动建议/下一步** → 行动建议区

### 2.3 区块间距规范

```
/* 所有 section 统一内边距 */
padding: 80px 20px;           /* 上下80px，左右20px */
max-width: 1100px;            /* 内容最大宽度 */
margin: 0 auto;               /* 水平居中 */
```

Hero 区域特殊处理：`min-height: 100vh` + `padding: 120px 20px 80px`（顶部留出导航栏空间）。

### 2.4 可视化选型矩阵（v3 新增）

内容层决定用哪种构件。先看数据的**形状**，再挑组件——不要先挑组件再塞内容。

| 数据形状 | 首选构件 | section type / 字段 | 判据 |
|---|---|---|---|
| 同一指标、多个对象比大小 | 条形图 | 任意 type + `bars` | 差异靠"长短"就能读出来 |
| 同一指标、含极小值（<最大项 10%） | 条形图（带地板宽度） | `bars` | 见 §7.7 约束①：极小值不能被读成 0 |
| 两个时间点/两种做法的条目对照 | 对比卡 | `compare` | 两组、条目式、互相排斥 |
| ≥2 列属性、逐行同结构（档位/价格/排期/参数） | 表格 | `table` + `columns`/`rows` | 需要**横向对齐**才能比较 |
| 有先后顺序的事件/演进 | 时间线 | `timeline` | 顺序本身是信息 |
| 因果链/步骤流转 | 流程图 | `flow` | 强调"从哪到哪" |
| 痛点与其对应解法 | 配对卡 | `pair` | 必须真实一一对应，否则用 default |
| 组织/分层结构 | 架构图 | `architecture` | 有并列的"面" |
| 一条一段话的观点集合 | 清单 / 卡片 | `list` / `default` | 无法压缩成同一维度比较 |
| 原话、结论句 | 金句卡 | `quote` / `conclusion.cards` | 措辞本身就是价值 |

**三条冲突裁决规则**

- **R6 一节一图**：一个 section 最多一个可视化构件（`bars` 与 `table` 二选一）。两个图挤在一节里，读者两个都读不进去。构件下方说明最多一行，只补充"这数哪来的"，不复述图里已有内容。
- **R7 长短优先**：同一份数据既能做 `bars` 又能做 `table` 时，先看差异是否靠"长短"表达——是就 `bars`；否则（是多列属性）用 `table`；两者都不合适才退回 `compare`/卡片。
- **宁少勿多**：拿不准用哪个，用 `default`。构件选错会让信息变形（把表格拆成卡片就丢了横向对比），而 `default` 至少不撒谎。

### 2.5 数字可视化前置检查

任何要画进图里的数字，先确认三件事（校验器 `validate_analysis.py` 会逐条拦）：

1. 能在校正稿里找到出处（阿拉伯数字与中文数字都算，如"六成"↔"60%"）；
2. `value` 是**纯数字**，展示文案放 `text`（`{"value":0.4,"text":"0.4%"}`，不要写 `"value":"0.4%"`）；
3. 同一数字全页只出现一次（R4 去重）——首屏 `hero_facts` 已承载的记忆点数字，正文与要点里改用中文表述或不提。

---

## 三、组件设计模式

### 3.1 导航栏（Navbar）

**设计要点**：

- `position: fixed` 固定顶部
- `backdrop-filter: blur(12px)` 毛玻璃效果
- 半透明背景 `rgba(26,26,46,0.85)`
- Logo 使用渐变文字效果
- 链接 hover 时变强调色

**导航完整性（v2 §3.3）**：导航为**每个主要 section 提供锚点**（hero + 各章节 + 要点 + 金句），锚点文字用章节 heading（无 heading 时回退为「章节 N」）。**禁止出现指向不存在 id 的死链接**（渲染器在产出 HTML 后自检所有 `href="#..."` 是否都有对应 `id`，缺失即 ERROR 拒渲染）。章节多时移动端允许锚点条横向滚动（§5.3）。**导航链接 anchor 里的文字若含 `#` 或非法字符需转义**，链接 href 用 `sec{i}` 稳定 id 保证跳转正确。

**HTML 模板**：

```
<nav>
    <div class="nav-logo">品牌名</div>
    <div class="nav-links">
        <a href="#sec0">章节1标题</a>
        <a href="#sec1">章节2标题</a>
        <a href="#takeaways">要点</a>
        <a href="#quotes">金句</a>
    </div>
    <button class="theme-toggle" title="切换明/暗主题" aria-label="切换明暗主题">☀️</button>
</nav>
```

#### 3.1.1 明暗主题切换按钮（规范）

导航栏**最右侧**固定一个圆形主题切换按钮（即「页面右上角」）。摘要版与阅读版都实现，行为一致：

| 维度 | 规定 |
|------|------|
| 位置 | 导航栏内最右，`flex-shrink:0`；移动端导航链接可隐藏，**按钮保留贴右** |
| 尺寸 | 38×38px，`border-radius:50%` 圆形 |
| 外观 | 毛玻璃：`background:var(--card)` + `border:1px solid var(--card-border)` + `backdrop-filter:blur(6px)`；文字色 `var(--muted)` |
| 图标 | 摘要版用太阳/月亮 SVG（18×18，`currentColor`）；阅读版顶栏按钮同样圆形毛玻璃风格，图标为太阳 SVG |
| hover | `border-color`+`color` 变 `var(--accent)`，`transform:scale(1.08)`，过渡 `.25s` |
| 切换机制 | 点一下在 `<html>` 或 `<body>` 上切换 `data-theme` 属性（值 `light`/`dark`，默认省略=深色）；所有颜色走 CSS 变量，切换即换肤，无需重载 |
| 偏好记忆 | 切后写 `localStorage`（摘要版键 `dsh_theme`，阅读版键 `theme`），下次打开沿用 |
| 初始主题 | `finish` 的 `--theme dark\|light` 决定首屏（默认 dark）；首屏主题与用户偏好冲突时以首屏渲染值为准，按钮反映当前状态 |

CSS 与 JS 参考实现（与渲染器 `render_html.py`/`read_render.py` 一致）：

```css
/* 按钮（圆形毛玻璃，贴右） */
.theme-toggle{
  width:38px;height:38px;border-radius:50%;
  border:1px solid var(--card-border);background:var(--card);
  color:var(--muted);display:grid;place-items:center;cursor:pointer;
  transition:.25s;backdrop-filter:blur(6px);flex-shrink:0;
}
.theme-toggle:hover{border-color:var(--accent);color:var(--accent);transform:scale(1.08)}
.theme-toggle svg{width:18px;height:18px}
/* 切换过渡：背景与文字色柔和过渡 */
body{transition:background .3s,color .3s}
```

```js
// 摘要版：挂在 body，键 dsh_theme
function toggleTheme(){
  var b=document.body;
  var isDark=b.getAttribute("data-theme")!=="light";
  b.setAttribute("data-theme",isDark?"light":"dark");
  try{localStorage.setItem("dsh_theme",isDark?"light":"dark")}catch(e){}
}
(function(){try{
  var t=localStorage.getItem("dsh_theme");
  if(t==="dark")document.body.removeAttribute("data-theme");
  else if(t==="light")document.body.setAttribute("data-theme","light");
}catch(e){}})();

// 阅读版：挂在 html，键 theme
function toggleTheme(){
  var h=document.documentElement;
  var isLight=h.getAttribute("data-theme")==="light";
  h.setAttribute("data-theme",isLight?"":"light");
  try{localStorage.setItem("theme",isLight?"dark":"light")}catch(e){}
}
```

> **两版差异说明**：摘要版 CSS 选择器写 `body[data-theme="light"]`（属性挂在 body）；阅读版写 `html[data-theme="light"]`（属性挂在 html 元素，CSS 中 `[data-theme="light"]` 即匹配 html）。两者都遵守「深色为默认、亮色为 override」——`:root` 是深色变量，`[data-theme="light"]` 块是亮色变量。实现时**选一种挂载元素并保持 CSS 选择器与 JS 一致**，否则切换不生效。

### 3.2 Hero 首屏

**设计要点**：

- 全屏高度 `min-height: 100vh`
- Flex 居中布局
- 小标签 badge（圆角边框）+ 大标题 + 描述 + CTA 按钮
- 标题使用渐变文字 `background-clip: text`
- 入场动画 `fadeInUp` 带延迟实现逐层出现
- 底部滚动指示器（箭头动画）

**渐变文字技巧**：

```
.gradient-text {
    background: linear-gradient(135deg, var(--highlight), var(--gold), #ff6b6b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
```

### 3.3 卡片组件（通用模式）

所有卡片（概念卡、技能卡、行动卡）共享基础样式：

```
.card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 32px;
    backdrop-filter: blur(10px);
    box-shadow: var(--shadow);
    transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s;
}
.card:hover {
    transform: translateY(-8px);
    box-shadow: 0 16px 48px rgba(0,0,0,0.4);
    border-color: var(--highlight);
}
```

**卡片变体**：

- **王者卡片**：额外加金色边框 + 渐变背景 + 顶部渐变条
- **概念卡片**：左侧 4px 渐变条 `::before` 伪元素
- **行动卡片**：顶部编号圆形徽章

### 3.4 徽章/标签组件

用于标记等级/类型：

```
.rank-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 50px;
    font-size: 0.75rem;
    font-weight: 700;
}
/* 不同等级用不同颜色类 */
.rank-king { background: linear-gradient(135deg, #f5c518, #ff8c00); color: #000; }
.rank-high { background: linear-gradient(135deg, var(--highlight), #ff6b6b); color: #fff; }
.rank-mid  { background: linear-gradient(135deg, var(--accent), #4a90d9); color: #fff; }
```

### 3.5 逻辑流程图

**设计要点**：

- Flex 横向排列 + `flex-wrap: wrap` 允许换行
- 每个节点为卡片样式
- 节点内容双向居中：节点卡片 `display:flex; flex-direction:column; justify-content:center; align-items:center`（标题与副标题水平+垂直居中）
- 节点之间用箭头符号 `→` 连接
- 箭头添加 `pulse` 动画（透明度呼吸效果）
- 移动端改为纵向排列，箭头旋转 90 度

**对比卡（compare）细节**：

- 彩色小标题（h5）内带 SVG 图标时用 `display:flex; align-items:center; gap:6px` 让图标与文字垂直居中对齐
- 列表项 `li` 的 ✕/✓ 符号（`::before`）与首行文字对齐：`li` 固定 `line-height:1.6`，符号 `top:calc(4px + 11.2px - 6px)`（上内边距 + 行高一半 − 符号高一半），多行条目时符号跟首行居中而非整体居中

### 3.6 金句引用区

**设计要点**：

- 最大宽度限制（800px）居中
- 渐变背景 `linear-gradient(135deg, rgba(233,69,96,0.1), rgba(245,197,24,0.05))`
- 左侧大引号装饰 `::before` 伪元素（大号字体 + 低透明度）
- 文字使用斜体 `font-style: italic`
- 引用来源放在下方

### 3.7 CTA 按钮

```
.hero-cta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 14px 36px;
    background: linear-gradient(135deg, var(--highlight), #c0392b);
    color: #fff;
    text-decoration: none;
    border-radius: 50px;
    font-weight: 600;
    transition: transform 0.3s, box-shadow 0.3s;
}
.hero-cta:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(233,69,96,0.4);
}
```

---

## 四、动画与交互设计

### 4.1 入场动画

使用 `@keyframes` 定义，通过 `animation-delay` 实现 stagger（交错）效果：

```
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); }
    to   { opacity: 1; transform: translateY(0); }
}

.hero h1    { animation: fadeInUp 1s ease 0.2s both; }
.hero p     { animation: fadeInUp 1s ease 0.4s both; }
.hero-cta   { animation: fadeInUp 1s ease 0.6s both; }
```

**技巧**：`both` 伪值让动画在结束前保持 keyframe 状态，延迟后淡入。

### 4.2 悬浮交互

所有可交互元素统一 hover 效果：

- 卡片：`transform: translateY(-8px)` + 加深阴影 + 边框变色
- 按钮：`transform: translateY(-3px)` + 发光阴影
- 导航链接：颜色变为强调色

### 4.3 背景装饰动画

浮动粒子效果：

```
.bg-particles span {
    position: absolute;
    border-radius: 50%;
    background: rgba(233,69,96,0.08);
    animation: float 20s infinite;
}
@keyframes float {
    0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.6; }
    33%      { transform: translateY(-30px) rotate(120deg); opacity: 0.8; }
    66%      { transform: translateY(20px) rotate(240deg); opacity: 0.4; }
}
```

**技巧**：通过为每个粒子设置不同的 `animation-delay` 和 `animation-duration`，营造自然随机感。粒子用 `z-index: -1` 放在内容下方。

### 4.4 滚动指示器

底部箭头弹跳动画：

```
@keyframes bounce {
    0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-10px); }
    60% { transform: translateY(-5px); }
}
```

### 4.5 健壮性硬规则（v3 新增，逐条来自实测）

> 共同教训：**动画是可选增强，可见性是必须保证的底线。**
> 任何"等 JS / 等动画 / 等某个变量才显形"的写法，都要先回答"它失败时读者看到什么"。

**① 默认态 = 终态，动画态由 `.js` 门控**

给元素加"进场前隐藏"（`opacity:0` / `scaleX(0)`）之前，先问：JS 挂了、被禁了、IntersectionObserver 没触发，这个元素还会不会出现？

```html
<script>document.documentElement.className+=" js";</script>   <!-- 在 <style> 之前 -->
```
```css
.bar-fill{transform:scaleX(calc(var(--w,100)/100))}  /* 无 JS：直接终态 */
.js .bar-fill{transform:scaleX(0)}                   /* 有 JS：才允许从 0 长 */
.js .bar-chart.in .bar-fill{animation:barGrow .9s ... forwards}
```

⚠️ 这条规则是**对"我们新引入的 JS 依赖"的兜底**，不是说旧代码有 bug。旧写法 `scaleX(0) + animation ... forwards` 本身不依赖 JS（动画自动播完停在终态），所以旧页面不会白屏——它的问题是**动画在加载时就跑完了**（见 ③）。一旦为了修 ③ 而改成"滚动到才播"，就产生了真正的 JS 依赖，此时 ① 变成必须。规则要连着看：**先决定要不要滚动触发，再决定要不要 `.js` 门控。**

**② 不要用「transition + JS 改宽度」做条形生长**

实测翻车：`width:0` + `transition` + IO 回调里 `el.style.width = el.dataset.w`，结果量到 `meter 500px -> 0`，条永远是零宽。原因是回调读属性的时机与 transition 起始帧打架，不同内核实盘行为不一致。
正确做法：终态宽度写死在 CSS 变量里（`--w`），动画只动 `transform`。JS 只负责加一个类。

**③ 动画要滚动触发，不要在页面加载时跑完**

`animation:barGrow .9s forwards` 直接挂在元素上 → 首屏渲染时动画即播完 → 读者滚到那一节看到的是静止的条，"生长"这个信息（"这项比那项多得多"）就丢了。用 `IntersectionObserver` 在 `.bar-chart` 进入视口时加 `.in`；IO 不存在时直接给全部元素加 `.in`（退化成 ③ 之前的行为，仍然可见）。

**④ `prefers-reduced-motion` 必须还原"终态"，不能只写 `animation:none`**

只写 `animation:none` 会让元素退回**基础规则的状态**——在 ① 的写法下那就是 `scaleX(0)`，即"关闭动画导致内容消失"，比不写这条规则更糟。

```css
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}
  html{scroll-behavior:auto!important}                                     /* 见下方说明 */
  .hero h1,.hero .sub,.facts{animation:none;opacity:1;transform:none}   /* 逐个还原终态 */
  .js .bar-fill{transform:scaleX(calc(var(--w,100)/100))}
  .js .bar-chart.in .bar-fill{animation:none}
  .bg-particles{display:none}
}
```
注意 `html{scroll-behavior:auto}` 要带 `!important`：若该块在 CSS 前部，后面无标记的 `scroll-behavior:smooth` 会把它覆盖掉。

**⑤ 极小值必须有地板宽度**

`pct = v/mx*100` 对 `0.4 / 61` 给出 0.65%，约 5px。取 `max(pct, 10)`，但 **真 0 值保持 0**（空条诚实，10% 的假空条是在撒谎）。

**⑥ 卡片底色必须遮住背景装饰**

见 §7.1。`rgba(255,255,255,0.06)` 的"毛玻璃"等于没有遮罩。

**⑦ 声明了就必须渲染出来（自检）**

字段名打错（`bar` 而不是 `bars`、`colums` 而不是 `columns`）时，渲染器读不到就安静地什么都不画——页面少一节内容，而校验器 0 error 通过。这是最难发现的一类缺陷，因此渲染器在输出 HTML 后做**渲染后自检**（`render_html._selfcheck`）：

- 死锚点：`href="#x"` 必须有对应 `id="x"`；
- 声明数 == 构件数：写了 N 组 `bars` 就必须有 N 个 `.bar-chart`，N 个 `table` 章节对应 N 个 `<table class="tbl">`；
- 空章节：有 `heading` 却没渲染出任何构件 → 报错；
- 地板宽度：出现 `0 < --w < 10` 说明兜底被绕过。

配套地，校验器加了 unknown-key 检查（`check_unknown_keys`）：与合法键高度相似（≥0.82）且带非空内容 → ERROR（"写了但页面上没有"）；其余不认识的键 → WARN；`_` 前缀视为作者注释静默跳过。阈值从严是因为**误杀比漏放行更糟**——判死会逼模型删掉有用信息。

**⑧ 契约只能有一份定义**

`SECTION_TYPES` / `FACT_TONES` / 字段配对文案原先散在三处（渲染器分支、校验器白名单、起草提示词），注释写着"与 render_html.py 硬编码一致"——所谓一致靠人工维持，必然漂移。现在统一由 `scripts/schema.py` 提供：提示词那一整块由 `SC.section_pairing()` 生成，渲染器 import 时 `SC.assert_renderers()` 断言"每个登记类型都有分支"。新增一个 section type 只改 schema 的枚举与配对，渲染分支与专属字段校验仍各自实现。

**⑨ 主题相关颜色一律走变量**

`border-bottom:1px solid rgba(255,255,255,.06)` 在深色下正常、亮色下白上白直接消失。写 `var(--line)`。同类问题：内联 SVG 的 `fill` 用 `currentColor` 或 `var(--…)`，不要写死。

**⑩ 触控与命中区**

可点元素 ≥44px 高；`-webkit-tap-highlight-color:transparent`。表格在移动端**不缩字号**，靠 `.tbl-wrap` 横滑（`min-width:520px` 保证列不被压扁）。

---

## 五、响应式设计策略

### 5.1 断点设计

| 断点 | 目标设备 | 调整内容 |
|------|----------|----------|
| `max-width: 768px` | 手机 | 导航缩小、卡片单列、流程图纵向、内边距缩小 |

### 5.2 弹性布局技巧

- **卡片网格**：`grid-template-columns: repeat(auto-fit, minmax(320px, 1fr))` — 自动适应列数
- **流程图**：`flex-wrap: wrap` + 移动端改为 `flex-direction: column`
- **字号**：`font-size: clamp(1.8rem, 4vw, 2.8rem)` — 流体排版，无需断点即可平滑缩放

### 5.3 移动端适配清单

1. 导航栏内边距缩小；**链接横向滚动（`.nav-links{overflow-x:auto}`，`white-space:nowrap`）而非隐藏**（v2 导航完整性：每个主要 section 都有锚点，移动端保留可滚动锚点条）
2. 卡片网格变为单列
3. 流程图改为纵向排列，箭头旋转 90 度
4. 引用区内边距缩小
5. 确保触摸目标足够大（按钮 padding ≥ 44px）
6. **条形图（`.bar-chart`）**：`.bar-row` 改单列 `minmax(0,1fr)`，`.bar-label` 与 `.bar-val` 各占整行（`grid-column:1/-1; text-align:left; white-space:normal`），桌面端数值列用 `max-content` 自适应，避免任何定宽列溢出

---

## 六、实现流程（Agent 执行 SOP）

### Step 1：内容分析

读取文案内容，完成以下分析：

1. 提取**核心主题**（用于 Hero 标题）
2. 识别**关键概念**（用于概念解释区）
3. 找出**分类列举**的内容（用于卡片网格）
4. 识别**流程/步骤**（用于流程图）
5. 找出**金句/感悟**（用于引用区）
6. 提取**行动建议**（用于行动区）

### Step 2：搭建 HTML 骨架

```
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>页面标题</title>
    <style>
        /* CSS 全部写在这里 */
    </style>
</head>
<body>
    <!-- 背景粒子 -->
    <!-- 导航栏 -->
    <!-- Hero -->
    <!-- 各内容区块 -->
    <!-- Footer -->
</body>
</html>
```

### Step 3：写入 CSS 变量与基础重置

```
:root { /* 定义所有颜色/尺寸变量 */ }
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    font-family: 系统字体栈;
    background: var(--primary);
    color: var(--text-light);
    line-height: 1.8;
}
```

### Step 4：逐区块实现

按以下顺序编写每个区块的 HTML + CSS：

1. 背景粒子装饰
2. 导航栏
3. Hero 首屏
4. 概念解释区
5. 内容卡片区
6. 逻辑流程图
7. 金句引用区
8. 行动建议区
9. Footer

### Step 5：添加动画

为 Hero 元素添加入场动画，为卡片添加 hover 效果，为背景添加浮动动画。

### Step 6：响应式适配

添加 `@media (max-width: 768px)` 查询，调整移动端布局。

### Step 7：最终检查清单

- [ ] 所有文字颜色在深色背景上可读（对比度足够）
- [ ] 移动端布局无溢出/重叠
- [ ] 所有链接锚点可正常跳转
- [ ] 动画不会导致性能问题（使用 `transform` 和 `opacity` 而非 `top/left`）
- [ ] 文件可独立打开（无外部资源依赖）

---

## 七、可复用 CSS 代码片段库

### 7.1 毛玻璃卡片

> ⚠️ **卡片底色必须近乎不透明**（v3 修正）。旧版这里写的是 `rgba(255,255,255,0.06)`，
> 实测后果是背景粒子（300px 级色块）直接糊在正文上，截图里能看到紫红色脏斑，文字可读性下降。
> 毛玻璃的"透"应来自 `backdrop-filter: blur()` 的**模糊**，而不是把底色设成几乎全透明。
> 深色主题用带色相的实色（`rgba(38,41,66,0.88)`），亮色主题用纯白。

```
.glass-card {
    background: rgba(38,41,66,0.88);       /* 深色：遮住粒子 */
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 32px;
    backdrop-filter: blur(10px);            /* 模糊负责"毛"，底色负责"遮" */
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s;
}
body[data-theme="light"] .glass-card { background: #ffffff; }
.glass-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 16px 48px rgba(0,0,0,0.4);
    border-color: #e94560;
}
```

### 7.2 渐变文字

```
.gradient-text {
    background: linear-gradient(135deg, #e94560, #f5c518, #ff6b6b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
```

### 7.3 渐变按钮

```
.gradient-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 14px 36px;
    background: linear-gradient(135deg, #e94560, #c0392b);
    color: #fff;
    text-decoration: none;
    border-radius: 50px;
    font-weight: 600;
    transition: transform 0.3s, box-shadow 0.3s;
}
.gradient-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(233,69,96,0.4);
}
```

### 7.4 标签徽章

```
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 50px;
    font-size: 0.75rem;
    font-weight: 700;
}
.badge-gold { background: linear-gradient(135deg, #f5c518, #ff8c00); color: #000; }
.badge-red  { background: linear-gradient(135deg, #e94560, #ff6b6b); color: #fff; }
.badge-blue { background: linear-gradient(135deg, #0f3460, #4a90d9); color: #fff; }
```

### 7.5 左侧渐变条装饰

```
.left-bar::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, #e94560, #f5c518);
}
```

### 7.6 流体排版

```
/* 根据视口宽度自动缩放字号，有最小值和最大值 */
h1 { font-size: clamp(2.5rem, 6vw, 4.5rem); }
h2 { font-size: clamp(1.8rem, 4vw, 2.8rem); }
p  { font-size: clamp(1rem, 2vw, 1.25rem); }
```

### 7.7 量化机制条形图（v2 §3.3 / R3，v3 加固）

用于把原文里"可计算"的机制可视化——倍数、参照点、增减对比（如长期支持 61% vs 一次性 19%）。**纯 CSS 色块条形**；数值用 `--w` 自定义属性驱动 `transform:scaleX()` 生长动画（只用 transform/opacity，遵守 §4.2/§9.2）。挂在任意 section 的 `bars` 字段上：`bars=[{label,value,text?,tone?}]`、`bar_note?`。`value` 为数值（相对最大项归一化到宽度），`text` 为展示文案（缺省显示 value）。

**v3 三条硬约束（都是实测踩出来的）**

1. **极小值必须有地板宽度**。纯比例映射下 `0.4 / 61` 只有 0.65%，1280px 版面上约 5px，读者会判定"这项是 0"，于是把原文最要命的反差讲丢了。渲染器取 `max(v/mx*100, 10)`；**真 0 值仍归 0**（空条是诚实的表达，10% 的假空条不是）。
2. **默认态就是终态，动画是增强**。旧写法 `transform:scaleX(0)` + `animation ... forwards` 直接写在 `.bar-fill` 上，页面一加载动画就跑完，读者滚到那一节时看到的是静止的条；更糟的是若动画被拦，条永久停在 0。v3 改成：基础规则给终态宽度，只有 `<html class="js">` 且 `.bar-chart.in`（IntersectionObserver 滚动进场时加）才播动画。
3. **`--w` 要给 fallback**：`scaleX(calc(var(--w,100)/100))`。变量缺失时退回满宽，而不是整条声明失效导致条不显示。

```
.bar-chart{display:flex;flex-direction:column;gap:13px;margin-top:16px;padding:22px 24px;
  background:var(--card);border:1px solid var(--card-border);border-radius:var(--radius);
  box-shadow:var(--shadow);backdrop-filter:blur(10px)}
.bar-row{display:grid;grid-template-columns:minmax(0,120px) minmax(0,1fr) max-content;align-items:center;gap:12px}
.bar-row .bar-label{font-size:13px;font-weight:700;color:var(--muted);text-align:right;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{height:20px;border-radius:8px;background:var(--card2);overflow:hidden}
.bar-fill{display:block;height:100%;border-radius:8px;
  background:linear-gradient(90deg,var(--grad-a),var(--grad-b));
  transform:scaleX(calc(var(--w,100)/100));   /* ① 默认即终态 */
  transform-origin:left center}
.js .bar-fill{transform:scaleX(0)}            /* ② 只有 JS 在，才允许从 0 长 */
.js .bar-chart.in .bar-fill{animation:barGrow .9s cubic-bezier(.2,.7,.3,1) forwards}
.js .bar-chart.in .bar-row:nth-child(2) .bar-fill{animation-delay:80ms}
.js .bar-chart.in .bar-row:nth-child(3) .bar-fill{animation-delay:160ms}
.bar-row.green .bar-fill{background:linear-gradient(90deg,var(--accent2),var(--grad-b))}
.bar-row.red .bar-fill{background:linear-gradient(90deg,var(--danger),var(--grad-c))}
@keyframes barGrow{from{transform:scaleX(0)}to{transform:scaleX(calc(var(--w,100)/100))}}
.bar-note{margin-top:12px;font-size:12.5px;color:var(--dim);
  border-top:1px dashed var(--card-border);padding-top:10px}
/* 移动端：标签与数值各占整行，避免定宽列溢出 */
@media(max-width:768px){.bar-row{grid-template-columns:minmax(0,1fr)}
  .bar-row .bar-label{grid-column:1/-1;text-align:left;white-space:normal}
  .bar-row .bar-val{grid-column:1/-1;text-align:left;white-space:normal}}
```

### 7.8 二维对照表（v3 新增）

档位、价格、排期、参数这类**多列属性**数据用表格，不要用卡片堆叠（卡片适合"一条一段话"，表格适合"同一维度横向比"）。选型口诀见 §2.4。

```
.tbl-wrap{overflow-x:auto;border:1px solid var(--card-border);border-radius:var(--radius);
  box-shadow:var(--shadow);background:var(--card);backdrop-filter:blur(10px)}
table.tbl{width:100%;border-collapse:collapse;font-size:14.5px;min-width:520px}
table.tbl th{position:sticky;top:0;background:var(--card2);color:var(--txt);font-weight:800;
  text-align:left;padding:12px 14px;border-bottom:1px solid var(--card-border);white-space:nowrap}
table.tbl td{padding:11px 14px;border-bottom:1px solid var(--line);   /* 用 --line，不要写死白色 alpha：亮色主题下白上白=看不见 */
  color:var(--muted);vertical-align:top}
table.tbl td.num{font-variant-numeric:tabular-nums;color:var(--txt);font-weight:700;white-space:nowrap}
table.tbl th:first-child,table.tbl td:first-child{white-space:nowrap;padding-right:18px}  /* 首列通常是行名，auto 布局会把它挤到换行 */
```

要点：外层 `.tbl-wrap` 负责横滑（移动端不缩字号、不折行），`min-width:520px` 保证列不被压扁；首列 `nowrap`；数字列 `tabular-nums` 对齐。**表格单元格里的数字同样是原文数字**，必须可回溯（校验器会查）。

### 7.9 页脚折叠（v2 §3.1-6）

校正说明与实体列表默认折叠，普通读者不被生产过程信息干扰，点开可见；生成声明不折叠。

```
footer details{margin:10px auto 0;max-width:720px;text-align:left;
  background:var(--card);border:1px solid var(--card-border);
  border-radius:var(--radius);padding:10px 14px}
footer summary{cursor:pointer;font-weight:700;color:var(--muted);font-size:13px;user-select:none}
footer details .details-body{margin-top:8px;color:var(--dim);font-size:12.5px;line-height:1.7}
```

---

## 八、配色替换指南

如需更换主题色，只需修改 `:root` 中的变量：

| 变量 | 控制 | 建议替换值 |
|------|------|-----------|
| `--primary` | 页面背景 | 选深色：#0a0a0a / #1a1a2e / #0d1b2a |
| `--highlight` | 强调色（按钮/高亮） | 选醒目色：#e94560 / #00d9ff / #ff6b00 |
| `--gold` | 价值色（价格/等级） | 选金色系：#f5c518 / #ffd700 / #00ff88 |
| `--card-bg` | 卡片透明度 | 调整 alpha 值控制透明度 |
| `--text-light` | 主文字色 | 确保与背景对比度 ≥ 4.5:1 |
| `--text-muted` | 次要文字色 | 通常为 #888 / #aaa / #b0b0b0 |

---

## 九、技术约束与注意事项

### 9.1 必须遵守的规则

1. **零外部依赖**：不使用任何 CDN 链接、外部字体、外部图片。所有资源内联
2. **单文件交付**：HTML + CSS + JS 全部在一个 `.html` 文件中
3. **无框架**：不依赖 React/Vue/Bootstrap 等，纯原生 HTML/CSS/JS
4. **中文字体**：使用系统字体栈，不引入外部中文字体文件
5. **语义化标签**：使用 `<section>`、`<nav>`、`<footer>` 等语义标签

### 9.2 性能优化

- 动画使用 `transform` 和 `opacity`（GPU 加速），避免动画 `width/height/top/left`
- 背景粒子数量控制在 5-8 个，避免过多影响性能
- 不使用外部图片，用 emoji 或 CSS 形状替代图标
- CSS 不压缩（保持可读性，便于其他 Agent 理解和修改）

### 9.3 无障碍考虑

- 颜色对比度确保可读（浅色文字在深色背景上）
- 导航链接有明确的 `href` 锚点
- 按钮/链接有足够的点击区域
- 不使用纯颜色传达信息（辅以文字/图标）

---

## 十、快速启动模板

以下为最小可用模板，复制后即可开始填充内容：

```
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>标题</title>
    <style>
        :root {
            --primary: #1a1a2e; --highlight: #e94560; --gold: #f5c518;
            --text-light: #f0f0f0; --text-muted: #b0b0b0;
            --card-bg: rgba(255,255,255,0.06); --card-border: rgba(255,255,255,0.1);
            --radius: 16px; --shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        html { scroll-behavior: smooth; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                         "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: var(--primary); color: var(--text-light); line-height: 1.8;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 80px 20px; }
        .card {
            background: var(--card-bg); border: 1px solid var(--card-border);
            border-radius: var(--radius); padding: 32px;
            backdrop-filter: blur(10px); box-shadow: var(--shadow);
        }
        h1 { font-size: clamp(2.5rem, 6vw, 4.5rem); }
        h2 { font-size: clamp(1.8rem, 4vw, 2.8rem); }
        @media (max-width: 768px) {
            .skills-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <nav><!-- 导航 --></nav>
    <section class="hero"><!-- 首屏 --></section>
    <section class="container"><!-- 内容 --></section>
    <footer><!-- 页脚 --></footer>
</body>
</html>
```

---

> **总结**：这套方法论的核心是 **深色主题 + 毛玻璃卡片 + 渐变强调 + 流畅动画 + 响应式网格** 五要素组合。掌握 CSS 变量系统后，可快速换肤适配不同品牌调性。所有内容区块均可独立复用，按需组合即可生成完整页面。
