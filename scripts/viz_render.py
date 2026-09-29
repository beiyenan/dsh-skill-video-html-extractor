#!/usr/bin/env python3
"""viz_render.py — 文案（已转写/已校准）→ 数据看板风格单文件 HTML（亮/暗双主题）。
默认 --theme=light；原暗色风格用 --theme=dark，一次出两版用 --theme=both。

按《文案转可视化HTML_skill方案.md》第 6/7 节实现：
  · 单文件 HTML，UTF-8；样式全内联 <style>，图形仅 CSS / 内联 SVG
  · 禁止任何外部 http(s) 资源（JS/CSS/字体/CDN）；本页不含任何 JS
  · 深色底 + 金(--acc)/蓝(--acc2) 强调；≤760px 自动降单列
  · 数字/事实全部来自传入的 dashboard.json，脚本不做任何推算或补全

用法:
  python3 viz_render.py <dashboard.json> [输出.html] [transcript.txt] [--theme=light|dark|both] [--clean]

  --clean  交付模式（默认建议）：不内嵌 ASR 原始逐字稿附录，正文里 [mm:ss] 分钟标记也一并去掉；
           逐字稿存证由随附的 transcript.txt 承担。需要内嵌附录/溯源徽章时去掉该开关即可。

dashboard.json 结构（字段全部可选，缺省即不渲染该模块）:
{
  "title": str, "subtitle": str, "tags": [str],
  "metrics":  [{"k":str,"unit":str,"label":str,"tone":"acc|red|green|blue|purple","note":str}],
  "chain":    [{"t":str,"d":str}],                      # 横向叙事逻辑链
  "events":   [{"h":str,"who":str,"d":str,"tag":str,"tone":"red|acc"}],
  "timeline": [{"time":str,"h":str,"d":str,"tag":str}],
  "tables":   [{"heading":str,"cols":[str],"rows":[[str]],"note":str}],
  "points":   [{"n":str,"h":str,"d":str}],               # 编号观点卡片
  "list":     {"heading":str,"d":str,"items":[str],"missing":str,"tone":"red|acc"},
  "framework":{"heading":str,"cols":[{"h":str,"d":str,"points":[str]}]},
  "sections": [{"heading":str,"paras":[str]}],           # 需要成段论述时（可选）
  "entities": [str],
  "conclusion":{"heading":str,"lines":[str],"quote":str,"quote_by":str},
  "footer":   {"source":str,"calibration":[str],"extra":str}
}
"""
import json, os, re, sys, html, datetime

TONE_VAR = {"acc": "--acc", "red": "--red", "green": "--green",
            "blue": "--acc2", "purple": "--purple"}

THEMES = {
"dark": """:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2330;--line:#2a3140;
--txt:#e6edf3;--sub:#9aa7b6;--acc:#f5b942;--acc2:#4ea1ff;
--red:#ff6b6b;--green:#3fb950;--purple:#bc8cff;--glow:#1b2436;
--shadow1:rgba(255,255,255,.03);--shadow2:rgba(0,0,0,.28);
--red-line:#4a2a2e;--acc-line:#4a3c22;--purple-line:#3b2f52;--blue-line:#243b55;
--hover:rgba(245,185,66,.045);--miss-bg:rgba(255,107,107,.08);--miss-line:#4a2a2e;--miss-txt:#ffb3b3;
--concl-bg:linear-gradient(135deg,rgba(245,185,66,.16),rgba(78,161,255,.14));--concl-line:#4a3c22;--concl-txt:#dbe4ee;
--no-grad2:#ffd479;--no-txt:#0d1117;--tp-line:#212836;--ts-bg:rgba(245,185,66,.1);--ts-line:#3b3a2a;--prose:#cdd6e0;}
""",
"light": """:root{--bg:#f6f7fb;--panel:#ffffff;--panel2:#eef1f7;--line:#dfe4ee;
--txt:#1c2333;--sub:#5b6577;--acc:#a8720a;--acc2:#2f6fed;
--red:#d64550;--green:#1f9d55;--purple:#7c3aed;--glow:#e8eefb;
--shadow1:rgba(15,23,42,.02);--shadow2:rgba(15,23,42,.07);
--red-line:#f2c7cb;--acc-line:#e8d29a;--purple-line:#d9c6f5;--blue-line:#c3d6f7;
--hover:rgba(47,111,237,.05);--miss-bg:#fdf1f2;--miss-line:#f2c7cb;--miss-txt:#a83240;
--concl-bg:linear-gradient(135deg,rgba(168,114,10,.10),rgba(47,111,237,.10));--concl-line:#e8d29a;--concl-txt:#33415c;
--no-grad2:#ffd479;--no-txt:#1c2333;--tp-line:#e7ebf2;--ts-bg:#fbf3dd;--ts-line:#e8d29a;--prose:#33415c;}
"""
}

