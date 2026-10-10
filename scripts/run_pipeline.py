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
      → 校验 analysis.json（仅 ERROR 拒绝渲染；WARN 放行）→ 渲染摘要版 + 阅读版 → 打印交付路径

断点/复用（关键提速）：
  prepare 开始前检查 out 目录里是否已有 transcript.txt / transcript_calibrated.txt。
  有就跳过对应步骤（ASR/校正很贵，命中缓存几乎零成本）。不会覆盖已有的 analysis.json。

退出码：0 成功；1 校验/前置失败；2 ASR 个别块失败但已有结果；3/4 见 llm_calibrate。
"""

import argparse, json, os, re, shutil, subprocess, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.expanduser("~/.dsh/secrets")

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.stdout: print(r.stdout, end="")
    if r.stderr: print(r.stderr, end="", file=sys.stderr)
    return r.returncode

def out_dir_for(inp, out):
    # 统一解析为绝对路径，避免相对路径 + 子进程 cwd 造成的"找不到文件"混乱。
    if out:
        return os.path.abspath(out)
    return os.path.dirname(os.path.abspath(inp)) or os.path.abspath(".")

def read_tavily_key(od=""):
    """Tavily key 读取链（按顺序，命中即返回）：工作区/命令行 → skill 根目录 → ~/.dsh/secrets → 环境变量。

    Key 放在 skill 根目录的 `.tavily_key`（被 .gitignore 忽略，不进 Git；但 dsh-backup 把
    skills/ 整目录打进 zip，所以换机/重装时随 skill 一起恢复）。
    """
    candidates = []
    if od:
        candidates.append(os.path.join(od, ".tavily_key"))
    candidates += [".tavily_key", os.path.join(SCRIPT_DIR, "..", ".tavily_key"),
                   os.path.join(SECRETS, "tavily_api_key")]
    for cand in candidates:
        if os.path.isfile(cand):
            with open(cand, encoding="utf-8") as f:
                return f.read().strip()
    return os.environ.get("TAVILY_API_KEY", "")


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
        "reader_highlights": [],
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

    task = f"""# 任务单：终审 `analysis.json`（GLM 已起草，你只做修订）

这条 skill 的重活（转写、校正、起草）都已由脚本完成。analysis.json 里现在通常是一份
**GLM 预填的草稿**（若起草失败则是空骨架，此时按下方字段规范从零填）。
你唯一要做的：**读校正稿 → 审草稿 → 修订 → 自检 → finish**。不要去改 transcript 或 HTML。

## 终审清单（按序做，别跳步）
1. 读校正稿：`{os.path.basename(calib_path)}`（正文以它为准）。
2. **先跑网络校准（此时 analysis.json 还没被你动过，脚本写 footer 不会和你的编辑冲突）**：
   `python3 {os.path.join(SCRIPT_DIR, 'run_pipeline.py')} calibrate <输入文件> --out {od}`
   Tavily 批量核实 entities 并写 calibration_report.json；footer.calibration 为骨架时自动回填，
   已有人工内容不覆盖。**跑完这一步后，脚本在 finish 前不会再写 analysis.json，之后你随便 edit。**
   你只需审读报告里的「未确认」项，确实写错的按「『原文』→『官方写法』（出处）」补录。
   无 Tavily key 时静默跳过，可改用 web_search 手动核实。
   （生活/教程类视频的 entities 多为口语称谓——如烧烤料名、炭名——搜不到官方写法是常态，
   未确认项保留原文即可，不必逐条深究。）
3. 读 `analysis.json` 草稿，逐项核对：
   - **事实/数字**：每个数字都要能在校正稿里找到出处，删掉或改正编造的；
   - **reader_highlights**：每条必须逐字摘自校正稿（含标点），不在原文的改写或删除；
   - **结构与类型**：sections 的 type 是否贴内容（时序→timeline、对比→compare…），不像话的改；
   - **表达质量**：title 是否具体可检索、summary 是否抓住主线、金句引用是否原样。
   用 edit 工具做针对性修订；只有草稿整体不合格才用 write 整体重写。
