#!/usr/bin/env python3
"""run_pipeline.py — 单命令编排器（把 skill 的确定性工作全部收进脚本）

设计目标：任何 LLM 模型执行本 skill 时，不需要自己编排步骤、不需要读渲染器源码。
模型只负责【一个 bounded 动作】：读 TASK.md 任务单 + 填 analysis.json，然后跑 finish。

用法（两种模式）：
  python3 run_pipeline.py prepare <输入.mp4/.mov/…> [--out 输出目录] [--workers 3]
      → 提取音频 → ASR 分块转写 → 机器校正 → 生成 analysis.json 骨架 + TASK.md 任务单
      → 跑一次初检（骨架未填完，报错是预期的）
      之后由模型按 TASK.md 填好 analysis.json，跑 validate_analysis.py 自检到 0 error，
      再执行 finish。
  python3 run_pipeline.py finish <输入.mp4/…> [--theme light|dark] [--out 输出目录]
      → 校验 analysis.json（0 error 才继续）→ 渲染摘要版 + 阅读版 → 打印交付路径

断点/复用（关键提速）：
  prepare 开始前检查 out 目录里是否已有 transcript.txt / transcript_calibrated.txt。
  有就跳过对应步骤（ASR/校正很贵，命中缓存几乎零成本）。不会覆盖已有的 analysis.json。

退出码：0 成功；1 校验/前置失败；2 ASR 个别块失败但已有结果；3/4 见 llm_calibrate。
"""

import argparse, json, os, re, subprocess, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.expanduser("~/.dsh/secrets")

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.stdout: print(r.stdout, end="")
    if r.stderr: print(r.stderr, end="", file=sys.stderr)
    return r.returncode

def out_dir_for(inp, out):
    if out: return out
    return os.path.dirname(os.path.abspath(inp)) or "."

def read_secret(name):
    p = os.path.join(SECRETS, name)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get(name.replace("_api_key", "").upper() + "_API_KEY", "")

def ensure_input(inp):
    if not os.path.isfile(inp):
        print(f"ERROR: 找不到输入文件 {inp}", file=sys.stderr); sys.exit(1)
    return os.path.abspath(inp)

def nonempty(path):
    return os.path.isfile(path) and os.path.getsize(path) > 0