BASE = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1200px 600px at 80% -10%,var(--glow) 0%,var(--bg) 55%) fixed;
color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",
"Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;line-height:1.75;
padding:40px 20px 80px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto}
a{color:var(--acc2);text-decoration:none}

/* ---------- header ---------- */
header{text-align:center;margin-bottom:38px}
header h1{font-size:32px;font-weight:800;line-height:1.4;
background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;
background-clip:text;color:transparent}
header .sub{color:var(--sub);margin:14px auto 0;max-width:760px;font-size:15.5px}
.tags{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
.tag{background:var(--panel2);border:1px solid var(--line);color:var(--acc);
	font-size:12px;padding:4px 12px;border-radius:999px;white-space:nowrap}
.tag.b{color:var(--acc2)} .tag.p{color:var(--purple)}

/* ---------- section shell ---------- */
section{margin:32px 0}
.sec-title{font-size:13px;letter-spacing:2px;color:var(--acc);text-transform:uppercase;
margin-bottom:14px;display:flex;align-items:center;gap:10px;font-weight:700}
.sec-title::before{content:"";width:6px;height:18px;
background:linear-gradient(var(--acc),var(--acc2));border-radius:3px;flex:none}
.sec-title .n{color:var(--sub);font-weight:600;letter-spacing:0;text-transform:none}
.grid{display:grid;gap:14px}
.g5{grid-template-columns:repeat(5,1fr)} .g4{grid-template-columns:repeat(4,1fr)}
.g3{grid-template-columns:repeat(3,1fr)} .g2{grid-template-columns:repeat(2,1fr)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;
box-shadow:0 1px 0 var(--shadow1),0 8px 24px var(--shadow2)}

/* ---------- metrics ---------- */
.metric .k{font-size:27px;font-weight:800;color:var(--acc);letter-spacing:-.5px;line-height:1.2}
.metric .k small{font-size:13px;color:var(--sub);font-weight:600;margin-left:2px}
.metric .l{color:var(--sub);font-size:12.5px;margin-top:8px;line-height:1.6}
.metric .note{color:var(--sub);font-size:11.5px;margin-top:6px;opacity:.75}
.metric.red .k{color:var(--red)} .metric.green .k{color:var(--green)}
.metric.blue .k{color:var(--acc2)} .metric.purple .k{color:var(--purple)}
.metric.red{border-left:3px solid var(--red)}
.metric.green{border-left:3px solid var(--green)}
.metric.blue{border-left:3px solid var(--acc2)}
.metric.purple{border-left:3px solid var(--purple)}
.metric.acc{border-left:3px solid var(--acc)}

/* ---------- chain ---------- */
.chain{counter-reset:c}
.chain .step{position:relative;padding-top:44px}
.chain .step::before{counter-increment:c;content:counter(c,decimal-leading-zero);
position:absolute;top:14px;left:18px;font-size:22px;font-weight:800;
color:transparent;-webkit-text-stroke:1px var(--acc);letter-spacing:1px}
.chain .step::after{content:"";position:absolute;top:26px;left:60px;right:-7px;height:1px;
background:linear-gradient(90deg,var(--line),transparent)}
.chain .step:last-child::after{display:none}
.chain .step h4{font-size:14.5px;margin-bottom:6px;color:var(--txt)}
.chain .step p{font-size:13px;color:var(--sub);line-height:1.65}

/* ---------- events ---------- */
.event{border-left:3px solid var(--red)}
.event.acc{border-left-color:var(--acc)} .event.purple{border-left-color:var(--purple)}
.event .eh{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.event h4{font-size:15.5px}
.event .who{color:var(--acc2);font-size:12.5px;font-weight:700}
.event p{font-size:13.5px;color:var(--sub)}
.pill{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid var(--line);
color:var(--sub);background:var(--panel2);white-space:nowrap}
.pill.red{color:var(--red);border-color:var(--red-line)}
.pill.acc{color:var(--acc);border-color:var(--acc-line)}
.pill.purple{color:var(--purple);border-color:var(--purple-line)}
.pill.blue{color:var(--acc2);border-color:var(--blue-line)}

/* ---------- timeline ---------- */
.tl{list-style:none;position:relative;padding-left:24px}
.tl::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;
background:linear-gradient(var(--acc),var(--acc2));opacity:.45}
.tl li{position:relative;padding:10px 0 10px 6px}
.tl li::before{content:"";position:absolute;left:-24px;top:18px;width:12px;height:12px;
border-radius:50%;background:var(--bg);border:2px solid var(--acc)}
.tl .tm{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;
color:var(--acc);font-weight:700;margin-right:8px}
.tl h4{display:inline;font-size:15px}
.tl p{font-size:13.5px;color:var(--sub);margin-top:4px}

/* ---------- tables ---------- */
.tbl-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:660px;font-size:13.5px}
th{background:var(--panel2);color:var(--acc);text-align:left;padding:12px 14px;
font-weight:700;font-size:12.5px;letter-spacing:.5px;border-bottom:1px solid var(--line);
white-space:nowrap}
td{padding:13px 14px;border-bottom:1px solid var(--line);color:var(--sub);
vertical-align:top;line-height:1.65}
tr:last-child td{border-bottom:none}
td.lead{color:var(--txt);font-weight:700}
tbody tr:hover{background:var(--hover)}
.tbl-note{color:var(--sub);font-size:12px;margin-top:8px;opacity:.8}