4. 低置信度校正项（report.json 里的 low，需你终审判断 accept/reject；high 项已由脚本应用）：
{render_low(low_items)}
5. 机器确认的术语表（entities 应沿用这些写法）：
{render_glossary(glossary)}
6. 补上 `footer.calibration`：在网络校准回填的内容**前面**追加一句人工说明（本次校正接受了哪些术语修正，如「'EB9鲁'→伊壁鸠鲁」），不要删掉已回填的网络校准记录。

## 红线
- 只改高置信度错；改错代价大于不改。不确定就保留原文。
- 不改观点、不改数字量级、不添加原文没有的事实。
- 金句**原样**引用（加引号），不篡改。

## 自检（直到 0 error 再 finish）
```
python3 {os.path.join(SCRIPT_DIR, 'validate_analysis.py')} {os.path.join(od, 'analysis.json')}
```
（不带 --transcript 时会自动探测校正稿做溯源基准；显式传参也行。）
照提示改 analysis.json 重跑，ERROR 全消后执行：
`python3 {os.path.join(SCRIPT_DIR, 'run_pipeline.py')} finish <输入文件>`

## 若草稿是空骨架（GLM 起草失败时）
按范本 `{os.path.basename(example_path)}` 的字段结构手填。字段规范：
title(≤30字,禁泛词) / tone / summary(3–5句) / hero_facts(3–6个,{{value,label,tone:acc|green|red|warn|purple}}) /
sections(6–10个,type∈default|timeline|compare|pair|architecture|flow|quote|list,字段照范本) /
key_takeaways(5–10条,desc 带 [mm:ss]) / reader_highlights(8–15条,4–30字,逐字摘自校正稿,禁过渡词) /
conclusion.cards(1–3条金句) / entities / footer.calibration。
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

def cmd_calibrate(args):
    """网络校准：把 analysis.json 的 entities 分组 → Tavily 批量搜索 → 写 calibration_report.json；
    若模型尚未填写 footer.calibration，自动回填（保护人工已写内容）。"""
    inp = ensure_input(args.inp)
    od = out_dir_for(inp, args.out)
    ap = os.path.join(od, "analysis.json")
    if not nonempty(ap):
        print(f"ERROR: 找不到 {ap}。请先跑 prepare 并填好 analysis.json。", file=sys.stderr); sys.exit(1)
    print(f"== 网络校准 ==  读取 {ap} 的 entities，Tavily API")
    rc = run([sys.executable, os.path.join(SCRIPT_DIR, "network_calibrate.py"), ap,
              "--out", od, "--batch", str(args.batch), "--append", "--reuse"], cwd=od)
    if rc != 0:
        print("ERROR: 网络校准失败，请检查上方输出", file=sys.stderr); sys.exit(rc)
    print("== 下一步 ==  按 TASK.md 审读校准结果，自检到 0 error 后运行 finish")


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
                  "--report", rep, "--workers", str(args.workers)], env=env)
        if rc == 3 or rc == 4:
            print(f"WARN: 校正 key 不可用（exit={rc}），已跳过校正。校正改为你在填 analysis.json 时手工完成。",
                  file=sys.stderr)

    # 3) 骨架 + 任务单 + 初检
    build_skeleton(od, tx, calib, rep, example)
    build_task(od, tx, calib, rep, example)

    # 4) GLM 起草 analysis.json（模型无关提速：重生成钉在固定的 glm-4.7 上，
    #    会话模型切换不影响主耗时。失败/无 key 时静默回退为骨架手填。）
    draft_src = calib if nonempty(calib) else tx
    if args.no_draft:
        print("→ --no-draft：跳过 GLM 起草，analysis.json 由主模型手填")
    elif nonempty(draft_src):
        print(f"== 第 4 步 GLM 起草 analysis.json ==  ← {os.path.basename(draft_src)}")
        key = read_secret("zhipu_api_key")
        env = dict(os.environ)
        if key: env["ZHIPU_API_KEY"] = key
        rc = run([sys.executable, os.path.join(SCRIPT_DIR, "llm_draft_analysis.py"),
                  draft_src, os.path.join(od, "analysis.json"), "--report", rep], env=env)
        if rc == 0:
            print("→ 草稿就绪：你只需【终审修订】（见 TASK.md），不必从零写")
        else:
            print(f"WARN: 草稿生成失败（exit={rc}），analysis.json 保持骨架，由你手填。", file=sys.stderr)

    print(f"\n== 下一步 ==\n按 {os.path.join(od, 'TASK.md')} 终审/填写 analysis.json，自检到 0 error，再运行：")
    print(f"  python3 {os.path.join(SCRIPT_DIR, 'run_pipeline.py')} finish {inp}")
    print("（骨架未填完，validate 报 ERROR 是预期现象，不必惊慌。）")

