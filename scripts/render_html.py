#!/usr/bin/env python3
"""render_html.py — analysis.json → 单文件可视化 HTML（摘要版）

8 种视觉组件混合排版：
  数据卡组 / 时间线 / 对比卡 / 配对卡 / 架构图 / 流程图 / 金句卡 / 清单行
设计令牌系统：亮色默认，--theme=dark 切换暗色，全部走 CSS 变量。
零 JS、零外部资源、单文件可直接双击打开。

用法:
  python3 render_html.py analysis.json [transcript.txt] [--clean] [--theme=light|dark]

输出:
  文件名自动 = analysis.json 的 title 字段（校验泛词会拒绝渲染）。
  --clean 时不内嵌逐字稿、不输出时间戳。
"""

import argparse, json, re, sys, html, os

# ── 泛词校验 ──
BAN_WORDS = ["转写", "视频文案", "内容整理", "transcript", "未命名", "视频转写", "文本整理"]

def validate_title(title):
    t = title.strip().lower()
    for w in BAN_WORDS:
        if w.lower() in t:
            print(f"ERROR: 标题含泛词「{w}」，必须用具体主题。修改 analysis.json 的 title 字段。", file=sys.stderr)
            sys.exit(1)

# ── 设计令牌 ──
LIGHT_TOKENS = """:root{
  --bg:#f5f7fc;--bg2:#ffffff;--card:#ffffff;--card2:#eef2fa;
  --line:#e2e8f4;--txt:#16203a;--muted:#55617a;--dim:#8b96ac;
  --accent:#2f6bff;--accent2:#0d9f7d;--warn:#d98400;--danger:#e11d48;--purple:#7c5cf0;
  --radius:16px;--shadow:0 1px 2px rgba(22,32,58,.04),0 10px 28px -14px rgba(22,32,58,.14);
}"""

DARK_TOKENS = """:root{
  --bg:#0f1117;--bg2:#161a24;--card:#1c212e;--card2:#232937;
  --line:#2c3344;--txt:#e8ecf4;--muted:#9aa5b8;--dim:#6b7688;
  --accent:#5b8cff;--accent2:#22d3a6;--warn:#ffb020;--danger:#ff5c7a;--purple:#a78bfa;
  --radius:16px;--shadow:0 1px 2px rgba(0,0,0,.2),0 10px 28px -14px rgba(0,0,0,.4);
}"""

