#!/usr/bin/env python3
"""schema.py — analysis.json 契约的唯一定义处（single source of truth）

背景：同一套规则此前散在三处——
  1) render_html.py 的 type→渲染分支
  2) validate_analysis.py 的 SECTION_TYPES / FACT_TONES / TL_STATUS / FLOW_HIGHLIGHT 白名单
  3) llm_draft_analysis.py 的 SYS_PROMPT（自然语言复述了一遍字段配对）
三处手工同步，任一处漂移就产生「校验器放过、渲染器不认」或「提示词写了、校验器打回」的静默失败。

本模块把**机器可判定的部分**（枚举集合、类型清单、字段配对文案、章节图标）收拢到一处：
  - validate_analysis.py 从这里取白名单与报错文案；
  - render_html.py 从这里取图标映射，并在导入时断言「每个已登记类型都有渲染分支」；
  - llm_draft_analysis.py 用 section_pairing() 生成提示词的【sections 类型与字段配对】整块。

新增一个 section type 的正确顺序：
  在此加一条 SECTION_SPECS（含 pairing 文案与图标）→ 在 render_html.RENDERERS 加分支 →
  在 validate_analysis 的 check 表加分支（若该类型有专属字段约束）→
  跑 `python3 schema.py` 看一致性断言是否通过。
纯约束（枚举、配对文案、图标）不需要再改提示词——它是从这里生成的。
"""

# ── 泛词（标题禁用）──
BAN_WORDS = ["转写", "视频文案", "内容整理", "transcript", "未命名", "视频转写", "文本整理"]

# ── 语气/色调枚举（hero_facts.tone、bars.tone 共用）──
# 顺序即展示顺序（提示词与报错文案沿用它，acc=强调色=默认，故排首位）。
TONE_ORDER = ["acc", "green", "red", "warn", "purple"]
FACT_TONES = {""} | set(TONE_ORDER)

# ── timeline item.status ──
TL_STATUS = {"default", "good", "warn", "danger"}

# ── flow step.highlight ──
FLOW_HIGHLIGHT = {None, "start", "end"}

# ── 章节类型契约 ──
# pairing = 「type：何时用 → 专属字段」一行，既进提示词也进文档；改这里即三处同步。
# icon    = render_html.ICONS 的键（缺失会在导入断言里报错）。
# fields  = 该类型除 heading/desc/bars 之外**渲染器真实读取**的键名。
#           ⚠️ 这份清单是 unknown-key 检查的依据，必须与 render_html 的分支逐字对齐：
#           多写一个键 → 合法输入被判错；少写一个键 → 真正会渲染的键被警告。
#           （default/quote 带 items 是渲染器的兜底读法，architecture 的 bottom_note 同理。）
SECTION_SPECS = {
    "default": {
        "use": "普通论述",
        "pairing": '- default：普通论述 → content:[字符串或{"title","desc"}]',
        "fields": ["content", "key_points", "items"],
        "icon": "compass",
    },
    "timeline": {
        "use": "时序历程",
        "pairing": '- timeline：时序历程 → items:[{"year"?,"title","desc"?,"status": default|good|warn|danger}]',
        "fields": ["items"],
        "icon": "timeline",
    },
    "compare": {
        "use": "前后/好坏对照",
        "pairing": '- compare：前后/好坏对照 → old_title, old:[…], new_title, new:[…]',
        "fields": ["old_title", "old", "new_title", "new"],
        "icon": "scale",
    },
    "pair": {
        "use": "痛点-解法",
        "pairing": '- pair：痛点-解法 → pains:[{"title","desc"?,"quote"?}], fixes:[同构]',
        "fields": ["pains", "fixes"],
        "icon": "grid2",
    },
    "architecture": {
        "use": "结构/组织",
        "pairing": '- architecture：结构/组织 → node_title, cols:[{"role","title","items"?,"nope"?}]',
        "fields": ["node_title", "node_sub", "cols", "bottom_note"],
        "icon": "building",
    },
    "flow": {
        "use": "流程/流向",
        "pairing": '- flow：流程/流向 → steps:[{"title","sub"?,"highlight"?}]（highlight 只允许 start/end）',
        "fields": ["steps"],
        "icon": "flow",
    },
    "quote": {
        "use": "金句集",
        "pairing": '- quote：金句集 → cards:[{"text","source"?}]',
        "fields": ["cards", "items"],
        "icon": "quote",
    },
    "list": {
        "use": "清单/条目",
        "pairing": '- list：清单/条目 → items:[{"title","desc"?}]',
        "fields": ["items"],
        "icon": "list",
    },
    "table": {
        "use": "二维对照（档位/价格/排期/参数），≥2 列且各行同列数",
        "pairing": '- table：二维对照 → columns:[字符串], rows:[[字符串|数字]（每行长度须等于 columns 长度）], caption?:字符串',
        "fields": ["columns", "rows", "caption"],
        "icon": "table",
    },
}

