# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>1つのタスク → マルチロールAIコラボレーション → 1つの結論</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-1561%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.6.1-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

---

## 🚀 V3.6.1: サイバネティクス強化リリース

**DevSquad V3.6.1** は FeedbackControlLoop 制御論フィードバックループ、ExecutionGuard リアルタイム実行ガード、PerformanceFingerprint 統一実行フィンガープリント、SimilarTaskRecommender 履歴タスク推奨、AdaptiveRoleSelector 適応型ロール選択を追加 — マルチエージェントコラボレーションをよりインテリジェント・自己修復・可観測にします。

## 🔄 V3.6.1 サイバネティクス強化詳細

### FeedbackControlLoop — 閉ループフィードバック制御

**核心能力**: ディスパッチ結果の品質メトリックを継続的にモニタリングし、閉ループフィードバックで自動調整を行う制御論システム。

**主な機能**:
- **品質メトリック収集**: 各ディスパッチサイクルから信頼度スコア、コンセンサス達成率、レスポンス遅延を収集
- **フィードバック計算**: 加重平均アルゴリズムで現在のシステム状態を評価
- **自動調整**: 品質が閾値を下回った場合、ロール重みやLLMパラメータを動的に調整
- **履歴トレンド分析**: 直近 N 回のディスパッチデータから傾向を検出し、劣化を予防

```python
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop

# フィードバックループ初期化
loop = FeedbackControlLoop(
    quality_threshold=85.0,
    adjustment_factor=0.1,
    history_window=10
)

# ディスパッチ結果を登録
result = disp.dispatch("API設計タスク")
loop.record_dispatch(result)

# フィードバックを取得して調整
feedback = loop.get_feedback()
if feedback.needs_adjustment:
    adjusted_params = loop.suggest_adjustments()
    print(f"調整提案: {adjusted_params}")
```

### ExecutionGuard — ロールバック付き安全実行ガード

**核心能力**: タスク実行前後に安全チェックを実行し、問題発生時に自動ロールバックする実行保護システム。

**主な機能**:
- **事前条件検証**: タスク開始前に依存関係、リソース可用性、権限レベルをチェック
- **実行時モニタリング**: タイムアウト検出、例外キャプチャ、リソース使用量追跡
- **自動ロールバック**: 失敗時または品質基準未達成時に状態を直前のチェックポイントに復元
- **セーフティネット**: 最大再試行回数、緊急停止トリガー、部分成功ハンドリング

```python
from scripts.collaboration.execution_guard import ExecutionGuard

guard = ExecutionGuard(
    max_retries=3,
    timeout_seconds=300,
    auto_rollback=True
)

# 安全なタスク実行
with guard.execute("マイグレーションタスク") as execution:
    result = disp.dispatch(execution.task)
    
    # 実行後の品質チェック
    if result.quality_score < 80:
        execution.mark_failed("品質基準未達成")
        # 自動ロールバックが発動
```

### PerformanceFingerprint — パフォーマンスベースライン追跡

**核心能力**: 各種操作のパフォーマンス指標をベースラインとして記録し、異常検知とボトルネック特定を行うシステム。

**主な機能**:
- **ベースライン記録**: 初期実行から P50/P95/P99 レイテンシ、スループット、エラー率を記録
- **異常検出**: 統計的手法（Z-score、IQR）でパフォーマンス逸脱を検出
- **トレンド分析**: 時系列データからパフォーマンス劣化または改善傾向を識別
- **レポート生成**: マークダウン形式のパフォーマンスダッシュボードを出力

```python
from scripts.collaboration.performance_fingerprint import PerformanceFingerprint

pf = PerformanceFingerprint(baseline_samples=20)

# 操作を計測
with pf.measure("dispatch_operation") as metric:
    result = disp.dispatch("テストタスク")

# ベースラインと比較
report = pf.analyze()
if report.has_anomaly():
    print(f"⚠️ 異常検出: {report.anomalies}")
    print(f"ボトルネック: {report.bottlenecks}")
```

### SimilarTaskRecommender — TF-IDFベースタスク類似性検索

**核心能力**: 過去のタスク履歴から TF-IDF ベクトル空間モデルを使用して、類似タスクを推薦する知的検索システム。

**主な機能**:
- **TF-IDFベクトル化**: 日本語・英語・中国語対応のテキスト特徴抽出
- **類似度計算**: コサイン類似度による高速近似最近傍探索
- **コンテキスト-aware推薦**: 使用されたロール、結果の品質スコア、実行時間を考慮
- **学習機能**: 新しいタスク実行結果をインデックスに自動追加

