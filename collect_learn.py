#!/usr/bin/env python3
"""
collect_learn.py  —  学習コース収集フェーズ (APIキー不要)
=========================================================
AI 30日講座のカリキュラムを管理し、今日の学習トピックを
learn_today.json に書き出す。

  1. START_DATE から今日まで「平日のみ」カウントして day_number を決定
  2. day_number > TOTAL_DAYS なら skip=true (コース完走)
  3. 今日が土日 JST なら skip=true
  4. 当日のカリキュラム情報 + 参照URL を learn_today.json に出力

出力: learn_today.json (このスクリプトと同じディレクトリ)
"""

import os
import sys
import json
from datetime import date, datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEARN_JSON = os.path.join(BASE_DIR, "learn_today.json")

# コースの開始日 (JST) — 初回実行日に合わせて設定
START_DATE = date(2026, 6, 30)
TOTAL_DAYS = 30

# ---------------------------------------------------------------------------
# 30日カリキュラム定義
# ---------------------------------------------------------------------------
CURRICULUM = [
    # --- Week 1: 数学的基礎 ---
    {
        "week": "Week 1: 数学的基礎 ─ AIが動く土台",
        "title": "行列は「変換」だった ─ 線形代数の直感を身につける",
        "refs": [
            "https://en.wikipedia.org/wiki/Linear_map",
            "https://en.wikipedia.org/wiki/Matrix_(mathematics)",
            "https://en.wikipedia.org/wiki/Eigenvalues_and_eigenvectors",
            "https://en.wikipedia.org/wiki/Singular_value_decomposition",
        ],
    },
    {
        "week": "Week 1: 数学的基礎 ─ AIが動く土台",
        "title": "誤差の山を下る ─ 微分とバックプロパゲーションの数学",
        "refs": [
            "https://en.wikipedia.org/wiki/Backpropagation",
            "https://en.wikipedia.org/wiki/Chain_rule",
            "https://en.wikipedia.org/wiki/Automatic_differentiation",
        ],
    },
    {
        "week": "Week 1: 数学的基礎 ─ AIが動く土台",
        "title": "不確かさを測る ─ 確率・エントロピー・KL ダイバージェンス",
        "refs": [
            "https://en.wikipedia.org/wiki/Entropy_(information_theory)",
            "https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence",
            "https://en.wikipedia.org/wiki/Cross_entropy",
        ],
    },
    {
        "week": "Week 1: 数学的基礎 ─ AIが動く土台",
        "title": "どこへ進む？ ─ 勾配降下法と最適化アルゴリズムの数理",
        "refs": [
            "https://en.wikipedia.org/wiki/Gradient_descent",
            "https://en.wikipedia.org/wiki/Stochastic_gradient_descent",
            "https://en.wikipedia.org/wiki/Adam_(optimization_algorithm)",
        ],
    },
    {
        "week": "Week 1: 数学的基礎 ─ AIが動く土台",
        "title": "汎化とは何か ─ 統計的学習理論と PAC 学習の入口",
        "refs": [
            "https://en.wikipedia.org/wiki/Computational_learning_theory",
            "https://en.wikipedia.org/wiki/Probably_approximately_correct_learning",
            "https://en.wikipedia.org/wiki/Bias%E2%80%93variance_tradeoff",
        ],
    },
    # --- Week 2: ニューラルネットワーク基礎 ---
    {
        "week": "Week 2: ニューラルネットワーク基礎 ─ 層を重ねる意味",
        "title": "なぜ深さが必要か ─ 多層パーセプトロンと表現の階層性",
        "refs": [
            "https://en.wikipedia.org/wiki/Multilayer_perceptron",
            "https://en.wikipedia.org/wiki/Universal_approximation_theorem",
            "https://en.wikipedia.org/wiki/Depth_(artificial_neural_network)",
        ],
    },
    {
        "week": "Week 2: ニューラルネットワーク基礎 ─ 層を重ねる意味",
        "title": "非線形の魔法 ─ 活性化関数 ReLU・GELU・SiLU の数理",
        "refs": [
            "https://en.wikipedia.org/wiki/Rectifier_(neural_networks)",
            "https://en.wikipedia.org/wiki/Activation_function",
            "https://arxiv.org/abs/1606.08415",
        ],
    },
    {
        "week": "Week 2: ニューラルネットワーク基礎 ─ 層を重ねる意味",
        "title": "損失関数の設計思想 ─ クロスエントロピーはなぜ使われるのか",
        "refs": [
            "https://en.wikipedia.org/wiki/Loss_function",
            "https://en.wikipedia.org/wiki/Cross_entropy",
            "https://en.wikipedia.org/wiki/Maximum_likelihood_estimation",
        ],
    },
    {
        "week": "Week 2: ニューラルネットワーク基礎 ─ 層を重ねる意味",
        "title": "過学習と戦う ─ L1/L2 正則化・ドロップアウトの数学",
        "refs": [
            "https://en.wikipedia.org/wiki/Regularization_(mathematics)",
            "https://en.wikipedia.org/wiki/Dropout_(neural_networks)",
            "https://en.wikipedia.org/wiki/Overfitting",
        ],
    },
    {
        "week": "Week 2: ニューラルネットワーク基礎 ─ 層を重ねる意味",
        "title": "学習を安定させる ─ バッチ正規化・Layer Norm の仕組み",
        "refs": [
            "https://en.wikipedia.org/wiki/Batch_normalization",
            "https://en.wikipedia.org/wiki/Layer_normalization",
            "https://arxiv.org/abs/1502.03167",
        ],
    },
    # --- Week 3: 注意機構と Transformer ---
    {
        "week": "Week 3: Transformer ─ 現代 LLM の心臓部",
        "title": "すべての注意を向ける ─ Scaled Dot-Product Attention の数学",
        "refs": [
            "https://en.wikipedia.org/wiki/Attention_(machine_learning)",
            "https://arxiv.org/abs/1706.03762",
            "https://en.wikipedia.org/wiki/Softmax_function",
        ],
    },
    {
        "week": "Week 3: Transformer ─ 現代 LLM の心臓部",
        "title": "多様な視点で見る ─ Multi-Head Attention の設計と直感",
        "refs": [
            "https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
            "https://arxiv.org/abs/1706.03762",
            "https://en.wikipedia.org/wiki/Representation_learning",
        ],
    },
    {
        "week": "Week 3: Transformer ─ 現代 LLM の心臓部",
        "title": "Transformer の全体図 ─ Encoder・Decoder・FFN の役割分担",
        "refs": [
            "https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
            "https://arxiv.org/abs/1706.03762",
            "https://en.wikipedia.org/wiki/Feed-forward_neural_network",
        ],
    },
    {
        "week": "Week 3: Transformer ─ 現代 LLM の心臓部",
        "title": "順序を覚える ─ 位置エンコーディング・RoPE・ALiBi の数学",
        "refs": [
            "https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)#Positional_encoding",
            "https://arxiv.org/abs/2104.09864",
            "https://arxiv.org/abs/2108.12409",
        ],
    },
    {
        "week": "Week 3: Transformer ─ 現代 LLM の心臓部",
        "title": "Attention を速くする ─ FlashAttention と IO-Aware 計算の数理",
        "refs": [
            "https://arxiv.org/abs/2205.14135",
            "https://en.wikipedia.org/wiki/Memory_bandwidth",
            "https://en.wikipedia.org/wiki/Tiling_(computation)",
        ],
    },
    # --- Week 4: 事前学習と微調整 ---
    {
        "week": "Week 4: 事前学習と適応 ─ LLM を育てる技術",
        "title": "次のトークンを予測する ─ 言語モデルの事前学習と Perplexity",
        "refs": [
            "https://en.wikipedia.org/wiki/Language_model",
            "https://en.wikipedia.org/wiki/Perplexity",
            "https://en.wikipedia.org/wiki/N-gram",
        ],
    },
    {
        "week": "Week 4: 事前学習と適応 ─ LLM を育てる技術",
        "title": "大きいほど賢い？ ─ スケーリング則の数学と Neural Scaling Laws",
        "refs": [
            "https://en.wikipedia.org/wiki/Neural_scaling_law",
            "https://arxiv.org/abs/2001.08361",
            "https://arxiv.org/abs/2203.15556",
        ],
    },
    {
        "week": "Week 4: 事前学習と適応 ─ LLM を育てる技術",
        "title": "例を見せるだけで動く ─ In-Context Learning と Few-Shot の仕組み",
        "refs": [
            "https://en.wikipedia.org/wiki/In-context_learning_(natural_language_processing)",
            "https://arxiv.org/abs/2005.14165",
            "https://arxiv.org/abs/2202.12837",
        ],
    },
    {
        "week": "Week 4: 事前学習と適応 ─ LLM を育てる技術",
        "title": "少ない更新で大きな適応 ─ LoRA / PEFT の数学と低ランク近似",
        "refs": [
            "https://en.wikipedia.org/wiki/Low-rank_approximation",
            "https://arxiv.org/abs/2106.09685",
            "https://en.wikipedia.org/wiki/Singular_value_decomposition",
        ],
    },
    {
        "week": "Week 4: 事前学習と適応 ─ LLM を育てる技術",
        "title": "人間の好みから学ぶ ─ RLHF・PPO・DPO の数理",
        "refs": [
            "https://en.wikipedia.org/wiki/Reinforcement_learning_from_human_feedback",
            "https://arxiv.org/abs/2203.02155",
            "https://arxiv.org/abs/2305.18290",
        ],
    },
    # --- Week 5: 推論と評価 ---
    {
        "week": "Week 5: 推論と評価 ─ モデルを使いこなす技術",
        "title": "確率分布からトークンを選ぶ ─ Greedy・Sampling・Beam の数学",
        "refs": [
            "https://en.wikipedia.org/wiki/Beam_search",
            "https://en.wikipedia.org/wiki/Temperature_(language_models)",
            "https://en.wikipedia.org/wiki/Top-k_sampling",
        ],
    },
    {
        "week": "Week 5: 推論と評価 ─ モデルを使いこなす技術",
        "title": "考えてから答える ─ Chain-of-Thought 推論の仕組みと理論",
        "refs": [
            "https://en.wikipedia.org/wiki/Chain-of-thought_prompting",
            "https://arxiv.org/abs/2201.11903",
            "https://arxiv.org/abs/2205.01068",
        ],
    },
    {
        "week": "Week 5: 推論と評価 ─ モデルを使いこなす技術",
        "title": "どうやって賢さを測るか ─ BLEU・ROUGE・Perplexity の数学",
        "refs": [
            "https://en.wikipedia.org/wiki/BLEU",
            "https://en.wikipedia.org/wiki/ROUGE_(metric)",
            "https://en.wikipedia.org/wiki/Perplexity",
        ],
    },
    {
        "week": "Week 5: 推論と評価 ─ モデルを使いこなす技術",
        "title": "メモリを減らす ─ 量子化の数学：INT8・GPTQ・AWQ",
        "refs": [
            "https://en.wikipedia.org/wiki/Quantization_(machine_learning)",
            "https://arxiv.org/abs/2210.17323",
            "https://arxiv.org/abs/2306.00978",
        ],
    },
    {
        "week": "Week 5: 推論と評価 ─ モデルを使いこなす技術",
        "title": "過去の計算を再利用する ─ KV キャッシュの仕組みと最適化",
        "refs": [
            "https://en.wikipedia.org/wiki/Key-value_store",
            "https://arxiv.org/abs/2309.06180",
            "https://en.wikipedia.org/wiki/Cache_(computing)",
        ],
    },
    # --- Week 6: 発展トピック ---
    {
        "week": "Week 6: 発展と応用 ─ 研究の最前線へ",
        "title": "モデルの中を覗く ─ Mechanistic Interpretability と回路解析",
        "refs": [
            "https://en.wikipedia.org/wiki/Explainable_artificial_intelligence",
            "https://arxiv.org/abs/2211.00593",
            "https://transformer-circuits.pub/2021/framework/index.html",
        ],
    },
    {
        "week": "Week 6: 発展と応用 ─ 研究の最前線へ",
        "title": "画像もテキストも一緒に ─ マルチモーダルモデルの数理",
        "refs": [
            "https://en.wikipedia.org/wiki/Multimodal_learning",
            "https://arxiv.org/abs/2103.00020",
            "https://en.wikipedia.org/wiki/Vision_transformer",
        ],
    },
    {
        "week": "Week 6: 発展と応用 ─ 研究の最前線へ",
        "title": "ツールを呼び出す LLM ─ エージェント・関数呼び出しの設計",
        "refs": [
            "https://en.wikipedia.org/wiki/Intelligent_agent",
            "https://arxiv.org/abs/2210.03629",
            "https://arxiv.org/abs/2305.16291",
        ],
    },
    {
        "week": "Week 6: 発展と応用 ─ 研究の最前線へ",
        "title": "AI は安全か ─ アライメント・Constitutional AI・RLAIF の数理",
        "refs": [
            "https://en.wikipedia.org/wiki/AI_alignment",
            "https://arxiv.org/abs/2212.08073",
            "https://en.wikipedia.org/wiki/Reward_hacking",
        ],
    },
    {
        "week": "Week 6: 発展と応用 ─ 研究の最前線へ",
        "title": "30日間の総まとめ ─ LLM の設計哲学と研究者への道",
        "refs": [
            "https://arxiv.org/abs/2303.18223",
            "https://en.wikipedia.org/wiki/Large_language_model",
        ],
    },
]

