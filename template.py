"""
HTML テンプレート
-----------------
確定した「note 風・新人研究者向け技術解説」デザインを、
記事データ (dict) から組み立てる。digest.py から呼ばれる。

記事データの構造は build_article_html() の docstring を参照。
"""

import html as _html


# ---------------------------------------------------------------------------
# CSS (サンプルで確定したものをそのまま使用)
# ---------------------------------------------------------------------------

STYLE = """
:root{
  --ink:#1c1c1c;--ink-soft:#41463a;--ink-faint:#7a7d75;
  --bg:#ffffff;--wash:#f7f8f5;--line:#e6e6e6;
  --accent:#2cb696;--accent-ink:#14866c;--accent-wash:#e8f6f2;
  --code-bg:#1e2420;--code-ink:#e4e8e0;--code-green:#7fd6b5;
  --code-dim:#8a9a90;--code-key:#f0b86c;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--wash);color:var(--ink);
  font-family:'Noto Sans JP',sans-serif;line-height:1.95;
  -webkit-font-smoothing:antialiased;font-size:16px;}
.topbar{background:var(--bg);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10;}
.topbar-inner{max-width:700px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;}
.brand{font-weight:700;font-size:17px;display:flex;align-items:center;gap:8px;}
.brand .dot{width:22px;height:22px;background:var(--accent);border-radius:50%;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:13px;}
.date-pill{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--ink-faint);}
.page{background:var(--bg);max-width:700px;margin:24px auto;border-radius:12px;padding:56px 64px 48px;}
.tags{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--accent-ink);letter-spacing:0.04em;margin-bottom:20px;}
h1.headline{font-size:30px;font-weight:700;line-height:1.55;margin-bottom:26px;}
.author{display:flex;align-items:center;gap:12px;padding-bottom:26px;border-bottom:1px solid var(--line);}
.avatar{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#2cb696,#1c6f8c);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:18px;flex-shrink:0;}
.author-meta .name{font-weight:700;font-size:14px;}
.author-meta .sub{font-size:12px;color:var(--ink-faint);}
.paper-card{background:var(--wash);border-radius:10px;padding:20px 22px;margin:30px 0 8px;}
.paper-card .pc-label{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.16em;color:var(--ink-faint);text-transform:uppercase;margin-bottom:8px;}
.paper-card .pc-title{font-size:16px;font-weight:700;line-height:1.6;margin-bottom:10px;}
.paper-card .pc-row{font-size:12.5px;color:var(--ink-faint);display:flex;flex-wrap:wrap;gap:6px 16px;}
.paper-card a{color:var(--accent-ink);font-weight:700;text-decoration:none;}
.content{margin-top:14px;}
.content h2{font-size:21px;font-weight:700;line-height:1.5;margin:44px 0 16px;display:flex;align-items:center;gap:10px;}
.content h2 .n{font-family:'JetBrains Mono',monospace;font-size:14px;color:#fff;background:var(--accent);width:28px;height:28px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;}
.content h3{font-size:16px;font-weight:700;margin:28px 0 10px;color:var(--ink);padding-left:12px;border-left:3px solid var(--accent);}
.content p{font-size:16px;color:var(--ink-soft);margin-bottom:18px;}
.content p strong{color:var(--ink);font-weight:700;background:linear-gradient(transparent 62%,var(--accent-wash) 62%);}
.pull{border-left:3px solid var(--accent);padding:6px 0 6px 20px;margin:26px 0;font-size:18px;font-weight:500;color:var(--ink);line-height:1.7;}
.stats{display:flex;gap:12px;margin:28px 0;flex-wrap:wrap;}
.stat{flex:1;min-width:130px;background:var(--accent-wash);border-radius:10px;padding:16px 18px;}
.stat .v{font-size:24px;font-weight:700;color:var(--accent-ink);line-height:1.2;}
.stat .v small{font-size:14px;}
.stat .k{font-size:12px;color:var(--ink-soft);margin-top:4px;line-height:1.5;}
.step{display:flex;gap:14px;margin-bottom:16px;align-items:flex-start;}
.step .si{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--accent-ink);background:var(--accent-wash);border-radius:6px;padding:3px 9px;flex-shrink:0;margin-top:3px;}
.step p{margin-bottom:0;}
.code{background:var(--code-bg);border-radius:10px;padding:18px 0;margin:22px 0;overflow-x:auto;font-family:'JetBrains Mono',monospace;font-size:13.5px;line-height:1.7;color:var(--code-ink);}
.code .ln{display:grid;grid-template-columns:38px 1fr;min-height:1.7em;}
.code .ln>.no{color:#4a564f;text-align:right;padding-right:14px;user-select:none;font-size:12px;}
.code .ln>.ct{white-space:pre;}
.code .ind{display:inline-block;width:22px;height:1.7em;border-left:1px solid #38443d;vertical-align:top;}
.code .ln.comment .ct{color:var(--code-dim);}
.code .cm{color:var(--code-dim);}.code .kw{color:var(--code-key);}
.code .fn{color:var(--code-green);}.code .st{color:var(--code-green);}.code .nm{color:#c4a3f0;}
.code .badge{display:inline-block;background:var(--accent);color:#fff;font-size:11px;font-weight:700;border-radius:5px;padding:0 7px;margin-left:6px;vertical-align:middle;}
.code-cap{font-size:12.5px;color:var(--ink-faint);margin:8px 0 24px;text-align:center;}
.formula{background:var(--wash);border:1px solid var(--line);border-radius:10px;padding:20px 24px;margin:22px 0;text-align:center;}
.formula .eq{font-family:'JetBrains Mono',monospace;font-size:17px;color:var(--ink);margin-bottom:6px;}
.formula .eq .frac{display:inline-flex;flex-direction:column;vertical-align:middle;margin:0 4px;}
.formula .eq .frac .top{border-bottom:1.5px solid var(--ink);padding:0 8px;font-size:14px;}
.formula .eq .frac .bot{padding:2px 8px 0;font-size:14px;}
.formula .cap{font-size:12.5px;color:var(--ink-faint);}
.note-box{background:#fff8f0;border:1px solid #f0e0cc;border-radius:10px;padding:18px 20px;margin:26px 0;font-size:14.5px;color:var(--ink-soft);}
.note-box .nb-label{font-weight:700;color:#b5781f;font-size:13px;margin-bottom:4px;}
.tip-box{background:var(--accent-wash);border-radius:10px;padding:18px 20px;margin:26px 0;font-size:14.5px;color:var(--ink-soft);}
.tip-box .tb-label{font-weight:700;color:var(--accent-ink);font-size:13px;margin-bottom:4px;}
.tip-box strong{color:var(--accent-ink);}
.term{border-bottom:1.5px dotted var(--accent);font-weight:500;color:var(--ink);}
.footer{text-align:center;font-size:12px;color:var(--ink-faint);padding:24px;line-height:1.9;}
@media(max-width:560px){
  .page{padding:36px 22px 28px;margin:12px;border-radius:10px;}
  h1.headline{font-size:24px;}.content h2{font-size:19px;}
  .stat{min-width:100%;}.code{font-size:12px;}
}
"""


