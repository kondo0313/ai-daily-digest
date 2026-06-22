#!/usr/bin/env python3
"""
AI Daily Digest  —  完成版
==========================
毎朝 arXiv から AI 論文を収集し、Claude が最も注目すべき1本を選んで
「新人研究者向けに、やさしく・でも技術まで」深掘りした記事を生成。
note 風の HTML にして GitHub Pages に公開し、Discord にカード＋リンクを送る。

処理の流れ:
  1. arXiv RSS から新着を収集
  2. Claude が興味に沿って "今日の1本" を選定
  3. Claude がその論文を深掘りし、記事を構造化 JSON で生成
  4. template.py で note 風 HTML に変換し docs/ に保存 (GitHub Pages 公開用)
  5. アーカイブ一覧 (index.html) を更新
  6. Discord に embed カード＋HTML リンクを送信

環境変数:
  ANTHROPIC_API_KEY    (必須)  Claude API キー
  DISCORD_WEBHOOK_URL  (必須)  Discord Webhook
  SITE_BASE_URL        (任意)  公開 URL の基底。例: https://USER.github.io/ai-daily-digest
                              未設定だと Discord のリンクが相対表記になる
  LOOKBACK_HOURS       (任意)  収集対象の時間幅 (デフォルト 30)
  MODEL                (任意)  使用モデル (デフォルト claude-opus-4-8)
"""

import os
import sys
import re
import json
import time
import html
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests
import feedparser

from template import build_article_html, build_index_html

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")

# 月曜日 (JST) は週末分を含めて 78 時間さかのぼる（arXiv は週末に論文を公開しないため）
_jst_now = datetime.now(timezone(timedelta(hours=9)))
_default_lookback = 78 if _jst_now.weekday() == 0 else 30
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", str(_default_lookback)))

# コスト重視で既定は Sonnet。記事の質を最優先したいなら "claude-opus-4-8" に変更。
MODEL = os.environ.get("MODEL", "claude-sonnet-4-6")

# 出力先 (GitHub Pages は docs/ を公開する設定にする)
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")

# 重複防止: 過去 N 日分の記事と被らないように論文を除外する
HISTORY_DAYS = int(os.environ.get("HISTORY_DAYS", "20"))

# タイムゾーン: 配信日時の判定は JST で行う (GitHub Actions は既定で UTC)
JST = timezone(timedelta(hours=9))

# --- LLM 中心の日 (奇数日) -------------------------------------------------
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

# --- フィジカル AI / ロボティクスの日 (偶数日) -----------------------------
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
    ("arXiv cs.LG", "https://arxiv.org/rss/cs.LG"),  # VLA や policy 学習は cs.LG にも多い
    ("arXiv cs.AI", "https://arxiv.org/rss/cs.AI"),
    ("arXiv cs.CV", "https://arxiv.org/rss/cs.CV"),  # マニピュレーションは vision がらみ
]


def pick_topic_for_today():
    """JST の日付の "日" を見て、今日のトピックを決める。
    奇数日 → フィジカル AI / 偶数日 → LLM。
    返り値: (feeds, interests, label)"""
    day = datetime.now(JST).day
    if day % 2 == 1:
        return PHYSICAL_FEEDS, PHYSICAL_INTERESTS, "🤖 Physical AI"
    return LLM_FEEDS, LLM_INTERESTS, "🧠 LLM"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


# ---------------------------------------------------------------------------
# 1. 収集
# ---------------------------------------------------------------------------

def _strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text or "")


def fetch_entries(feeds):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items, seen = [], set()

    for source_name, url in feeds:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[warn] {source_name} 取得失敗: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in seen:
                continue

            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif entry.get("published"):
                try:
                    published = parsedate_to_datetime(entry.published)
                except Exception:
                    published = None
            if published and published < cutoff:
                continue

            summary = html.unescape(_strip_tags(
                entry.get("summary", "") or entry.get("description", ""))).strip()

            items.append({
                "source": source_name,
                "title": html.unescape(entry.get("title", "").strip()),
                "link": link,
                "abstract": summary[:5000],
            })
            seen.add(link)

    print(f"[info] 収集: {len(items)} 件", file=sys.stderr)
    return items


# ---------------------------------------------------------------------------
# 1.5. 重複防止 (docs/ の過去記事から紹介済み論文 URL を抽出)
# ---------------------------------------------------------------------------

def extract_recent_paper_urls():
    """docs/ 内の最新 HISTORY_DAYS 日分の記事 HTML から、
    紹介済み論文の URL を抽出して set で返す。"""
    if not os.path.isdir(DOCS_DIR):
        return set()

    # YYYY-MM-DD.html を新しい順に並べて上位 N 件を対象に
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
            # paper-card 内の <a href="...">原文 →</a> を拾う
            for m in re.finditer(r'href="(https?://[^"]+)"[^>]*>\s*原文', txt):
                urls.add(m.group(1))
        except Exception as e:
            print(f"[warn] {path} 読み込み失敗: {e}", file=sys.stderr)

    print(f"[info] 過去 {len(files)} 日分から {len(urls)} 件の論文を除外対象に",
          file=sys.stderr)
    return urls