```python
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender

recommender = SimilarTaskRecommender(language="ja")

# 過去のタスクを登録（通常は自動）
recommender.index_task("ユーザー認証API設計", roles=["arch", "sec"], success=True)

# 類似タスクを推薦
similar = recommender.find_similar("ログイン機能実装", top_k=5)
for task in similar:
    print(f"📋 {task.description} (類似度: {task.similarity:.2f})")
    print(f"   推奨ロール: {task.suggested_roles}")
    print(f"   過去の成功率: {task.success_rate}%")
```

### AdaptiveRoleSelector — タスク特性に基づく知的ロール選択

**核心能力**: タスクのテキスト特徴、複雑度、ドメインから最適なロール組み合わせを機械学習的に選択する適応システム。

**主な機能**:
- **タスク解析**: キーワード抽出、複雑度スコアリング、ドメイン分類
- **ロールスコアリング**: 各ロールのタスク適合度を多因子モデルで評価
- **動的最適化**: 過去の成功/失敗データから選択精度を継続的に改善
- **説明可能AI**: 選択理由の透明な説明（どの特徴が影響したか）

```python
from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector

selector = AdaptiveRoleSelector()

# タスクから最適ロールを自動選択
selection = selector.select_roles(
    "高負荷分散システムの設計と実装",
    max_roles=4,
    explain=True
)

print(f"選択ロール: {selection.roles}")
print(f"各ロールの適合スコア:")
for role, score in selection.scores.items():
    print(f"  {role}: {score:.2f}")

if selection.explanation:
    print(f"選択理由: {selection.explanation.reasoning}")
```

## DevSquadとは？

DevSquadは、**単一のAIタスクをマルチロールAIコラボレーションに変換**します。タスクを最適な専門ロールの組み合わせに自動ディスパッチし、共有ワークスペースで並行コラボレーションを編成し、重み付きコンセンサス投票で競合を解決し、統一された構造化レポートを提供します。

## クイックスタート

### インストール

```bash
# 方法1: PyPI直接インストール（推奨）
pip install devsquad

# オプション依存関係付き
pip install "devsquad[api]"   # FastAPI + Streamlit含む
pip install "devsquad[all]"   # 全オプション依存関係含む

git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 方法2: 直接実行（インストール不要）
# 依存関係なし、即時使用可能、設定ファイル機能は制限されます
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計"

# 方法3: pip インストール（開発モード）
# 全機能、設定ファイルサポートあり（pyyaml自動インストール）
pip install -e .
devsquad dispatch -t "ユーザー認証システムを設計"
```

> **どちらを選ぶ？** 方法 A はお試し向け — 依存関係なしですぐ使えますが、`~/.devsquad.yaml` 設定ファイルは読み込まれません。方法 B は全機能を有効にするパッケージインストールで、YAML設定、`devsquad` CLIコマンド、オプション連携（CarryMem、OpenAI、Anthropic）が利用可能です。

### リアルAI出力

```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "認証システムを設計" --backend openai

# ロール指定（短縮ID: arch/pm/sec/test/coder/infra/ui）
python3 scripts/cli.py dispatch -t "認証システムを設計" -r arch sec --backend openai

# ストリーミング出力
python3 scripts/cli.py dispatch -t "認証システムを設計" -r arch --backend openai --stream
```

## 7つのコアロール

| ロール | CLI ID | 重み | 最適な用途 |
|--------|--------|------|-----------|
| アーキテクト | `arch` | 1.5 | システム設計、技術選定 |
| プロダクトマネージャー | `pm` | 1.2 | 要件分析、ユーザーストーリー |
| セキュリティ専門家 | `sec` | 1.1 | 脅威モデリング、脆弱性監査 |
| テスター | `test` | 1.0 | テスト戦略、品質保証 |
| コーダー | `coder` | 1.0 | 実装、コードレビュー |
| DevOps | `infra` | 1.0 | CI/CD、コンテナ化、監視 |
| UIデザイナー | `ui` | 0.9 | UX設計、インタラクション |

## 主な機能

### セキュリティ
- **入力検証**: XSS、SQLインジェクション、コマンドインジェクション、HTMLインジェクション検出
- **Prompt注入防护**: 21+パターン（以前の指示無視、脱獄、DANモード、システムプロンプト抽出等）
- **APIキー保護**: 環境変数のみ使用、コマンドライン引数やログに露出しない
- **権限ガード**: 4レベルセーフティゲート（PLAN → DEFAULT → AUTO → BYPASS）

