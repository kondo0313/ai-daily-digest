#!/usr/bin/env python3
"""
publish_learn.py  —  学習記事公開フェーズ (APIキー不要)
=========================================================
エージェント (Claude) が生成した学習記事 JSON を受け取り、
  1. KaTeX 対応 HTML に変換して docs/learn/ に保存
  2. 学習コースのカリキュラム index (docs/learn/index.html) を更新
  3. Discord に embed カード＋リンクを送信
する。

入力ファイル:
  article_learn.json   エージェントが生成した学習記事データ

環境変数:
  DISCORD_WEBHOOK_URL  (必須)  Discord Webhook
  SITE_BASE_URL        (任意)  公開 URL の基底

出力: docs/learn/YYYY-MM-DD.html, docs/learn/index.html, Discord 通知
"""

import os
import sys
import re
import json
import time
import html as _html
from datetime import datetime, timezone, timedelta

import requests

from template import STYLE, esc, _inline

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
LEARN_DIR = os.path.join(DOCS_DIR, "learn")
ARTICLE_LEARN_JSON = os.path.join(BASE_DIR, "article_learn.json")

JST = timezone(timedelta(hours=9))

# Extra CSS for learn articles (KaTeX override + course card)
LEARN_EXTRA_CSS = """
.course-card{background:linear-gradient(135deg,#1c6f8c15,#2cb69615);border:1.5px solid var(--accent);border-radius:10px;padding:20px 22px;margin:30px 0 8px;}
.course-card .cc-label{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.16em;color:var(--accent-ink);text-transform:uppercase;margin-bottom:6px;}
.course-card .cc-title{font-size:16px;font-weight:700;line-height:1.6;margin-bottom:10px;color:var(--ink);}
.course-card .cc-row{font-size:12.5px;color:var(--ink-faint);display:flex;flex-wrap:wrap;gap:4px 16px;}
.cc-badge{display:inline-flex;align-items:center;gap:6px;background:var(--accent);color:#fff;border-radius:6px;padding:4px 12px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;}
.progress-bar{height:4px;background:var(--line);border-radius:2px;margin:10px 0 4px;}
.progress-bar .bar{height:100%;background:var(--accent);border-radius:2px;transition:width .4s;}
.progress-label{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--ink-faint);text-align:right;}
/* KaTeX blocks */
.tex-block{background:var(--wash);border:1px solid var(--line);border-radius:10px;padding:20px 24px;margin:22px 0;overflow-x:auto;}
.tex-block .katex-display{margin:0;}
.tex-block .tx-cap{font-size:12.5px;color:var(--ink-faint);margin-top:10px;text-align:center;}
.tex-derive{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;}
.tex-derive-row{display:flex;gap:10px;align-items:baseline;margin-top:6px;font-size:14px;}
.tex-derive-label{font-size:12px;color:var(--ink-faint);flex-shrink:0;min-width:80px;}
"""


def _render_learn_block(block):
    """Learning article block renderer (extends base template blocks + tex_block)."""
    t = block.get("type")

    if t == "tex_block":
        tex = block.get("tex", "")
        cap = block.get("cap", "")
        derives = block.get("derive", [])

        cap_html = f'<div class="tx-cap">{esc(cap)}</div>' if cap else ""
        derive_html = ""
        if derives:
            rows = "".join(
                f'<div class="tex-derive-row">'
                f'<span class="tex-derive-label">{esc(d.get("label",""))}</span>'
                f'<span class="katex-display-wrapper" data-tex="{esc(d.get("tex",""))}"></span>'
                f'</div>'
                for d in derives
            )
            derive_html = f'<div class="tex-derive">{rows}</div>'

        return (
            f'<div class="tex-block">'
            f'<div class="katex-display-wrapper" data-tex="{esc(tex)}"></div>'
            f'{cap_html}{derive_html}'
            f'</div>'
        )

    if t == "svg":
        cap = block.get("cap", "")
        svg = block.get("svg", "")
        cap_html = f'<div class="code-cap">{esc(cap)}</div>' if cap else ""
        return f'<div style="margin:22px 0;overflow-x:auto;">{svg}</div>{cap_html}'

    # fall back to base template blocks
    from template import _render_block
    return _render_block(block)