# ── CSS ──
ALL_CSS = """:root{--bg:#f5f7fc;--bg2:#ffffff;--card:#ffffff;--card2:#eef2fa;--line:#e2e8f4;--txt:#16203a;--muted:#55617a;--dim:#8b96ac;--accent:#2f6bff;--accent2:#0d9f7d;--warn:#d98400;--danger:#e11d48;--purple:#7c5cf0;--radius:16px;--shadow:0 1px 2px rgba(22,32,58,.04),0 10px 28px -14px rgba(22,32,58,.14);}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1100px 600px at 12% -8%,rgba(47,107,255,.13),transparent 55%),radial-gradient(900px 500px at 100% 0%,rgba(13,159,125,.10),transparent 50%),var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",Roboto,sans-serif;line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 22px}
section{padding:46px 0}
.hero{padding:64px 0 32px;text-align:center}
.hero .tagline{font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:16px}
.hero h1{font-size:clamp(30px,5.2vw,54px);font-weight:800;line-height:1.2;margin-bottom:16px}
.hero .sub{font-size:18px;color:var(--muted);max-width:700px;margin:0 auto 36px}
.hero .sub strong{color:var(--txt)}
.facts{display:flex;flex-wrap:wrap;justify-content:center;gap:20px}
.fact{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 32px;box-shadow:var(--shadow);min-width:140px;transition:.25s border-color,.25s transform;display:flex;flex-direction:column;align-items:center}
.fact:hover{border-color:var(--accent);transform:translateY(-2px)}
.fact .fact-ico{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;background:rgba(47,107,255,.1);color:var(--accent);margin-bottom:10px}
.fact.green .fact-ico{background:rgba(13,159,125,.1);color:var(--accent2)}
.fact.red .fact-ico{background:rgba(225,29,72,.1);color:var(--danger)}
.fact.warn .fact-ico{background:rgba(217,132,0,.1);color:var(--warn)}
.fact.purple .fact-ico{background:rgba(124,92,240,.1);color:var(--purple)}
.fact .fact-ico svg{width:16px;height:16px}
.fact b{display:block;font-size:32px;font-weight:800;color:var(--accent);line-height:1.1}
.fact.green b{color:var(--accent2)}.fact.red b{color:var(--danger)}.fact.warn b{color:var(--warn)}.fact.purple b{color:var(--purple)}
.fact span{display:block;font-size:13px;color:var(--dim);margin-top:6px;font-weight:600}
.sec-head{display:flex;align-items:center;gap:14px;margin-bottom:8px}
.sec-icon{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:rgba(47,107,255,.08);color:var(--accent);flex-shrink:0;border:1px solid rgba(47,107,255,.2)}
.sec-head h2{font-size:23px;font-weight:800}
.sec-desc{color:var(--dim);font-size:14px;margin:0 0 26px 48px}
.std-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px 26px;box-shadow:var(--shadow);margin-bottom:16px}
.std-card h4{font-size:16px;font-weight:700;margin-bottom:8px}
.std-card p{color:var(--muted);font-size:15px;margin-bottom:8px}
.std-card ul{list-style:none;padding-left:0}
.std-card li{padding:6px 0 6px 22px;position:relative;color:var(--muted);font-size:15px}
.std-card li::before{content:"";position:absolute;left:4px;top:15px;width:6px;height:6px;border-radius:50%;background:var(--accent)}
.timeline{position:relative;padding-left:34px}
.timeline::before{content:"";position:absolute;left:9px;top:8px;bottom:8px;width:2px;background:linear-gradient(180deg,var(--accent),var(--purple),var(--warn),var(--danger),var(--accent2));border-radius:2px;opacity:.55}
.tl-item{position:relative;margin-bottom:20px}
.tl-item::before{content:"";position:absolute;left:-31px;top:20px;width:12px;height:12px;border-radius:50%;background:var(--bg);border:3px solid var(--accent);box-shadow:0 0 0 4px rgba(47,107,255,.14)}
.tl-icon{position:absolute;left:-40px;top:14px;width:22px;height:22px;border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;z-index:2}
.tl-icon svg{width:12px;height:12px}
.tl-item.warn::before{border-color:var(--warn);box-shadow:0 0 0 4px rgba(217,132,0,.14)}.tl-item.warn .tl-icon{background:var(--warn)}
.tl-item.danger::before{border-color:var(--danger);box-shadow:0 0 0 4px rgba(225,29,72,.14)}.tl-item.danger .tl-icon{background:var(--danger)}
.tl-item.good::before{border-color:var(--accent2);box-shadow:0 0 0 4px rgba(13,159,125,.14)}.tl-item.good .tl-icon{background:var(--accent2)}
.tl-card{background:linear-gradient(180deg,var(--card),var(--bg2));border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;transition:.25s border-color,.25s transform;box-shadow:var(--shadow)}
.tl-card:hover{border-color:rgba(47,107,255,.35);transform:translateX(3px)}
.tl-year{font-size:12px;font-weight:800;letter-spacing:.1em;color:var(--accent);margin-bottom:4px}
.tl-item.warn .tl-year{color:var(--warn)}.tl-item.danger .tl-year{color:var(--danger)}.tl-item.good .tl-year{color:var(--accent2)}
.tl-card h3{font-size:16px;font-weight:700;margin-bottom:6px}
.tl-card p{color:var(--muted);font-size:14px}
.compare{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-top:16px}
.compare>div{padding:16px 18px}
.compare .old{background:rgba(225,29,72,.04)}.compare .new{background:rgba(13,159,125,.05);border-left:1px solid var(--line)}
.compare h5{font-size:13px;font-weight:800;margin-bottom:8px;letter-spacing:.05em;text-transform:uppercase}
.compare .old h5{color:var(--danger)}.compare .new h5{color:var(--accent2)}
.compare li{padding-left:18px;position:relative;list-style:none;font-size:14px;color:var(--muted);padding:4px 0 4px 18px}
.compare .old li::before{content:"";position:absolute;left:0}.compare .new li::before{content:"";position:absolute;left:0}
.compare .old li .ico-mark,.compare .new li .ico-mark{display:inline-block;margin-right:6px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px;box-shadow:var(--shadow)}
.label{font-size:11.5px;font-weight:800;letter-spacing:.12em;padding:4px 10px;border-radius:100px;display:inline-block;margin-bottom:12px}
.label.pain{background:rgba(225,29,72,.08);color:var(--danger);border:1px solid rgba(225,29,72,.25)}
.label.fix{background:rgba(13,159,125,.09);color:var(--accent2);border:1px solid rgba(13,159,125,.28)}
.card h4{font-size:16px;font-weight:700;margin-bottom:8px}
.card p{color:var(--muted);font-size:14px;margin-bottom:8px}
.card .quote{border-left:3px solid var(--accent);padding:6px 0 6px 14px;margin-top:14px;color:var(--muted);font-style:italic;font-size:14px}
.diagram{background:linear-gradient(180deg,var(--bg2),var(--card));border:1px solid var(--line);border-radius:22px;padding:34px 24px;box-shadow:var(--shadow)}
.diagram .you{text-align:center}
.diagram .you .pill{display:inline-block;padding:10px 26px;border-radius:100px;font-weight:800;background:rgba(47,107,255,.1);border:1px solid rgba(47,107,255,.4);color:var(--accent);font-size:15px}
.diagram .you small{display:block;color:var(--dim);font-size:12px;margin-top:4px}
.diagram .arrow-down{width:2px;height:26px;background:linear-gradient(var(--accent),var(--line));margin:8px auto}
.diagram .connector{height:2px;background:var(--line);margin:0 16.6%;position:relative}
.diagram .connector::before,.diagram .connector::after{content:"";position:absolute;top:0;width:2px;height:20px;background:var(--line)}
.diagram .connector::before{left:0}.diagram .connector::after{right:0}
.diagram .cols{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:20px}
.diagram .col{border-radius:14px;padding:18px;border:1px solid var(--line);background:var(--card);box-shadow:var(--shadow)}
.diagram .col.safe{border-top:3px solid var(--accent)}.diagram .col.show{border-top:3px solid var(--purple)}.diagram .col.biz{border-top:3px solid var(--accent2)}
.diagram .col .role{font-size:11.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.diagram .col .role svg{width:14px;height:14px}
.diagram .col.safe .role{color:var(--accent)}.diagram .col.show .role{color:var(--purple)}.diagram .col.biz .role{color:var(--accent2)}
.diagram .col h4{font-size:15px;font-weight:700;margin-bottom:8px}
.diagram .col ul{list-style:none;padding:0}
.diagram .col li{font-size:13px;color:var(--muted);padding:3px 0 3px 14px;position:relative}
.diagram .col li::before{content:"\\b7";position:absolute;left:2px;font-weight:700}
.diagram .col .nope{margin-top:12px;font-size:12.5px;color:var(--danger);border-top:1px dashed var(--line);padding-top:10px}
.diagram .bottomnote{margin-top:22px;background:rgba(13,159,125,.06);border:1px solid rgba(13,159,125,.24);border-radius:12px;padding:16px 18px;font-size:14px;color:var(--muted)}
.diagram .bottomnote b{color:var(--txt)}
.flow{display:flex;flex-wrap:wrap;align-items:center;gap:10px;justify-content:center}
.flow .node{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:130px;text-align:center;font-weight:600;box-shadow:var(--shadow);font-size:14px}
.flow .node small{display:block;color:var(--dim);font-weight:400;font-size:12px;margin-top:2px}
.flow .arr{color:var(--accent);font-size:20px;font-weight:800}
.flow .node.hl{background:rgba(47,107,255,.08);border-color:rgba(47,107,255,.4)}
.flow .node.hl2{background:rgba(13,159,125,.09);border-color:rgba(13,159,125,.4)}
.quotes{display:grid;gap:16px}
.qcard{background:linear-gradient(135deg,var(--card),var(--bg2));border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:12px;padding:20px 22px;box-shadow:var(--shadow)}
.qcard:nth-child(2){border-left-color:var(--accent2)}.qcard:nth-child(3){border-left-color:var(--warn)}.qcard:nth-child(4){border-left-color:var(--purple)}
.qcard p{font-size:16px;color:var(--txt);font-weight:600;line-height:1.6}
.qcard small{display:block;color:var(--dim);margin-top:8px;font-size:13px}
.takeaway{display:flex;gap:14px;padding:16px 0;border-bottom:1px dashed var(--line)}
.takeaway:last-child{border-bottom:none}
.takeaway .ico{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:rgba(47,107,255,.1);color:var(--accent);font-weight:800;font-size:14px;flex-shrink:0}
.takeaway .ico svg{width:18px;height:18px}
.takeaway .ico.green{background:rgba(13,159,125,.1);color:var(--accent2)}
.takeaway .ico.red{background:rgba(225,29,72,.1);color:var(--danger)}
.takeaway .ico.warn{background:rgba(217,132,0,.1);color:var(--warn)}
.takeaway .ico.purple{background:rgba(124,92,240,.1);color:var(--purple)}
.takeaway h4{font-size:15px;font-weight:700;margin-bottom:4px}
.takeaway p{color:var(--muted);font-size:14px}
.transcript-section{padding:46px 0}
.search-box{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.search-box input{flex:1;min-width:200px;padding:10px 16px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--txt);font-size:14px;outline:none}
.search-box input:focus{border-color:var(--accent)}
.search-box .match-info{font-size:13px;color:var(--dim);padding:10px 14px;white-space:nowrap}
.transcript-block{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;max-height:500px;overflow-y:auto;font-size:14px;line-height:1.8}
.transcript-block .line{padding:2px 0}
.transcript-block .line .ts{color:var(--accent);font-size:12px;font-weight:700;margin-right:8px}
.transcript-block mark{background:rgba(217,132,0,.2);border-radius:3px;padding:0 2px}
.transcript-block .no-match{color:var(--dim);text-align:center;padding:40px 0}
footer{padding:32px 0 48px;border-top:1px solid var(--line);color:var(--dim);font-size:13px;text-align:center}
footer p{margin:4px 0}
@media(max-width:820px){.grid2{grid-template-columns:1fr}.cols{grid-template-columns:1fr}.connector{display:none}.compare{grid-template-columns:1fr}.compare .new{border-left:none;border-top:1px solid var(--line)}.facts{gap:12px}.fact{padding:16px 22px;min-width:110px}.fact b{font-size:26px}.hero{padding:40px 0 24px}.hero h1{font-size:clamp(24px,7vw,36px)}.hero .sub{font-size:15px}.diagram{padding:24px 16px}.diagram .arrow-down{height:18px}section{padding:32px 0}.sec-desc{margin-left:0}}
"""

