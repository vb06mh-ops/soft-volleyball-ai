#!/usr/bin/env python3
"""
ソフトバレー競技力研究所 - バックエンドサーバー v2.0
10モジュール対応
"""
import json
import os
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request

# ─── セキュリティ設定 ───
MAX_BODY_SIZE = 100_000          # リクエスト上限 100KB
RATE_LIMIT_PER_MIN = 15          # 1IPあたり 15リクエスト/分
MAX_FIELD_LEN = 400              # 入力1項目の最大文字数
MAX_CHAT_MESSAGES = 30           # チャット履歴の上限
_rate_log = {}                   # IP別アクセス記録

def is_rate_limited(ip):
    now = time.time()
    hits = [t for t in _rate_log.get(ip, []) if now - t < 60]
    if len(hits) >= RATE_LIMIT_PER_MIN:
        _rate_log[ip] = hits
        return True
    hits.append(now)
    _rate_log[ip] = hits
    # メモリ肥大防止
    if len(_rate_log) > 10000:
        _rate_log.clear()
    return False

def sanitize_data(d):
    """入力データを安全な形に正規化（文字数制限・型強制）"""
    if not isinstance(d, dict):
        return {}
    return {str(k)[:50]: str(v)[:MAX_FIELD_LEN] for k, v in list(d.items())[:60]}

PORT = int(os.environ.get("PORT", 8080))  # Render等のホスティングはPORT環境変数を指定してくる
GEMINI_MODEL = "gemini-2.5-flash"  # Google の無料AIモデル

def _load_api_key():
    """APIキーを 環境変数(GEMINI_API_KEY) → api_key.txt の順で読み込む"""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    keyfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if os.path.exists(keyfile):
        with open(keyfile, "r") as f:
            return f.read().strip()
    return ""

API_KEY = _load_api_key()

# ─────────────────────────────────────────────
# ベースシステムプロンプト
# ─────────────────────────────────────────────
BASE_PROMPT = """あなたは「ソフトバレー競技力研究所」の専属AIアナリストです。

核心思想：
- 競技力 = 技術 × フィジカル × 回復 × 判断力 × 再現性
- 努力不足より回復不足を優先的に疑う
- 表面的症状ではなく根本原因を探る
- ソフトバレー特化（ボールが軽い・ラリーが続く・再現性重視）
- 練習量増加だけを提案しない
- 感情論禁止。データと根拠で語る

科学的根拠（分析に必ず活用すること）：
- ACWR（急性:慢性負荷比）: 直近1週の負荷÷直近4週平均負荷。0.8〜1.3が安全圏、1.5超で怪我リスク急増。負荷は週10%以内で漸増
- sRPE法: 主観的運動強度(RPE 0-10)×練習時間で負荷を定量化。主観データは科学的に有効なモニタリング手段
- フィットネス-疲労理論: パフォーマンス＝体力−疲労。試合前は負荷を落とし疲労だけを抜くと最高の準備状態になる
- 睡眠研究: 睡眠8時間未満の選手は怪我リスク約1.7倍。アスリート推奨は7〜9時間。運動スキルの記憶定着も睡眠中に起こる
- ジャンプ研究(Markovic 2007等): プライオメトリクスは垂直跳びを有意に向上。筋力トレーニングとの併用が単独より効果的
- ソフトバレー競技特性: ボールが軽く反発が強い→強打よりコントロール・正確性が得点に直結。サーブは威力より狙いと安定。守備とラリー継続力が勝敗を決める

伝え方：
- 専門用語は必ず一言で噛み砕く（例:「ACWR=急に練習を増やしすぎていないかの指標」）
- 根拠を添えると納得感が生まれる。「〜という研究があります」を適度に使う
- 40〜60代にも伝わる平易な日本語で"""