/* ---------- numbered points ---------- */
.pt{display:flex;gap:14px;align-items:flex-start}
.pt .no{flex:none;width:34px;height:34px;border-radius:9px;display:flex;align-items:center;
justify-content:center;font-weight:800;font-size:14px;color:var(--no-txt);
background:linear-gradient(135deg,var(--acc),var(--no-grad2))}
.pt h4{font-size:15px;margin-bottom:5px}
.pt p{font-size:13.5px;color:var(--sub)}
.pt .ref{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--acc2)}

/* ---------- list (遗憾/清单) ---------- */
.listbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
.listbox.red{border-left:3px solid var(--red)} .listbox.acc{border-left:3px solid var(--acc)}
.listbox .lh{font-size:15.5px;font-weight:700;margin-bottom:6px}
.listbox .ld{font-size:13.5px;color:var(--sub);margin-bottom:12px}
ol.rank{list-style:none;counter-reset:r;display:grid;gap:8px}
ol.rank li{counter-increment:r;position:relative;padding-left:40px;font-size:14px}
ol.rank li::before{content:counter(r);position:absolute;left:0;top:2px;width:24px;height:24px;
border-radius:7px;background:var(--panel2);border:1px solid var(--line);color:var(--acc);
display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800}
.missing{margin-top:14px;padding:12px 14px;border-radius:10px;background:var(--miss-bg);
border:1px dashed var(--miss-line);color:var(--miss-txt);font-size:13.5px}

