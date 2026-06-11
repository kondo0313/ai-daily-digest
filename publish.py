#!/usr/bin/env python3
"""
publish.py  —  公開フェーズ (APIキー不要)
==========================================
エージェント (Claude) が生成した記事 JSON を受け取り、
  1. template.py で note 風 HTML に変換し docs/ に保存
  2. アーカイブ一覧 (index.html) を更新
  3. Discord に embed カード＋リンクを送信
する。digest.py の save_html / post_to_discord をそのまま流用。

入力ファイル (このスクリプトと同じディレクトリ):
  article.json   エージェントが生成した記事データ。形式:
    {
      "headline": "...", "tags": "...", "subtitle": "...",
      "paper": {"title","authors","venue","url"},
      "blocks": [ ... ],
      "selection": {"reason": "選定理由", "source": "arXiv cs.LG", "url": "原文URL"}
    }
    ※ selection は Discord カード用。digest.py の paper(reason/source) に相当。

環境変数:
  DISCORD_WEBHOOK_URL  (必須)  Discord Webhook
  SITE_BASE_URL        (任意)  公開 URL の基底

出力: docs/YYYY-MM-DD.html, docs/index.html, Discord 通知
"""

import os
import sys
import re
import json
import time
import html
from datetime import datetime, timezone, timedelta

import requests

from template import build_article_html, build_index_html

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
ARTICLE_JSON = os.path.join(BASE_DIR, "article.json")

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# HTML 保存 & アーカイブ更新 (digest.py からそのまま)
# ---------------------------------------------------------------------------

def save_html(article, date_str):
    os.makedirs(DOCS_DIR, exist_ok=True)

    page_html = build_article_html(article, date_str)
    filename = f"{date_str}.html"
    with open(os.path.join(DOCS_DIR, filename), "w", encoding="utf-8") as f:
        f.write(page_html)

    entries = []
    for fn in sorted(os.listdir(DOCS_DIR), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.html$", fn)
        if not m:
            continue
        d = m.group(1)
        if d == date_str:
            hl = article.get("headline", d)
        else:
            hl = _extract_headline(os.path.join(DOCS_DIR, fn)) or d
        entries.append({"date": d, "headline": hl, "file": fn})

    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index_html(entries))

    print(f"[info] 保存: docs/{filename} とアーカイブ更新", file=sys.stderr)
    return filename


def _extract_headline(path):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r'<h1 class="headline">(.*?)</h1>', txt, re.S)
        return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip()) if m else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Discord 配信 (digest.py からそのまま。paper 情報は selection から取る)
# ---------------------------------------------------------------------------

def post_to_discord(article, filename, sel, date_str):
    if SITE_BASE_URL:
        article_url = f"{SITE_BASE_URL}/{filename}"
        archive_url = f"{SITE_BASE_URL}/index.html"
    else:
        article_url = filename
        archive_url = "index.html"

    preview = ""
    for b in article.get("blocks", []):
        if b.get("type") == "p":
            preview = re.sub(r"\*\*(.+?)\*\*", r"\1", b.get("text", ""))
            preview = re.sub(r"\[\[(.+?)\]\]", r"\1", preview)
            break
    preview = preview[:280] + ("…" if len(preview) > 280 else "")

    paper_title = article.get("paper", {}).get("title", "")
    embed = {
        "title": f"📄 {article.get('headline','本日のダイジェスト')[:240]}",
        "url": article_url,
        "description": preview,
        "color": 0x2CB696,
        "fields": [
            {"name": "今日の論文", "value": paper_title[:200], "inline": False},
            {"name": "なぜ注目", "value": (sel.get("reason") or "—")[:200], "inline": False},
        ],
        "footer": {"text": f"{sel.get('source','arXiv')} ・ {date_str}"},
    }
    payload = {
        "content": f"**🤖 AI Daily Digest — {date_str}**　今朝の1本が届きました　[{sel.get('topic_label', '')}]",
        "embeds": [embed],
        "components": [],
    }
    _send(payload)

    _send({"content": f"▶ じっくり読む: {article_url}\n📚 過去の記事: {archive_url}"})
    print("[info] Discord 配信完了", file=sys.stderr)


def post_discord_empty(date_str):
    _send({"content": f"**🤖 AI Daily Digest — {date_str}**\n"
                      "本日は対象期間内に新着が見つかりませんでした。"})


def _send(payload):
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    if r.status_code == 429:
        retry = r.json().get("retry_after", 2)
        time.sleep(float(retry) + 0.5)
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    if r.status_code not in (200, 204):
        print(f"[warn] Discord 送信失敗 {r.status_code}: {r.text[:300]}", file=sys.stderr)
    time.sleep(1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if not DISCORD_WEBHOOK_URL:
        print("[error] 環境変数 DISCORD_WEBHOOK_URL が未設定", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(ARTICLE_JSON):
        print(f"[error] {ARTICLE_JSON} が見つかりません", file=sys.stderr)
        sys.exit(1)

    with open(ARTICLE_JSON, encoding="utf-8") as f:
        article = json.load(f)

    # 空き日 (新着なし) のハンドリング: article.json に {"empty": true} を許可
    date_str = article.get("date") or datetime.now(JST).strftime("%Y-%m-%d")
    if article.get("empty"):
        post_discord_empty(date_str)
        print("[info] 空き日として通知", file=sys.stderr)
        return

    sel = article.get("selection", {})

    # paper.url が空なら selection の url で補完
    article.setdefault("paper", {})
    if not article["paper"].get("url") and sel.get("url"):
        article["paper"]["url"] = sel["url"]

    filename = save_html(article, date_str)
    post_to_discord(article, filename, sel, date_str)
    print("[info] 完了", file=sys.stderr)


if __name__ == "__main__":
    main()
