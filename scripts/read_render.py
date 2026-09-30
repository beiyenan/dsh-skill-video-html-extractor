#!/usr/bin/env python3
"""read_render.py — transcript.txt → 单文件阅读版 HTML

逐字稿按段落分段排版，带时间戳导航，适合细读。
设计令牌系统：亮色默认，--theme=dark 切换暗色，全部走 CSS 变量。
零外部资源、单文件可直接双击打开。

用法:
  python3 read_render.py transcript.txt [analysis.json] [--theme=light|dark] [--title "标题"]

输出:
  文件名自动 = <标题>_阅读版.html
"""

import argparse, json, re, sys, html, os

def esc(s):
    return html.escape(str(s), quote=True)

def parse_transcript(text):
    """Parse transcript into paragraphs (no timestamps)."""
    lines = [l for l in text.strip().split("\n") if not l.startswith("#")]
    paragraphs = []
    for line in lines:
        m = re.match(r'^\[?(\d{2}:\d{2})\]?\s*(.*)', line)
        if m:
            text = m.group(2).strip()
        else:
            text = line.strip()
        # Split on sentence-ending punctuation
        sentences = re.split(r'(?<=[。？！])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        # Group into paragraphs: aim for ~50-150 chars per paragraph
        para = ""
        for sent in sentences:
            if len(para) + len(sent) > 150 and para:
                paragraphs.append(para)
                para = sent
            else:
                para += sent
        if para:
            paragraphs.append(para)
    return paragraphs

def format_paragraph(text):
    """Apply visual formatting to a paragraph: bold key quotes, stats, and highlights."""
    # 1. Bold direct quotes in 「」or "" (Chinese quotes)
    text = re.sub(r'「([^」]+)」', r'<strong>「\1」</strong>', text)
    
    # Chinese double quotes (U+201C and U+201D)
    def replace_chinese_quote(match):
        return '<strong>' + match.group(0) + '</strong>'
    text = re.sub(r'[\u201c][^\u201d]+[\u201d]', replace_chinese_quote, text)
    
    # Regular ASCII quotes
    text = re.sub(r'"([^"]+)"', r'<strong>"\1"</strong>', text)
    text = re.sub(r"'([^']+)'", r'<strong>''\1''</strong>', text)
    
    # 2. Bold numbers and statistics (e.g., 26讲, 6100万, 9倍, 33%, 140%)
    text = re.sub(r'(\d+\s*(?:个|讲|小时|万|亿|倍|%|美元|人|年|岁|次|天|月))', r'<strong>\1</strong>', text)
    
    # 3. Bold key transition/emphasis phrases
    emphasis_phrases = [
        r'(第一[句，]?)', r'(第二[句，]?)', r'(第三[句，]?)', r'(第四[句，]?)',
        r'(首先)', r'(其次)', r'(最后)', r'(总之)',
        r'(因此)', r'(所以)', r'(但是)', r'(然而)', r'(可是)',
        r'(这意味着)', r'(换句话说)',
    ]
    for phrase in emphasis_phrases:
        text = re.sub(phrase, r'<strong>\1</strong>', text)
    
    return text

def render_html(paragraphs, title, theme):
    parts = []
    # HTML head
    parts.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f'<title>{esc(title)}</title>')
    parts.append('<style>')

    # CSS
    css = """:root{--bg:#f5f7fc;--bg2:#ffffff;--card:#ffffff;--card2:#eef2fa;--line:#e2e8f4;--txt:#16203a;--muted:#55617a;--dim:#8b96ac;--accent:#2f6bff;--accent2:#0d9f7d;--warn:#d98400;--danger:#e11d48;--purple:#7c5cf0;--radius:16px;--shadow:0 1px 2px rgba(22,32,58,.04),0 10px 28px -14px rgba(22,32,58,.14);--fs-body:16px;--fs-title:44px;--fs-small:14px;--fs-toc:13px;--font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",Roboto,sans-serif}
[data-theme="dark"]{--bg:#0f1117;--bg2:#161a24;--card:#1c212e;--card2:#232937;--line:#2c3344;--txt:#e8ecf4;--muted:#9aa5b8;--dim:#6b7688;--accent:#5b8cff;--accent2:#22d3a6;--warn:#ffb020;--danger:#ff5c7a;--purple:#a78bfa;--shadow:0 1px 2px rgba(0,0,0,.2),0 10px 28px -14px rgba(0,0,0,.4)}
body{background:radial-gradient(1100px 600px at 12% -8%,rgba(47,107,255,.13),transparent 55%),radial-gradient(900px 500px at 100% 0%,rgba(13,159,125,.10),transparent 50%),var(--bg);color:var(--txt);transition:background .3s,color .3s}
[data-theme="dark"] body{background:radial-gradient(1100px 600px at 12% -8%,rgba(91,140,255,.10),transparent 55%),radial-gradient(900px 500px at 100% 0%,rgba(34,211,166,.08),transparent 50%),var(--bg)}
"""
    parts.append(css)
    parts.append("""
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font-family);line-height:1.85;-webkit-font-smoothing:antialiased}
.wrap{max-width:780px;margin:0 auto;padding:0 22px}
.hero{padding:60px 0 28px;text-align:center}
.hero .tagline{font-size:var(--fs-small);font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:14px}
.hero h1{font-size:clamp(28px,4.5vw,var(--fs-title));font-weight:800;line-height:1.25;margin-bottom:12px}
.hero .meta{font-size:var(--fs-small);color:var(--dim)}
.topbar{position:sticky;top:0;z-index:100;background:var(--bg2);border-bottom:1px solid var(--line);padding:8px 16px;display:flex;align-items:center;justify-content:flex-end;gap:8px;box-shadow:0 2px 8px rgba(0,0,0,.04);transition:background .3s,border-color .3s}
.ctrl-btn{width:32px;height:32px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--muted);display:grid;place-items:center;cursor:pointer;transition:.2s;font-size:13px;font-weight:700;line-height:1}
.ctrl-btn:hover{border-color:var(--accent);color:var(--accent);transform:scale(1.1)}
.ctrl-btn:disabled{opacity:.35;cursor:default;transform:none}
.ctrl-btn svg{width:15px;height:15px}
.fs-label{display:grid;place-items:center;font-size:10px;font-weight:800;letter-spacing:-.5px;min-width:28px;color:var(--muted)}
.font-select{position:relative}
.font-menu{display:none;position:absolute;top:38px;right:0;background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.1);z-index:200;min-width:80px;padding:4px}
.font-menu.show{display:block}
.font-menu button{display:block;width:100%;padding:6px 10px;border:none;background:none;color:var(--txt);font-size:12px;cursor:pointer;border-radius:4px;text-align:left}
.font-menu button:hover{background:var(--card2)}
.font-menu button.active{color:var(--accent);font-weight:700}
.content{padding:36px 0}
.para{margin-bottom:28px;font-size:var(--fs-body);line-height:1.85;color:var(--txt);text-align:justify;transition:font-size .2s}
.divider{width:40px;height:2px;background:var(--line);margin:0 auto 36px;border-radius:1px}
footer{padding:40px 0 48px;border-top:1px solid var(--line);color:var(--dim);font-size:var(--fs-small);text-align:center}
footer p{margin:4px 0}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--line);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--dim)}
@media(max-width:820px){.hero{padding:40px 0 20px}.hero h1{font-size:clamp(22px,7vw,32px)}.content{padding:24px 0}.topbar{padding:6px 10px}.ctrl-btn{width:28px;height:28px;font-size:12px}.fs-label{min-width:24px;font-size:9px}}
""")
    parts.append('</style></head><body>')

    # Topbar with controls
    parts.append('<div class="topbar">')
    parts.append('<button class="ctrl-btn" id="fsMinus" onclick="changeFont(-1)" title="减小字体">A-</button>')
    parts.append('<span class="fs-label" id="fsLabel">16</span>')
    parts.append('<button class="ctrl-btn" id="fsPlus" onclick="changeFont(1)" title="增大字体">A+</button>')
    parts.append('<div class="font-select">')
    parts.append('<button class="ctrl-btn" onclick="toggleFontMenu()" title="选择字体" id="fontBtn">宋</button>')
    parts.append('<div class="font-menu" id="fontMenu">')
    parts.append('<button onclick="setFontFamily(0)" id="fontOpt0">宋体</button>')
    parts.append('<button onclick="setFontFamily(1)" id="fontOpt1">黑体</button>')
    parts.append('<button onclick="setFontFamily(2)" id="fontOpt2">仿宋</button>')
    parts.append('<button onclick="setFontFamily(3)" id="fontOpt3">等线</button>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('<button class="ctrl-btn" onclick="toggleTheme()" title="切换亮/暗主题">')
    parts.append('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>')
    parts.append('</button>')
    parts.append('</div>')

    # Hero
    parts.append(f'<div class="hero"><div class="wrap"><span class="tagline">逐字稿 · 阅读版</span>')
    parts.append(f'<h1>{esc(title)}</h1>')
    parts.append(f'<p class="meta">共 {len(paragraphs)} 段</p>')
    parts.append('</div></div>')

    # Content - paragraphs with dividers every ~10 paragraphs
    parts.append('<div class="content"><div class="wrap">')
    for i, para in enumerate(paragraphs):
        if i > 0 and i % 10 == 0:
            parts.append('<div class="divider"></div>')
        parts.append(f'<p class="para">{esc(para)}</p>')
    parts.append('</div></div>')

    # Footer
    parts.append(f'<footer><div class="wrap"><p>由视频文案提取 skill 生成 · 所有文字来自原始转写</p>')
    parts.append(f'<p style="margin-top:8px">共 {len(paragraphs)} 段 · 单文件、无外部依赖</p>')
    parts.append('</div></footer>')

    # JS
    parts.append('<script>')
    parts.append('var FS=[14,16,18,20,22,25];')
    parts.append('var fsi=1;')
    parts.append('var FONTS=[')
    parts.append('  {n:"宋体",f:"SimSun,\\"Songti SC\\",serif",s:"宋"},')
    parts.append('  {n:"黑体",f:"SimHei,\\"Heiti SC\\",sans-serif",s:"黑"},')
    parts.append('  {n:"仿宋",f:"FangSong,\\\"FangSong_GB2312\\\",serif",s:"仿"},')
    parts.append('  {n:"等线",f:"DengXian,\\\"DengXian Light\\\",sans-serif",s:"等"}')
    parts.append('];')
    parts.append('var ffonti=0;')
    parts.append('function setFont(idx){')
    parts.append('  fsi=Math.max(0,Math.min(FS.length-1,idx));')
    parts.append('  var fs=FS[fsi];')
    parts.append('  document.documentElement.style.setProperty("--fs-body",fs+"px");')
    parts.append('  document.documentElement.style.setProperty("--fs-title",Math.round(fs*2.75)+"px");')
    parts.append('  document.documentElement.style.setProperty("--fs-small",Math.max(11,fs-2)+"px");')
    parts.append('  document.getElementById("fsLabel").textContent=fs;')
    parts.append('  document.getElementById("fsMinus").disabled=(fsi===0);')
    parts.append('  document.getElementById("fsPlus").disabled=(fsi===FS.length-1);')
    parts.append('  try{localStorage.setItem("fontSize",fs)}catch(e){}')
    parts.append('}')
    parts.append('function changeFont(dir){setFont(fsi+dir);}')
    parts.append('function setFontFamily(idx){')
    parts.append('  ffonti=Math.max(0,Math.min(FONTS.length-1,idx));')
    parts.append('  var ff=FONTS[ffonti];')
    parts.append('  document.documentElement.style.setProperty("--font-family",ff.f);')
    parts.append('  document.getElementById("fontBtn").textContent=ff.s;')
    parts.append('  for(var i=0;i<FONTS.length;i++){document.getElementById("fontOpt"+i).classList.toggle("active",i===ffonti);}')
    parts.append('  try{localStorage.setItem("fontFamily",ff.n)}catch(e){}')
    parts.append('  document.getElementById("fontMenu").classList.remove("show");')
    parts.append('}')
    parts.append('function toggleFontMenu(){document.getElementById("fontMenu").classList.toggle("show");}')
    parts.append('function toggleTheme(){')
    parts.append('  var html=document.documentElement;')
    parts.append('  var isDark=html.getAttribute("data-theme")==="dark";')
    parts.append('  html.setAttribute("data-theme",isDark?"":"dark");')
    parts.append('  try{localStorage.setItem("theme",isDark?"light":"dark")}catch(e){}')
    parts.append('}')
    parts.append('document.addEventListener("click",function(e){if(!e.target.closest(".font-select")){document.getElementById("fontMenu").classList.remove("show");}});')
    parts.append('try{')
    parts.append('  var t=localStorage.getItem("theme");')
    parts.append('  if(t==="dark")document.documentElement.setAttribute("data-theme","dark");')
    parts.append('  var fs=parseInt(localStorage.getItem("fontSize"));')
    parts.append('  if(!isNaN(fs)&&FS.indexOf(fs)>=0){setFont(FS.indexOf(fs));}')
    parts.append('  var fn=localStorage.getItem("fontFamily");')
    parts.append('  if(fn){for(var i=0;i<FONTS.length;i++){if(FONTS[i].n===fn){setFontFamily(i);break;}}}')
    parts.append('}catch(e){}')
    parts.append('</script>')
    parts.append('</body></html>')
    return "\n".join(parts)

def main():
    ap = argparse.ArgumentParser(description="transcript.txt → 单文件阅读版 HTML")
    ap.add_argument("transcript", help="transcript.txt 路径")
    ap.add_argument("analysis", nargs="?", default="", help="analysis.json 路径（取 title）")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--title", default="", help="手动指定标题")
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    if not os.path.isfile(args.transcript):
        print(f"ERROR: 找不到 {args.transcript}", file=sys.stderr)
        sys.exit(1)
    with open(args.transcript, "r", encoding="utf-8") as f:
        text = f.read()

    # Get title
    title = args.title
    if not title and args.analysis and os.path.isfile(args.analysis):
        with open(args.analysis, "r", encoding="utf-8") as f:
            data = json.load(f)
            title = data.get("title", "")
    if not title:
        title = "逐字稿"

    paragraphs = parse_transcript(text)
    if not paragraphs:
        print("ERROR: transcript 为空或格式不正确", file=sys.stderr)
        sys.exit(1)

    html_out = render_html(paragraphs, title, args.theme)
    out_path = args.output if args.output else f"{title}_阅读版.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    sz = os.path.getsize(out_path)
    print(f"OK: {out_path}  ({sz:,} bytes)")
    print(f"   {len(paragraphs)} paragraphs, theme={args.theme}")

if __name__ == "__main__":
    main()