def _arxiv_id(url):
    """arXiv URL から論文 ID だけ抽出して正規化。
    abs / pdf やバージョン違いの URL を同一視するため。"""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url or "")
    return f"arxiv:{m.group(1)}" if m else (url or "")


def filter_already_seen(items, seen_urls):
    """既に紹介した論文を除外。"""
    seen_ids = {_arxiv_id(u) for u in seen_urls}
    fresh = [it for it in items if _arxiv_id(it["link"]) not in seen_ids]
    print(f"[info] 重複除外: {len(items)} → {len(fresh)} 件", file=sys.stderr)
    return fresh


# ---------------------------------------------------------------------------
# 2. Claude 呼び出し基盤
# ---------------------------------------------------------------------------

def call_claude(system, user, max_tokens=8000, retries=4):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    for attempt in range(retries):
        try:
            r = requests.post(ANTHROPIC_URL, headers=headers,
                              data=json.dumps(payload), timeout=180)
            if r.status_code == 200:
                data = r.json()
                return "".join(b.get("text", "") for b in data.get("content", [])
                               if b.get("type") == "text")
            if r.status_code in (429, 500, 502, 503, 529):
                wait = 2 ** attempt * 5
                print(f"[warn] HTTP {r.status_code} → {wait}s 待機", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"API エラー {r.status_code}: {r.text[:400]}")
        except requests.RequestException as e:
            wait = 2 ** attempt * 5
            print(f"[warn] 通信失敗 ({e}) → {wait}s 待機", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("Claude API 呼び出しが規定回数失敗")


def parse_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    raw = raw.strip().strip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        s, e = raw.find("{"), raw.rfind("}")
        a, b = raw.find("["), raw.rfind("]")
        # オブジェクトと配列のどちらか、外側にある方を採用
        if s != -1 and (a == -1 or s < a):
            return json.loads(raw[s:e + 1])
        return json.loads(raw[a:b + 1])


# ---------------------------------------------------------------------------
# 3. 今日の1本を選定
# ---------------------------------------------------------------------------

def select_one(items, interests):
    import random

    # レート制限・コスト対策: 最大 SELECT_MAX_ITEMS 件にランダムサンプリング
    # arXiv の論文は投稿時刻順に並んでいて偏りが無いので、ランダム選出で十分。
    SELECT_MAX_ITEMS = 150
    SELECT_ABSTRACT_CHARS = 300

    if len(items) > SELECT_MAX_ITEMS:
        sample = random.sample(items, SELECT_MAX_ITEMS)
        print(f"[info] 選定用サンプリング: {len(items)} → {SELECT_MAX_ITEMS} 件",
              file=sys.stderr)
    else:
        sample = items

    catalog = "\n\n".join(
        f"[{i}] {it['title']}\n{it['abstract'][:SELECT_ABSTRACT_CHARS]}"
        for i, it in enumerate(sample)
    )
    system = ("あなたは AI 研究を追うシニアリサーチャーです。"
              "新人研究者が毎朝1本だけ学ぶのに最適な論文を選びます。")
    user = f"""本日収集した AI 関連論文のリストです。

読者の興味:
{interests}

リスト:
{catalog}

この中から、理論・技術的に最も注目すべき "今日の1本" を選んでください。
新規性・教育的価値・面白さを重視。
出力は JSON のみ。説明や ``` は不要。
形式: {{"index": 数値, "reason": "選定理由を一文"}}"""
    sel = parse_json(call_claude(system, user, max_tokens=1000))
    idx = sel.get("index", 0)
    if not (isinstance(idx, int) and 0 <= idx < len(sample)):
        idx = 0
    chosen = dict(sample[idx])
    chosen["reason"] = sel.get("reason", "")
    print(f"[info] 選定: {chosen['title'][:70]}", file=sys.stderr)
    return chosen


# ---------------------------------------------------------------------------
# 4. 深掘り記事を構造化 JSON で生成
# ---------------------------------------------------------------------------

# Claude に渡す "記事の設計図" 仕様。template.py のブロック仕様と一致させる。
ARTICLE_SPEC = r"""
あなたは AI 研究の解説者です。読者は「これから AI の R&D 部署で働く新人研究者」。
目標は「詳しく知りたいが、わかりやすく優しく」。専門用語は噛み砕き、たとえ話を使い、
擬似コードや数式も出すが必ず日本語で解説する。誇張やハイプは避け、論文の限界も誠実に書く。

与えられた論文を解説する記事を、以下の JSON 形式で出力してください。
**JSON のみを出力**し、前後に説明や ``` を付けないこと。

全体構造:
{
  "headline": "魅力的だが正確な日本語タイトル",
  "tags": "#AI #論文解説 #(内容に応じたタグ) #新人研究者向け",
  "subtitle": "07:00 ・ きょうの1本をじっくり解説",
  "paper": {
    "title": "論文の原題(英語のまま)",
    "authors": "著者名と所属",
    "venue": "arXiv カテゴリ ・ 投稿年月",
    "url": "論文 URL"
  },
  "blocks": [ ...コンテンツブロックの配列... ]
}

blocks に使えるブロック (順番・個数は内容に応じて自由、ただし読み物として自然に):
- 見出し:        {"type":"h2","n":"1","text":"見出し文"}   (n は連番の文字列)
- 小見出し:      {"type":"h3","text":"小見出し"}
- 段落:          {"type":"p","text":"本文。**強調**と[[専門用語|短い解説]]が使える"}
- 引用(主張):    {"type":"pull","text":"記事の核心となる一文"}
- 数値ハイライト: {"type":"stats","items":[{"v":"50.6%","k":"説明"},...]}  (2〜3個)
- 手順/箇条:     {"type":"steps","items":[{"si":"STEP 1","text":"..."},...]}
- ヒント箱:      {"type":"tip","label":"💡 R&Dでよく出る考え方","text":"..."}
- 補足箱:        {"type":"note","label":"⚙️ ひとことメモ","text":"..."}
- 擬似コード:    下記 code 仕様を参照

擬似コード (該当論文にアルゴリズム/手順がある場合のみ。無ければ省略可):
{
  "type":"code",
  "cap":"コードの説明キャプション",
  "lines":[
    {"no":"","comment":true,"indent":0,"text":"# まとまりの説明コメント"},
    {"no":"1","indent":0,"tokens":[{"t":"plain","s":"model = "},{"t":"fn","s":"load_LLM"},{"t":"plain","s":"()"}]},
    {"no":"3","indent":0,"tokens":[{"t":"kw","s":"for"},{"t":"plain","s":" x "},{"t":"kw","s":"in"},{"t":"plain","s":" data:"}]},
    {"no":"4","indent":1,"tokens":[{"t":"plain","s":"process(x)"}],"badge":"①"}
  ]
}
code のルール:
- "no": 表示する行番号(文字列)。コメント行や空行は ""。
- "indent": ネストの深さ(整数)。縦線で表示される。実コードのインデントと一致させる。
- "comment": true ならコメント行。コメントは処理のまとまりの【上】に置く(行末に付けない)。
- "tokens": コード行の中身。t は plain/kw(予約語)/fn(関数名)/st(文字列)/nm(数値)。
- "badge": その行が処理の節目なら丸数字(①②③...)。後の解説の見出しと対応させる。
- 読みやすさ最優先。1行を詰め込みすぎない。重要な節目だけ badge を付ける。

専門用語の扱い (重要):
- 新人研究者が「初めて見る or うろ覚えな」専門用語が出てきたら、必ず [[用語|短い解説]] を使う。
- 縦棒 | の右側に **15〜40 字程度のやさしい解説** を入れる。これがホバー/タップで表示される説明になる。
- 例: [[KVキャッシュ|Transformerが過去の文脈を保持するメモリ。長文ほど膨らむ]]
- 例: [[VLAモデル|Vision-Language-Action: 視覚と言語からロボットの行動を出力するモデル]]
- 用語の選び方: 学部レベルの教科書に出てこないもの, 略語, 最近出てきた手法名, 分野特有の概念
- 普通の日本語や、文中で十分説明してある語には付けない。
- 1段落あたり多くて 2 個まで。多すぎると読みにくい。
- 解説は文章を断ち切らない自然な短文で。「〜のこと」「〜する手法」など。

記事の構成指針 (厳守ではないが目安):
1. 導入(なぜこのテーマが重要か / 問いの提示)
2. 背景・問題設定
3. 手法の全体像(可能なら擬似コード)
4. 手法の要素技術を h3 で分解し、数式やたとえで優しく解説
   - 数式が必要なら formula ではなく p の中で文章＋簡単な記述で説明してよい
     (formula ブロックは複雑なので使わない)
5. 実験結果(stats で数値を見せる)
6. 新規性・なぜ重要か(pull で核心)
7. 意義と限界(steps で限界を列挙すると良い。論文が認める弱点も書く)
8. 新人へのひとこと・大きな文脈(note/tip)

文章は優しく丁寧に。たとえ話を効果的に。全体で 2500〜4000 字程度。
"""


def generate_article(paper):
    user = f"""次の論文を解説する記事を JSON で作ってください。

論文タイトル: {paper['title']}
ソース: {paper['source']}
URL: {paper['link']}
選定理由: {paper.get('reason','')}

アブストラクト等:
{paper['abstract']}

注意: アブストラクトに無い数値や事実を創作しないこと。
不明な著者名・所属・投稿月は無理に埋めず、分かる範囲で簡潔に書く。
"""
    raw = call_claude(ARTICLE_SPEC, user, max_tokens=12000)
    article = parse_json(raw)

    # paper.url が空なら元リンクで補完
    article.setdefault("paper", {})
    if not article["paper"].get("url"):
        article["paper"]["url"] = paper["link"]
    return article


# ---------------------------------------------------------------------------
# 5. HTML 保存 & アーカイブ更新
# ---------------------------------------------------------------------------

def save_html(article, date_str):
    os.makedirs(DOCS_DIR, exist_ok=True)

    # 当日記事
    page_html = build_article_html(article, date_str)
    filename = f"{date_str}.html"
    with open(os.path.join(DOCS_DIR, filename), "w", encoding="utf-8") as f:
        f.write(page_html)

    # アーカイブ index を再構築 (docs 内の YYYY-MM-DD.html を集める)
    entries = []
    for fn in sorted(os.listdir(DOCS_DIR), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.html$", fn)
        if not m:
            continue
        d = m.group(1)
        # 当日分は手元の headline、過去分はファイルから抽出
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
# 6. Discord 配信
# ---------------------------------------------------------------------------

def post_to_discord(article, filename, paper, date_str):
    if SITE_BASE_URL:
        article_url = f"{SITE_BASE_URL}/{filename}"
        archive_url = f"{SITE_BASE_URL}/index.html"
    else:
        article_url = filename
        archive_url = "index.html"

    # 記事冒頭の段落を抜粋してプレビューにする
    preview = ""
    for b in article.get("blocks", []):
        if b.get("type") == "p":
            preview = re.sub(r"\*\*(.+?)\*\*", r"\1", b.get("text", ""))
            preview = re.sub(r"\[\[(.+?)\]\]", r"\1", preview)
            break
    preview = preview[:280] + ("…" if len(preview) > 280 else "")

    embed = {
        "title": f"📄 {article.get('headline','本日のダイジェスト')[:240]}",
        "url": article_url,
        "description": preview,
        "color": 0x2CB696,
        "fields": [
            {"name": "今日の論文", "value": paper["title"][:200], "inline": False},
            {"name": "なぜ注目", "value": (paper.get("reason") or "—")[:200], "inline": False},
        ],
        "footer": {"text": f"{paper['source']} ・ {date_str}"},
    }
    payload = {
        "content": f"**🤖 AI Daily Digest — {date_str}**　今朝の1本が届きました　[{paper.get('topic_label', '')}]",
        "embeds": [embed],
        "components": [],
    }
    _send(payload)

    # 読むためのリンクを本文にも (embed のリンクに気づかない人向け)
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
    missing = [k for k in ("ANTHROPIC_API_KEY", "DISCORD_WEBHOOK_URL")
               if not os.environ.get(k)]
    if missing:
        print(f"[error] 環境変数が未設定: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # 日付は JST 基準 (GitHub Actions は UTC で動くため明示的に変換)
    # JST 日曜に実行した場合は翌月曜の日付で生成（週末に月曜分を先行作成）
    now_jst = datetime.now(JST)
    if now_jst.weekday() == 6:  # 日曜
        now_jst = now_jst + timedelta(days=1)
    date_str = now_jst.strftime("%Y-%m-%d")

    # 今日のトピックを決定 (偶数日: フィジカル AI / 奇数日: LLM)
    feeds, interests, topic_label = pick_topic_for_today()
    print(f"[info] 今日のトピック: {topic_label}", file=sys.stderr)

    items = fetch_entries(feeds)
    if not items:
        post_discord_empty(date_str)
        return

    # 過去 HISTORY_DAYS 日分の記事と被らないように除外
    seen_urls = extract_recent_paper_urls()
    fresh_items = filter_already_seen(items, seen_urls)
    if not fresh_items:
        print("[info] 新規論文なし。配信スキップ。", file=sys.stderr)
        post_discord_empty(date_str)
        return

    paper = select_one(fresh_items, interests)
    paper["topic_label"] = topic_label

    # レート制限のクールダウン (選定で使ったトークンの枠を解放させる)
    print("[info] レート制限回避のため 8秒待機...", file=sys.stderr)
    time.sleep(8)

    print("[info] 記事生成中... (モデル: %s)" % MODEL, file=sys.stderr)
    article = generate_article(paper)

    filename = save_html(article, date_str)
    post_to_discord(article, filename, paper, date_str)
    print("[info] 完了", file=sys.stderr)


if __name__ == "__main__":
    main()
