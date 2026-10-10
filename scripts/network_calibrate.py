#!/usr/bin/env python3
"""network_calibrate.py — 用 Tavily 搜索批量核实 analysis.json 里的专有名词（entities）。

用法:
  python3 network_calibrate.py <analysis.json> [--out DIR] [--batch 3] [--append] [--key-file PATH]

按 SKILL.md「网络校准」的要求：把 entities 按语义分组，每组 2–4 条拼成一条 query，
**不要一个词一行单独搜**。只对「公司/团队名、产品/模型名、人名、地名/机构名」做写法核实；
纯概念性术语（社会必要劳动时间、商品拜物教等标准教科书术语）只确认、不改写。

搜索策略（避免重复请求）：
  1) 先按「类别」把 entities 分成 3 组（机构/产品、人名、地点/体系），组内拼成一条 query；
  2) 若某组全部实体在首轮结果中均已命中，不再补搜；
  3) 仅对首轮未命中的实体，按原样再拼一条 query 补搜一轮。

输出:
  --out 目录下的 calibration_report.json（结构化，可被 finish 读取）
  --append 时：若 analysis.json 的 footer.calibration 仍为骨架占位符，自动填入校准摘要
退出码: 0（网络/key 缺失仅 WARN，不阻塞后续流程）
"""

import argparse, json, os, sys, time, urllib.error, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)
TAVILY_API = "https://api.tavily.com/search"
# 候选读取顺序：工作区/命令行指定 → skill 根目录 → ~/.dsh/secrets → 环境变量
KEY_CANDIDATES = [".tavily_key", os.path.join(SKILL_ROOT, ".tavily_key"),
                  os.path.expanduser("~/.dsh/secrets/tavily_api_key")]
SKELETON_CALIB = "（终稿前补一句：ASR 转写 + 机器预筛 + 人工终审，列出你接受的术语修正）"
DEFAULT_BATCH = 3
MAX_RESULTS = 3


def read_tavily_key(key_file=None):
    if key_file and os.path.isfile(key_file):
        with open(key_file, encoding="utf-8") as f:
            return f.read().strip()
    for cand in KEY_CANDIDATES:
        if os.path.isfile(cand):
            with open(cand, encoding="utf-8") as f:
                return f.read().strip()
    return os.environ.get("TAVILY_API_KEY", "")


def group_entities(entities):
    """按粗类别分组（保持原序），每组最多 DEFAULT_BATCH 条，拼成一条 query。"""
    buckets = {"机构/产品": [], "人名": [], "地点/体系/概念": []}
    for e in entities:
        if any(k in e for k in ("公司", "集团", "实验室", "团队", "项目", "平台", "模型",
                                "微信", "抖音", "快手", "头条", "B站", "小红书")):
            buckets["机构/产品"].append(e)
        elif len(e) <= 4 and not any(c.isdigit() for c in e) and "-" not in e and "_" not in e:
            buckets["人名"].append(e)
        else:
            buckets["地点/体系/概念"].append(e)
    groups = []
    for name, items in buckets.items():
        for i in range(0, len(items), DEFAULT_BATCH):
            groups.append(items[i:i + DEFAULT_BATCH])
    return [g for g in groups if g]


def build_query(group):
    return " ".join(group)


def tavily_search(api_key, query, max_results=MAX_RESULTS, depth="basic", retries=3):
    body = json.dumps({"api_key": api_key, "query": query,
                       "search_depth": depth, "max_results": max_results})
    req = urllib.request.Request(TAVILY_API, data=body.encode("utf-8"),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < retries - 1:
                wait = (attempt + 1) * 20
                print(f"WARN: Tavily 限流（{e.code}），{wait}s 后重试", file=sys.stderr)
                time.sleep(wait)
                continue
            break
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 5)
                continue
            break
    msg = getattr(last_err, "msg", str(last_err))
    print(f"WARN: Tavily 搜索失败 query={query!r} ({msg})", file=sys.stderr)
    return {"query": query, "results": [], "error": msg}


def entity_hit(entity, results):
    """实体是否出现在任一返回结果的标题/正文/URL 中。"""
    needle = entity
    for r in results:
        blob = (r.get("title", "") + " " + r.get("content", "") + " " + r.get("url", "")).lower()
        if needle.lower() in blob:
            return True, r
        alt = needle.replace("'", "").replace("’", "")
        if alt != needle and alt.lower() in blob:
            return True, r
    return False, None