def build_learn_article_html(article, date_str):
    blocks_html = "\n".join(_render_learn_block(b) for b in article.get("blocks", []))
    course = article.get("course", {})
    day_num = article.get("day_number", 1)
    total_days = article.get("total_days", 30)
    progress_pct = min(100, int(day_num / total_days * 100))

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 30日講座 — {esc(course.get("title", date_str))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<style>{STYLE}{LEARN_EXTRA_CSS}</style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="dot">📚</span> AI 30日講座</div>
      <div class="date-pill">{esc(date_str)}</div>
    </div>
  </div>

  <div class="page">
    <div class="tags">{esc(article.get("tags",""))}</div>
    <h1 class="headline">{esc(article.get("headline",""))}</h1>

    <div class="author">
      <div class="avatar" style="background:linear-gradient(135deg,#1c6f8c,#2cb696);">📚</div>
      <div class="author-meta">
        <div class="name">AI 30日講座</div>
        <div class="sub">{esc(date_str)} ・ {esc(article.get("subtitle",""))}</div>
      </div>
    </div>

    <div class="course-card">
      <div class="cc-label">本日のカリキュラム</div>
      <div class="cc-title">
        <span class="cc-badge">DAY {day_num} / {total_days}</span>
        &nbsp;{esc(course.get("title",""))}
      </div>
      <div class="progress-bar"><div class="bar" style="width:{progress_pct}%"></div></div>
      <div class="progress-label">{progress_pct}% 完了</div>
      <div class="cc-row">
        <span>{esc(course.get("week",""))}</span>
        <span>{esc(course.get("level",""))}</span>
      </div>
    </div>

    <div class="content">
{blocks_html}
    </div>
  </div>

  <div class="footer">
    AI 30日講座 — Week 1〜6 ・ generated by Claude
  </div>

  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
      // Render explicit tex-block wrappers
      document.querySelectorAll('.katex-display-wrapper').forEach(el => {{
        const tex = el.dataset.tex;
        if (tex) {{
          try {{
            katex.render(tex, el, {{displayMode: true, throwOnError: false}});
          }} catch(e) {{
            el.textContent = tex;
          }}
        }}
      }});
      // Auto-render inline $...$ and $$...$$ in text
      renderMathInElement(document.body, {{
        delimiters: [
          {{left: '$$', right: '$$', display: true}},
          {{left: '$', right: '$', display: false}}
        ],
        throwOnError: false
      }});
    }});
  </script>
</body>
</html>"""


def build_learn_index_html(entries):
    """Curriculum index page."""
    items = "\n".join(
        f'<a class="idx-item" href="{esc(e["file"])}">'
        f'<span class="idx-date">{esc(e.get("day_label",""))}</span>'
        f'<span class="idx-title">{esc(e["headline"])}</span></a>'
        for e in entries
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 30日講座 — カリキュラム</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{STYLE}
.idx-wrap{{max-width:700px;margin:24px auto;background:var(--bg);border-radius:12px;padding:48px 56px;}}
.idx-h{{font-size:26px;font-weight:700;margin-bottom:8px;}}
.idx-sub{{font-size:14px;color:var(--ink-faint);margin-bottom:24px;}}
.idx-item{{display:flex;gap:16px;align-items:baseline;padding:16px 0;border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink);}}
.idx-item:hover .idx-title{{color:var(--accent-ink);}}
.idx-date{{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--ink-faint);flex-shrink:0;min-width:70px;}}
.idx-title{{font-size:15px;font-weight:500;line-height:1.6;}}
</style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="dot">📚</span> AI 30日講座</div>
      <div class="date-pill">カリキュラム</div>
    </div>
  </div>
  <div class="idx-wrap">
    <div class="idx-h">AI 30日講座 ─ カリキュラム</div>
    <div class="idx-sub">AI R&D 新人研究者向け ・ 数理重視 ・ 全30回</div>
    {items}
  </div>
  <div class="footer">AI 30日講座 ・ generated by Claude</div>
</body>
</html>"""


def _extract_learn_headline(path):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r'<h1 class="headline">(.*?)</h1>', txt, re.S)
        return _html.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip()) if m else None
    except Exception:
        return None


def _extract_learn_day_label(path):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r'DAY\s+(\d+)\s*/\s*(\d+)', txt)
        if m:
            return f"DAY {m.group(1)}"
        return None
    except Exception:
        return None