/* ---------- framework ---------- */
.fw{border-top:2px solid var(--acc)}
.fw h4{font-size:15.5px;color:var(--acc);margin-bottom:8px}
.fw p{font-size:13.5px;color:var(--sub);margin-bottom:10px}
.fw ul{list-style:none;display:grid;gap:6px}
.fw li{font-size:12.8px;color:var(--sub);padding-left:16px;position:relative;line-height:1.6}
.fw li::before{content:"▸";position:absolute;left:0;color:var(--acc2)}

/* ---------- prose sections ---------- */
.prose h3{font-size:16.5px;margin-bottom:10px;color:var(--acc)}
.prose p{font-size:14.5px;color:var(--prose);margin:9px 0}
.prose strong{color:var(--txt)}
.prose em{color:var(--acc);font-style:normal;font-weight:700}

/* ---------- entities ---------- */
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:var(--panel2);border:1px solid var(--line);color:var(--txt);
font-size:12.5px;padding:5px 13px;border-radius:999px}

/* ---------- conclusion ---------- */
.concl{background:var(--concl-bg);
border:1px solid var(--concl-line);border-radius:16px;padding:30px 28px;text-align:center}
.concl h3{font-size:20px;margin-bottom:14px;
background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;
background-clip:text;color:transparent}
.concl p{font-size:15px;color:var(--concl-txt);margin:8px auto;max-width:800px}
.concl .quote{margin-top:20px;padding-top:18px;border-top:1px solid rgba(245,185,66,.28);
font-size:16px;color:var(--acc);line-height:1.85}
.concl .by{font-size:12.5px;color:var(--sub);margin-top:8px}

/* ---------- transcript appendix ---------- */
details.tp{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:0;margin-top:26px}
details.tp summary{cursor:pointer;padding:16px 20px;font-size:14px;font-weight:700;
color:var(--sub);list-style:none;display:flex;justify-content:space-between;align-items:center}
details.tp summary::-webkit-details-marker{display:none}
details.tp summary::after{content:"▾";color:var(--acc)}
details.tp[open] summary::after{content:"▴"}
details.tp[open] summary{border-bottom:1px solid var(--line)}
.tp-body{padding:16px 20px;max-height:520px;overflow:auto}
.tp-line{font-size:13px;color:var(--sub);padding:8px 0;border-bottom:1px dashed var(--tp-line);line-height:1.85}
.tp-line:last-child{border-bottom:none}
.tp-line .ts{display:inline-block;font-family:ui-monospace,Menlo,monospace;font-size:11px;
color:var(--acc);background:var(--ts-bg);border:1px solid var(--ts-line);border-radius:5px;
padding:0 6px;margin-right:8px;vertical-align:1px}
.tp-tip{font-size:12px;color:var(--sub);opacity:.75;padding:0 20px 16px}

footer{color:var(--sub);font-size:12px;text-align:center;margin-top:44px;
border-top:1px solid var(--line);padding-top:20px;line-height:1.9}
footer .cal{text-align:left;max-width:820px;margin:14px auto 0;font-size:11.5px;opacity:.85}
footer .cal b{color:var(--acc);font-weight:700}