DARK_CSS_OVERRIDE = """
:root{--bg:#0f1117;--bg2:#161a24;--card:#1c212e;--card2:#232937;--line:#2c3344;--txt:#e8ecf4;--muted:#9aa5b8;--dim:#6b7688;--accent:#5b8cff;--accent2:#22d3a6;--warn:#ffb020;--danger:#ff5c7a;--purple:#a78bfa;--radius:16px;--shadow:0 1px 2px rgba(0,0,0,.2),0 10px 28px -14px rgba(0,0,0,.4);}
body{background:radial-gradient(1100px 600px at 12% -8%,rgba(91,140,255,.10),transparent 55%),radial-gradient(900px 500px at 100% 0%,rgba(34,211,166,.08),transparent 50%),var(--bg)}
"""

def esc(s):
    return html.escape(str(s), quote=True)

def tone_class(tone):
    m = {"acc": "", "green": " green", "red": " red", "warn": " warn", "purple": " purple"}
    return m.get(tone, "")

# ── 内联 SVG 图标（全部 currentColor 继承设计系统颜色）──
ICONS = {
    "rocket":   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>',
    "compass":  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>',
    "timeline": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "scale":    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18"/><path d="m3 9 3-6h12l3 6"/><path d="M3 9h18"/><path d="M6 9l-3 6a3 3 0 0 0 6 0L6 9z"/><path d="M18 9l-3 6a3 3 0 0 0 6 0l-3-6z"/></svg>',
    "grid2":    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>',
    "building": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>',
    "flow":     '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="6" r="3"/><circle cx="19" cy="18" r="3"/><path d="M5 9v3a4 4 0 0 0 4 4h6"/><path d="m18 12-3 3 3 3"/></svg>',
    "quote":    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1 1 1 0 0 0-1 1 1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1 1 1 0 0 0-1 1 1 1 0 0 1-1 1"/></svg>',
    "list":     '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>',
    "alert":    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    "check":    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>',
    "x":        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>',
    "shield":   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>',
    "eye":      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>',
    "briefcase":'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="7" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    "star":     '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    "check2":   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    "search":   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
    "footprint":'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5c0 2.12-.5 4-3 4"/><path d="M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 2.12.5 4 3 4"/><path d="M16 17h4"/><path d="M10 17H4"/><path d="M18 17v1a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-1"/><path d="M6 17v1a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-1"/></svg>',
    "flag":     '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/></svg>',
    "heart":    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>',
}

