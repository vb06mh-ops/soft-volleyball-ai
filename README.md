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

## Cloudflare Pages へのデプロイ（無料・推奨）

スリープなし・世界規模の高速配信・DDoS/WAF防御つき。バックエンドは `functions/` のPages Functions（JavaScript）。

1. このリポジトリをGitHubに置く（済）
2. [Cloudflare](https://dash.cloudflare.com) に無料登録 → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
3. リポジトリ `soft-volleyball-ai` を選択
4. ビルド設定: フレームワーク=なし / ビルドコマンド=空 / 出力ディレクトリ=`/`（ルート）
5. **環境変数** に `GEMINI_API_KEY` = Google AI Studio の無料キー を追加
6. Deploy → `https://soft-volleyball-ai.pages.dev` で公開

### ローカルでCloudflare環境を再現
```bash
export GEMINI_API_KEY="あなたのキー"
npx wrangler pages dev . --port 8788
# → http://localhost:8788
```

## 構成（単一データソース）
- `index.html` … フロント（静的）
- `functions/api/*.js` … バックエンド（Gemini呼び出し・全プロンプト）
- `shoes.json` … シューズDB（**ここを編集するだけで推薦対象を更新**。フロント/バックの両方が参照）
- `server.py` … ローカル開発用のPython版（Cloudflareでは未使用）
