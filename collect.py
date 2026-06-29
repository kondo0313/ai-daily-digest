#!/usr/bin/env python3
"""
collect.py  —  収集フェーズ (APIキー不要)
==========================================
digest.py から「Claude を使わない処理」だけを取り出したもの。

  1. JST の日付からトピックを決定 (偶数日: LLM / 奇数日: Physical AI)
  2. arXiv RSS から新着を収集
  3. docs/ の過去記事と被る論文を除外
  4. 候補論文リストと当日メタ情報を papers.json に書き出す

この後、ルーティンのエージェント (Claude) が papers.json を読んで
  ・今日の1本を選定
  ・記事を構造化 JSON で生成
し、article.json に保存する。最後に publish.py が HTML 化＋配信を行う。

環境変数:
  LOOKBACK_HOURS  (任意)  収集対象の時間幅 (デフォルト 30)
  HISTORY_DAYS    (任意)  重複除外の対象日数 (デフォルト 20)

出力: papers.json  (このスクリプトと同じディレクトリ)
"""

import os
import sys
import re
import json
import html
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests

# ---------------------------------------------------------------------------
# 設定 (digest.py から流用)
# ---------------------------------------------------------------------------

LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "30"))
HISTORY_DAYS = int(os.environ.get("HISTORY_DAYS", "20"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
PAPERS_JSON = os.path.join(BASE_DIR, "papers.json")

JST = timezone(timedelta(hours=9))

LLM_INTERESTS = """
- 大規模言語モデルの新しいアーキテクチャ・学習手法 (attention 改良, MoE, 状態空間モデルなど)
- 推論能力・reasoning の理論的な進展
- 効率化技術 (量子化, 蒸留, KVキャッシュ最適化, 推論高速化)
- 強化学習 / RLHF / ポスト学習の新手法
- マルチモーダル・エージェントの基盤技術
- 解釈可能性 (interpretability) ・安全性の研究
理論的な新規性や技術的なブレークスルーがあるものを高く評価する。
単なる応用事例・ベンチマーク報告だけのものは低め。
"""

LLM_FEEDS = [
    ("arXiv cs.LG", "https://arxiv.org/rss/cs.LG"),
    ("arXiv cs.CL", "https://arxiv.org/rss/cs.CL"),
    ("arXiv cs.AI", "https://arxiv.org/rss/cs.AI"),
]

PHYSICAL_INTERESTS = """
- ロボティクスの基盤モデル (VLA / Vision-Language-Action モデル, RT-X, OpenVLA 系)
- マニピュレーション学習 (拡散ポリシー, 模倣学習, デモから学ぶ手法)
- 自律行動・タスク計画 (LLM を使ったタスク分解, ロボットエージェント)
- sim-to-real, ドメイン適応, データ収集の効率化
- ヒューマノイド / 四足 / 操作器の制御学習
- 触覚センサー・マルチモーダル知覚
- world model のロボット応用
身体を持つ AI が周囲と相互作用しながら賢くなる流れに関わる研究を高く評価する。
純粋なシミュレーションだけのものや、応用事例だけのものは低め。
理論的・手法的に新しいものを優先。
"""

PHYSICAL_FEEDS = [
    ("arXiv cs.RO", "https://arxiv.org/rss/cs.RO"),
    ("arXiv cs.LG", "https://arxiv.org/rss/cs.LG"),
    ("arXiv cs.AI", "https://arxiv.org/rss/cs.AI"),
    ("arXiv cs.CV", "https://arxiv.org/rss/cs.CV"),
]


def pick_topic_for_today():
    """JST の "日" を見て今日のトピックを決める。
    奇数日 → Physical AI / 偶数日 → LLM。
    返り値: (feeds, interests, label)"""
    day = datetime.now(JST).day
    if day % 2 == 1:
        return PHYSICAL_FEEDS, PHYSICAL_INTERESTS, "🤖 Physical AI"
    return LLM_FEEDS, LLM_INTERESTS, "🧠 LLM"


# ---------------------------------------------------------------------------
# 収集 (digest.py の fetch_entries をそのまま)
# ---------------------------------------------------------------------------

_RSS_NS = {"rss": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text or "")


def _parse_rss_xml(content, source_name, cutoff, seen):
    """Parse arXiv RSS XML directly with ElementTree."""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"[warn] RSS XML パース失敗 {source_name}: {e}", file=sys.stderr)
        return items

    # RSS 2.0 format: <rss><channel><item>...</item></channel></rss>
    for item in root.iter("item"):
        link_el = item.find("link")
        if link_el is None:
            # Try guid
            link_el = item.find("guid")
        link = (link_el.text or "").strip() if link_el is not None else ""
        if not link or link in seen:
            continue

        pub_el = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
        published = None
        if pub_el is not None and pub_el.text:
            try:
                published = parsedate_to_datetime(pub_el.text.strip())
            except Exception:
                pass
        if published and published < cutoff:
            continue

        title_el = item.find("title")
        title = html.unescape(_strip_tags(title_el.text or "")).strip() if title_el is not None else ""
        desc_el = item.find("description")
        abstract = html.unescape(_strip_tags(desc_el.text or "")).strip() if desc_el is not None else ""

        items.append({
            "source": source_name,
            "title": title,
            "link": link,
            "abstract": abstract[:5000],
        })
        seen.add(link)
    return items


def _fetch_arxiv_api(category, cutoff):
    """arXiv Search API fallback when RSS is empty."""
    start_str = cutoff.strftime("%Y%m%d")
    end_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=cat:{category}+AND+submittedDate:[{start_str}+TO+{end_str}]"
        f"&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending"
    )
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "AI-Daily-Digest/1.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] arXiv API {category} 失敗: {e}", file=sys.stderr)
        return []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"[warn] arXiv API XML パース失敗 {category}: {e}", file=sys.stderr)
        return []
    items = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        link_el = entry.find("atom:id", _ATOM_NS)
        if link_el is None:
            continue
        link = (link_el.text or "").strip()
        if not link:
            continue
        title_el = entry.find("atom:title", _ATOM_NS)
        title = html.unescape(" ".join((title_el.text or "").split())) if title_el is not None else ""
        summary_el = entry.find("atom:summary", _ATOM_NS)
        abstract = html.unescape(" ".join((summary_el.text or "").split())) if summary_el is not None else ""
        items.append({
            "source": f"arXiv {category}",
            "title": title,
            "link": link,
            "abstract": abstract[:5000],
        })
    return items