def esc(text):
    """HTML エスケープ。None は空文字に。"""
    if text is None:
        return ""
    return _html.escape(str(text))


def _inline(text):
    """
    本文中の簡易記法を HTML に変換。Claude には以下だけ使わせる:
      **強調**        -> <strong>
      [[用語]]        -> <span class="term">
    それ以外はエスケープして安全に。
    """
    if text is None:
        return ""
    # まずエスケープ
    s = _html.escape(str(text))
    # **bold**
    import re
    s = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', s)
    # [[term]]
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="term">\1</span>', s)
    return s


# ---------------------------------------------------------------------------
# 各セクションのレンダラ
# ---------------------------------------------------------------------------

def _render_block(block):
    """1 つのコンテンツブロックを HTML 化。
    block は {"type": ..., ...} の dict。
    対応 type:
      h2        : {"type":"h2","n":"1","text":"..."}
      h3        : {"type":"h3","text":"..."}
      p         : {"type":"p","text":"..."}
      pull      : {"type":"pull","text":"..."}
      stats     : {"type":"stats","items":[{"v":"50.6%","k":"説明"},...]}
      steps     : {"type":"steps","items":[{"si":"STEP 1","text":"..."},...]}
      code      : {"type":"code","lines":[...],"cap":"..."}  (lines 形式は下記)
      formula   : {"type":"formula","eq_html":"...","cap":"..."}
      note      : {"type":"note","label":"⚙️ メモ","text":"..."}
      tip       : {"type":"tip","label":"💡 ヒント","text":"..."}
    """
    t = block.get("type")

    if t == "h2":
        return (f'<h2><span class="n">{esc(block.get("n",""))}</span>'
                f'{esc(block.get("text",""))}</h2>')

    if t == "h3":
        return f'<h3>{esc(block.get("text",""))}</h3>'

    if t == "p":
        return f'<p>{_inline(block.get("text",""))}</p>'

    if t == "pull":
        return f'<div class="pull">{_inline(block.get("text",""))}</div>'

    if t == "stats":
        cells = "".join(
            f'<div class="stat"><div class="v">{esc(it.get("v",""))}</div>'
            f'<div class="k">{_inline(it.get("k",""))}</div></div>'
            for it in block.get("items", [])
        )
        return f'<div class="stats">{cells}</div>'

    if t == "steps":
        rows = "".join(
            f'<div class="step"><span class="si">{esc(it.get("si",""))}</span>'
            f'<p>{_inline(it.get("text",""))}</p></div>'
            for it in block.get("items", [])
        )
        return rows

    if t == "code":
        return _render_code(block.get("lines", []), block.get("cap", ""))

    if t == "formula":
        # eq_html は信頼済みの組み込み式のみ (Claude には作らせない設計)
        cap = f'<div class="cap">{esc(block.get("cap",""))}</div>' if block.get("cap") else ""
        return f'<div class="formula"><div class="eq">{block.get("eq_html","")}</div>{cap}</div>'

    if t == "note":
        return (f'<div class="note-box"><div class="nb-label">'
                f'{esc(block.get("label","⚙️ メモ"))}</div>'
                f'{_inline(block.get("text",""))}</div>')

    if t == "tip":
        return (f'<div class="tip-box"><div class="tb-label">'
                f'{esc(block.get("label","💡 ヒント"))}</div>'
                f'{_inline(block.get("text",""))}</div>')

    return ""