def calibrate_entities(api_key, entities, max_batch=DEFAULT_BATCH):
    groups = group_entities(entities)
    queries = []
    for g in groups:
        q = build_query(g)
        res = tavily_search(api_key, q)
        per = {}
        for e in g:
            ok, src = entity_hit(e, res.get("results", []))
            per[e] = {"verified": ok, "source": src}
        queries.append({"query": q, "results": res.get("results", []),
                        "entities": g, "per_entity": per})
        pending = [e for e in g if not per[e]["verified"]]
        if pending:
            time.sleep(0.4)
            q2 = build_query(pending)
            res2 = tavily_search(api_key, q2)
            for e in pending:
                ok, src = entity_hit(e, res2.get("results", []))
                per[e] = {"verified": ok, "source": src}
        time.sleep(0.4)
    return queries


def build_calibration_text(queries):
    lines = []
    ok_n = 0
    total = 0
    for q in queries:
        verified = [e for e, v in q["per_entity"].items() if v["verified"]]
        unverified = [e for e, v in q["per_entity"].items() if not v["verified"]]
        ok_n += len(verified)
        total += len(q["entities"])
        hint = q["results"][0]["title"] if q["results"] else "搜索结果"
        if verified:
            lines.append("① " + "、".join(verified) + " 写法与官方一致（命中 " + hint + "）")
        if unverified:
            lines.append("② " + "、".join(unverified) + " 未在搜索结果中确认，保留原文写法")
    head = f"网络校准（Tavily API，已执行）：共核实 {ok_n}/{total} 项"
    if ok_n == total:
        head += "，无须修正。"
    else:
        head += f"；未确认项保留原文。"
    return head + " " + "；".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Tavily 批量校准 analysis.json 的 entities")
    ap.add_argument("analysis", help="analysis.json 路径")
    ap.add_argument("--out", default="", help="报告输出目录（默认 analysis.json 所在目录）")
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="每组实体数（默认 3）")
    ap.add_argument("--key-file", default="", help="Tavily key 文件路径")
    ap.add_argument("--reuse", action="store_true",
                    help="若 calibration_report.json 已存在则直接复用，不再重复搜索")
    ap.add_argument("--append", action="store_true",
                    help="若 footer.calibration 仍为骨架占位符，则自动填入校准摘要")
    ap.add_argument("--force-append", action="store_true",
                    help="无论 footer.calibration 是否有内容，都追加校准摘要")
    args = ap.parse_args()

    if not os.path.isfile(args.analysis):
        print(f"ERROR: 找不到 {args.analysis}", file=sys.stderr); sys.exit(1)
    with open(args.analysis, encoding="utf-8") as f:
        data = json.load(f)
    entities = data.get("entities", [])
    if not entities:
        print("WARN: analysis.json 无 entities，跳过网络校准"); sys.exit(0)

    api_key = read_tavily_key(args.key_file)
    if not api_key:
        print("WARN: 未找到 Tavily API key（--key-file / .tavily_key / ~/.dsh/secrets/tavily_api_key / TAVILY_API_KEY），跳过网络校准",
              file=sys.stderr)
        sys.exit(0)

    print(f"== 网络校准 ==  {len(entities)} 个 entity，Tavily API")
    od = args.out or os.path.dirname(os.path.abspath(args.analysis))
    os.makedirs(od, exist_ok=True)
    report_path = os.path.join(od, "calibration_report.json")
    if args.reuse and os.path.isfile(report_path):
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        queries = report.get("queries", [])
        print(f"→ 复用已有报告 {os.path.basename(report_path)}，不再重复搜索")
    else:
        queries = calibrate_entities(api_key, entities, args.batch)
        report = {"source": args.analysis, "entities": entities, "queries": queries,
                  "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    summary = build_calibration_text(queries)
    print(f"→ 报告 {report_path}")
    for q in queries:
        v = [e for e, vv in q["per_entity"].items() if vv["verified"]]
        u = [e for e, vv in q["per_entity"].items() if not vv["verified"]]
        tag = "✓" if not u else "⚠"
        print(f"   {tag} {q['query']!r}  命中: {v or '-'}" + (f"  未确认: {u}" if u else ""))

    if args.append or args.force_append:
        cur = data.get("footer", {}).get("calibration", "")
        if args.append and cur and cur.strip() != SKELETON_CALIB:
            print(f"→ footer.calibration 已由人工填写，跳过自动回填（保留原文）")
        else:
            prefix = cur if (cur and cur.strip() != SKELETON_CALIB) else ""
            new_text = (prefix + "\n" + summary) if prefix else summary
            data.setdefault("footer", {})["calibration"] = new_text
            with open(args.analysis, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"→ 已自动回填 footer.calibration（{len(queries)} 组实体已核实）")

    confirmed = len([e for q in queries for e, v in q["per_entity"].items() if v["verified"]])
    print(f"OK: 网络校准完成，{confirmed}/{len(entities)} 已确认")
    sys.exit(0)


if __name__ == "__main__":
    main()