### パフォーマンス
- **ThreadPoolExecutor**: マルチロールディスパッチの真の並列実行
- **LLMキャッシュ**: TTLベースLRUキャッシュ + ディスク永続化（60-80%コスト削減）
- **LLMリトライ**: 指数バックオフ + サーキットブレーカー + マルチバックエンドフォールバック
- **ストリーミング出力**: `--stream` によるリアルタイムチャンク出力

### 信頼性
- **チェックポイント管理**: SHA256整合性、ハンドオフ文書、自動クリーンアップ
- **ワークフローエンジン**: タスク→ワークフロー自動分割、ステップ実行、チェックポイント復元、**11フェーズライフサイクルテンプレート**（full/backend/frontend/internal_tool/minimal）、要件変更管理
- **タスク完了チェッカー**: DispatchResult/ScheduleResult完了度追跡
- **コンセンサスエンジン**: 重み付け投票 + 拒否権 + 人間へのエスカレーション

### ⚓ AnchorChecker アンカー検証 (NEW)
マイルストーンアンカー検証システム。重要なチェックポイントが先に進む前に適切に検証されることを保証：
- **アンカー定義** — 重要なライフサイクルマイルストーンに必須検証アンカーを定義
- **クロスフェーズ検証** — フェーズ出力とアンカー基準間の一貫性を検証
- **ドリフト検出** — プロジェクト実行が定義されたアンカーポイントから逸脱したことを検出
- **自動リカバリ** — アンカーチェック失敗時に修正措置を提案

### 🔄 RetrospectiveEngine 独立レトロスペクティブ (NEW)
独立レトロスペクティブメカニズム。各ディスパッチサイクル後の継続的改善：
- **ディスパッチ後レビュー** — 何がうまくいったか、何を改善できるかを自動分析
- **パターン抽出** — 成功したコラボレーションから再利用可能なパターンを抽出
- **アンチパターン検出** — 繰り返し発生する問題を特定し、プロセス改善を提案
- **メトリックトレンド分析** — ディスパッチ間の品質メトリックを追跡し、劣化を検出

### 🎯 StructuredGoal 構造化目標 (NEW)
構造化目標管理。高レベル目標を追跡可能・検証可能なサブ目標に分解：
- **目標分解** — 複雑な目標を明確な基準を持つ階層的サブ目標に分解
- **進捗追跡** — 定義された目標構造に対するリアルタイム進捗測定
- **依存関係マッピング** — サブ目標間の依存関係を可視化・管理
- **完了検証** — 目標が成功基準を満たしているかを自動検証

### 🔀 FallbackBackend 自動フェイルオーバー (NEW)
自動LLMバックエンドフェイルオーバー。プライマリバックエンドがダウン時もLLM可用性を確保：
- **ヘルスモニタリング** — 設定された全LLMバックエンドの継続的ヘルスチェック
- **自動フェイルオーバー** — プライマリ障害時にバックアップバックエンドへシームレスに切り替え
- **優先度ベースルーティング** — バックエンド優先順序を設定（例：OpenAI → Anthropic → Mock）
- **リカバリ検出** — プライマリバックエンド復旧時に自動的に復元

## 🧩 レイヤードサブスキルアーキテクチャ (V3.6.1 NEW)

> DevSquadは **6つの原子サブスキル** を提供し、独立または組み合わせて使用可能。
> 各サブスキルは約 **50行の薄いラッパー** で、既存コアモジュールをインポート — 重複ロジックなし。

```
skills/
├── dispatch/       → DispatchSkill — マルチエージェントディスパッチ（7ロール）
├── intent/         → IntentSkill   — 意図検出（6意図 × 3言語）
├── review/         → ReviewSkill   — 5軸コードレビュー
├── security/       → SecuritySkill — 入力スキャン + 操作分類
├── test/           → TestSkill     — テスト戦略 + 品質監査
└── retrospective/  → RetroSkill    — ディスパッチ後レトロスペクティブ
```

### サブスキル一覧

| スキル | コアメソッド | ラップモジュール | Mockモード |
|-------|------------|---------------|:---------:|
| `dispatch` | `run(task, roles)` | MultiAgentDispatcher | ✅ |
| `intent` | `detect(text, lang)` | IntentWorkflowMapper | ✅ |
| `review` | `review(code)` | FiveAxisConsensusEngine | ✅ |
| `security` | `scan_input(text)` | InputValidator + OpClassifier | ✅ |
| `test` | `generate_strategy(module)` | TestQualityGuard | ✅ |
| `retrospective` | `run_retrospective(results)` | RetrospectiveEngine | ✅ |