# ─────────────────────────────────────────────
# モジュール別プロンプト
# ─────────────────────────────────────────────
MODULE_PROMPTS = {

"diagnose": BASE_PROMPT + """

評価項目（各100点）：技術・フィジカル・回復・判断力・練習設計・再現性・怪我リスク・将来性

必ず以下のJSON形式のみで返答（コードブロック不要）：
{
  "scores": {"technical":75,"physical":68,"recovery":45,"judgment":72,"training_design":60,"reproducibility":70,"injury_risk":65,"potential":80},
  "total_score": 67,
  "competitive_type": "回復不足型",
  "competitive_type_nickname": "眠れる獅子",
  "competitive_type_description": "能力はあるが回復が追いついていない選手",
  "national_comparison": "全国平均70点に対し...",
  "strengths": ["強み1","強み2","強み3","強み4","強み5"],
  "weaknesses": ["弱み1","弱み2","弱み3","弱み4","弱み5"],
  "bottleneck": "根本的なボトルネック分析...",
  "top_priority": "最優先改善ポイント...",
  "plan_4weeks": ["週1:...","週2:...","週3:...","週4:..."],
  "plan_3months": ["1ヶ月目:...","2ヶ月目:...","3ヶ月目:..."],
  "prediction_1year": "1年後の予測...",
  "daily_habits": ["今日から毎日できる習慣1(15文字以内・具体的・測定可能)","習慣2","習慣3"],
  "scientific_basis": "この診断の根拠となる理論・研究を2〜3個、平易な言葉で説明(150字程度)",
  "ai_analysis": "500字程度の詳細分析..."
}

competitive_type_nickname は16Personalities風の覚えやすくシェアしたくなる二つ名(例:眠れる獅子/コートの司令塔/不屈の壁/静かな狙撃手)。""",

"fatigue": BASE_PROMPT + """

疲労・回復分析の専門家として評価する。
身体疲労・神経疲労を区別して評価。

必ず以下のJSON形式のみで返答：
{
  "body_fatigue_score": 72,
  "neuro_fatigue_score": 85,
  "recovery_score": 35,
  "overwork_risk": "高",
  "fatigue_type": "神経疲労優位型",
  "headline": "神経疲労が深刻。すぐに回復対策が必要",
  "cause_analysis": "原因の詳細分析（200字）",
  "immediate_actions": ["今日すること1","今日すること2","今日すること3"],
  "week_recovery_plan": ["月:...","火:...","水:...","木:...","金:...","土:...","日:..."],
  "warning_signs": ["注意すべきサイン1","注意すべきサイン2"],
  "performance_impact": "疲労がパフォーマンスに与える影響の説明",
  "recovery_timeline": "完全回復までの目安期間と理由",
  "scientific_basis": "ACWR・sRPE・睡眠研究など、この評価の根拠を平易に説明(150字程度)"
}

評価にはACWRの考え方(急に練習量を増やしていないか)とフィットネス-疲労理論を必ず使うこと。""",

"jump": BASE_PROMPT + """

ジャンプ力分析の専門家として評価。
ジャンプ力不足の真因を特定する。筋力不足・体重・疲労・技術・神経疲労を区別。

必ず以下のJSON形式のみで返答：
{
  "jump_type": "筋力不足型",
  "current_level": "平均以下",
  "main_limiter": "最大筋力不足（スクワット強化が最優先）",
  "limiters": [
    {"factor":"最大筋力","impact":40,"score":45,"description":"..."},
    {"factor":"体重・体脂肪","impact":25,"score":60,"description":"..."},
    {"factor":"爆発力・神経系","impact":20,"score":55,"description":"..."},
    {"factor":"助走・技術","impact":10,"score":70,"description":"..."},
    {"factor":"疲労状態","impact":5,"score":80,"description":"..."}
  ],
  "target_jump": 55,
  "improvement_potential": 12,
  "plan_4weeks": [
    {"week":1,"focus":"筋力基盤","training":["スクワット3×5 75%","RDL3×8"],"volume":"中","note":"..."},
    {"week":2,"focus":"強度上昇","training":["スクワット4×4 80%","ボックスジャンプ3×5"],"volume":"高","note":"..."},
    {"week":3,"focus":"爆発力","training":["スクワット3×3 85%","デプスジャンプ3×5"],"volume":"高","note":"..."},
    {"week":4,"focus":"回復・確認","training":["軽量スクワット","垂直跳び測定"],"volume":"低","note":"..."}
  ],
  "key_exercises": [
    {"name":"スクワット","sets":"4×5","intensity":"80%1RM","reason":"最大筋力向上"},
    {"name":"ボックスジャンプ","sets":"4×5","intensity":"最大努力","reason":"爆発力訓練"},
    {"name":"シングルレッグRDL","sets":"3×10","intensity":"軽〜中","reason":"臀部・ハムストリング強化"}
  ],
  "nutrition_tip": "ジャンプ力向上のための栄養アドバイス",
  "common_mistakes": ["よくある間違い1","よくある間違い2","よくある間違い3"],
  "scientific_basis": "プライオメトリクス研究(Markovic 2007等)・筋力併用の根拠を平易に説明(150字程度)"
}

プランにはプライオメトリクス(ジャンプ系トレ)と筋力トレの併用を原則とし、年齢が高い場合は着地衝撃の少ない段階から始めること。""",

"match": BASE_PROMPT + """

試合パフォーマンス分析の専門家として評価。
練習でできるのに試合でできない原因を分析。

必ず以下のJSON形式のみで返答：
{
  "player_type": "練習型選手",
  "type_description": "練習では高いパフォーマンスを発揮するが試合で実力が出ない選手",
  "practice_vs_match_gap": 28,
  "main_factor": "メンタル・プレッシャー管理",
  "factor_breakdown": [
    {"name":"技術再現性","score":72,"impact":"中","description":"..."},
    {"name":"判断力","score":58,"impact":"高","description":"..."},
    {"name":"メンタル","score":45,"impact":"最高","description":"..."},
    {"name":"戦術理解","score":65,"impact":"中","description":"..."},
    {"name":"疲労管理","score":70,"impact":"低","description":"..."}
  ],
  "match_analysis": "試合パフォーマンスの詳細分析（200字）",
  "error_pattern": "ミスのパターン分析",
  "mental_strategy": ["メンタル戦略1","メンタル戦略2","メンタル戦略3"],
  "tactical_advice": ["戦術アドバイス1","戦術アドバイス2","戦術アドバイス3"],
  "pre_match_routine": "試合前ルーティンの提案",
  "improvement_plan": ["改善プラン1","改善プラン2","改善プラン3"]
}""",

"injury": BASE_PROMPT + """

怪我リスク分析の専門家として評価。
年齢・練習量・既往歴・疲労・筋力バランスから危険箇所を特定。

必ず以下のJSON形式のみで返答：
{
  "overall_risk": "中",
  "overall_risk_score": 52,
  "body_parts": [
    {"part":"膝","risk":"高","score":72,"reason":"スクワット不足と膝外反傾向","prevention":["ヒンジパターン強化","VMO強化","ジャンプ着地技術改善"]},
    {"part":"足首","risk":"中","score":48,"reason":"...","prevention":["..."]},
    {"part":"腰","risk":"中","score":55,"reason":"...","prevention":["..."]},
    {"part":"肩","risk":"低","score":30,"reason":"...","prevention":["..."]},
    {"part":"手首・指","risk":"低","score":25,"reason":"...","prevention":["..."]}
  ],
  "highest_risk_part": "膝",
  "immediate_concerns": ["今すぐ対処すべきこと1","今すぐ対処すべきこと2"],
  "lifestyle_risks": ["生活習慣リスク1","生活習慣リスク2"],
  "prevention_program": ["予防プログラム1","予防プログラム2","予防プログラム3","予防プログラム4"],
  "when_to_see_doctor": "医師への相談が必要なサイン",
  "risk_timeline": "現在の状態が続いた場合のリスク予測",
  "scientific_basis": "睡眠8時間未満で怪我リスク約1.7倍などの研究的根拠を平易に説明(150字程度)"
}

睡眠時間が短い場合は必ず睡眠-怪我リスクの研究(8時間未満で約1.7倍)を反映させること。""",

"longevity": BASE_PROMPT + """

競技寿命分析の専門家として評価。
ソフトバレーは60代70代まで競技可能。長期的視点で評価。

必ず以下のJSON形式のみで返答：
{
  "longevity_score": 78,
  "estimated_peak_age": 52,
  "competitive_years_remaining": 18,
  "trajectory": "上昇中",
  "prediction_5years": {"score":82,"level":"安定・成長","key_factor":"筋力維持が鍵"},
  "prediction_10years": {"score":75,"level":"高水準維持可能","key_factor":"回復力の低下に注意"},
  "age_advantage": ["年齢的強み1","年齢的強み2","年齢的強み3"],
  "age_risks": ["年齢的リスク1","年齢的リスク2","年齢的リスク3"],
  "longevity_keys": [
    {"factor":"睡眠・回復","importance":"最高","current":"不十分","action":"7時間確保を最優先"},
    {"factor":"筋力維持","importance":"高","current":"普通","action":"週2回の筋トレ継続"},
    {"factor":"柔軟性","importance":"高","current":"不明","action":"毎日10分ストレッチ"},
    {"factor":"体重管理","importance":"中","current":"良好","action":"現状維持"}
  ],
  "decade_strategy": {
    "now": "現在やるべきこと",
    "5years": "5年後に向けた準備",
    "10years": "10年後を見据えた基盤"
  },
  "role_evolution": "競技スタイルの進化提案（年齢とともに）",
  "inspiration": "長期競技継続への激励メッセージ"
}""",

"training": BASE_PROMPT + """

練習設計分析の専門家として評価。
努力量ではなく努力効率を見る。過少・適正・過剰を判定。

必ず以下のJSON形式のみで返答：
{
  "training_status": "過剰練習気味",
  "efficiency_score": 55,
  "volume_score": 75,
  "quality_score": 45,
  "balance": {
    "practice": {"actual":70,"optimal":60,"status":"多い"},
    "rest": {"actual":20,"optimal":30,"status":"少ない"},
    "match": {"actual":5,"optimal":10,"status":"少ない"},
    "weight_training": {"actual":0,"optimal":15,"status":"なさすぎ"},
    "sleep": {"actual":50,"optimal":70,"status":"不足"}
  },
  "verdict": "練習量より練習の質が問題。疲労を抱えた状態での練習は成長しない",
  "bottleneck": "練習設計の最大のボトルネック",
  "optimal_week": {
    "mon": "バレー練習（技術）2h",
    "tue": "ウェイトトレーニング1h",
    "wed": "休養または軽いストレッチ",
    "thu": "バレー練習（戦術）2h",
    "fri": "ウェイトトレーニング1h",
    "sat": "試合または強度高い練習",
    "sun": "完全休養"
  },
  "immediate_changes": ["今すぐ変えること1","今すぐ変えること2","今すぐ変えること3"],
  "quality_tips": ["質を上げるコツ1","質を上げるコツ2","質を上げるコツ3"],
  "periodization": "ピリオダイゼーション（強弱サイクル）の提案",
  "scientific_basis": "ACWR(0.8〜1.3が安全圏)・週10%漸増ルールなどの根拠を平易に説明(150字程度)"
}

過剰/過少の判定にはACWRの考え方を必ず使い、「急に増やしすぎ」を最重要リスクとして扱うこと。""",

"shoes": BASE_PROMPT + """

あなたは経験豊富なスポーツシューズフィッター兼バレー/バスケシューズのレビュアーです。
プロのフィッターとYouTubeの人気レビュアーが実際に使う選定基準で、その人に最適な「具体的な現行商品」を推薦します。

【プロのフィッターが見る選定基準】
1. 足型適合: 足長(cm)＋足囲(ワイズ)＋甲の高さ。日本人は幅広・甲高が多く2E〜4E向き。ナイキ等の海外ブランドは細身なので幅広の人はハーフ〜1サイズ上やワイド版を検討
2. ヒールカウンター(かかとの硬さ)＝足首の安定＝捻挫予防。捻挫癖・回内(内側に倒れる)の人はサポート/安定性重視
3. クッション(着地衝撃の吸収)とコート感覚(接地の素早さ)はトレードオフ。体重が重い・ジャンプが多い人はクッション厚め、素早さ重視は薄め
4. グリップ(アウトソール)＝止まる・切り返し。木床はヘリンボーン、化学床(リノリウム)は専用ラバー
5. カット: ローカット=軽快/自由、ミドル・ハイ=足首ホールド。捻挫癖があればミドル以上
6. 重量: 軽量=素早さ、重め=安定・保護
7. サイズの鉄則: 夕方に試着、つま先に5〜10mmゆとり、かかとは密着

【現行シューズDB(2025-2026年に購入可能な代表モデル。ここから最適なものを選ぶこと)】
■バレーボール用
- ミズノ ウエーブライトニングZ8: 軽量オールラウンドの定番No.1。反発と安定のバランス◎。中〜上級。約1.4万円。幅は2E標準
- ミズノ ウエーブモメンタム3: クッション(MIZUNO ENERZY)と安定性。ジャンプ着地が多い人・初中級・体重重めに最適。約1.4万円
- ミズノ サイクロンスピード4: 軽量で価格が安くフィット良好。初中級のコスパ最強。約8千〜1万円
- ミズノ サンダーブレイド3: 軽量エントリー。初心者向けコスパ。約8千円
- アシックス スカイエリートFF2: トップ選手向け。軽量・高反発(FF)。上級〜全国・スパイカー。約1.7万円
- アシックス メタライズ: ジャンプ反発特化のハイエンド。パワースパイカー上級。約2万円〜
- アシックス ネットバーナーバリスティックFF3: 安定オールラウンド。中級。約1.4万円
- アシックス アップコート5: 多用途エントリー。初心者・室内全般のコスパ。約6〜7千円
- ヨネックス パワークッションエアラスダッシュ: 軽量クッション。約1.3万円

■バスケットボール用(バレーにも適合。ジャンプ・切り返しに強い)
- ナイキ サブリナ2: 軽量で万能、グリップ・反発のバランス◎、ユニセックスで人気・コスパ優秀。素早い動き重視の万能型。約1.2万円
- ナイキ ジアニス(イモータル系): 軽量・強グリップ・低価格。オールラウンド/ジャンプ。約1万円。コスパ◎
- ナイキ レブロン ウィットネス: 厚いクッションで着地保護。体重が重い人・パワー型・ジャンプ多い人。約1万円(本家レブロンは約2万円)
- ナイキ ジャ(Ja Morant系): 軽量・反発・グリップ。素早い切り返し・守備的。約1.3万円
- ナイキ G.T. カット: 低重心でコート感覚とグリップ最強。素早い守備・切り返し。上級向け。約1.8万円
- ナイキ G.T. ジャンプ: ジャンプ反発に特化。スパイカー・ジャンプ重視。約2万円
- アディダス デイム(Lillard系): 安定・万能・コスパ。約1万円
- アンダーアーマー カリー系: 軽量・強グリップ。素早い動き。約1.3〜1.7万円
- アシックス NOVA/アンプリファイ: 日本人の足型に合うバスケ用。幅広の人。約1万円

注意: バスケシューズはバレーにも使えるが、海外ブランドは幅が細めなので幅広・甲高の人はサイズ調整を案内すること。体育館の床で滑らないアウトソールか確認も添える。

ユーザーが「バレー専用がいい」を選んだ場合はバスケ用を推薦しない。価格は必ずユーザーの予算帯を尊重する。

必ず以下のJSON形式のみで返答：
{
  "shoe_type": "あなたのシューズタイプ(例:軽量オールラウンド型/着地保護重視型/グリップ特化型)",
  "your_foot_profile": "足型と動きの総合プロフィール(120字程度。幅広/甲高ならその助言も)",
  "priority_profile": [
    {"feature":"グリップ","priority":1,"score":5,"reason":"急激な方向転換が多いため最重要"},
    {"feature":"クッション","priority":2,"score":4,"reason":"..."},
    {"feature":"足首の安定","priority":3,"score":4,"reason":"..."},
    {"feature":"軽量性","priority":4,"score":3,"reason":"..."},
    {"feature":"反発性","priority":5,"score":3,"reason":"..."},
    {"feature":"フィット(幅)","priority":6,"score":3,"reason":"..."}
  ],
  "top_pick": {
    "name":"ミズノ ウエーブモメンタム3",
    "brand":"ミズノ",
    "category":"バレーボール用",
    "price_range":"約14,000円",
    "match_score":92,
    "why":"なぜこの人に最適なのかを具体的に(150字程度。足型・体重・プレースタイル・予算と結びつけて)",
    "features":["MIZUNO ENERZYで着地衝撃を吸収","2Eで日本人の足に合う","安定性が高く捻挫しにくい"],
    "best_for":"ジャンプ着地が多く膝を守りたい中級者",
    "search_query":"ミズノ ウエーブモメンタム3 バレーボールシューズ"
  },
  "alternatives": [
    {"name":"アシックス スカイエリートFF2","brand":"アシックス","category":"バレーボール用","price_range":"約17,000円","match_score":85,"why":"...(80字)","features":["軽量","高反発"],"best_for":"より軽さと反発が欲しい人","search_query":"アシックス スカイエリートFF2"},
    {"name":"ナイキ サブリナ2","brand":"ナイキ","category":"バスケットボール用","price_range":"約12,000円","match_score":80,"why":"...(80字)","features":["万能","コスパ"],"best_for":"バスケ用も試したい素早い動きの人","search_query":"ナイキ サブリナ2 バスケットボールシューズ"}
  ],
  "sizing_advice": "この人の足サイズ・足幅を踏まえた具体的なサイズ選びの助言(例:幅広なので普段26.5cmなら同モデルは27cmかワイド版を)",
  "fit_advice": "試着・フィッティングのアドバイス",
  "what_to_avoid": ["この人が避けるべき特性1","避けるべき特性2"],
  "replacement_timing": "交換の目安",
  "reviewer_tip": "YouTubeレビュアーがよく言う実用的なワンポイント(例:紐は結び直して足首をしっかり固定すると安定感が段違い)",
  "scientific_basis": "シューズ選びの根拠を平易に(足首サポートと捻挫予防、クッションと着地衝撃など。120字程度)"
}

match_scoreは100点満点でユーザーへの適合度。top_pickは最もおすすめの1足、alternativesは2〜3足。必ずDBの実在モデルから選ぶこと。""",

"type": BASE_PROMPT + """

競技タイプ診断の専門家として分類。
8タイプから最も近いタイプと副タイプを特定。

タイプ：パワー型・技術型・戦術型・安定型・成長型・思考型・回復不足型・オールラウンダー型

必ず以下のJSON形式のみで返答：
{
  "primary_type": "戦術型",
  "type_nickname": "コートの指揮者",
  "secondary_type": "技術型",
  "type_score": {
    "power": 45,
    "technical": 78,
    "tactical": 82,
    "stable": 72,
    "growth": 68,
    "thinking": 80,
    "recovery_deficit": 55,
    "allrounder": 65
  },
  "type_description": "戦術型の詳細説明（100字）",
  "strengths": ["強み1","強み2","強み3"],
  "weaknesses": ["弱み1","弱み2","弱み3"],
  "ideal_role": "チームでの理想的な役割",
  "growth_strategy": "このタイプの最適な成長戦略",
  "famous_player_analogy": "このタイプに近い有名選手のスタイル（架空でOK）",
  "team_compatibility": "どのタイプの選手と相性が良いか",
  "training_approach": "このタイプに最適な練習アプローチ",
  "mental_approach": "メンタル面でのアドバイス",
  "evolution_path": "このタイプが次に目指すべき方向"
}

type_nickname は16Personalities風の覚えやすくシェアしたくなる二つ名(例:コートの指揮者/不屈の壁/静かな狙撃手/みんなの太陽/影の参謀)。本人が誇らしく感じる前向きな表現にすること。""",

"winrate": BASE_PROMPT + """

勝率向上分析の専門家として評価。
技術だけでは勝てない。判断・戦術・ミス削減が鍵。

必ず以下のJSON形式のみで返答：
{
  "win_rate_score": 58,
  "current_win_rate_estimate": "40〜50%",
  "potential_win_rate": "65〜70%",
  "biggest_win_factor": "ミス削減",
  "factor_scores": [
    {"factor":"ミス率","score":45,"impact":35,"description":"得点より失点が多い可能性"},
    {"factor":"得点力","score":62,"impact":25,"description":"..."},
    {"factor":"戦術理解","score":58,"impact":20,"description":"..."},
    {"factor":"判断速度","score":70,"impact":15,"description":"..."},
    {"factor":"チーム連携","score":65,"impact":5,"description":"..."}
  ],
  "error_analysis": "ミスパターンの分析",
  "tactical_gaps": ["戦術的課題1","戦術的課題2","戦術的課題3"],
  "quick_wins": ["すぐ勝率を上げる方法1","すぐ勝率を上げる方法2","すぐ勝率を上げる方法3"],
  "serve_strategy": "サーブ戦略のアドバイス",
  "receive_strategy": "レシーブ戦略のアドバイス",
  "attack_strategy": "攻撃戦略のアドバイス",
  "mental_game": "試合中のメンタルゲーム管理",
  "team_communication": "チームコミュニケーション改善点",
  "match_prep": "試合前準備の最適化",
  "scientific_basis": "ソフトバレーはボールが軽く強打が入りにくい→ミス削減とサーブの正確性が勝率に直結する、という競技特性の根拠を平易に説明(150字程度)"
}

ソフトバレーの鉄則「強打よりコントロール」「サーブは威力より狙い」「ラリーを制する者が試合を制す」を分析の軸にすること。""",

}

