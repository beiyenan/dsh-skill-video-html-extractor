#!/usr/bin/env python3
"""llm_draft_analysis.py — 用智谱 GLM 把校正稿一次性起草成完整 analysis.json。

设计定位：把「读稿 + 写 analysis.json」这个耗时大头从**当前会话模型**挪到流水线里
**固定的、便宜的、带重试**的模型上。会话模型切换（快/慢/限流）不再影响 skill 的主耗时；
主模型只做终审（读草稿、对照校正稿修订、跑校验），生成量从 ~14k 字降到按需改动。

用法:
  python3 llm_draft_analysis.py <transcript_calibrated.txt> <analysis.json> \
      [--report report.json] [--example examples/analysis.example.json] \
      [--model glm-4.7] [--force]

行为:
- analysis.json 已存在且 title 非空（主模型已开始填）时，默认跳过不覆盖；--force 强制覆盖。
- 生成后立刻用 validate_analysis.validate 自检；有 ERROR 则把错误清单回喂给 GLM 修复，
  最多 2 轮；仍有 ERROR 也照样落盘（主模型终审时会再跑校验兜底），并打印剩余错误。
- GLM 调用失败/无配额/鉴权失败时不覆盖骨架，退出码非 0，主流程回退到「主模型手填」。

退出码: 0 草稿已落盘 | 3 无余额 | 4 鉴权失败 | 5 草稿生成失败（骨架保留）
"""
import argparse, json, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from llm_calibrate import (zhipu_chat, extract_json, load_key, log,  # noqa: E402
                           AuthError, NoQuota, TransientError, RateLimitedError, RATE_WAIT)
import time  # noqa: E402

SYS_PROMPT = """你是视频内容结构化编辑。给你一份视频转写校正稿，你要输出一个完整的 analysis.json（内容结构化描述），供两个 HTML 渲染器使用。

【硬性红线】
- 只使用校正稿里的事实/数字/人名，禁止编造；数字必须能在校正稿里找到出处。
- 金句引用保持原样（原话），不篡改。
- title：具体、可检索、≤30 字；禁用泛词（转写/视频文案/内容整理/transcript/未命名/视频转写/文本整理）。
- reader_highlights：8–15 条，每条 4–30 字，必须【逐字摘自校正稿】（一个字都不能改，含标点）；挑含金量最高的核心概念定义、关键结论、金句、重要数字表述；禁止挑「首先/所以/但是」这类过渡词。
- key_takeaways：5–10 条，desc 末尾带 [mm:ss] 时间戳，时间戳必须来自校正稿里出现过的行首时间戳。
- 只输出一个合法 JSON 对象：不要代码块围栏、不要任何解释文字、不要省略号。

【字段结构（照此输出，键名一字不差）】
{
  "title": "字符串",
  "tone": "语气（教程/访谈/演讲/新闻/…）",
  "summary": "3–5 句话概括全文",
  "hero_facts": [{"value": "冲击性数字", "label": "一句话说明", "tone": "acc|green|red|warn|purple"}],
  "sections": [ {"type": "…", "heading": "≤40字", "desc": "可选", …按类型配字段…} ],
  "key_takeaways": [{"title": "…", "desc": "…… [mm:ss]"}],
  "reader_highlights": ["逐字短语", "…"],
  "conclusion": {"cards": [{"text": "金句", "source": "出处说明"}]},
  "entities": ["人名/作品/地名/专名", "…"],
  "footer": {"calibration": "（留空字符串即可，由终审填写）"}
}

【sections 类型与字段配对】（6–10 个章节，按内容本质选类型，不要全堆成 default）
- default：普通论述 → content:[字符串或{"title","desc"}]
- timeline：时序历程 → items:[{"year"?,"title","desc"?,"status": default|good|warn|danger}]
- compare：前后/好坏对照 → old_title, old:[…], new_title, new:[…]
- pair：痛点-解法 → pains:[{"title","desc"?,"quote"?}], fixes:[同构]
- architecture：结构/组织 → node_title, cols:[{"role","title","items"?,"nope"?}]
- flow：流程/流向 → steps:[{"title","sub"?,"highlight"?}]（highlight 只允许 start/end）
- quote：金句集 → cards:[{"text","source"?}]
- list：清单/条目 → items:[{"title","desc"?}]
判断口诀：时序→timeline、对比→compare、痛点解法→pair、结构→architecture、流向→flow、观点句→quote、清单→list、其余→default。

【质量要求】
- hero_facts 3–6 个，挑全文最冲击的数字做读者记忆锚点。
- sections 的 desc/content 要具体（带数字、人名、细节），不要空泛概括。
- conclusion.cards 1–3 条最提神的金句。"""

REPAIR_TMPL = """你上次输出的 analysis.json 未通过结构校验。错误清单：
{errors}

请修正后重新输出【完整】 JSON 对象（不要围栏、不要解释、不要省略）。
校正稿原文不变，仍是上一份输入里的那份；所有 reader_highlights 必须逐字摘自校正稿。"""

MAX_TRANSCRIPT_CHARS = 60000   # 超出截断（glm-4.7 上下文足够，这里只防极端长视频把输出预算挤没）
GEN_MAX_TOKENS = 16000