def cleanup_intermediates(od, inp):
    """删除本次任务产生的中间产物（精确路径，不做 glob 通配，绝不碰历史文件/交付物）。

    只删脚本自己生成过的路径：
      <输入名>.wav、<输入名>.wav.chunks/、transcript_calibrated.txt.calib_cache/、
      report.json、TASK.md、analysis.json
    不存在的路径静默跳过。返回实际删除的路径列表。
    """
    base = os.path.splitext(os.path.basename(inp))[0]
    wav = os.path.join(od, base + ".wav")
    candidates = [
        wav,
        wav + ".chunks",
        os.path.join(od, "transcript.txt"),
        os.path.join(od, "transcript_calibrated.txt.calib_cache"),
        os.path.join(od, "report.json"),
        os.path.join(od, "calibration_report.json"),
        os.path.join(od, "TASK.md"),
        os.path.join(od, "analysis.json"),
    ]
    removed = []
    for t in candidates:
        try:
            if os.path.isdir(t):
                shutil.rmtree(t)
                removed.append(os.path.basename(t.rstrip("/")) + "/")
            elif os.path.isfile(t):
                os.remove(t)
                removed.append(os.path.basename(t))
        except FileNotFoundError:
            pass
    return removed

def cmd_finish(args):
    inp = ensure_input(args.inp)
    od = out_dir_for(inp, args.out)
    tx = os.path.join(od, "transcript.txt")
    # 兜底：transcript.txt 可能已被上次 finish 清理，改用校正稿（含已重命名的 *_校正稿.txt）
    if not os.path.isfile(tx):
        import glob as _g
        _cands = [os.path.join(od, "transcript_calibrated.txt")] + \
                 sorted(_g.glob(os.path.join(od, "*_校正稿.txt")))
        tx = next((c for c in _cands if os.path.isfile(c)), tx)
    ap = os.path.join(od, "analysis.json")
    example = os.path.join(SCRIPT_DIR, "..", "examples", "analysis.example.json")

    if not nonempty(ap):
        print(f"ERROR: 找不到 {ap}。请先跑 prepare 生成骨架并填好。", file=sys.stderr); sys.exit(1)

    # 网络校准：核实 entities 官方写法。若模型已手写 footer.calibration 则保留原文（不覆盖），
    # 否则用核实结果自动回填；报告不存在时发起搜索，存在时直接复用（不再重复扣 API 次数）。
    print("== 网络校准 ==")
    rc = run([sys.executable, os.path.join(SCRIPT_DIR, "network_calibrate.py"), ap,
              "--out", od, "--append", "--reuse"], cwd=od)
    if rc != 0:
        print("WARN: 网络校准失败，继续渲染（footer.calibration 留空）", file=sys.stderr)

    # 终检：ERROR 拒绝渲染；WARN 仅提示、放行。
    # 数字溯源优先用校正稿（机器校正改过的数字在 raw 里查不到属正常）；
    # 渲染时摘要版仍内嵌原始稿作存证（见下方渲染部分）。
    tx_check = tx
    tx_calib = os.path.join(od, "transcript_calibrated.txt")
    if nonempty(tx_calib):
        tx_check = tx_calib
    vp = os.path.join(SCRIPT_DIR, "validate_analysis.py")
    rc = run([sys.executable, vp, ap, "--transcript", tx_check], cwd=od)
    if rc == 1:
        print("ERROR: analysis.json 存在 ERROR，不渲染。请按上方 ERROR 修正后重跑。", file=sys.stderr)
        sys.exit(1)
    if rc == 2:
        print("WARN: analysis.json 有 WARN（建议修），仍继续渲染。", file=sys.stderr)
    # 渲染两版
    print(f"== 渲染摘要版 ==")
    r1 = run([sys.executable, os.path.join(SCRIPT_DIR, "render_html.py"), ap, tx, "--theme", args.theme], cwd=od)
    print(f"== 渲染阅读版（校正稿）==")
    r2 = run([sys.executable, os.path.join(SCRIPT_DIR, "read_render.py"), tx, ap, "--theme", args.theme, "--calibrated"], cwd=od)
    if r1 != 0 or r2 != 0:
        print("ERROR: 渲染失败，已中止（不清理中间产物，便于排查后重跑 finish）。", file=sys.stderr)
        sys.exit(1)

    # 按 title 重命名校正稿（交付时文件名与 HTML 一致）
    with open(ap, encoding="utf-8") as f:
        title = json.load(f).get("title", "").strip()
    if title:
        safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        new_calib = os.path.join(od, f"{safe}_校正稿.txt")
        if os.path.isfile(tx_calib):
            os.rename(tx_calib, new_calib)
            print(f"→ 校正稿已重命名: {os.path.basename(new_calib)}")
            # 校正稿头部的「原始存证见 transcript.txt」在下方清理后会变成死引用，改写为最终说明
            try:
                with open(new_calib, encoding="utf-8") as f:
                    lines = f.read().splitlines(keepends=True)
                for i, ln in enumerate(lines[:5]):
                    if ln.startswith("# 原始存证见"):
                        lines[i] = "# 原始 ASR 逐字稿已随中间产物清理；本文件为校正后的唯一存证。\n"
                        break
                with open(new_calib, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            except OSError:
                pass

    # 默认自动清理本次中间产物；--keep-cache 时保留（断点重跑 prepare 可命中缓存）
    if args.keep_cache:
        print("→ --keep-cache：保留中间产物（wav/chunks/校正缓存/report/TASK.md）")
    else:
        removed = cleanup_intermediates(od, inp)
        if removed:
            print("→ 已自动清理中间产物：" + "、".join(removed))
        else:
            print("→ 无中间产物需清理（已全部完成或此前已清理）")

    # 规则：所有交付物复制一份到系统 Download 目录（/storage/emulated/0/Download），
    # 便于用户在系统文件管理器/分享入口直接找到。失败仅警告，不影响主流程。
    DOWNLOAD_DIR = "/storage/emulated/0/Download"
    if title:
        safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        copied = []
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            for f in sorted(os.listdir(od)):
                if f.startswith(safe + "_") and (f.endswith(".html") or f.endswith(".txt")):
                    src_f = os.path.join(od, f)
                    dst_f = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.abspath(src_f) != os.path.abspath(dst_f):
                        shutil.copy2(src_f, dst_f)
                        copied.append(f)
        except OSError as e:
            print(f"WARN: 复制到 Download 目录失败（不影响交付）: {e}", file=sys.stderr)
        if copied:
            print(f"→ 已复制 {len(copied)} 件交付物到 {DOWNLOAD_DIR}：" + "、".join(copied))

    print(f"\n== 交付物位于 {od} ==")
    for f in sorted(os.listdir(od)):
        if f.endswith(".html"):
            print(f"  {os.path.join(od, f)}")
        elif f.endswith(".txt"):
            print(f"  {os.path.join(od, f)}")

def main():
    p = argparse.ArgumentParser(description="video-html-extractor 单命令编排器")
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("prepare", help="提取+转写+校正+生成任务单与骨架")
    pa.add_argument("inp")
    pa.add_argument("--out", default="")
    pa.add_argument("--workers", type=int, default=3)
    pa.add_argument("--no-draft", action="store_true",
                    help="跳过 GLM 起草 analysis.json（主模型从骨架手填，慢但完全自控）")
    pa.set_defaults(fn=cmd_prepare)
    pc = sub.add_parser("calibrate", help="Tavily 批量核实 analysis.json 的 entities 并回填 footer.calibration")
    pc.add_argument("inp")
    pc.add_argument("--out", default="")
    pc.add_argument("--batch", type=int, default=3, help="每组实体数（默认 3）")
    pc.set_defaults(fn=cmd_calibrate)
    pf = sub.add_parser("finish", help="校验+渲染两版+默认清理中间产物")
    pf.add_argument("inp")
    pf.add_argument("--out", default="")
    pf.add_argument("--theme", choices=["light", "dark"], default="dark",
                    help="默认 dark（DESIGN-SPEC 深色主题）")
    pf.add_argument("--keep-cache", action="store_true",
                    help="保留中间产物（wav/chunks/校正缓存/report/TASK.md），默认 finish 后自动清理")
    pf.set_defaults(fn=cmd_finish)
    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()