CHAT_SYSTEM = BASE_PROMPT + "\n\n診断結果を踏まえた追加質問に、具体的かつ根拠に基づいて日本語で答えてください。回答は300字以内で簡潔に。"
JOURNAL_SYSTEM = BASE_PROMPT + "\n\n競技日誌データから選手のコンディション推移を分析し、洞察と改善提案を日本語で提供してください。"


# ─────────────────────────────────────────────
# Claude API 呼び出し
# ─────────────────────────────────────────────
def call_ai(messages, system_prompt, max_tokens=4000, json_mode=False):
    """Google Gemini API（無料）を呼び出してテキストを返す"""
    if not API_KEY:
        raise RuntimeError("APIキーが未設定です。Google AI Studio (aistudio.google.com) で無料APIキーを取得し、api_key.txt に保存してサーバーを再起動してください。")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    gen_cfg = {"maxOutputTokens": max_tokens, "temperature": 0.7}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    payload = json.dumps({
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": gen_cfg
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    # Gemini無料枠は503(混雑)/429が出やすいためリトライ付きで呼ぶ
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(5)
                continue
            raise
    raise last_err


def extract_json(text):
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:]
            p = p.strip()
            if p.startswith("{"):
                text = p
                break
    # 最初の{から最後の}まで
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)


