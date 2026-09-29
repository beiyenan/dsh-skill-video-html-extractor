#!/usr/bin/env python3
"""render_html.py — 把 analysis.json + transcript.txt 渲染为单文件、无外部依赖的可视化 HTML。

用法:
  python3 render_html.py <analysis.json> <transcript.txt> [输出.html] [--clean]
  若不指定输出，则根据 analysis.json 的 title 自动生成文件名（同目录）

  --clean  交付模式（默认建议）：不内嵌「完整逐字稿（可搜索）」附录、时间线、
           时间戳锚点与「N 段转写」meta；正文 [mm:ss] 标记直接去掉。
           逐字稿存证由随附的 transcript.txt 承担。需要旧版内嵌附录时去掉该开关即可。

analysis.json 结构（第4步由 LLM 写入）:
  {
    "title": str,            # 用于产物命名
    "summary": str,
    "tone": str,             # 教程/访谈/演讲/新闻...
    "sections": [ { "heading": str, "content": [str], "key_points": [str] } ],
    "key_takeaways": [ str ],   # 带 [mm:ss] 时间戳
    "entities": [str],
    "timeline": [ {"time": "mm:ss", "event": str} ]   # 可选
  }
"""
import json, os, re, sys, html, datetime

GENERIC_WORDS = r'(?:转写|文案|视频|音频|文件|整理|内容|transcript|text|output|untitled|未命名)'
GENERIC_TITLES = re.compile(
    rf'^{GENERIC_WORDS}(?:[\s\-_，,]*{GENERIC_WORDS})*[\s\-_0-9:：]*$',
    re.I)

def check_title(title):
    """标题必须反映文案内容：非空、非泛词、≤40 字，否则拒绝渲染。
    这是「按内容命名」的硬保证——防止产出 transcript.html 这类无意义文件名。"""
    t = (title or '').strip()
    if not t:
        sys.exit("ERROR: analysis.json 缺少 title。标题必须概括文案主题（写 analysis 时根据转写内容拟定），不允许泛称。")
    if GENERIC_TITLES.match(t):
        sys.exit(f"ERROR: 标题「{t}」是泛称，没有反映文案内容。请改为具体主题（如「耶鲁死亡课：直面死亡才能活明白」）。")
    if len(t) > 40:
        print(f"WARN: 标题超过 40 字（{len(t)}），文件名将被截断，建议在 analysis.json 里精简。", file=sys.stderr)

def slugify_title(title, fallback='transcript', stamped=False):
    s = html.unescape(title).strip()
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s[:40] or fallback
    if stamped:
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
        s = f"{stamp}-{s}"
    return s

def esc(x):
    return html.escape(str(x or ''), quote=True)

def ts_links(text):
    """把 [mm:ss] / [hh:mm:ss] 时间戳变成锚点，指向逐字稿对应行。"""
    def repl(m):
        ts = m.group(1)
        anchor = 'ts-' + ts.replace(':', '_')
        return f'<a class="ts" href="#{anchor}" data-ts="{ts}">[{ts}]</a>'
    return re.sub(r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]', repl, text)

def ts_strip(text):
    """clean 模式：直接删掉 [mm:ss] 标记（含其后的空格），不生成锚点。"""
    return re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]\s?', '', text)