def save_html(article, date_str):
    os.makedirs(LEARN_DIR, exist_ok=True)

    page_html = build_learn_article_html(article, date_str)
    filename = f"{date_str}.html"
    with open(os.path.join(LEARN_DIR, filename), "w", encoding="utf-8") as f:
        f.write(page_html)

    # Rebuild index
    files = []
    for fn in sorted(os.listdir(LEARN_DIR), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.html$", fn)
        if not m:
            continue
        d = m.group(1)
        fp = os.path.join(LEARN_DIR, fn)
        if d == date_str:
            headline = article.get("headline", d)
            day_num = article.get("day_number", "")
            day_label = f"DAY {day_num}" if day_num else d
        else:
            headline = _extract_learn_headline(fp) or d
            day_label = _extract_learn_day_label(fp) or d
        files.append({"date": d, "headline": headline, "file": fn, "day_label": day_label})

    with open(os.path.join(LEARN_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_learn_index_html(files))

    print(f"[info] 保存: docs/learn/{filename} とカリキュラム index 更新", file=sys.stderr)
    return filename


def post_to_discord(article, filename, date_str):
    if SITE_BASE_URL:
        article_url = f"{SITE_BASE_URL}/learn/{filename}"
        archive_url = f"{SITE_BASE_URL}/learn/index.html"
    else:
        article_url = f"learn/{filename}"
        archive_url = "learn/index.html"

    day_num = article.get("day_number", 1)
    total = article.get("total_days", 30)
    week = article.get("week", "")

    # Preview from first paragraph block
    preview = ""
    for b in article.get("blocks", []):
        if b.get("type") == "p":
            preview = re.sub(r"\*\*(.+?)\*\*", r"\1", b.get("text", ""))
            preview = re.sub(r"\[\[(.+?)\]\]", r"\1", preview)
            preview = re.sub(r"\$[^$]+\$", "", preview)
            break
    preview = preview[:280] + ("…" if len(preview) > 280 else "")

    embed = {
        "title": f"📚 {article.get('headline','本日の学習記事')[:240]}",
        "url": article_url,
        "description": preview,
        "color": 0x1C6F8C,
        "fields": [
            {"name": "DAY", "value": f"{day_num} / {total}", "inline": True},
            {"name": "今週のテーマ", "value": week[:100], "inline": True},
        ],
        "footer": {"text": f"AI 30日講座 ・ {date_str}"},
    }
    payload = {
        "content": f"**📚 AI 30日講座 — {date_str}**　今日の学習が届きました　[DAY {day_num}/{total}]",
        "embeds": [embed],
    }
    _send(payload)
    _send({"content": f"▶ 今日の授業を読む: {article_url}\n📋 カリキュラム: {archive_url}"})
    print("[info] Discord 配信完了", file=sys.stderr)


def post_to_slack_learn(article, filename, date_str):
    if not SLACK_WEBHOOK_URL:
        return
    if SITE_BASE_URL:
        article_url = f"{SITE_BASE_URL}/learn/{filename}"
        archive_url = f"{SITE_BASE_URL}/learn/index.html"
    else:
        article_url = f"learn/{filename}"
        archive_url = "learn/index.html"

    day_num = article.get("day_number", 1)
    total = article.get("total_days", 30)
    week = article.get("week", "")
    progress_pct = min(100, int(day_num / total * 100))

    preview = ""
    for b in article.get("blocks", []):
        if b.get("type") == "p":
            preview = re.sub(r"\*\*(.+?)\*\*", r"\1", b.get("text", ""))
            preview = re.sub(r"\[\[(.+?)\|[^\]]+\]\]", r"\1", preview)
            preview = re.sub(r"\[\[(.+?)\]\]", r"\1", preview)
            preview = re.sub(r"\$[^$]+\$", "", preview)
            break
    preview = preview[:200] + ("…" if len(preview) > 200 else "")

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📚 AI 30日講座 — {date_str}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*DAY {day_num} / {total}*　`{progress_pct}% 完了`\n*{article.get('headline', '')}*\n{preview}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"{week}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "▶ 今日の授業を読む"},
                        "url": article_url,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📋 カリキュラム"},
                        "url": archive_url,
                    },
                ],
            },
        ]
    }
    _send_slack(payload)
    print("[info] Slack 配信完了", file=sys.stderr)


def _send(payload):
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    if r.status_code == 429:
        retry = r.json().get("retry_after", 2)
        time.sleep(float(retry) + 0.5)
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    if r.status_code not in (200, 204):
        print(f"[warn] Discord 送信失敗 {r.status_code}: {r.text[:300]}", file=sys.stderr)
    time.sleep(1)


def _send_slack(payload):
    r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=30)
    if r.status_code not in (200, 204):
        print(f"[warn] Slack 送信失敗 {r.status_code}: {r.text[:300]}", file=sys.stderr)
    time.sleep(0.5)


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[error] 環境変数 DISCORD_WEBHOOK_URL が未設定", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(ARTICLE_LEARN_JSON):
        print(f"[error] {ARTICLE_LEARN_JSON} が見つかりません", file=sys.stderr)
        sys.exit(1)

    with open(ARTICLE_LEARN_JSON, encoding="utf-8") as f:
        article = json.load(f)

    date_str = article.get("date") or datetime.now(JST).strftime("%Y-%m-%d")
    if article.get("skip"):
        print(f"[info] skip=true のため何もしない", file=sys.stderr)
        return

    filename = save_html(article, date_str)
    post_to_discord(article, filename, date_str)
    post_to_slack_learn(article, filename, date_str)
    print("[info] 完了", file=sys.stderr)


if __name__ == "__main__":
    main()