def _render_code(lines, cap):
    """
    擬似コードをレンダリング。確定デザイン (行番号 + インデント縦線 + バッジ) 準拠。
    各 line は dict:
      {"no": "6", "indent": 2, "comment": false,
       "tokens": [{"t":"plain","s":"code = "},{"t":"fn","s":"generate"},...],
       "badge": "①"}
    - comment=true の行はコメントスタイル (緑グレー)
    - indent はネストの深さ (縦線の本数)
    - tokens の t は: plain / kw / fn / st / nm
    - badge があれば行末に丸数字バッジ
    """
    token_class = {"kw": "kw", "fn": "fn", "st": "st", "nm": "nm"}
    out = ['<div class="code">']
    for ln in lines:
        no = esc(ln.get("no", ""))
        indent = "".join('<span class="ind"></span>' for _ in range(ln.get("indent", 0)))
        is_comment = ln.get("comment", False)

        if is_comment:
            text = esc(ln.get("text", ""))
            badge = ln.get("badge")
            badge_html = f'<span class="badge">{esc(badge)}</span>' if badge else ""
            body = f'{indent}{text}{badge_html}'
            out.append(f'<div class="ln comment"><span class="no">{no}</span>'
                       f'<span class="ct">{body}</span></div>')
        else:
            parts = []
            for tok in ln.get("tokens", []):
                cls = token_class.get(tok.get("t"))
                s = esc(tok.get("s", ""))
                parts.append(f'<span class="{cls}">{s}</span>' if cls else s)
            badge = ln.get("badge")
            badge_html = f'<span class="badge">{esc(badge)}</span>' if badge else ""
            body = f'{indent}{"".join(parts)}{badge_html}'
            out.append(f'<div class="ln"><span class="no">{no}</span>'
                       f'<span class="ct">{body}</span></div>')
    out.append('</div>')
    cap_html = f'<div class="code-cap">{esc(cap)}</div>' if cap else ""
    return "".join(out) + cap_html