CSS = """
:root{
  --bg:#fafaf8; --card:#fff; --ink:#1a1a1a; --muted:#6b6b6b;
  --accent:#0a7d5c; --accent-soft:#e7f5ef; --line:#e4e2dd;
  --chip:#f0efe9; --hl:#fff3bf;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 80px}
header.hero{background:linear-gradient(135deg,#0a7d5c 0%,#12a37c 100%);color:#fff;
  border-radius:16px;padding:36px 34px;margin-bottom:28px}
header.hero h1{margin:0 0 10px;font-size:28px;line-height:1.35;font-weight:700}
header.hero .summary{font-size:16px;opacity:.92;margin:0}
.meta-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.meta{background:rgba(255,255,255,.16);border-radius:999px;padding:4px 12px;font-size:13px}
.section{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:24px 26px;margin-bottom:18px}
.section h2{margin:0 0 14px;font-size:20px;color:var(--accent);
  padding-bottom:10px;border-bottom:1px solid var(--line)}
.takeaways{background:var(--accent-soft);border-color:var(--accent)}
.takeaways h2{color:var(--accent);border-color:transparent}
.takeaways ol{margin:0;padding-left:22px}
.takeaways li{margin:8px 0}
.points{list-style:none;padding:0;margin:14px 0 0}
.points li{position:relative;padding:4px 0 4px 26px;margin:4px 0;color:#333}
.points li::before{content:"▸";position:absolute;left:6px;color:var(--accent)}
.content-block p{margin:10px 0}
.entities{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;
  padding:3px 12px;font-size:14px;color:#444}
.timeline{list-style:none;margin:0;padding:0;position:relative}
.timeline::before{content:"";position:absolute;left:8px;top:6px;bottom:6px;width:2px;background:var(--line)}
.timeline li{position:relative;padding:6px 0 6px 28px;margin:0}
.timeline li::before{content:"";position:absolute;left:3px;top:12px;width:12px;height:12px;
  border-radius:50%;background:var(--accent);border:3px solid var(--accent-soft)}
.timeline .t{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--accent);
  display:inline-block;min-width:56px}
details.transcript{margin-top:24px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:0}
details.transcript summary{cursor:pointer;padding:18px 24px;font-weight:600;list-style:none;
  display:flex;justify-content:space-between;align-items:center}
details.transcript summary::after{content:"▾";color:var(--muted)}
details.transcript[open] summary::after{content:"▴"}
.transcript-body{padding:0 24px 20px;border-top:1px solid var(--line)}
.searchbox{margin:14px 0}
.searchbox input{width:100%;padding:10px 14px;border:1px solid var(--line);border-radius:10px;
  font-size:15px;background:#fff}
.line{padding:6px 8px;border-radius:8px;font-size:15px}
.line .ts{color:var(--accent);font-family:ui-monospace,Menlo,monospace;font-size:13px;
  text-decoration:none;margin-right:6px}
.line .ts:hover{background:var(--accent-soft);border-radius:4px}
.line .txt{color:#222}
.line .txt mark,.line mark{background:var(--hl);border-radius:3px;padding:0 2px}
.line:hover{background:#f6f6f3}
footer{margin-top:36px;text-align:center;color:var(--muted);font-size:13px}
@media print{
  body{background:#fff}
  .searchbox,header.hero .meta-row a{display:none}
  details.transcript{border:none}
  details.transcript summary{cursor:default}
}
"""

JS = r"""
(function(){
  var box=document.querySelector('.searchbox input');
  var lines=document.querySelectorAll('.line');
  if(!box)return;
  box.addEventListener('input',function(){
    var q=this.value.trim().toLowerCase();
    lines.forEach(function(el){
      var txt=el.querySelector('.txt');
      var m=el.dataset.raw;
      if(!q){ txt.innerHTML=m; el.style.display=''; return; }
      var hay=m.toLowerCase();
      if(hay.indexOf(q)<0){ el.style.display='none'; return; }
      el.style.display='';
      var re=new RegExp('('+q.replace(/[.*+?^${}()|[\]/\\]/g,'\\$&')+')','gi');
      txt.innerHTML=m.replace(re,'<mark>$1</mark>');
    });
  });
})();
"""