def build_skeleton(od, transcript_path, calib_path, report_path, example_path):
    """生成 analysis.json 骨架：正确顶层键 + 从校正术语表预填 entities。模型只需填内容。"""
    ap = os.path.join(od, "analysis.json")
    if nonempty(ap):
        print("→ analysis.json 已存在，保留不覆盖（如需重建请先删除它）")
        return
    skeleton = {
        "title": "",
        "tone": "",
        "summary": "",
        "hero_facts": [],
        "sections": [],
        "key_takeaways": [],
        "conclusion": {"cards": []},
        "entities": [],
        "footer": {"calibration": "（终稿前补一句：ASR 转写 + 机器预筛 + 人工终审，列出你接受的术语修正）"},
    }
    # 从报告术语表预填 entities（机器已确认的专名，模型可增补）
    if nonempty(report_path):
        try:
            with open(report_path, encoding="utf-8") as f:
                rep = json.load(f)
            gl = rep.get("glossary", {})
            if isinstance(gl, dict):
                skeleton["entities"] = list(gl.keys())
        except Exception:
            pass
    with open(ap, "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)
    print(f"→ 生成骨架 {ap}（entities 已从校正术语表预填）")

def build_task(od, transcript_path, calib_path, report_path, example_path):
    """生成 TASK.md 任务单：告诉模型【只做一件事】——按范本填 analysis.json。"""
    # 收集低置信度校正项 + 术语表，供模型终审
    low_items, glossary = [], {}
    if nonempty(report_path):
        try:
            with open(report_path, encoding="utf-8") as f:
                rep = json.load(f)
            glossary = rep.get("glossary", {}) or {}
            for c in rep.get("changes", []):
                if c.get("confidence") == "low":
                    low_items.append(c)
        except Exception:
            pass
    # 统计输入规模
    with open(transcript_path, encoding="utf-8") as f:
        tx = f.read()
    n_chars = len(tx)

    task = f"""# 任务单：为本次视频填写 `analysis.json`

你（LLM）在这条 skill 里唯一要做的，就是把 `analysis.json` 从一个【骨架】填成一个【完整文档】。
除此之外的一切——转写、校正、渲染、校验——都由脚本完成，你**不要**去改 transcript 或 HTML。

## 输入（请都读一遍）
1. 转写稿：`{os.path.basename(transcript_path)}`（约 {n_chars} 字，含 [mm:ss] 时间戳）← 内容来源，必须读。
2. 校正稿：`{os.path.basename(calib_path)}`（已修正 ASR 常见错别字/断句；正文以它为准）。
3. 范本（结构照抄它，别猜字段名）：`{os.path.basename(example_path)}`。
4. 低置信度校正项（report.json 里的 low，需你终审判断 accept/reject；其它 high 项已由脚本应用，不用管）：
{render_low(low_items)}
5. 机器确认的术语表（已并入骨架 entities，可增补）：
{render_glossary(glossary)}

## 你要写的字段（用 write 工具整体覆盖 analysis.json，保留正确键名）
- `title`：根据全文主题拟定，具体、可检索、≤30 字。禁用泛词（转写/文案/内容整理/transcript/未命名/视频文件名）。
  例：「耶鲁死亡课：直面死亡才能活明白」「2026 年中端手机选购指南」。
- `tone`：语气（教程/访谈/演讲/新闻/…）。
- `summary`：3–5 句话概括全文。
- `hero_facts`：3–6 个「全局记忆点数字」，每项 {{value, label, tone?}}，tone 取 acc/green/red/warn/purple 之一。数字是读者的记忆锚点，务必挑最冲击的。
- `sections`：6–10 个章节。每个 {{heading, desc?, type, …}}。**type 按内容本质选，字段必须配对该 type**（照范本）：
  - `default`：普通论述 → {{content:[字符串或{{title,desc}}]}}
  - `timeline`：有时间顺序的历程 → {{items:[{{year?,title,desc?,status}}]}}，status∈default/good/warn/danger
  - `compare`：前后/好坏对照 → {{old_title, old:[…], new_title, new:[…]}}
  - `pair`：痛点-解法 → {{pains:[{{title,desc?,quote?}}], fixes:[…]}}
  - `architecture`：结构/组织 → {{node_title, cols:[{{role,title,items?,nope?}}]}}
  - `flow`：流程/流向 → {{steps:[{{title,sub?,highlight?}}]}}，起/止可 highlight=start/end
  - `quote`：金句集 → {{cards:[{{text,source?}}]}}
  - `list`：可执行清单/条目 → {{items:[{{title,desc?}}]}}
  - 判断口诀：先问「这段本质是哪种关系」——时序→timeline、对比→compare、痛点解法→pair、结构→architecture、流向→flow、观点句→quote、清单→list、其余→default。**不要全堆成 default。**
- `key_takeaways`：5–10 条最重要的结论/数字/建议，每项 {{title, desc}}，desc 里带 [mm:ss] 引用时间戳。
- `conclusion`：{{cards:[{{text,source?}}]}}，放 1–3 条最提神的金句。
- `entities`：全文出现的人名/作品/地名/专名（骨架已预填术语表，可增补）。
- `footer.calibration`：一句话说明你接受了哪些术语校正（如「'EB9鲁'→伊壁鸠鲁」）。

## 红线（填的时候务必遵守）
- 只改高置信度错；改错代价大于不改。不确定就保留原文。
- 不改观点、不改数字量级、不添加原文没有的事实。
- 金句**原样**引用（加引号），不篡改。
- 所有数字必须能在转写稿里找到出处，禁止编造。

## 填完必须自检（直到 0 error 再继续）
```
python3 {os.path.join(SCRIPT_DIR, 'validate_analysis.py')} {os.path.join(od, 'analysis.json')} --transcript {transcript_path}
```
它只报告 ERROR（不修就不让过）和 WARN（建议修）。照提示改 analysis.json，重跑，直到 ERROR 全消。
然后执行：`python3 {os.path.join(SCRIPT_DIR, 'run_pipeline.py')} finish <输入文件>` 完成渲染。
"""
    with open(os.path.join(od, "TASK.md"), "w", encoding="utf-8") as f:
        f.write(task)
    print(f"→ 生成任务单 {os.path.join(od, 'TASK.md')}")

def render_low(items):
    if not items:
        return "  （无 low 项，全部高置信度，无需你终审）"
    lines = []
    for i, c in enumerate(items, 1):
        lines.append(f"  {i}. 原文「{c.get('original','')}」 → 校正稿「{c.get('corrected','')}」｜{c.get('reason','')}")
    return "\n".join(lines)

def render_glossary(gl):
    if not gl:
        return "  （无）"
    return "\n".join(f"  {k} ← {v}" for k, v in gl.items())

def cmd_prepare(args):
    inp = ensure_input(args.inp)
    od = out_dir_for(inp, args.out)
    os.makedirs(od, exist_ok=True)
    base = os.path.splitext(os.path.basename(inp))[0]
    wav = os.path.join(od, base + ".wav")
    tx = os.path.join(od, "transcript.txt")
    calib = os.path.join(od, "transcript_calibrated.txt")
    rep = os.path.join(od, "report.json")
    example = os.path.join(SCRIPT_DIR, "..", "examples", "analysis.example.json")

    # 1) 音频提取
    if nonempty(tx):
        print("→ 命中缓存 transcript.txt，跳过音频提取与 ASR")
    else:
        print(f"== 第 1 步 提取音频 ==  {inp}")
        rc = run([sys.executable, os.path.join(SCRIPT_DIR, "extract_audio.py"), inp, wav])
        if rc != 0:
            print("ERROR: 音频提取失败。请阅读上方输出；若为容器/编解码问题走 SKILL.md 降级方案。", file=sys.stderr)
            sys.exit(1)
        print(f"== 第 2 步 ASR 分块转写 ==  → {tx}")
        key = read_secret("siliconflow_api_key")
        env = dict(os.environ)
        if key: env["SILICONFLOW_API_KEY"] = key
        rc = run([sys.executable, os.path.join(SCRIPT_DIR, "asr_transcribe.py"), wav, tx,
                  "--workers", str(args.workers)], env=env)
        if rc == 2:
            print("WARN: 部分 ASR 块失败，但已有部分结果写出，可继续。", file=sys.stderr)

    # 2) 机器校正
    if nonempty(calib):
        print("→ 命中缓存 transcript_calibrated.txt，跳过机器校正")
    else:
        print(f"== 第 3 步 机器校正预筛 ==  → {calib}")
        key = read_secret("zhipu_api_key")
        env = dict(os.environ)
        if key: env["ZHIPU_API_KEY"] = key
        rc = run([sys.executable, os.path.join(SCRIPT_DIR, "llm_calibrate.py"), tx, calib,
                  "--report", rep], env=env)
        if rc == 3 or rc == 4:
            print(f"WARN: 校正 key 不可用（exit={rc}），已跳过校正。校正改为你在填 analysis.json 时手工完成。",
                  file=sys.stderr)

    # 3) 骨架 + 任务单 + 初检
    build_skeleton(od, tx, calib, rep, example)
    build_task(od, tx, calib, rep, example)
    print(f"\n== 下一步 ==\n按 {os.path.join(od, 'TASK.md')} 填好 analysis.json，自检到 0 error，再运行：")
    print(f"  python3 {os.path.join(SCRIPT_DIR, 'run_pipeline.py')} finish {inp}")
    print("（骨架未填完，validate 报 ERROR 是预期现象，不必惊慌。）")

def cmd_finish(args):
    inp = ensure_input(args.inp)
    od = out_dir_for(inp, args.out)
    tx = os.path.join(od, "transcript.txt")
    ap = os.path.join(od, "analysis.json")
    example = os.path.join(SCRIPT_DIR, "..", "examples", "analysis.example.json")

    if not nonempty(ap):
        print(f"ERROR: 找不到 {ap}。请先跑 prepare 生成骨架并填好。", file=sys.stderr); sys.exit(1)
    # 终检：0 error 才渲染
    vp = os.path.join(SCRIPT_DIR, "validate_analysis.py")
    rc = run([sys.executable, vp, ap, "--transcript", tx])
    if rc != 0:
        print("ERROR: analysis.json 未通过校验，不渲染。请按上面的 ERROR 改到 0。", file=sys.stderr)
        sys.exit(1)
    # 渲染两版
    print(f"== 渲染摘要版 ==")
    r1 = run([sys.executable, os.path.join(SCRIPT_DIR, "render_html.py"), ap, tx, "--theme", args.theme], cwd=od)
    print(f"== 渲染阅读版（校正稿）==")
    r2 = run([sys.executable, os.path.join(SCRIPT_DIR, "read_render.py"), tx, ap, "--theme", args.theme, "--calibrated"], cwd=od)
    if r1 != 0 or r2 != 0:
        print("WARN: 有渲染器报错，请检查上方输出。", file=sys.stderr)
    print(f"\n== 交付物位于 {od} ==")
    for f in sorted(os.listdir(od)):
        if f.endswith(".html"):
            print(f"  {os.path.join(od, f)}")

def main():
    p = argparse.ArgumentParser(description="video-html-extractor 单命令编排器")
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("prepare", help="提取+转写+校正+生成任务单与骨架")
    pa.add_argument("inp")
    pa.add_argument("--out", default="")
    pa.add_argument("--workers", type=int, default=3)
    pa.set_defaults(fn=cmd_prepare)
    pf = sub.add_parser("finish", help="校验+渲染两版")
    pf.add_argument("inp")
    pf.add_argument("--out", default="")
    pf.add_argument("--theme", choices=["light", "dark"], default="light")
    pf.set_defaults(fn=cmd_finish)
    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()