# 章节类型→图标映射
SEC_ICON = {
    "timeline": "timeline", "compare": "scale", "pair": "grid2",
    "architecture": "building", "flow": "flow", "quote": "quote",
    "list": "list", "default": "compass",
}

# 状态→图标映射
STATUS_ICON = {
    "default": "footprint", "good": "check2", "warn": "alert", "danger": "x",
}

# 架构列类型→图标映射
COL_ICON = {"safe": "shield", "show": "eye", "biz": "briefcase"}

def render_hero(data):
    parts = []
    tone = data.get("tone", "")
    if tone:
        parts.append(f'<div class="hero"><div class="wrap"><span class="tagline">{esc(tone)}</span>')
    title = data.get("title", "")
    parts.append(f"<h1>{esc(title)}</h1>")
    sub = data.get("summary", "")
    if sub:
        parts.append(f'<p class="sub">{esc(sub)}</p>')
    facts = data.get("hero_facts", [])
    if facts:
        fact_icons = ["rocket", "check", "flag", "heart"]
        parts.append('<div class="facts">')
        for i, f in enumerate(facts):
            tc = tone_class(f.get("tone", ""))
            ico_name = fact_icons[i % len(fact_icons)]
            parts.append(f'<div class="fact{tc}"><div class="fact-ico">{ICONS.get(ico_name,"")}</div><b>{esc(f.get("value",""))}</b><span>{esc(f.get("label",""))}</span></div>')
        parts.append('</div>')
    if tone:
        parts.append('</div></div>')
    return "\n".join(parts)