# ─────────────────────────────────────────────
# プロンプトビルダー
# ─────────────────────────────────────────────
def build_diagnose_prompt(d):
    return f"""以下データでソフトバレー競技力総合診断を実施してください。

年齢:{d.get('age')}歳 / 性別:{d.get('gender')} / 身長:{d.get('height')}cm / 体重:{d.get('weight')}kg / 体脂肪:{d.get('body_fat')}%
競技歴:{d.get('career')}年 / 週練習:{d.get('practice_days')}回 / 練習時間:{d.get('practice_hours')}h
仕事:{d.get('job_type')} / 勤務:{d.get('work_hours')}h/日 / 睡眠:{d.get('sleep_hours')} / 睡眠質:{d.get('sleep_quality')}
ウェイト:{d.get('weight_training')}回/週 / スクワット:{d.get('squat')}kg / 垂直跳:{d.get('vertical_jump')}cm
食事:{d.get('diet')} / サプリ:{d.get('supplements')} / 体重変動:{d.get('weight_change')}
既往歴・痛み:{d.get('injuries')}
目標:{d.get('goal')} / 悩み:{d.get('concern')}"""


def build_fatigue_prompt(d):
    return f"""疲労・回復分析を実施してください。

睡眠時間:{d.get('sleep_hours')}h / 睡眠満足度:{d.get('sleep_satisfaction')} / 昼寝:{d.get('nap_time')}分
昨日の練習量:{d.get('practice_load')} / 今週の練習日数:{d.get('practice_days_week')}日
仕事量:{d.get('work_load')} / 精神的ストレス:{d.get('stress_level')}/10
疲労感（全体）:{d.get('fatigue_level')}/10 / 筋肉痛:{d.get('muscle_soreness')}/10
体重変動（1週間）:{d.get('weight_change')}kg / 食欲:{d.get('appetite')}
現在の気になる症状:{d.get('symptoms')}"""