def build(analysis, transcript_text, out_path, clean=False):
    title = analysis.get('title') or 'transcript'
    summary = analysis.get('summary', '')
    tone = analysis.get('tone', '')
    sections = analysis.get('sections', [])
    takeaways = analysis.get('key_takeaways', [])
    entities = analysis.get('entities', [])
    timeline = analysis.get('timeline', [])

    # clean 模式：正文/要点里的 [mm:ss] 直接删除而非转锚点；不输出时间线、
    # 逐字稿附录、逐字稿搜索 JS；保留类型 meta。
    tx = ts_strip if clean else ts_links

    # 解析 transcript 行 -> [mm:ss] text
    tlines = []
    for ln in transcript_text.splitlines():
        m = re.match(r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$', ln)
        if m:
            tlines.append((m.group(1), m.group(2)))

    def section_html(sec):
        h = []
        h.append(f'<h2>{esc(sec.get("heading",""))}</h2>')
        content = sec.get('content') or []
        if content:
            h.append('<div class="content-block">')
            for c in content:
                h.append(f'<p>{tx(esc(c))}</p>')
            h.append('</div>')
        kp = sec.get('key_points') or []
        if kp:
            h.append('<ul class="points">')
            for p in kp:
                h.append(f'<li>{tx(esc(p))}</li>')
            h.append('</ul>')
        return f'<section class="section">{"".join(h)}</section>'

    parts = []
    parts.append(f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    parts.append(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append(f'<title>{esc(title)}</title>')
    parts.append(f'<style>{CSS}</style></head><body><div class="wrap">')

    # hero
    parts.append('<header class="hero">')
    parts.append(f'<h1>{esc(title)}</h1>')
    if summary:
        parts.append(f'<p class="summary">{esc(summary)}</p>')
    parts.append('<div class="meta-row">')
    if tone:
        parts.append(f'<span class="meta">类型：{esc(tone)}</span>')
    if tlines and not clean:
        parts.append(f'<span class="meta">{len(tlines)} 段转写 · 至 {esc(tlines[-1][0])}</span>')
    parts.append(f'<span class="meta">生成于 {esc(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))}</span>')
    parts.append('</div></header>')

    # 核心要点
    if takeaways:
        parts.append('<section class="section takeaways">')
        parts.append('<h2>核心要点</h2><ol>')
        for t in takeaways:
            parts.append(f'<li>{tx(esc(t))}</li>')
        parts.append('</ol></section>')

    # 实体
    if entities:
        parts.append('<section class="section">')
        parts.append('<h2>涉及对象</h2><div class="entities">')
        for e in entities:
            parts.append(f'<span class="chip">{esc(e)}</span>')
        parts.append('</div></section>')

    # 主题分节
    for sec in sections:
        parts.append(section_html(sec))

    # 时间轴（clean 模式整体略过）
    if timeline and not clean:
        parts.append('<section class="section">')
        parts.append('<h2>时间线</h2><ol class="timeline">')
        for t in timeline:
            tt = t.get('time',''); ev = t.get('event','')
            anchor = 'ts-' + tt.replace(':','_')
            parts.append(f'<li><a class="t" href="#{anchor}">{esc(tt)}</a> {esc(ev)}</li>')
        parts.append('</ol></section>')

    # 逐字稿（clean 模式略过）
    if not clean:
        parts.append('<details class="transcript" open>')
        parts.append('<summary>完整逐字稿（可搜索）</summary><div class="transcript-body">')
        parts.append('<div class="searchbox"><input type="search" placeholder="在逐字稿中搜索…" aria-label="搜索"></div>')
        for ts, txt in tlines:
            anchor = 'ts-' + ts.replace(':','_')
            raw = txt
            parts.append(
                f'<div class="line" data-raw="{esc(raw)}" id="{anchor}">'
                f'<a class="ts" href="#{anchor}">[{esc(ts)}]</a>'
                f'<span class="txt">{esc(txt)}</span></div>'
            )
        parts.append('</div></details>')

    parts.append(f'<footer>由 video-html-extractor skill 生成 · 忠实于原转写内容</footer>')
    if clean:
        parts.append('</div></body></html>')
    else:
        parts.append(f'</div><script>{JS}</script></body></html>')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    print(f"OK: 生成 {out_path}")

def main():
    if len(sys.argv) < 3:
        print("用法: render_html.py <analysis.json> <transcript.txt> [输出.html] [--clean] [--stamp]", file=sys.stderr)
        sys.exit(1)
    clean = '--clean' in sys.argv[1:]
    stamped = '--stamp' in sys.argv[1:]
    posargs = [a for a in sys.argv[1:] if not a.startswith('--')]
    aj, txt = posargs[0], posargs[1]
    analysis = json.load(open(aj, encoding='utf-8'))
    transcript_text = open(txt, encoding='utf-8').read()
    # 标题必须来源于文案内容：缺失/泛词直接拒绝（产物文件名与 <h1> 都用它）
    check_title(analysis.get('title', ''))
    if len(posargs) >= 3:
        out = posargs[2]
    else:
        out = os.path.join(os.path.dirname(os.path.abspath(aj)),
                           slugify_title(analysis.get('title',''), stamped=stamped) + '.html')
    build(analysis, transcript_text, out, clean=clean)

if __name__ == '__main__':
    main()
