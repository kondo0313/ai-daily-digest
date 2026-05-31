# AI Daily Digest

毎朝 arXiv から AI 論文を1本選び、**新人研究者向けに「やさしく・でも技術まで」深掘りした記事**を
Claude が自動生成。note 風の HTML にして GitHub Pages に公開し、Discord にカード＋リンクで届けます。

```
arXiv収集 → Claudeが1本選定 → Claudeが深掘り記事を生成
  → note風HTMLにしてGitHub Pagesへ公開 → Discordにカード＋リンク
        ↑ GitHub Actions が毎朝 cron で全自動実行 (サーバー不要)
```

毎朝 Discord に「📄 今朝の1本」が届き、リンクを開くと擬似コード・数式・図解つきの
じっくり読める解説記事が表示されます。過去記事はアーカイブに自動で溜まります。

---

## ファイル構成

| ファイル | 役割 | 触る必要 |
|---|---|---|
| `digest.py` | 本体。収集・選定・記事生成・配信を統括 | 興味設定だけ |
| `template.py` | note風デザインのHTMLテンプレート | 基本不要 |
| `.github/workflows/daily.yml` | 毎朝の自動実行スケジュール | 時刻変更時のみ |
| `requirements.txt` | 依存パッケージ | 不要 |
| `docs/` | 生成された記事の公開フォルダ(自動で増える) | 不要 |

---

## セットアップ手順 (全部で30分くらい)

鍵を3つ用意 → GitHubに置く → 設定を入れる、の3段階です。
**鍵は誰にも渡さず、自分でGitHubの金庫(Secrets)に入れます。**

### 手順1. Discord Webhook を作る (5分)

1. 通知を受け取りたい Discord チャンネルを開く
2. チャンネル名の横の ⚙️ →「連携サービス」→「ウェブフックを作成」
3. 「ウェブフックURLをコピー」 → このURLを後で使う(鍵その1)

### 手順2. Anthropic API キーを取る (10分)

1. https://console.anthropic.com にログイン
2. 「API Keys」→「Create Key」でキー発行 → コピー(鍵その2)
3. 「Billing」からクレジットを購入(先払い式なので使いすぎる心配なし)
   - 1,000円ほど入れておけば数ヶ月もちます
   - 「残高が減ったら通知」も設定しておくと安心

### 手順3. GitHub にリポジトリを作って push (10分)

1. GitHub で新しいリポジトリを作成(private 推奨)
2. このフォルダを push:
   ```bash
   git init
   git add .
   git commit -m "init ai-daily-digest"
   git branch -M main
   git remote add origin https://github.com/あなた/ai-daily-digest.git
   git push -u origin main
   ```

### 手順4. Secrets と変数を登録する (5分)

リポジトリの **Settings → Secrets and variables → Actions** で登録します。

**Secrets タブ**(「New repository secret」)で2つ:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | 手順2のキー |
| `DISCORD_WEBHOOK_URL` | 手順1のURL |

**Variables タブ**(「New repository variable」)で1つ:

| Name | Value |
|------|-------|
| `SITE_BASE_URL` | `https://あなたのID.github.io/ai-daily-digest` |

※ SITE_BASE_URL は Discord に貼る記事リンクの基底です。次の手順5でPagesを有効にすると、このURLで公開されます。

### 手順5. GitHub Pages を有効にする (3分)

1. リポジトリの **Settings → Pages**
2. 「Build and deployment」の Source を「Deploy from a branch」に
3. Branch を **main**、フォルダを **/docs** に設定して Save
4. 数分後、`https://あなたのID.github.io/ai-daily-digest/` で記事が見られるようになる

### 手順6. 動作確認 (3分)

1. **Actions** タブ →「AI Daily Digest」→「Run workflow」で手動実行
2. 数分待つと Discord に「今朝の1本」が届く
3. リンクを開いて記事が表示されれば成功 🎉

以降は毎朝7時(日本時間)に全自動で動きます。

---

## カスタマイズ

### 興味の方向を変える(一番よく触る場所)
`digest.py` 上部の `INTERESTS` を書き換える。ここが選定の心臓部。
例:「マルチモーダル中心にしたい」「強化学習は除きたい」など自由に。

### 情報ソースを足す
`digest.py` の `FEEDS` に RSS を追加。研究ブログなども足せる。

### 配信時刻を変える
`.github/workflows/daily.yml` の cron。UTC 表記なので JST から -9 時間。
- 朝7時(JST) → `"0 22 * * *"` (前日 UTC 22:00) ← 現在の設定
- 朝9時(JST) → `"0 0 * * *"`

### モデルを変える
`daily.yml` の `MODEL`。既定は最高品質の `claude-opus-4-8`。
コストを抑えたいなら `claude-sonnet-4-6` に変更可(記事の質は少し下がる)。

### 記事の構成・トーンを変える
`digest.py` の `ARTICLE_SPEC`(Claude への指示)を編集。
「たとえ話を減らして密度を上げる」「限界の章を厚く」など、ここで調整できる。

### デザインを変える
`template.py` の `STYLE`(CSS)。色やフォントを変えられる。

---

## コスト目安

- **GitHub Actions / Pages**: 無料枠内(private でも月2000分の枠に対し1日数分)
- **Claude API**: 1日 = 選定1回 + 記事生成1回。
  - Opus 使用時: **1日 15〜25円程度 / 月 500〜800円**
  - Sonnet に変更すると: 月 150〜250円程度

止めたいときは Actions タブで「Disable workflow」。設定はそのまま残り、いつでも再開可。

---

## ローカルで試す

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export SITE_BASE_URL=""   # ローカルなら空でOK
python digest.py
# docs/ に当日のHTMLが生成される。ブラウザで開いて確認できる。
```

---

## 仕組みの補足

- Claude には記事を「構造化された設計図(JSON)」として書かせ、それを `template.py` が
  確定デザインの HTML に変換します。これによりデザインが毎朝安定して再現されます。
- 擬似コードは行番号・インデント縦線・処理の節目バッジつきで描画されます。
- 記事内の数値はアブストラクトに基づくよう指示していますが、AI生成物なので
  重要な数字は原文(各記事の「原文 →」リンク)で確認する習慣をつけると安心です。