### 使用例

```python
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("ログインバグ修正", roles=["coder", "tester"])

from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
```

すべてのサブスキルは **APIキー不要** でMockモード動作可能。

### 自然言語ルール収集

ユーザーの自然言語入力からルールを自動検出・保存。設定ファイルの手動編集不要：

```python
# ユーザー：「ルールを覚えて：コードを書く時は必ずコメントを追加」
# DevSquadが自動的に：
# 1. ルール保存意図を検出
# 2. 抽出：trigger="コードを書く時", action="必ずコメントを追加", type="always"
# 3. 安全サニタイズ（危険パターン除去 + プロンプト注入防止）
# 4. 保存（CarryMem優先 + ローカルJSON代替）

# ルール一覧
# ユーザー：「ルール一覧」 → 保存済みルールを全件返却

# ルール削除
# ユーザー：「ルール削除 RULE-LOCAL-abc123」
```

**パイプライン**: ユーザー入力 → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage (CarryMem + ローカルJSON)

**機能**:
- 11の意図パターン（中国語・英語）
- 4つのルールタイプ：always / avoid / prefer / forbid
- ルール内容のプロンプト注入防止（14パターン）
- CarryMem優先 + ローカルJSON代替ストレージ
- Workerプロンプトへのルール自動注入

### プロジェクトライフサイクル（11フェーズモデル）

DevSquad V3.6.1は **11フェーズ（4つオプション）** のプロジェクトライフサイクルを定義。各フェーズには明確なロール、依存関係、ゲート条件があります：

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

| テンプレート | フェーズ | ユースケース |
|-------------|---------|-------------|
| `full` | P1-P11全フェーズ | 完全プロジェクト |
| `backend` | P5なし | バックエンドサービス |
| `frontend` | P4,P6なし | フロントエンドアプリ |
| `internal_tool` | P4,P5,P6,P11なし | 社内ツール |
| `minimal` | P1,P3,P7,P8,P9 | 最小セット |

詳細は [GUIDE_JP.md](GUIDE_JP.md) §4 を参照（ゲート条件と要件変更プロセス含む）。

### 開発者体験
- **設定ファイル**: プロジェクトルートの `.devsquad.yaml` + 環境変数オーバーライド
- **品質管理注入**: `.devsquad.yaml` 設定に基づき、QCルール（ハルシネーション防止、過信チェック、セキュリティガード、RACIプロトコル）をWorkerプロンプトに自動注入
- **Dockerサポート**: `docker build -t devsquad .`
- **GitHub Actions CI**: Python 3.9-3.12マトリックステスト
- **pipインストール可能**: `pip install devsquad` + オプション依存関係

## 📦 モジュール参照 (53 モジュール)