def render_section(sec, idx):
    parts = ['<section><div class="wrap">']
    stype = sec.get("type", "default")
    ico_key = SEC_ICON.get(stype, "compass")
    num = f"{idx + 1:02d}"
    parts.append(f'<div class="sec-head"><span class="sec-icon">{ICONS.get(ico_key,"")}</span><h2>{esc(sec.get("heading",""))}</h2></div>')
    desc = sec.get("desc", "")
    if desc:
        parts.append(f'<p class="sec-desc">{esc(desc)}</p>')
    stype = sec.get("type", "default")
    if stype == "timeline":
        parts.append(render_timeline(sec))
    elif stype == "compare":
        parts.append(render_compare(sec))
    elif stype == "pair":
        parts.append(render_pair(sec))
    elif stype == "architecture":
        parts.append(render_architecture(sec))
    elif stype == "flow":
        parts.append(render_flow(sec))
    elif stype == "quote":
        parts.append(render_quote_section(sec))
    elif stype == "list":
        parts.append(render_list_section(sec))
    else:
        parts.append(render_default_section(sec))
    parts.append('</div></section>')
    return "\n".join(parts)

def render_timeline(sec):
    items = sec.get("items", [])
    p = ['<div class="timeline">']
    for item in items:
        s = item.get("status", "default")
        cls = f"tl-item {s}" if s != "default" else "tl-item"
        ico_name = STATUS_ICON.get(s, "footprint")
        p.append(f'<div class="{cls}"><div class="tl-icon">{ICONS.get(ico_name,"")}</div><div class="tl-card">')
        if item.get("year"):
            p.append(f'<span class="tl-year">{esc(item["year"])}</span>')
        p.append(f'<h3>{esc(item.get("title",""))}</h3>')
        if item.get("desc"):
            p.append(f'<p>{esc(item["desc"])}</p>')
        p.append('</div></div>')
    p.append('</div>')
    return "\n".join(p)

