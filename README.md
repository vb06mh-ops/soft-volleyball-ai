# 🏐 ソフトバレー競技力研究所

ソフトバレーボール選手のための無料AI競技力診断アプリ。

**競技力 = 技術 × フィジカル × 回復 × 判断力 × 再現性**

ACWR（負荷管理）・睡眠研究・プライオメトリクス研究など最新スポーツ科学に基づき、
「努力不足」ではなく「回復不足」を見抜く11のAI分析モジュールを搭載。

## モジュール

1. 🔬 競技力総合診断（8項目・タイプ二つ名つき）
2. 😴 疲労・回復分析（身体疲労/神経疲労を区別）
3. ⬆️ ジャンプ力分析
4. 🎯 試合パフォーマンス分析
5. 🩺 怪我リスク分析（部位別）
6. ♾️ 競技寿命分析（5年/10年予測）
7. 📐 練習設計分析（過剰/適正/過少）
8. 👟 シューズ分析
9. 🧬 競技タイプ診断
10. 🏆 勝率向上システム
11. 📔 AI競技日誌（推移グラフ）

## 技術構成

- フロントエンド: HTML/CSS/JS（Chart.js, jsPDF）
- バックエンド: Python 標準ライブラリのみ（依存なし）
- AI: Google Gemini API（無料枠）

## ローカル起動

```bash
# Google AI Studio (https://aistudio.google.com/apikey) で無料キーを取得し
# api_key.txt に保存するか、環境変数 GEMINI_API_KEY を設定
python3 server.py
# → http://localhost:8080
```

## Renderへのデプロイ（無料）

1. このリポジトリをGitHubに置く
2. [Render](https://render.com) にGitHubでログイン
3. New + → Blueprint → このリポジトリを選択
4. 環境変数 `GEMINI_API_KEY` に Google AI Studio の無料キーを設定
5. デプロイ完了 → `https://soft-volleyball-ai.onrender.com`