def fetch_entries(feeds):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items, seen = [], set()
    rss_had_entries = False

    for source_name, url in feeds:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "AI-Daily-Digest/1.0"})
            r.raise_for_status()
        except Exception as e:
            print(f"[warn] {source_name} 取得失敗: {e}", file=sys.stderr)
            continue

        parsed = _parse_rss_xml(r.content, source_name, cutoff, seen)
        if parsed:
            rss_had_entries = True
        items.extend(parsed)

    # arXiv API fallback when RSS batch is between updates (common on Mon UTC)
    if not rss_had_entries:
        print("[info] RSS エントリなし — arXiv Search API にフォールバック", file=sys.stderr)
        seen_cats = set()
        for source_name, _ in feeds:
            cat = source_name.replace("arXiv ", "")
            if cat not in seen_cats:
                seen_cats.add(cat)
                api_items = _fetch_arxiv_api(cat, cutoff)
                new_items = [it for it in api_items if it["link"] not in seen]
                items.extend(new_items)
                for it in new_items:
                    seen.add(it["link"])
                time.sleep(3)

    print(f"[info] 収集: {len(items)} 件", file=sys.stderr)
    return items


# ---------------------------------------------------------------------------
# 重複防止 (digest.py からそのまま)
# ---------------------------------------------------------------------------

def extract_recent_paper_urls():
    if not os.path.isdir(DOCS_DIR):
        return set()

    files = []
    for fn in os.listdir(DOCS_DIR):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.html$", fn)
        if m:
            files.append((m.group(1), os.path.join(DOCS_DIR, fn)))
    files.sort(reverse=True)
    files = files[:HISTORY_DAYS]

    urls = set()
    for _, path in files:
        try:
            with open(path, encoding="utf-8") as f:
                txt = f.read()
            for m in re.finditer(r'href="(https?://[^"]+)"[^>]*>\s*原文', txt):
                urls.add(m.group(1))
        except Exception as e:
            print(f"[warn] {path} 読み込み失敗: {e}", file=sys.stderr)

    print(f"[info] 過去 {len(files)} 日分から {len(urls)} 件の論文を除外対象に",
          file=sys.stderr)
    return urls


def _arxiv_id(url):
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url or "")
    return f"arxiv:{m.group(1)}" if m else (url or "")


def filter_already_seen(items, seen_urls):
    seen_ids = {_arxiv_id(u) for u in seen_urls}
    fresh = [it for it in items if _arxiv_id(it["link"]) not in seen_ids]
    print(f"[info] 重複除外: {len(items)} → {len(fresh)} 件", file=sys.stderr)
    return fresh


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    feeds, interests, topic_label = pick_topic_for_today()
    print(f"[info] 今日のトピック: {topic_label}", file=sys.stderr)

    items = fetch_entries(feeds)
    seen_urls = extract_recent_paper_urls()
    fresh_items = filter_already_seen(items, seen_urls) if items else []

    payload = {
        "date": date_str,
        "topic_label": topic_label,
        "interests": interests.strip(),
        "count": len(fresh_items),
        "papers": fresh_items,
    }
    with open(PAPERS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[info] papers.json に {len(fresh_items)} 件を書き出し", file=sys.stderr)
    # エージェントが拾いやすいよう、サマリを stdout にも出す
    print(json.dumps({
        "date": date_str,
        "topic_label": topic_label,
        "count": len(fresh_items),
        "papers_json": PAPERS_JSON,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