def render_compare(sec):
    p = ['<div class="compare">']
    p.append(f'<div class="old"><h5>{ICONS.get("x","")}{esc(sec.get("old_title","原来的做法"))}</h5><ul>')
    for it in sec.get("old", []):
        p.append(f'<li><span class="ico-mark">{ICONS.get("x","")}</span>{esc(it)}</li>')
    p.append('</ul></div>')
    p.append(f'<div class="new"><h5>{ICONS.get("check","")}{esc(sec.get("new_title","更好的做法"))}</h5><ul>')
    for it in sec.get("new", []):
        p.append(f'<li><span class="ico-mark">{ICONS.get("check2","")}</span>{esc(it)}</li>')
    p.append('</ul></div></div>')
    return "\n".join(p)

def render_pair(sec):
    p = ['<div class="grid2">']
    for i, item in enumerate(sec.get("pains", [])):
        p.append('<div class="card"><span class="label pain">痛点 ' + str(i+1) + '</span>')
        p.append(f'<h4>{esc(item.get("title",""))}</h4>')
        if item.get("desc"):
            p.append(f'<p>{esc(item["desc"])}</p>')
        if item.get("quote"):
            p.append(f'<div class="quote">"{esc(item["quote"])}"</div>')
        p.append('</div>')
    for i, item in enumerate(sec.get("fixes", [])):
        p.append('<div class="card"><span class="label fix">解法 ' + str(i+1) + '</span>')
        p.append(f'<h4>{esc(item.get("title",""))}</h4>')
        if item.get("desc"):
            p.append(f'<p>{esc(item["desc"])}</p>')
        if item.get("quote"):
            p.append(f'<div class="quote">"{esc(item["quote"])}"</div>')
        p.append('</div>')
    p.append('</div>')
    return "\n".join(p)

def render_architecture(sec):
    p = ['<div class="diagram">']
    p.append('<div class="you"><span class="pill">' + esc(sec.get("node_title","主体")) + '</span>')
    if sec.get("node_sub"):
        p.append(f'<small>{esc(sec["node_sub"])}</small>')
    p.append('</div><div class="arrow-down"></div><div class="connector"></div><div class="cols">')
    ct = ["safe","show","biz"]
    for i, col in enumerate(sec.get("cols", [])):
        p.append(f'<div class="col {ct[i%3]}">')
        col_ico = COL_ICON.get(ct[i%3], "briefcase")
        p.append(f'<span class="role">{ICONS.get(col_ico,"")}{esc(col.get("role",""))}</span>')
        p.append(f'<h4>{esc(col.get("title",""))}</h4>')
        if col.get("items"):
            p.append('<ul>')
            for it in col["items"]:
                p.append(f'<li>{esc(it)}</li>')
            p.append('</ul>')
        if col.get("nope"):
            p.append(f'<div class="nope">\u2715 {esc(col["nope"])}</div>')
        p.append('</div>')
    p.append('</div>')
    if sec.get("bottom_note"):
        p.append(f'<div class="bottomnote"><b>关键机制：</b>{esc(sec["bottom_note"])}</div>')
    p.append('</div>')
    return "\n".join(p)

def render_flow(sec):
    p = ['<div class="flow">']
    steps = sec.get("steps", [])
    for i, step in enumerate(steps):
        cls = "node"
        if step.get("highlight") == "start": cls = "node hl"
        elif step.get("highlight") == "end": cls = "node hl2"
        p.append(f'<div class="{cls}">{esc(step.get("title",""))}')
        if step.get("sub"):
            p.append(f'<small>{esc(step["sub"])}</small>')
        p.append('</div>')
        if i < len(steps)-1:
            p.append('<span class="arr">→</span>')
    p.append('</div>')
    return "\n".join(p)

def render_quote_section(sec):
    cards = sec.get("cards", [])
    if not cards:
        cards = [{"text": it.get("title",""), "source": it.get("desc","")} for it in sec.get("items",[])]
    p = ['<div class="quotes">']
    for c in cards:
        p.append('<div class="qcard"><p>"' + esc(c.get("text","")) + '"</p>')
        if c.get("source"):
            p.append(f'<small>{esc(c["source"])}</small>')
        p.append('</div>')
    p.append('</div>')
    return "\n".join(p)