def build_jump_prompt(d):
    return f"""ジャンプ力向上分析を実施してください。

年齢:{d.get('age')}歳 / 体重:{d.get('weight')}kg / 体脂肪率:{d.get('body_fat')}%
現在の垂直跳び:{d.get('current_jump')}cm / 目標垂直跳び:{d.get('target_jump')}cm
スクワット1RM:{d.get('squat')}kg / デッドリフト1RM:{d.get('deadlift')}kg
ウェイト頻度:{d.get('weight_freq')}回/週 / 疲労度:{d.get('fatigue')}/10
助走ジャンプと立ちジャンプの差:{d.get('approach_diff')}cm / 苦手な点:{d.get('jump_weakness')}
怪我・痛み:{d.get('injuries')}"""


def build_match_prompt(d):
    return f"""試合パフォーマンス分析を実施してください。

競技歴:{d.get('career')}年 / 試合経験:{d.get('match_exp')}
直近の試合での体感スコア（練習比）:{d.get('match_vs_practice')}/10
試合でのミス頻度:{d.get('error_rate')} / ミスが出やすい場面:{d.get('error_scene')}
試合中の集中力:{d.get('concentration')}/10 / 緊張度:{d.get('nervousness')}/10
試合前の準備:{d.get('pre_match_prep')} / 試合後の体感疲労:{d.get('post_match_fatigue')}/10
最近の試合での悩み:{d.get('match_concern')}"""