assert len(CURRICULUM) == TOTAL_DAYS, f"カリキュラム日数が {len(CURRICULUM)} != {TOTAL_DAYS}"


# ---------------------------------------------------------------------------
# 平日カウント (土日をスキップして day_number を計算)
# ---------------------------------------------------------------------------

def count_weekdays(start: date, today: date) -> int:
    """start から today まで（両端含む）の平日数を返す。"""
    if today < start:
        return 0
    count = 0
    d = start
    while d <= today:
        if d.weekday() < 5:  # 0=月 … 4=金
            count += 1
        d += timedelta(days=1)
    return count


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    now_jst = datetime.now(JST)
    today = now_jst.date()
    date_str = today.strftime("%Y-%m-%d")

    # 土日はスキップ
    if today.weekday() >= 5:
        payload = {"date": date_str, "skip": True, "reason": "weekend"}
        with open(LEARN_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(json.dumps({"date": date_str, "skip": True}, ensure_ascii=False))
        return

    day_number = count_weekdays(START_DATE, today)

    if day_number > TOTAL_DAYS:
        payload = {"date": date_str, "skip": True, "reason": "course_complete",
                   "day_number": day_number, "total_days": TOTAL_DAYS}
        with open(LEARN_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(json.dumps({"date": date_str, "skip": True, "reason": "course_complete"},
                         ensure_ascii=False))
        return

    entry = CURRICULUM[day_number - 1]
    payload = {
        "date": date_str,
        "skip": False,
        "day_number": day_number,
        "total_days": TOTAL_DAYS,
        "week": entry["week"],
        "title": entry["title"],
        "refs": entry["refs"],
    }

    with open(LEARN_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[info] Day {day_number}/{TOTAL_DAYS}: {entry['title']}", file=sys.stderr)
    print(json.dumps({
        "date": date_str,
        "day_number": day_number,
        "total_days": TOTAL_DAYS,
        "week": entry["week"],
        "title": entry["title"],
        "learn_json": LEARN_JSON,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