def render_list_section(sec):
    items = sec.get("items", [])
    tones = ["","green","red","warn","purple"]
    p = ['<div>']
    for i, item in enumerate(items):
        tc = tones[i % len(tones)]
        cls = f"ico {tc}" if tc else "ico"
        p.append('<div class="takeaway"><div class="' + cls + '">' + f'{i+1:02d}' + '</div><div>')
        p.append(f'<h4>{esc(item.get("title",""))}</h4>')
        if item.get("desc"):
            p.append(f'<p>{esc(item["desc"])}</p>')
        p.append('</div></div>')
    p.append('</div>')
    return "\n".join(p)

def render_default_section(sec):
    p = []
    items = sec.get("content", []) or sec.get("items", [])
    if isinstance(items, str):
        items = [items]
    for item in items:
        if isinstance(item, dict):
            p.append('<div class="std-card">')
            if item.get("title"):
                p.append(f'<h4>{esc(item["title"])}</h4>')
            if item.get("desc"):
                p.append(f'<p>{esc(item["desc"])}</p>')
            p.append('</div>')
        else:
            p.append(f'<div class="std-card"><p>{esc(item)}</p></div>')
    if sec.get("key_points"):
        kps = sec["key_points"]
        if isinstance(kps, str):
            kps = [kps]
        p.append('<div class="std-card"><ul>')
        for kp in kps:
            p.append(f'<li>{esc(kp)}</li>')
        p.append('</ul></div>')
    return "\n".join(p)

def render_key_takeaways(data):
    tks = data.get("key_takeaways", [])
    if not tks:
        return ""
    tones = ["","green","red","warn","purple"]
    p = ['<section><div class="wrap"><div class="sec-head"><span class="sec-icon">' + ICONS.get("list","") + '</span><h2>核心要点</h2></div>']
    for i, ta in enumerate(tks):
        if isinstance(ta, dict):
            title = ta.get("title", ta.get("text",""))
            desc = ta.get("desc", ta.get("source",""))
        else:
            title, desc = ta, ""
        tc = tones[i % len(tones)]
        cls = f"ico {tc}" if tc else "ico"
        p.append('<div class="takeaway"><div class="' + cls + '">' + f'{i+1:02d}' + '</div><div>')
        p.append(f'<h4>{esc(title)}</h4>')
        if desc:
            p.append(f'<p>{esc(desc)}</p>')
        p.append('</div></div>')
    p.append('</div></section>')
    return "\n".join(p)

def render_conclusion(data):
    c = data.get("conclusion", {})
    if not c:
        return ""
    cards = c.get("cards", [])
    if not cards and c.get("quote"):
        cards = [{"text": c["quote"], "source": c.get("source","")}]
    if not cards:
        return ""
    p = ['<section><div class="wrap"><div class="sec-head"><span class="sec-icon">' + ICONS.get("quote","") + '</span><h2>金句</h2></div>']
    p.append(render_quote_section({"cards": cards}))
    p.append('</div></section>')
    return "\n".join(p)

def render_transcript(text, clean):
    if clean or not text:
        return ""
    lines = [l for l in text.strip().split("\n") if not l.startswith("#")]
    p = ['<section class="transcript-section"><div class="wrap"><div class="sec-head"><span class="sec-icon">' + ICONS.get("search","") + '</span><h2>逐字稿</h2></div>']
    p.append('<p class="sec-desc">输入关键词搜索，匹配行高亮显示</p>')
    p.append('<div class="search-box"><input type="text" id="searchInput" placeholder="输入关键词搜索..." oninput="searchTranscript()"><span class="match-info" id="matchInfo"></span></div>')
    p.append('<div class="transcript-block" id="transcriptBlock">')
    for line in lines:
        m = re.match(r'^\[?(\d{2}:\d{2})\]?\s*(.*)', line)
        if m:
            p.append(f'<div class="line"><span class="ts">[{esc(m.group(1))}]</span>{esc(m.group(2))}</div>')
        else:
            p.append(f'<div class="line">{esc(line)}</div>')
    p.append('</div><div class="no-match" id="noMatch" style="display:none">无匹配结果</div>')
    p.append('</div></section>')
    return "\n".join(p)