def build_user(transcript, glossary, low_items):
    gl = "\n".join(f"- {k}：{v}" for k, v in glossary.items()) or "（无）"
    if low_items:
        lo = "\n".join(f"- 原文「{c.get('original','')}」→ 建议「{c.get('corrected','')}」｜{c.get('reason','')}"
                       for c in low_items)
    else:
        lo = "（无）"
    tx = transcript
    note = ""
    if len(tx) > MAX_TRANSCRIPT_CHARS:
        half = MAX_TRANSCRIPT_CHARS // 2
        tx = tx[:half] + "\n…（中段因过长省略，entities/高亮请从可见部分选取）…\n" + tx[-half:]
        note = "\n（注意：转写稿过长，中段已省略；章节数取 6–8 个即可）"
    return (f"【机器确认的术语表（entities 请沿用这些规范写法）】\n{gl}\n\n"
            f"【低置信度存疑项（请你终审决定采不采用）】\n{lo}\n\n"
            f"【校正稿全文（每行以 [mm:ss] 开头）】\n{tx}{note}\n\n"
            "请输出完整 analysis.json。")


def try_generate(key, base_url, model, messages):
    """带限流退避的单次生成。返回解析后的 dict 或 None。"""
    last = ""
    for attempt in (1, 2, 3):
        try:
            resp = zhipu_chat(key, base_url, model, messages, GEN_MAX_TOKENS)
        except (AuthError, NoQuota):
            raise
        except RateLimitedError as e:
            last = str(e)
            log(f"  尝试{attempt} {last}，等待 {RATE_WAIT * attempt}s 退避")
            time.sleep(RATE_WAIT * attempt)
            continue
        except TransientError as e:
            last = str(e)
            log(f"  尝试{attempt} 网络/HTTP 失败: {last}")
            time.sleep(3 * attempt)
            continue
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        d = extract_json(content)
        if isinstance(d, dict) and d.get("title") and isinstance(d.get("sections"), list) and d["sections"]:
            log(f"  生成 OK tokens={resp.get('usage', {}).get('total_tokens')}"
                f" sections={len(d['sections'])}")
            return d
        last = f"JSON 解析失败或缺关键字段（输出 {len(content)} 字符）"
        log(f"  尝试{attempt} {last}")
        messages = messages + [
            {"role": "assistant", "content": content[:2000] if content else "（空）"},
            {"role": "user", "content": "上次输出不合法或残缺。重新输出完整合法 JSON：不要围栏、不要省略，sections 至少 6 个。"}]
    return None


def main():
    ap = argparse.ArgumentParser(description="校正稿 → analysis.json 草稿（GLM 一次性起草）")
    ap.add_argument("transcript")
    ap.add_argument("analysis")
    ap.add_argument("--report", default="", help="report.json（取术语表与 low 项）")
    ap.add_argument("--model", default="glm-4.7")
    ap.add_argument("--base-url", default="https://open.bigmodel.cn/api/paas/v4")
    ap.add_argument("--force", action="store_true", help="覆盖已有非空 analysis.json")
    args = ap.parse_args()

    # 主模型已开始填的 analysis.json 不覆盖
    if os.path.isfile(args.analysis) and not args.force:
        try:
            old = json.load(open(args.analysis, encoding="utf-8"))
            if old.get("title"):
                log("→ analysis.json 已有内容（title 非空），跳过草稿生成")
                sys.exit(0)
        except Exception:
            pass

    key = load_key()
    if not key:
        log("WARN: 无智谱 key，跳过草稿（主模型手填 analysis.json）")
        sys.exit(4)

    transcript = open(args.transcript, encoding="utf-8").read()
    glossary, low_items = {}, []
    if args.report and os.path.isfile(args.report):
        try:
            rep = json.load(open(args.report, encoding="utf-8"))
            glossary = rep.get("glossary", {}) or {}
            low_items = [c for c in rep.get("changes", []) if c.get("confidence") == "low"]
        except Exception:
            pass

    messages = [{"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": build_user(transcript, glossary, low_items)}]

    log(f"INFO: 起草 analysis.json（model={args.model}, 校正稿 {len(transcript)} 字）")
    try:
        draft = try_generate(key, args.base_url, args.model, messages)
    except NoQuota as e:
        log(f"WARN: 无余额/资源包（{e}），跳过草稿，回退主模型手填"); sys.exit(3)
    except AuthError as e:
        log(f"WARN: 鉴权失败（{e}），跳过草稿，回退主模型手填"); sys.exit(4)
    if draft is None:
        log("WARN: 3 次生成均失败，保留骨架，回退主模型手填"); sys.exit(5)

    # 自检 + 最多 2 轮修复回喂
    from validate_analysis import validate
    for rd in (1, 2):
        r = validate(draft, transcript)
        if not r.errors:
            if r.warns:
                log(f"INFO: 自检 {len(r.warns)} 条 WARN（终审时再处理）")
            break
        log(f"INFO: 自检 {len(r.errors)} 个 ERROR，回喂修复（第 {rd} 轮）: {'；'.join(r.errors[:3])}")
        fix_msgs = [{"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": build_user(transcript, glossary, low_items)},
                    {"role": "assistant", "content": json.dumps(draft, ensure_ascii=False)[:12000]},
                    {"role": "user", "content": REPAIR_TMPL.format(errors="\n".join("- " + e for e in r.errors))}]
        try:
            fixed = try_generate(key, args.base_url, args.model, fix_msgs)
        except (NoQuota, AuthError):
            break
        if fixed is None:
            break
        draft = fixed
    else:
        pass

    r = validate(draft, transcript)
    json.dump(draft, open(args.analysis, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"OK: 草稿已写入 {args.analysis}（剩余 ERROR={len(r.errors)} WARN={len(r.warns)}，由终审处理）")
    for e in r.errors[:8]:
        log(f"  残留 ERROR: {e}")
    sys.exit(0)


if __name__ == "__main__":
    main()