# 提示词结尾的判断口诀（与 SECTION_SPECS 同步维护）
PAIRING_MNEMONIC = ("判断口诀：时序→timeline、对比→compare、痛点解法→pair、结构→architecture、"
                    "流向→flow、观点句→quote、清单→list、二维对照→table、其余→default。")

# 供校验器报错时展示的合法类型串（排序稳定，便于 diff）
SECTION_TYPES = set(SECTION_SPECS)


def section_pairing(header: str = "【sections 类型与字段配对】（6–10 个章节，按内容本质选类型，不要全堆成 default）") -> str:
    """生成提示词里那一整块「类型与字段配对」文本。顺序即 SECTION_SPECS 的声明顺序。"""
    lines = [header]
    lines += [SECTION_SPECS[t]["pairing"] for t in SECTION_SPECS]
    lines.append(PAIRING_MNEMONIC)
    return "\n".join(lines)


def tone_list() -> str:
    """tone 枚举的展示串（不含空串，保持声明顺序），用于提示词/报错。"""
    return "|".join(TONE_ORDER)


def field_names(stype: str) -> str:
    return ", ".join(SECTION_SPECS[stype]["fields"])


# section 上的通用键（与 type 无关）+ bars 的历史别名
COMMON_SECTION_KEYS = {"type", "heading", "desc", "bars", "bar_note", "bar_chart"}


def known_section_keys(stype: str) -> set:
    """该 type 下允许出现的键名全集（供校验器抓「字段名打错」）。"""
    spec = SECTION_SPECS.get(stype)
    if not spec:
        return set(COMMON_SECTION_KEYS)
    return set(COMMON_SECTION_KEYS) | set(spec["fields"])


def _selfcheck() -> None:
    """导入即跑的一致性断言：契约自身不能自相矛盾。"""
    for t, spec in SECTION_SPECS.items():
        # pairing 行必须以 `- <type>：` 开头，否则提示词与类型名脱节
        prefix = f"- {t}："
        if not spec["pairing"].startswith(prefix):
            raise RuntimeError(f"schema.SECTION_SPECS[{t}].pairing 未以 {prefix!r} 开头，提示词会误导模型")
        if not spec["icon"]:
            raise RuntimeError(f"schema.SECTION_SPECS[{t}] 缺 icon")
    if "default" not in SECTION_SPECS:
        raise RuntimeError("schema.SECTION_SPECS 必须包含 default（渲染器与校验器的兜底类型）")
    # 口诀里提到的每个类型都要真实存在
    for t in SECTION_SPECS:
        if f"→{t}" not in PAIRING_MNEMONIC and t != "default":
            raise RuntimeError(f"schema.PAIRING_MNEMONIC 漏了 {t}")
    if "其余→default" not in PAIRING_MNEMONIC:
        raise RuntimeError("schema.PAIRING_MNEMONIC 漏了 default 兜底口诀")


_selfcheck()


def assert_renderers(renderers: dict, caller: str) -> None:
    """渲染器在构建完 type→函数表后调用：已登记类型必须有分支，否则宁可拒绝渲染。
    宁可现在炸，也不要上线后静默降级成 default（模型以为写了 table，读者看到一段散文）。"""
    missing = sorted(SECTION_TYPES - set(renderers))
    extra = sorted(set(renderers) - SECTION_TYPES)
    if missing:
        raise SystemExit(f"ERROR: {caller} 缺少 section 渲染分支：{missing}（schema 已登记，必须实现或从 schema 删除）")
    if extra:
        raise SystemExit(f"ERROR: {caller} 存在未登记类型：{extra}（先在 schema.SECTION_SPECS 声明，再实现分支）")


if __name__ == "__main__":
    print("schema.py 一致性断言：通过")
    print(f"合法 type（{len(SECTION_TYPES)}）：{sorted(SECTION_TYPES)}")
    print(f"tone：{sorted(FACT_TONES)}")
    print("—— 生成的提示词配对块 ——")
    print(section_pairing())