| # | モジュール | ファイル | 責任 |
|---|----------|---------|------|
| 1 | **MultiAgentDispatcher** | `dispatcher.py` | 統一エントリポイント |
| 2 | **Coordinator** | `coordinator.py` | グローバルオーケストレーション：計画→割り当て→実行→収集 |
| 3 | **Worker** | `worker.py` | LLMバックエンド統合付きロール実行者 |
| 4 | **EnhancedWorker** | `enhanced_worker.py` | 自動QA付きワーカー（ブリーフィング + 信頼度 + リトライ + メモリルール） |
| 5 | **Scratchpad** | `scratchpad.py` | ワーカー間通信用共有ブラックボード |
| 6 | **ConsensusEngine** | `consensus.py` | 重み付け投票 + 拒否権 + エスカレーション |
| 7 | **RoleMatcher** | `role_matcher.py` | キーワードベースのロールマッチングとエイリアス解決 |
| 8 | **ReportFormatter** | `report_formatter.py` | 構造化/コンパクト/詳細レポート生成 |
| 9 | **InputValidator** | `input_validator.py` | セキュリティ検証 + プロンプト注入検出 |
| 10 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM駆動セマンティックロールマッチング |
| 11 | **CheckpointManager** | `checkpoint_manager.py` | 状態永続化 + ハンドオフ文書 |
| 12 | **WorkflowEngine** | `workflow_engine.py` | タスク→ワークフロー自動分割 + 11フェーズライフサイクルテンプレート + 要件変更管理 |
| 13 | **TaskCompletionChecker** | `task_completion_checker.py` | 完了度追跡 + 進捗レポート |
| 14 | **CodeMapGenerator** | `code_map_generator.py` | Python ASTベースのコード構造解析 |
| 15 | **DualLayerContextManager** | `dual_layer_context.py` | プロジェクトレベル + タスクレベルコンテキスト管理 |
| 16 | **SkillRegistry** | `skill_registry.py` | 再利用可能スキル登録 + 発見 |
| 17 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | ユーザー意図 → ワークフローチェーンマッピング（6意図 × 3言語） |
| 18 | **OperationClassifier** | `operation_classifier.py` | 3階層操作分類（ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN） |
| 19 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | 5軸レビューコンセンサスと重み付け投票 |
| 20 | **FeatureUsageTracker** | `feature_usage_tracker.py` | 機能使用追跡 + レポート + 自動永続化 |
| 21 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic + ストリーミングサポート |
| 22 | **LLMCache** | `llm_cache.py` | TTLベースLRUキャッシュ + ディスク永続化 |
| 23 | **LLMRetry** | `llm_retry.py` | 指数バックオフ + サーキットブレーカー |
| 24 | **ConfigManager** | `config_loader.py` | YAML設定 + 環境変数オーバーライド |
| 25 | **PromptAssembler** | `prompt_assembler.py` | 動的プロンプトアセンブリ + QCルール注入 |
| 26 | **AgentBriefing** | `agent_briefing.py` | 優先度フィルタリング付きコンテキスト対応タスクブリーフィング |
| 27 | **ConfidenceScorer** | `confidence_score.py` | 5因子応答品質評価 |
| 28 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99追跡 + CPU/メモリ監視 |
| 29 | **MCEAdapter** | `mce_adapter.py` | CarryMem統合アダプター（オプション依存、match_rules + format_rules_as_prompt + add_ruleをサポート） |
| 30 | **Protocols** | `protocols.py` | インターフェース定義（CacheProvider, MemoryProvider等） |
| 31 | **NullProviders** | `null_providers.py` | グレースフルデグラデーションプロバイダー |
| 32 | **PermissionGuard** | `permission_guard.py` | 4レベルセーフティゲート |
| 33 | **MemoryBridge** | `memory_bridge.py` | クロスセッションメモリ |
| 34 | **BatchScheduler** | `batch_scheduler.py` | バッチタスクスケジューリング |
| 35 | **ContextCompressor** | `context_compressor.py` | 長時間タスク用コンテキスト圧縮 |
| 36 | **RoleTemplateMarket** | `role_template_market.py` | ロールテンプレートシェアリングマーケットプレイス |
| 37 | **Skillifier** | `skillifier.py` | タスクからの自動スキル学習 |
| 38 | **UsageTracker** | `usage_tracker.py` | トークン/コスト追跡 |
| 39 | **WarmupManager** | `warmup_manager.py` | 起動ウォームアップ最適化 |
| 40 | **TestQualityGuard** | `test_quality_guard.py` | テスト品質強制 |
| 41 | **PromptVariantGenerator** | `prompt_variant_generator.py` | A/Bプロンプトテスト |
| 42 | **ConfigManager (YAML)** | `config_manager.py` | プロジェクトレベルYAML設定 |
| 43 | **WorkBuddyClawSource** | `memory_bridge.py` | WorkBuddy読み取り専用ブリッジ |
| 44 | **Models** | `models.py` | 共有データモデルと型定義 |
| 45 | **LLMCacheAsync** | `llm_cache_async.py` | 並列ワークロード用非同期LLMキャッシュ |
| 46 | **LLMRetryAsync** | `llm_retry_async.py` | バックオフ付き非同期LLMリトライ |
| 47 | **IntegrationExample** | `integration_example.py` | DevSquad統合サンプルコード |
| 48 | **AsyncIntegrationExample** | `async_integration_example.py` | 非同期DevSquad統合サンプル |
| 49 | **AnchorChecker** | `anchor_checker.py` | マイルストーンアンカー検証 + ドリフト検出 + 自動リカバリ |
| 50 | **RetrospectiveEngine** | `retrospective.py` | 独立ディスパッチ後レトロスペクティブ + パターン抽出 + アンチパターン検出 |
| 51 | **FallbackBackend** | `llm_backend.py` | ヘルスモニタリング付き自動LLMバックエンドフェイルオーバー |
| 52 | **FeedbackControlLoop** | `feedback_control_loop.py` | 閉ループフィードバック制御（V3.6.1新規） |
| 53 | **ExecutionGuard** | `execution_guard.py` | ロールバック付き安全実行ガード（V3.6.1新規） |
| 54 | **PerformanceFingerprint** | `performance_fingerprint.py` | パフォーマンスベースライン追跡（V3.6.1新規） |
| 55 | **SimilarTaskRecommender** | `similar_task_recommender.py` | TF-IDFベースタスク類似性検索（V3.6.1新規） |
| 56 | **AdaptiveRoleSelector** | `adaptive_role_selector.py` | タスク特性に基づく知的ロール選択（V3.6.1新規） |

