#!/usr/bin/env python3
"""
digest_learn.py  —  学習記事生成フェーズ
=========================================
collect_learn.py が出力した learn_today.json を読み込み、
Claude API を呼び出して深掘り学習記事を article_learn.json に書き出す。

処理の流れ:
  1. learn_today.json を読む
  2. skip=true なら article_learn.json にそのままスキップ情報を書いて終了
  3. Claude API でカリキュラムトピックの解説記事を JSON 生成
  4. article_learn.json に書き出す (次の publish_learn.py が読む)

環境変数:
  ANTHROPIC_API_KEY  (必須)
  MODEL              (任意) デフォルト claude-sonnet-4-6
"""

import os
import sys
import json
import time

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = os.environ.get("MODEL", "claude-sonnet-4-6")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEARN_JSON = os.path.join(BASE_DIR, "learn_today.json")
ARTICLE_LEARN_JSON = os.path.join(BASE_DIR, "article_learn.json")


# ---------------------------------------------------------------------------
# Claude 呼び出し
# ---------------------------------------------------------------------------

def call_claude(system, user, max_tokens=12000, retries=4):
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
        if s != -1 and (a == -1 or s < a):
            return json.loads(raw[s:e + 1])
        return json.loads(raw[a:b + 1])


# ---------------------------------------------------------------------------
# 記事生成プロンプト
# ---------------------------------------------------------------------------

ARTICLE_SPEC = r"""
あなたは AI 研究の教育者です。読者は「これから AI の R&D 部署で働く新人研究者」。
目標は「数学・理論まで深く、しかし親切に」。数式や擬似コード、たとえ話を使い、
専門用語は噛み砕き、背景から応用まで一貫したストーリーで解説してください。

指定されたカリキュラムトピックの学習記事を、以下の JSON 形式で出力してください。
**JSON のみを出力**し、前後に説明や ``` を付けないこと。

全体構造:
{
  "headline": "魅力的で正確な日本語タイトル (トピックを言い換えてもよい)",
  "tags": "#AI30日講座 #(内容に応じたタグ 3〜5個)",
  "subtitle": "DAY N ・ (今週のテーマ名)",
  "week": "Week X: テーマ名",
  "blocks": [ ...コンテンツブロックの配列... ]
}

blocks に使えるブロック:
- 見出し:        {"type":"h2","n":"1","text":"見出し文"}
- 小見出し:      {"type":"h3","text":"小見出し"}
- 段落:          {"type":"p","text":"本文。**強調**と[[専門用語|短い解説]]が使える"}
- 引用(主張):    {"type":"pull","text":"核心となる一文"}
- 数値ハイライト: {"type":"stats","items":[{"v":"値","k":"説明"},...]}  (2〜3個)
- 手順/箇条:     {"type":"steps","items":[{"si":"STEP 1","text":"..."},...]}
- ヒント箱:      {"type":"tip","label":"💡 R&Dでよく出る考え方","text":"..."}
- 補足箱:        {"type":"note","label":"⚙️ ひとことメモ","text":"..."}
- 数式ブロック:  {"type":"tex_block","tex":"LaTeX 数式","cap":"説明キャプション","derive":[{"label":"変形","tex":"..."}]}
- 擬似コード:    {"type":"code","cap":"説明","lines":[{"no":"1","indent":0,"tokens":[{"t":"plain","s":"code"}]}]}

tex_block のルール:
- "tex": KaTeX で表示できる LaTeX 数式 (displayMode)。
- "cap": 数式を 1 行で説明するキャプション (例: "Scaled Dot-Product Attention の計算")。
- "derive": 数式の変形ステップ。各要素は {"label": "変形の意味", "tex": "LaTeX 数式"}。

専門用語の扱い:
- [[用語|15〜40 字程度のやさしい解説]] の形式を使う。
- 1 段落あたり多くて 2 個まで。

記事の構成指針 (目安):
1. 導入 — このトピックがなぜ重要か。身近なたとえで問いを立てる。
2. 数学的基礎 — 数式を tex_block で丁寧に展開。変形の意味まで解説。
3. 直感・視覚的理解 — たとえ話・図の説明で本質をつかむ。
4. 深掘り (h3 複数) — 重要な要素技術を分解して解説。
5. LLM/AI への接続 — 現代の AI 研究でどう使われているか。
6. 実装のヒント (code, tip, note を活用)。
7. まとめ・次につながるひとこと。

文章は丁寧に。全体で 2500〜4000 字程度。数式は積極的に使う。
"""


def generate_article(curriculum, retries=3):
    refs_text = "\n".join(f"- {url}" for url in curriculum.get("refs", []))
    user = f"""以下のカリキュラムトピックについて学習記事を JSON で作成してください。

トピック: {curriculum['title']}
今週のテーマ: {curriculum['week']}
DAY: {curriculum['day_number']} / {curriculum['total_days']}
参考 URL (内容の参照に使ってください):
{refs_text}

数式は tex_block を使い、重要な定義・定理・アルゴリズムを丁寧に展開してください。
"""
    last_err = None
    for attempt in range(retries):
        raw = call_claude(ARTICLE_SPEC, user, max_tokens=14000)
        try:
            return parse_json(raw)
        except (ValueError, KeyError) as e:
            last_err = e
            print(f"[warn] JSON パース失敗 (試行 {attempt + 1}/{retries}): {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(5)
    raise RuntimeError(f"記事 JSON のパースが {retries} 回失敗: {last_err}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if not ANTHROPIC_API_KEY:
        print("[error] 環境変数 ANTHROPIC_API_KEY が未設定", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(LEARN_JSON):
        print(f"[error] {LEARN_JSON} が見つかりません。先に collect_learn.py を実行してください。",
              file=sys.stderr)
        sys.exit(1)

    with open(LEARN_JSON, encoding="utf-8") as f:
        curriculum = json.load(f)

    date_str = curriculum.get("date", "")

    if curriculum.get("skip"):
        reason = curriculum.get("reason", "skip")
        print(f"[info] skip ({reason}) — article_learn.json にスキップ情報を書き出す", file=sys.stderr)
        with open(ARTICLE_LEARN_JSON, "w", encoding="utf-8") as f:
            json.dump({"date": date_str, "skip": True, "reason": reason}, f,
                      ensure_ascii=False, indent=2)
        return

    print(f"[info] 記事生成中... DAY {curriculum['day_number']}: {curriculum['title']}",
          file=sys.stderr)
    print(f"[info] モデル: {MODEL}", file=sys.stderr)

    article = generate_article(curriculum)

    # collect_learn.py のメタデータをマージ
    article["date"] = date_str
    article["day_number"] = curriculum["day_number"]
    article["total_days"] = curriculum["total_days"]
    article["week"] = curriculum.get("week", article.get("week", ""))
    article["course"] = {
        "title": curriculum["title"],
        "week": curriculum.get("week", ""),
        "level": "基礎〜中級",
    }

    with open(ARTICLE_LEARN_JSON, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

    print(f"[info] article_learn.json 書き出し完了: {article.get('headline', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()