/* ---------- responsive ---------- */
@media(max-width:980px){.g5{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){
body{padding:24px 14px 60px}
header h1{font-size:24px}
.g5,.g4,.g3,.g2{grid-template-columns:1fr}
.chain .step::after{display:none}
.metric .k{font-size:24px}
}
"""


def esc(x):
    return html.escape(str(x if x is not None else ''), quote=True)


def rt(text):
    """行内富文本：**粗体** → <em>(金高亮)，`x` → <strong>，[mm:ss] → 溯源标记。"""
    s = esc(text)
    s = re.sub(r'\*\*(.+?)\*\*', r'<em>\1</em>', s)
    s = re.sub(r'`(.+?)`', r'<strong>\1</strong>', s)
    s = re.sub(r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]',
               r'<span class="pill acc">\1</span>', s)
    return s


def rt_clean(text):
    """clean 模式行内富文本：与 rt 相同，但 [mm:ss] 直接删除（不留标记）。"""
    s = esc(text)
    s = re.sub(r'\*\*(.+?)\*\*', r'<em>\1</em>', s)
    s = re.sub(r'`(.+?)`', r'<strong>\1</strong>', s)
    s = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]\s*', '', s)
    return s


def sec(title, n=None, inner=''):
    tag = f'<span class="n">{esc(n)}</span>' if n else ''
    return (f'<section><div class="sec-title">{esc(title)}{tag}</div>{inner}</section>')


def build(d, transcript_text='', theme='light', clean=False):
    P = []
    rt = rt_clean if clean else rt

    # ---- header ----
    tags = ''.join(f'<span class="tag">{esc(t)}</span>' for t in d.get('tags', []))
    P.append(f'<header><h1>{esc(d.get("title",""))}</h1>')
    if d.get('subtitle'):
        P.append(f'<p class="sub">{rt(d["subtitle"])}</p>')
    if tags:
        P.append(f'<div class="tags">{tags}</div>')
    P.append('</header>')

    # ---- metrics ----
    ms = d.get('metrics') or []
    if ms:
        cards = []
        for m in ms:
            tone = m.get('tone', 'acc')
            unit = f'<small>{esc(m["unit"])}</small>' if m.get('unit') else ''
            note = f'<div class="note">{rt(m["note"])}</div>' if m.get('note') else ''
            cards.append(f'<div class="card metric {tone}"><div class="k">'
                         f'{esc(m.get("k",""))}{unit}</div>'
                         f'<div class="l">{rt(m.get("label",""))}</div>{note}</div>')
        cls = d.get('metrics_cols') or ('g5' if len(ms) in (5, 10) else
                                        ('g4' if len(ms) in (4, 8) else 'g3'))
        P.append(sec(d.get('metrics_heading', '核心数据看板'),
                     f'{len(ms)} 项', f'<div class="grid {cls}">{"".join(cards)}</div>'))

    # ---- chain ----
    ch = d.get('chain') or []
    if ch:
        steps = ''.join(f'<div class="card step"><h4>{esc(s.get("t",""))}</h4>'
                        f'<p>{rt(s.get("d",""))}</p></div>' for s in ch)
        cls = d.get('chain_cols') or ('g3' if len(ch) > 4 else
                                      ('g4' if len(ch) == 4 else f'g{max(len(ch), 1)}'))
        P.append(sec(d.get('chain_heading', '叙事逻辑链'),
                     f'{len(ch)} 步', f'<div class="grid chain {cls}">{steps}</div>'))

    # ---- events ----
    ev = d.get('events') or []
    if ev:
        cards = []
        for e in ev:
            who = f'<span class="who">{esc(e["who"])}</span>' if e.get('who') else ''
            pill = f'<span class="pill {e.get("tone","red")}">{esc(e["tag"])}</span>' if e.get('tag') else ''
            cards.append(f'<div class="card event {e.get("tone","red")}">'
                         f'<div class="eh"><h4>{esc(e.get("h",""))}</h4>{pill}</div>'
                         f'{who}<p>{rt(e.get("d",""))}</p></div>')
        P.append(sec(d.get('events_heading', '关键事件'),
                     f'{len(ev)} 项', f'<div class="grid g2">{"".join(cards)}</div>'))

    # ---- timeline ----
    tl = d.get('timeline') or []
    if tl:
        items = []
        for t in tl:
            pill = f' <span class="pill blue">{esc(t["tag"])}</span>' if t.get('tag') else ''
            p = f'<p>{rt(t["d"])}</p>' if t.get('d') else ''
            items.append(f'<li><span class="tm">{esc(t.get("time",""))}</span>'
                         f'<h4>{esc(t.get("h",""))}</h4>{pill}{p}</li>')
        P.append(sec(d.get('timeline_heading', '时间线 / 案例对照'), '',
                     f'<div class="card"><ul class="tl">{"".join(items)}</ul></div>'))

    # ---- tables ----
    for tb in d.get('tables') or []:
        cols = tb.get('cols') or []
        head = ''.join(f'<th>{esc(c)}</th>' for c in cols)
        rows = []
        for r in tb.get('rows') or []:
            tds = []
            for i, cell in enumerate(r):
                k = ' class="lead"' if i == 0 else ''
                tds.append(f'<td{k}>{rt(cell)}</td>')
            rows.append('<tr>' + ''.join(tds) + '</tr>')
        note = f'<div class="tbl-note">{rt(tb["note"])}</div>' if tb.get('note') else ''
        inner = (f'<div class="tbl-wrap"><table><thead><tr>{head}</tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>{note}')
        P.append(sec(tb.get('heading', '对照表'), '', inner))

    # ---- list (带"没有的东西") ----
    lb = d.get('list')
    if lb:
        items = ''.join(f'<li>{rt(x)}</li>' for x in lb.get('items', []))
        miss = (f'<div class="missing">{rt(lb["missing"])}</div>' if lb.get('missing') else '')
        lead = f'<div class="ld">{rt(lb["d"])}</div>' if lb.get('d') else ''
        P.append(sec(lb.get('heading', '清单'), '',
                     f'<div class="listbox {lb.get("tone","red")}">'
                     f'<div class="lh">{rt(lb.get("lh",""))}</div>{lead}'
                     f'<ol class="rank">{items}</ol>{miss}</div>'))

    # ---- points ----
    pts = d.get('points') or []
    if pts:
        cards = []
        for p in pts:
            cards.append(f'<div class="card pt"><div class="no">{esc(p.get("n",""))}</div>'
                         f'<div><h4>{rt(p.get("h",""))}</h4><p>{rt(p.get("d",""))}</p></div></div>')
        P.append(sec(d.get('points_heading', '核心观点'),
                     f'{len(pts)} 条', f'<div class="grid g2">{"".join(cards)}</div>'))

    # ---- framework ----
    fw = d.get('framework')
    if fw and fw.get('cols'):
        cards = []
        for c in fw['cols']:
            ul = ''.join(f'<li>{rt(x)}</li>' for x in c.get('points', []))
            d_ = f'<p>{rt(c["d"])}</p>' if c.get('d') else ''
            cards.append(f'<div class="card fw"><h4>{rt(c.get("h",""))}</h4>{d_}'
                         f'<ul>{ul}</ul></div>')
        P.append(sec(fw.get('heading', '应对框架'),
                     f'{len(fw["cols"])} 维', f'<div class="grid g4">{"".join(cards)}</div>'))

    # ---- prose sections ----
    for s in d.get('sections') or []:
        paras = ''.join(f'<p>{rt(x)}</p>' for x in s.get('paras', []))
        P.append(f'<section class="card prose"><h3>{esc(s.get("heading",""))}</h3>{paras}</section>')

    # ---- entities ----
    ent = d.get('entities') or []
    if ent:
        chips = ''.join(f'<span class="chip">{esc(x)}</span>' for x in ent)
        P.append(sec('涉及人物与文本', f'{len(ent)} 项', f'<div class="chips">{chips}</div>'))

    # ---- conclusion ----
    cc = d.get('conclusion')
    if cc:
        lines = ''.join(f'<p>{rt(x)}</p>' for x in cc.get('lines', []))
        q = f'<div class="quote">{rt(cc["quote"])}</div>' if cc.get('quote') else ''
        by = f'<div class="by">{rt(cc["quote_by"])}</div>' if cc.get('quote_by') else ''
        P.append(f'<section class="concl"><h3>{esc(cc.get("heading","结论"))}</h3>'
                 f'{lines}{q}{by}</section>')

    # ---- transcript appendix ----
    if not clean:
        tlines = []
        for ln in (transcript_text or '').splitlines():
            m = re.match(r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$', ln)
            if m:
                tlines.append((m.group(1), m.group(2)))
        if tlines:
            rows = ''.join(f'<div class="tp-line"><span class="ts">{esc(t)}</span>{esc(x)}</div>'
                           for t, x in tlines)
            P.append(f'<details class="tp"><summary>附：ASR 原始逐字稿（未经校正，供回溯核对）'
                     f'· {len(tlines)} 段</summary><div class="tp-body">{rows}</div></details>\n'
                     f'<div class="tp-tip">正文为校正+归拢后的表述；此处为逐字识别原文，'
                     f'含同音错字与段边界切断，以原视频为准。</div>')

    # ---- footer ----
    ft = d.get('footer') or {}
    src = f'数据来源：{esc(ft.get("source",""))}。' if ft.get('source') else ''
    cal = ''
    if ft.get('calibration'):
        lis = ''.join(f'<div>· {rt(x)}</div>' for x in ft['calibration'])
        cal = f'<div class="cal"><b>校准与存疑说明</b>{lis}</div>'
    extra = f' {rt(ft["extra"])}' if ft.get('extra') else ''
    if clean:
        extra = f' {rt("正文为校正后表述；ASR 原始逐字稿与时间戳未收入本页，如需回溯请保留随附的 transcript.txt。")}'
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    P.append(f'<footer>{src}本页为单文件离线页面，样式全内联，'
             f'无任何外部脚本/字体/CDN 请求。生成于 {stamp}。{extra}{cal}</footer>')

    title = esc(d.get('title', '可视化'))
    return ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{title}</title><style>{THEMES[theme]}{BASE}</style></head><body><div class="wrap">'
            + ''.join(P) + '</div></body></html>')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    clean = '--clean' in sys.argv[1:]
    stamped = '--stamp' in sys.argv[1:]
    theme = 'light'
    for a in sys.argv[1:]:
        if a.startswith('--theme='):
            theme = a.split('=', 1)[1]
    if theme == 'both':
        for t in ('light', 'dark'):
            main_one(args, t, clean=clean, stamped=stamped)
        return
    if theme not in THEMES:
        sys.exit(f'ERROR: 未知主题 {theme}，可选 light|dark|both')
    main_one(args, theme, clean=clean, stamped=stamped)


def main_one(args, theme, clean=False, stamped=False):
    if not args:
        sys.exit(__doc__)
    dj = args[0]
    d = json.load(open(dj, encoding='utf-8'))
    tpath = args[2] if len(args) > 2 else None
    if not tpath:
        cand = os.path.join(os.path.dirname(os.path.abspath(dj)), 'transcript.txt')
        tpath = cand if os.path.exists(cand) else None
    tt = open(tpath, encoding='utf-8').read() if tpath else ''
    # 关键修复：空串输出名（bash 里写 "" 会原样传进来）视为未指定 → 走自动命名。
    # 旧版对空串做 splitext 会产出名为 "_light" 的无扩展名文件（两次实测都踩过，手动 mv 补救）。
    out_spec = args[1] if len(args) > 1 and args[1] != '' else None
    slug = re.sub(r'[\\/:*?"<>|\s]+', '', d.get('title', 'dashboard'))[:32]
    if out_spec is not None:
        stem, ext = os.path.splitext(out_spec)
        out = f'{stem}_{theme}{ext}' if theme != 'single' else out_spec
    else:
        prefix = f'{datetime.datetime.now().strftime("%Y%m%d-%H%M")}-' if stamped else ''
        out = os.path.join(os.path.dirname(os.path.abspath(dj)),
                           f'{prefix}{slug}_visualization_{theme}.html')
    htmlout = build(d, tt, theme, clean=clean)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(htmlout)
    ext2 = re.findall(r'(?:src|href)\s*=\s*["\']https?://', htmlout)
    print(f'OK: {out}  ({len(htmlout.encode("utf-8"))} bytes, theme={theme})')
    print(f'CHECK: 外部资源引用 {len(ext2)} 处；<script> 标签 {htmlout.count("<script")} 个')


if __name__ == '__main__':
    main()