def build_injury_prompt(d):
    return f"""怪我リスク分析を実施してください。

年齢:{d.get('age')}歳 / 体重:{d.get('weight')}kg / 週練習:{d.get('practice_days')}回
既往歴・現在の痛み:{d.get('injuries')} / 柔軟性の自己評価:{d.get('flexibility')}/10
スクワット:{d.get('squat')}kg / 垂直跳び:{d.get('jump')}cm / ウェイト頻度:{d.get('weight_freq')}回/週
睡眠時間:{d.get('sleep')}h / 仕事の身体負担:{d.get('work_load')}
準備運動の習慣:{d.get('warmup')} / クールダウンの習慣:{d.get('cooldown')}"""


def build_longevity_prompt(d):
    return f"""競技寿命分析を実施してください。ソフトバレーは60〜70代まで競技可能な競技です。

年齢:{d.get('age')}歳 / 競技歴:{d.get('career')}年 / 目標競技継続年数:{d.get('goal_years')}年
睡眠:{d.get('sleep')}h / 体重管理:{d.get('weight_mgmt')} / ウェイト習慣:{d.get('weight_training')}
既往歴:{d.get('injuries')} / 現在の痛み:{d.get('current_pain')}
仕事の身体負担:{d.get('work_load')} / 回復の優先度:{d.get('recovery_priority')}
健康診断の結果（任意）:{d.get('health_check')} / 競技継続への不安:{d.get('longevity_concern')}"""