# ---------------------------------------------------------------------------
# ページ全体の組み立て
# ---------------------------------------------------------------------------

def build_article_html(article, date_str):
    """
    記事データからページ全体の HTML 文字列を返す。

    article = {
      "tags": "#AI #論文解説 ...",
      "headline": "記事タイトル",
      "subtitle": "07:00 ・ きょうの1本をじっくり解説",
      "paper": {"title": "...", "authors": "...", "venue": "arXiv cs.LG ・ 2026年1月",
                "url": "https://arxiv.org/abs/..."},
      "blocks": [ {...}, {...}, ... ]   # _render_block が解釈する dict のリスト
    }
    """
    blocks_html = "\n".join(_render_block(b) for b in article.get("blocks", []))
    paper = article.get("paper", {})

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Daily Digest — {esc(date_str)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="dot">✦</span> AI Daily Digest</div>
      <div class="date-pill">{esc(date_str)}</div>
    </div>
  </div>

  <div class="page">
    <div class="tags">{esc(article.get("tags",""))}</div>
    <h1 class="headline">{esc(article.get("headline",""))}</h1>

    <div class="author">
      <div class="avatar">AI</div>
      <div class="author-meta">
        <div class="name">AI Daily Digest</div>
        <div class="sub">{esc(date_str)} ・ {esc(article.get("subtitle",""))}</div>
      </div>
    </div>

    <div class="paper-card">
      <div class="pc-label">本日の論文</div>
      <div class="pc-title">{esc(paper.get("title",""))}</div>
      <div class="pc-row">
        <span>{esc(paper.get("authors",""))}</span>
        <span>{esc(paper.get("venue",""))}</span>
        <a href="{esc(paper.get("url","#"))}">原文 →</a>
      </div>
    </div>

    <div class="content">
{blocks_html}
    </div>
  </div>

  <div class="footer">
    AI Daily Digest<br>
    arXiv cs.LG / cs.CL / cs.AI より自動収集・要約 ・ generated by Claude
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# インデックスページ (アーカイブ一覧)
# ---------------------------------------------------------------------------

def build_index_html(entries):
    """
    過去記事の一覧ページ。entries は新しい順の
    [{"date":"2026-05-29","headline":"...","file":"2026-05-29.html"}, ...]
    """
    items = "\n".join(
        f'<a class="idx-item" href="{esc(e["file"])}">'
        f'<span class="idx-date">{esc(e["date"])}</span>'
        f'<span class="idx-title">{esc(e["headline"])}</span></a>'
        for e in entries
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Daily Digest — アーカイブ</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{STYLE}
.idx-wrap{{max-width:700px;margin:24px auto;background:var(--bg);border-radius:12px;padding:48px 56px;}}
.idx-h{{font-size:26px;font-weight:700;margin-bottom:24px;}}
.idx-item{{display:flex;gap:16px;align-items:baseline;padding:16px 0;border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink);}}
.idx-item:hover .idx-title{{color:var(--accent-ink);}}
.idx-date{{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--ink-faint);flex-shrink:0;}}
.idx-title{{font-size:15px;font-weight:500;line-height:1.6;}}
</style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="dot">✦</span> AI Daily Digest</div>
      <div class="date-pill">アーカイブ</div>
    </div>
  </div>
  <div class="idx-wrap">
    <div class="idx-h">これまでのダイジェスト</div>
    {items}
  </div>
  <div class="footer">AI Daily Digest ・ generated by Claude</div>
</body>
</html>"""