SEARCH_JS = '''<script>
function searchTranscript(){
  var q=document.getElementById('searchInput').value.toLowerCase();
  var lines=document.querySelectorAll('#transcriptBlock .line');
  var count=0;
  lines.forEach(function(l){
    if(q&&l.textContent.toLowerCase().indexOf(q)>=0){l.style.display='';l.style.background='rgba(217,132,0,.1)';count++;}
    else{l.style.display=q?'none':'';l.style.background='';}
  });
  document.getElementById('matchInfo').textContent=q?(count+' 条匹配'):'';
  document.getElementById('noMatch').style.display=(q&&count===0)?'':'none';
}
</script>'''

def render_footer(data, clean):
    p = ['<footer><div class="wrap">']
    if clean:
        p.append('<p>逐字稿未收入本页，如需回溯请保留随附 transcript.txt</p>')
    cal = data.get("footer", {}).get("calibration", "")
    if cal:
        p.append(f'<p><b>校正说明：</b>{esc(cal)}</p>')
    ents = data.get("entities", [])
    if ents:
        p.append(f'<p><b>实体：</b>{"、".join(esc(e) for e in ents)}</p>')
    p.append('<p style="margin-top:12px">由视频文案提取 skill 生成 · 所有数字与引语来自原始转写</p>')
    p.append('</div></footer>')
    return "\n".join(p)

def render_html(data, transcript, clean, theme):
    validate_title(data.get("title",""))
    css = ALL_CSS
    if theme == "dark":
        css = css + DARK_CSS_OVERRIDE
    parts = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">']
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f'<title>{esc(data.get("title",""))}</title><style>{css}</style></head><body>')
    parts.append(render_hero(data))
    parts.append('<main>')
    for i, sec in enumerate(data.get("sections", [])):
        parts.append(render_section(sec, i))
    kt = render_key_takeaways(data)
    if kt:
        parts.append(kt)
    cl = render_conclusion(data)
    if cl:
        parts.append(cl)
    parts.append('</main>')
    tr = render_transcript(transcript, clean)
    if tr:
        parts.append(tr)
        parts.append(SEARCH_JS)
    parts.append(render_footer(data, clean))
    parts.append('</body></html>')
    return "\n".join(parts)

def main():
    ap = argparse.ArgumentParser(description="analysis.json → 单文件可视化 HTML")
    ap.add_argument("analysis", help="analysis.json 路径")
    ap.add_argument("transcript", nargs="?", default="", help="transcript.txt 路径")
    ap.add_argument("--clean", action="store_true", help="不内嵌逐字稿")
    ap.add_argument("--theme", choices=["light","dark"], default="light")
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    if not os.path.isfile(args.analysis):
        print(f"ERROR: 找不到 {args.analysis}", file=sys.stderr)
        sys.exit(1)
    with open(args.analysis, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 自检：调用统一 schema 校验器（发现 ERROR 直接拒绝渲染，保证任意调用方一致）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import validate_analysis as VA
        tx0 = ""
        if args.transcript and os.path.isfile(args.transcript):
            with open(args.transcript, encoding="utf-8") as f:
                tx0 = f.read()
        r = VA.validate(data, tx0)
        for e in r.errors:
            print(f"ERROR: {e}", file=sys.stderr)
        for w in r.warns:
            print(f"WARN : {w}", file=sys.stderr)
        if r.errors:
            sys.exit(1)
    except ImportError:
        pass
    transcript = ""
    if args.transcript and os.path.isfile(args.transcript):
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
    html_out = render_html(data, transcript, args.clean, args.theme)
    title = data.get("title", "output")
    out_path = args.output if args.output else f"{title}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    sz = os.path.getsize(out_path)
    nsec = len(data.get("sections", []))
    nkt = len(data.get("key_takeaways", []))
    print(f"OK: {out_path}  ({sz:,} bytes)")
    print(f"   {nsec} sections, {nkt} takeaways, theme={args.theme}, {'clean' if args.clean else 'full'}")

if __name__ == "__main__":
    main()