def build_training_prompt(d):
    return f"""練習設計分析を実施してください。

週の練習回数:{d.get('practice_days')}回 / 1回の練習時間:{d.get('practice_hours')}h
ウェイトトレーニング:{d.get('weight_training')}回/週 / 試合頻度:{d.get('match_freq')}回/月
睡眠時間:{d.get('sleep')}h / 完全休養日:{d.get('rest_days')}日/週
練習の主な内容:{d.get('practice_content')} / 練習の強度:{d.get('intensity')}/10
最近のパフォーマンス変化:{d.get('performance_trend')} / 練習後の疲労感:{d.get('post_practice_fatigue')}/10
目標:{d.get('goal')}"""


def build_shoes_prompt(d):
    return f"""この人に最適なシューズを、現行商品から具体的に推薦してください。

【足の情報】
年齢:{d.get('age')}歳 / 性別:{d.get('gender')} / 体重:{d.get('weight')}kg / 足のサイズ:{d.get('foot_size')}cm
足のアーチ:{d.get('arch')} / 足幅・甲:{d.get('foot_width')} / かかとの傾き:{d.get('pronation')}
靴で困ること:{d.get('fit_trouble')}

【プレースタイル】
競技レベル:{d.get('level')} / プレーの中心:{d.get('play_role')} / 主な動き:{d.get('movement_pattern')}
ジャンプ頻度:{d.get('jump_freq')} / 欲しい性能:{d.get('speed_or_stability')} / 着地時の膝:{d.get('knee_direction')} / 床:{d.get('floor_type')}

【希望条件】
バスケシューズ:{d.get('consider_basketball')} / 好みの履き心地:{d.get('cushion_pref')} / カット:{d.get('cut_pref')}
予算:{d.get('budget')} / 好きなブランド:{d.get('brand_pref')}
現在のシューズ:{d.get('current_shoes')} / 足・膝の不安:{d.get('injuries')}
その他の希望:{d.get('shoe_priority')}

予算帯と「バスケシューズを候補に入れるか」の希望を必ず尊重し、足幅・体重・プレースタイルに最も合う実在モデルを推薦してください。"""