## 設定

```yaml
# ~/.devsquad.yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85
  ai_quality_control:
    enabled: true
    hallucination_check:
      enabled: true
    overconfidence_check:
      enabled: true
  ai_security_guard:
    enabled: true
    permission_level: "DEFAULT"
  ai_team_collaboration:
    enabled: true
    raci:
      mode: "strict"

llm:
  backend: openai
  base_url: ""
  model: ""
  timeout: 120
  log_level: WARNING
```

## テスト実行

```bash
# コアテスト（1561+ 全テスト合格）
python3 -m pytest tests/ -q --tb=short
```

## ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [GUIDE_JP.md](GUIDE_JP.md) | 完全ユーザーガイド（日本語） |
| [GUIDE_EN.md](GUIDE_EN.md) | 完全ユーザーガイド（英語） |
| [GUIDE.md](../../GUIDE.md) | 完全ユーザーガイド（中国語） |
| [README.md](../../README.md) | English |
| [README-CN.md](README_CN.md) | 中文 |
| [INSTALL.md](../../INSTALL.md) | インストールガイド |
| [SKILL.md](../../SKILL.md) | スキルマニュアル |

## バージョン履歴

| 日付 | バージョン | ハイライト |
|------|-----------|-----------|
| 2026-05-17 | **V3.6.1** | 🔄 **サイバネティクス強化** — 5つの新モジュール(フィードバックループ/実行ガード/性能フィンガープリント/タスク推奨/適応型ロール)、アップストリームv2.5サイバネティクスアーキテクチャ分析由来。110新規テスト、計1561。Mockモードゼロ依存で動作可能。 |
| 2026-05-16 | **V3.6.0** | 🧩 **レイヤードサブスキルアーキテクチャ** — 6つの原子サブスキル(dispatch/intent/review/security/test/retrospective)、遅延ロードレジストリ、各~50行の薄いラッパー。クロスプラットフォーム対応：Claude Code/Cursor/OpenClaw/純Python/Docker/MCP 全サポート。Mockモードゼロ依存で動作可能。 |
| 2026-05-13 | **V3.6.0** | ⚓ AnchorChecker（マイルストーンアンカー検証+ドリフト検出）、RetrospectiveEngine（独立レトロスペクティブ+パターン抽出）、StructuredGoal（階層的目標分解+進捗追跡）、FallbackBackend（自動LLMフェイルオーバー+ヘルスモニタリング）、FeatureUsageTracker（機能呼び出し統計+使用レポート+自動永続化）、7モジュール統合（IntentWorkflowMapper/AISemanticMatcher/DualLayerContextManager/OperationClassifier/SkillRegistry/FiveAxisConsensusEngine/NullProviders）、1548+テスト、48コアモジュール |
| 2026-05-05 | **V3.5.0** | 📋 エンハンスメントスプリント — コードウォークスルー強化、ドキュメント整合性チェック、Karpathy原則、プロジェクト理解（AgentBriefing）、CLIライフサイクルコマンド、構造化出力、748+テスト |
| 2026-05-03 | **V3.4.1** | 🚀 エージェントスキル品質フレームワーク (P0) — AntiRationalizationEngine + VerificationGate + IntentWorkflowMapper + CLIライフサイクルコマンド + 167新規テスト + Googleエージェントスキル統合 + 49コアモジュール |
| 2026-05-02 | **V3.4.0** | 🆕 11フェーズプロジェクトライフサイクル（full/backend/frontend/internal_tool/minimalテンプレート）、要件変更管理、ゲートメカニズム+ギャップレポート、560+テスト合格 |
| 2026-04-27 | V3.4.0 | リアルLLMバックエンド、並列実行、セキュリティ強化、チェックポイント、ワークフロー、ストリーミング、Docker、CI、CarryMem統合 |

## ライセンス

MIT License