def build_type_prompt(d):
    return f"""競技タイプ診断を実施してください。

年齢:{d.get('age')}歳 / 競技歴:{d.get('career')}年
得意なプレー:{d.get('strength_play')} / 苦手なプレー:{d.get('weakness_play')}
練習で集中すること:{d.get('practice_focus')} / 試合中に大切にすること:{d.get('match_focus')}
チームでの役割:{d.get('team_role')} / スタイルの自己評価:{d.get('self_style')}
目指す選手像:{d.get('ideal_player')}"""


def build_winrate_prompt(d):
    return f"""勝率向上分析を実施してください。

最近の勝率（自己評価）:{d.get('win_rate')}% / 試合経験:{d.get('match_exp')}
主なミスの種類:{d.get('main_errors')} / ミスが出やすい状況:{d.get('error_situation')}
得点の取り方:{d.get('scoring_method')} / 苦手な相手タイプ:{d.get('tough_opponent')}
サーブの自己評価:{d.get('serve_eval')}/10 / レシーブの自己評価:{d.get('receive_eval')}/10
戦術理解度（自己評価）:{d.get('tactical_understanding')}/10
チームの連携:{d.get('team_communication')} / 最近の課題:{d.get('recent_challenge')}"""


def build_journal_prompt(entries):
    lines = []
    for e in entries[-14:]:  # 直近14日
        lines.append(f"{e.get('date')}: 睡眠{e.get('sleep')}h, 疲労{e.get('fatigue')}/10, 体重{e.get('weight')}kg, 練習{e.get('practice')}, 気分{e.get('mood')}/10, メモ:{e.get('note','')}")
    return "以下の競技日誌データを分析して、コンディション推移、気づき、改善提案を詳細に日本語で答えてください。\n\n" + "\n".join(lines)


PROMPT_BUILDERS = {
    "diagnose": build_diagnose_prompt,
    "fatigue": build_fatigue_prompt,
    "jump": build_jump_prompt,
    "match": build_match_prompt,
    "injury": build_injury_prompt,
    "longevity": build_longevity_prompt,
    "training": build_training_prompt,
    "shoes": build_shoes_prompt,
    "type": build_type_prompt,
    "winrate": build_winrate_prompt,
}


# ─────────────────────────────────────────────
# HTTPハンドラ
# ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200); self.cors(); self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._file("index.html", "text/html; charset=utf-8")
        elif path == "/health":
            self._json({"status": "ok", "api_key_configured": bool(API_KEY)})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if path == "/api/analyze":
            self._handle_analyze(body)
        elif path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/journal":
            self._handle_journal(body)
        else:
            self.send_response(404); self.end_headers()

    def _handle_analyze(self, body):
        module = body.get("module", "diagnose")
        data = body.get("data", {})
        try:
            builder = PROMPT_BUILDERS.get(module)
            if not builder:
                raise ValueError(f"unknown module: {module}")
            prompt = builder(data)
            system = MODULE_PROMPTS.get(module, MODULE_PROMPTS["diagnose"])
            text = call_ai([{"role": "user", "content": prompt}], system, max_tokens=8000, json_mode=True)
            parsed = extract_json(text)
            self._json({"success": True, "result": parsed})
        except Exception as e:
            print(f"  ERROR [{module}]: {e}")
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                msg = "本日の無料利用枠を使い切りました（429）。明日リセットされます。"
            elif "503" in msg:
                msg = "AIが混雑しています（503）。30秒ほど待って再度お試しください。"
            self._json({"success": False, "error": msg}, 500)

    def _handle_chat(self, body):
        try:
            messages = body.get("messages", [])
            text = call_ai(messages, CHAT_SYSTEM, max_tokens=600)
            self._json({"success": True, "message": text})
        except Exception as e:
            self._json({"success": False, "error": str(e)}, 500)

    def _handle_journal(self, body):
        try:
            entries = body.get("entries", [])
            prompt = build_journal_prompt(entries)
            text = call_ai([{"role": "user", "content": prompt}], JOURNAL_SYSTEM, max_tokens=1200)
            self._json({"success": True, "analysis": text})
        except Exception as e:
            self._json({"success": False, "error": str(e)}, 500)

    def _file(self, filename, ctype):
        path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", len(content))
            self.cors(); self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.cors(); self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    if not API_KEY:
        print("⚠️  APIキー未設定")
        print("   Google AI Studio (aistudio.google.com) の無料キーを api_key.txt に保存してください")
    else:
        print(f"✓ Gemini ({GEMINI_MODEL}) で起動")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🏐 ソフトバレー競技力研究所 v2.0 起動")
    print(f"   http://localhost:{PORT}")
    server.serve_forever()
