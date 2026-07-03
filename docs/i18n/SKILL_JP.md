---
name: devsquad
slug: devsquad
description: |
  V3.9.3 DevSquad — Enterprise マルチエージェントコラボレーションプラットフォーム。
  Coordinator/Worker/Scratchpad パターンに基づく完全なマルチエージェントコラボレーションシステム。
  7コアロール（アーキテクト/PM/セキュリティ/テスター/コーダー/DevOps/UIデザイナー）、
  リアルLLMバックエンド（OpenAI/Anthropic/MOKA AI）、CLI + MCP + Python API + REST API + Web Dashboard対応。
  ThreadPoolExecutor並列、CheckpointManager、WorkflowEngine、ストリーミング出力、Docker、CI。
  V3.9.3: 自動LLMバックエンドフォールバック + Dashboard分割 + SQLite監査永続化 + P3クリーンアップ,
  118 コアモジュール, 3312+ テスト合格 (CI 権威).
---

# DevSquad V3.9.3 — マルチエージェントコラボレーションプラットフォーム（Enterprise Ready）

## 🎯 一言で理解（3 秒）

**DevSquad = 「単一AIアシスタント」を「7人のAI専門チーム」にアップグレード**

```
従来AI: あなた ──→ ChatGPT ──→ 一つの回答（不完全の場合あり）
DevSquad: あなた ──→ DevSquad ──→ [アーキテクト+セキュリティ+テスト+開発...] ──→ 多次元コンセンサス結論
```

## コアポジショニング

このスキルは Trae を「単一AIアシスタント」から「マルチAIチーム」へアップグレードします。
タスクが提出されると、単一ロールで処理されるのではなく：

```
ユーザータスク → [入力検証] → [ロールマッチング] → [Coordinatorオーケストレーション]
             → [ThreadPoolExecutor並列Worker] → [Scratchpadリアルタイム共有]
             → [コンセンサス決定] → [レポート整形] → [構造化レポート]
```

## アーキテクチャ概要（118+コアモジュール）

| # | モジュール | ファイル | 責任 |
|---|-----------|--------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 統一ディスパッチ入口（全モジュール統合） |
| 1 | **Coordinator** | `coordinator.py` | グローバルオーケストレーター：タスク分解、Worker割り当て、結果収集、競合解決 |
| 2 | **Scratchpad** | `scratchpad.py` | 共有ブラックボード、Worker間リアルタイム情報交換 |
| 3 | **Worker** | `worker.py` | 実行者：各ロール1インスタンス、ストリーミング対応 |
| 4 | **ConsensusEngine** | `consensus.py` | コンセンサスエンジン：重み付け投票+拒否権+エスカレーション |
| 5 | **BatchScheduler** | `batch_scheduler.py` | 並列/直列ハイブリッドスケジューリング |
| 6 | **ContextCompressor** | `context_compressor.py` | 4段階コンテキスト圧縮 |
| 7 | **PermissionGuard** | `permission_guard.py` | 4レベル権限ガード |
| 8 | **Skillifier** | `skillifier.py` | 成功パターンから新Skill自動生成 |
| 9 | **WarmupManager** | `warmup_manager.py` | 3層起動予熱 |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7タイプ記憶ブリッジ+MCE/Claw外部統合 |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | テスト品質監査 |
| 12 | **PromptAssembler** | `prompt_assembler.py` | 動的プロンプトアセンブル / QC設定注入 |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillifyクローズドループ *(削除済み)* |
| 14 | **MCEAdapter** | `mce_adapter.py` | CarryMem統合アダプター（遅延ロード/グレースフルデグラデーション/タイプマッピング） |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py`(class) | Claw読み取り専用ブリッジ |
| 16 | **RoleMatcher** | `role_matcher.py` | キーワードベースロールマッチング+エイリアス解決 |
| 17 | **ReportFormatter** | `report_formatter.py` | 構造化/コンパクト/詳細レポート生成 |
| 18 | **InputValidator** | `input_validator.py` | セキュリティ検証+40種検出パターン |
| 19 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM駆動セマンティックマッチング+バイリンガルフォールバック |
| 20 | **CheckpointManager** | `checkpoint_manager.py` | SHA256整合性、ハンドオフ文書、自動クリーンアップ |
| 21 | **WorkflowEngine** | `workflow_engine.py` | タスク→ワークフロー自動分割、ステップ実行、チェックポイント復元、11フェーズライフサイクルテンプレート、要件変更管理 |
| 22 | **TaskCompletionChecker** | `task_completion_checker.py` | 完了追跡+進捗永続化 |
| 23 | **CodeMapGenerator** | `code_map_generator.py` | Python ASTベースコード分析+依存グラフ |
| 24 | **DualLayerContextManager** | `dual_layer_context.py` | プロジェクト+タスクレベルコンテキスト（TTL付き） |
| 25 | **SkillRegistry** | `skill_registry.py` | スキル登録+発見+永続化 |
| 26 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | ユーザー意図→ワークフローチェーンマッピング（6意図×3言語） |
| 27 | **OperationClassifier** | `operation_classifier.py` | 3層操作分類（ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN） |
| 28 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | 5軸レビューコンセンサス（正確性/可読性/アーキテクチャ/セキュリティ/パフォーマンス）重み付き投票 |
| 29 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic + ストリーミング + 120sタイムアウト |
| 30 | **ConfigManager** | `config_loader.py` | *(V3.7.2 で削除)* デッドコード — 参照ゼロ |
| 31 | **Protocols** | `protocols.py` | Protocolインターフェース(CacheProvider/RetryProvider/MonitorProvider/MemoryProvider) + 例外階層 |
| 32 | **NullProviders** | `null_providers.py` | 全Protocolインターフェースの空実装(デグレード+テストモック) |
| 33 | **EnhancedWorker** | `enhanced_worker.py` | ProtocolベースProvider注入Worker(キャッシュ/リトライ/モニター/ブリーフィング) |
| 34 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99応答時間/CPU/メモリ追跡/ボトルネック検出/Markdownレポート |
| 35 | **AgentBriefing** | `agent_briefing.py` | コンテキスト認識ブリーフィング生成 + 優先度フィルタリング + 永続化 |
| 36 | **ConfidenceScorer** | `confidence_score.py` | 5因子信頼度スコア(完全性/確実性/具体性/一貫性/モデル品質) |
| 37 | **RoleTemplateMarket** | `role_template_market.py` | ロールテンプレートマーケット(公開/検索/インストール/評価/エクスポート/インポート) *(削除済み)* |
| 38 | **LLMCache** | `llm_cache.py` | TTL LRUキャッシュ+ディスク永続化(60-80%コスト削減) |
| 39 | **LLMRetry** | `llm_retry.py` | 指数バックオフ+サーキットブレーカー+マルチバックエンドフォールバック |
| 40 | **UsageTracker** | `usage_tracker.py` | Token/コスト使用量追跡とレポート |
| 41 | **Models** | `models.py` | 共有データモデルと型定義 |
| 42 | **ConfigManager (YAML)** | `config_manager.py` | プロジェクトレベルYAML設定管理 |
| 43 | **LLMCacheAsync** | `llm_cache_async.py` | 非同期LLMキャッシュ |
| 44 | **LLMRetryAsync** | `llm_retry_async.py` | 非同期LLMリトライ+バックオフ |
| 45 | **IntegrationExample** | `integration_example.py` | DevSquad統合サンプルコード |
| 46 | **AsyncIntegrationExample** | `async_integration_example.py` | 非同期DevSquad統合サンプル |
| 47 | **AntiRationalizationEngine** | `anti_rationalization.py` | ロール別言い訳→反論テーブル（8汎用+6-7ロール固有）、PromptAssembler経由で注入し品質ショートカット防止 |
| 48 | **VerificationGate** | `verification_gate.py` | 必須証拠要求 + 7レッドフラグ検出 + Prove-Itパターン（完了主張検証） |
| 49 | **AnchorChecker** | `anchor_checker.py` | [V3.6.0] アンカー整合性チェック、出力の事実一致性検証 |
| 50 | **RetrospectiveEngine** | `retrospective_engine.py` | [V3.6.0] 振り返りエンジン、パターン抽出+改善提案生成 |
| 51 | **StructuredGoal** | `structured_goal.py` | [V3.6.0] 構造化目標定義、目標分解+追跡+達成度評価 |
| 52 | **FallbackBackend** | `fallback_backend.py` | [V3.6.0] フォールバックバックエンド、マルチバックエンド自動切替+グレースフルデグラデーション |
| 53 | **FeatureUsageTracker** | `feature_usage_tracker.py` | [V3.6.0] 機能使用量追跡、機能採用率分析+使用レポート |
| 54 | **FeedbackControlLoop** | `feedback_control_loop.py` | [V3.6.1] Sense→Decide→Act→Feedbackクローズドループ反復 |
| 55 | **ExecutionGuard** | `execution_guard.py` | [V3.6.1] リアルタイム実行ガード（タイムアウト/出力/キーワード検知） |
| 56 | **PerformanceFingerprint** | `performance_fingerprint.py` | [V3.6.1] 統一実行フィンガープリント+TF-IDF類似度検索 |
| 57 | **SimilarTaskRecommender** | `similar_task_recommender.py` | [V3.6.1] 履歴ベースタスク構成推奨 |
| 58 | **AdaptiveRoleSelector** | `adaptive_role_selector.py` | [V3.6.1] 成功率駆動適応型ロール選択 |

---

## インストール

```bash
# PyPIから直接インストール（推奨）
pip install devsquad
pip install "devsquad[api]"
pip install "devsquad[all]"
```

---

## クイックスタート

### 方法1：ワンクリックコラボレーション（推奨）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher
disp = MultiAgentDispatcher()
result = disp.dispatch("ユーザーのタスク")
print(result.to_markdown())
disp.shutdown()
```

**CLI同等コマンド**:
```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "認証システム設計" -r arch sec --backend openai
```

### 方法2：ロール指定

```python
result = disp.dispatch("認証システム設計", roles=["architect", "tester"])
```

### 方法3：ドライランシミュレーション

```python
result = disp.dispatch("テストタスク", dry_run=True)
```

### 方法4：便利関数

```python
from scripts.collaboration.dispatcher import quick_collaborate
result = quick_collaborate("マイクロサービス設計を手伝って")
```

---

## ロールシステム（7コアロール）

| ロールID | 名前 | キーワード | 主な責任 |
|----------|------|-----------|---------|
| `architect` | アーキテクト | 設計,選定,性能,データアーキテクチャ | システム設計,技術選定,パフォーマンス/セキュリティ/データアーキテクチャ |
| `product-manager` | PM | 要求,PRD,ユーザーストーリー | 要件分析,製品企画 |
| `security` | セキュリティ専門家 | セキュリティ,脆弱性,監査,脅威,OWASP | 脅威モデリング,脆弱性監査,コンプライアンス |
| `tester` | テスト専門家 | テスト,品質,自動化 | テスト戦略,品質保証 |
| `solo-coder` | コーダー | 実装,開発,コードレビュー,リファクタリング | 機能開発,コードレビュー,パフォーマンス最適化 |
| `devops` | DevOpsエンジニア | CI/CD,デプロイ,モニタリング,Docker,K8s | CI/CDパイプライン,コンテナ化,インフラ |
| `ui-designer` | UIデザイナー | UI,画面,アクセシビリティ | UI/UX設計,アクセシビリティ |

**CLIショートID**: `arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

---

## 完全ワークフロー（スキル呼び出し時）

### ステップ1：ディスパッチャー作成

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher
import tempfile

work_dir = tempfile.mkdtemp(prefix="mas_v3_")
disp = MultiAgentDispatcher(
    persist_dir=work_dir,
    enable_warmup=True,
    enable_compression=True,
    enable_permission=True,
    enable_memory=True,
    enable_skillify=True,
)
```

### ステップ2：タスク分析とロールマッチング

```python
matched = disp.analyze_task(user_task)
for role in matched:
    print(f"{role['name']} (信頼度: {role['confidence']:.0%}) - {role['reason']}")
```

### ステップ3：コラボレーション実行

```python
result = disp.dispatch(
    task_description=user_task,
    roles=None,          # None=自動マッチ、または ["architect", "tester"] 指定
    mode="auto",         # auto/parallel/sequential/consensus
    dry_run=False,       # True=シミュレーションのみ
)
```

### ステップ4：結果確認

```python
print(f"成功: {result.success}")
print(f"ロール: {result.matched_roles}")
print(f"実行時間: {result.duration_seconds:.2f}s")
print(result.summary)

if result.worker_results:
    for wr in result.worker_results:
        print(f"[{wr['role']}] {wr['output'][:200]}")
```

### ステップ5：Markdownレポート出力

```python
report = result.to_markdown()
print(report)
```

### ステップ6：クリーンアップ

```python
disp.shutdown()
```

---

## 高度な機能ガイド

### コンテキスト圧縮（長対話オーバーフロー防止）

対話が長くなりすぎると、ContextCompressor が自動的にトリガーされます：
- **レベル1 SNIP**: 古い対話の細粒度トリミング、重要な決定と結論を保持
- **レベル2 SessionMemory**: 重要な情報をメモリに抽出してからコンテキストをクリア
- **レベル3 FullCompact**: LLM が1ページ要約を生成（最も積極的）

圧縮状態の確認：
```python
stats = disp.coordinator.get_compression_stats()
memory = disp.coordinator.get_session_memory()
```

### パーミッションガード（セキュア操作センティネル）

PermissionGuard が危険な操作を自動チェックします：
- **PLAN レベル**: 読み取り専用操作のみ
- **DEFAULT レベル**: 書き込み操作は確認が必要
- **AUTO レベル**: AI 分類器が自動判定
- **BYPASS レベル**: 完全スキップ（最高信頼）

パーミッション記録は `result.permission_checks` に格納されます。

### メモリーブリッジ（クロスセッションメモリー）

MemoryBridge は7種類のメモリーを提供します：
- `knowledge` — ナレッジエントリ
- `episodic` — エピソード記憶（タスク実行記録）
- `semantic` — 意味記憶
- `feedback` — ユーザーフィードバック
- `pattern` — 成功パターン
- `analysis` — 分析ケース
- `correction` — 訂正記録

忘却曲線: 7d=1.0, 30d≈0.8, 60d≈0.5, 90d≈0.3

メモリー状態の確認：
```python
status = disp.get_status()
mem_stats = status.get("memory_stats")
```

### 起動ウォームアップ（コールドスタート遅延削減）

WarmupManager 3層ウォームアップ：
- **EAGER 層**: 重要リソースの同期的プリロード（〜15ms）
- **ASYNC 層**: 非同期バックグラウンドウォームアップ（〜300ms）
- **LAZY 層**: オンデマンド読み込み

ウォームアップ状態の確認：
```python
status = disp.get_status()
warmup = status.get("warmup_metrics")
```

### スキル学習（成功からの進化）

Skillifier が成功した操作シーケンスから再利用可能なパターンを自動抽出します：
```python
proposals = result.skill_proposals
for p in proposals:
    print(f"新スキル候補: {p['title']} (信頼度: {p['confidence']:.0%})")
```

### コンセンサス決定（マルチロール紛争解決）

Worker 間で意見が分かれた場合、ConsensusEngine が投票を開始します：
- 重み付き投票（ロール重要度で重み付け）
- 否決権（主要ロールが単独でブロック可能）
- 人間へのエスカレーション（コンセンサス到達不能時、人間の決定待ちとしてマーク）

コンセンサス記録は `result.consensus_records` に含まれます。

---

## ディスパッチモード表

| モード | 説明 | ユースケース |
|--------|------|--------------|
| `auto` | 最適モードを自動選択 | デフォルト推奨 |
| `parallel` | 全ロールが並行実行 | ロール間依存関係なし |
| `sequential` | 順次実行 | 依存チェーンあり |
| `consensus` | 実行後にコンセンサス投票を強制 | 全員一致の決定が必要 |

---

## システム状態照会

```python
status = disp.get_status()
# 戻り値:
# {
#   "version": "3.9.2",
#   "components": {...},        # コンポーネント有効状態
#   "dispatch_count": N,         # 完了ディスパッチ数
#   "scratchpad_stats": {...}, # ブラックボード統計
#   "warmup_metrics": {...},    # ウォームアップ指標（有効時）
#   "memory_stats": {...},      # メモリー統計（有効時）
# }

history = disp.get_history(limit=10)
# 直近N件のディスパッチ完全結果を返します
```

---

## エラーハンドリング

全例外は `DispatchResult` 内にキャプチャされ、スローされることはありません：

```python
result = disp.dispatch("任意のタスク")
if not result.success:
    print("エラー:", result.errors)
    print("サマリー:", result.summary)
```

一般的なエラーと対処：
- `FILE_CREATE` / パーミッション関連 → PermissionGuard がブロック、`result.permission_checks` を確認
- メモリー書き込み失敗 → MemoryBridge ストレージ問題、ディレクトリ権限を確認
- 圧縮失敗 → ContextCompressor の問題、通常メインフローには影響なし

---

## 言語ルール

- ユーザー言語を自動検出（中国語/英語/日本語）
- 全出力はユーザーと同じ言語を使用
- ロール名マッピング: 架构师→Architect, PM→Product Manager など

---

## プロジェクトライフサイクル：11フェーズモデル（V3.5）

> **定義ドキュメント**: `docs/prd/lifecycle_phases_definition.md`（権威）
> **レビューレポート**: `docs/prd/lifecycle_phases_review.md`（7ロールレビュー、9件の採択）

### フェーズ概要

| # | フェーズ | 主導 | レビュー担当者 | オプション | ゲート |
|---|---------|------|--------------|-----------|--------|
| P1 | 要件分析 | pm | arch+test+sec+ui | ❌ | 受入基準が定量的 |
| P2 | アーキテクチャ設計 | arch | pm+sec+infra | ❌ | 重み付きコンセンサス≥70% |
| P3 | 技術設計 | arch+coder | coder+test | ❌ | API仕様が明確 |
| P4 | データ設計 | arch+coder | arch+sec | ✅ | 3NFまたは非正規化の正当性 |
| P5 | インタラクション設計 | ui | pm+test+sec | ✅ | コアフロー可用性検証通過 |
| P6 | セキュリティレビュー | sec | arch+infra | ✅ | P0/P1脆弱性なし、コンプライアンス全緑 |
| P7 | テスト計画 | test | arch+sec+infra+pm | ❌ | テスト計画レビュー通過 |
| P8 | 開発実装 | coder | arch+sec+test+coder | ❌ | コードレビュー通過、P0欠陥なし |
| P9 | テスト実行 | test | arch+pm+sec+infra | ❌ | カバレッジ≥80%+P7計画100%実行 |
| P10 | デプロイ | infra | arch+sec+test | ❌ | デプロイ訓練通過 |
| P11 | 運用保障 | infra+sec | arch+infra | ✅ | P99<目標値、アラート100% |

### 依存グラフ

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

### ライフサイクルテンプレート

| テンプレート | フェーズ | ユースケース |
|-------------|---------|-------------|
| `full` | P1-P11全フェーズ | 完全プロジェクト |
| `backend` | P5なし | バックエンドサービス |
| `frontend` | P4,P6なし | フロントエンドアプリ |
| `internal_tool` | P4,P5,P6,P11なし | 社内ツール |
| `minimal` | P1,P3,P7,P8,P9 | 最小セット |

### ゲートメカニズム

- **強制実行**: 各フェーズのゲートは必ずチェック
- **非達成でも非ブロック**: ギャップレポート（ギャップ項目+原因分析）を生成、ユーザーが進行可否を判断
- **トレーサビリティ**: 全ゲート結果をチェックポイントに記録

### 要件変更プロセス

```
変更要求(pm/user) → 影響分析(arch+sec+test) → 変更レビュー(全ロール) → 承認/却下(pm+arch) → 影響フェーズへロールバック
```

---

## テスト鉄則（⚠️ AIがテストを書く時必須守）

### 鉄則1：ドキュメント先行 — API呼び出しを推測で書かない

### 鉄則2：失敗は報告 — アサーション修正で「通す」な禁止

### 鉄則3：次元完全 — Happy Pathだけテストしない

| 次元 | 最低比率 |
|------|---------|
| Happy Path | ≥50% |
| Error Case | **≥15%** |
| Boundary | ≥10% |
| Performance | **≥5%** |
| Integration | ≥10% |

---

## メタ鉄則：ドキュメント先行、全てをトレース（⚠️ 最高法）

> **ドキュメント先行、万事留痕** — 全ての他のルールを統轄する最高鉄則です。
> **このルール違反は重大エラーであり、行われた全作業を無効化します。**

### コア原則

```
コードを書く前 → Plan/Spec ドキュメントが存在すること
変更を加える前 → 影響分析が文書化されていること
作業完了後 → 結果がドキュメントに記録されていること
決定後 → 理由がトレース可能であること
```

### 必須要件

| フェーズ | 要件 | 検証 |
|----------|------|------|
| **作業前** | Spec/Plan ドキュメントなしにコードなし | `docs/spec/` または `docs/prd/` に該当ドキュメントあり |
| **作業中** | 全決定に理由付きでログ | コミットメッセージ、ADR、またはインラインコメントで WHY を説明 |
| **作業後** | 影響する全ドキュメントを同期的に更新 | バージョン/モジュール数/テスト数が全ドキュメントで一貫 |
| **常時** | ドキュメント由来のトレース不能な孤立コードなし | 全ファイルの目的が少なくとも1つのドキュメントに記録 |

### 「ドキュメント先行」の意味

1. **実装前に Spec**: SPEC や PRD がない場合は、まず書く。1段落の Spec でも無いよりマシ。
2. **コーディング前に設計**: アーキテクチャ決定はコード書く前に記録。
3. **テスト前にテスト計画**: 何をテストするか、なぜかを、テストコード書く前に。
4. **マージ前に変更ログ**: 何が変更されたか、なぜかを、プッシュ前に。

### 「全てをトレース」の意味

1. **全決定に WHY がある**: コードコメント、コミットメッセージ、ADR — 少なくとも1つ選ぶ。
2. **全ファイルにオーナー/目的がある**: なぜこのファイルが存在するか？文書化する。
3. **全変更にトレイルがある**: Git 履歴 + ドキュメント更新 = 完全監査トレイル。
4. **ステルス変更なし**: 対応するドキュメント更新なしにコミットなし。

### 強制

- CI チェック: `docs/` ディレクトリにコード変更にマッチする更新ファイルがなければならない
- レビューゲート: PR レビュアーがドキュメント同期状態をチェック
- コンセンサス: Coordinator が承認前にドキュメント完全性を検証
- 遡及的: 事前ドキュメントなしで行われた作業は即座にバックフィル必要

---

## デリバリーワークフロー鉄則（⚠️ 推進後毎回実行）

```
実装 → テスト(全量回帰) → コードウォークスルー → 注釈補完 → ドキュメント更新 → クリーンアップ → Git Push
```

### アノテーション標準（言語分離）

| カテゴリ | 言語 |
|----------|------|
| SKILL.md / README.md | **English** |
| README-CN.md | **中文（簡体）** |
| README-JP.md | **日本語（本ファイル）** |
| コード docstring | **English** (Args / Returns / Example) |
| 行内コメント | **English** |

---

## テストカバレッジ

| モジュール | テスト数 | ステータス |
|-----------|---------|----------|
| Core Tests (Dispatcher+Coordinator+Worker+Scratchpad+Consensus) | 39 | ✅ PASS |
| Role Mapping (RoleMatcher+エイリアス解決) | 25 | ✅ PASS |
| Upstream (Checkpoint+SemanticMatcher+Workflow+CompletionChecker) | 35 | ✅ PASS |
| MCEAdapter (CarryMem統合+タイプマッピング+グレースフルデグラデーション) | 30 | ✅ PASS |
| Contract Tests (Protocols+NullProviders+Cache+Monitor+Security) | 234 | ✅ PASS |
| V3.5 Integration (Lifecycle+ChangeRequest+Templates) | 7 | ✅ PASS |
**合計** | **560+** | **✅ ALL PASS** |

---

## バージョン履歴

- **v3.4.0** (2026-05-02): 11フェーズプロジェクトライフサイクル（full/backend/frontend/internal_tool/minimalテンプレート）+ 要件変更管理 + ゲートメカニズム+ギャップレポート + WorkflowEngineライフサイクル対応 + 560+テスト合格
- **v3.3** (2026-04-24): 7コアロール(security+devopsをコアに昇格) + RoleRegistry SSOT + TaskDefinition.role_prompt修正 + 環境変数のみAPI key入力 + InputValidator入力検証 + 3シナリオ検証完了
- **v3.3** (2026-04-17): WorkBuddy Claw統合 + MCE v0.4サポート + アノテーションEN化 + 多言語README
- **v3.2** (2026-04-17): MVP 3並行ライン (E2E Demo + Dispatcher UX + MCE Adapter)
- **v3.1** (2026-04-16): プロンプト最適化システム
- **v3.0** (2026-04-16): V3アーキテクチャ基盤

---

## サブスキルアーキテクチャ（V3.6.1 新機能）

> 6つの原子サブスキル。独立使用または組み合わせ呼出しが可能で、完全なDispatcherを起動する必要はありません。

### アーキテクチャ概要

```
skills/
├── __init__.py              # パッケージ初期化、get_skill/list_skills/discover_allをエクスポート
├── registry.py               # BaseSkillクラス + 遅延ロードレジストリ（importlib自動検出）
├── dispatch/handler.py       # → MultiAgentDispatcher
├── intent/handler.py         # → IntentWorkflowMapper
├── review/handler.py         # → FiveAxisConsensusEngine
├── security/handler.py       # → InputValidator + OperationClassifier
├── test/handler.py           # → TestQualityGuard
└── retrospective/handler.py  # → RetrospectiveEngine
```

### いつサブスキルを使う？

| シナリオ | 推奨方式 | 説明 |
|----------|---------|------|
| 完全マルチロールコラボレーション | `MultiAgentDispatcher` または `DispatchSkill` | 7ロール自動マッチング+並列+コンセンサス |
| 意図検出のみ | `IntentSkill` | ライトウェイト、完全なDispatcher不要 |
| コードレビューのみ | `ReviewSkill` | 5軸レビュー、スケジューリングフローから独立 |
| セキュリティ入力スキャン | `SecuritySkill` | 40種検出パターン、単独使用可能 |
| テスト戦略生成 | `TestSkill` | テスト品質監査+テストケース提案 |
| スケジューリング後の振り返り | `RetrospectiveSkill` | パターン抽出+改善提案 |

#### Mock Mode の振る舞い

全6つのサブスキルは **APIキーなし** で Mock モード動作可能：

| Skill | Mock 戻り値 | 忠実度 | 備考 |
|-------|------------|--------|------|
| **DispatchSkill** | 事前構築済み Markdown レポート（シミュレート済みWorker結果） | 高 | 全7ロールをリアルなコンテンツでシミュレート |
| **IntentSkill** | 検出された意図 + 信頼度スコア + ワークフロー提案 | 高 | ルールベースのキーワードマッチング、決定論的 |
| **ReviewSkill** | 5軸レビュースコア + 合格/警告/不合格判定 | 中 | スコアは0.75周辺のガウス分布に従う |
| **SecuritySkill** | スキャン結果：安全/警告/クリティカル + 一致パターン | 高 | パターンデータベースは実物（40種検出パターン） |
| **TestSkill** | テスト戦略 + 品質スコア + 改善提案 | 中 | タスクキーワードから生成 |
| **RetrospectiveSkill** | ディスパッチ後分析 + パターン抽出 | 低〜中 | 初回実行時は履歴が空、経過とともに蓄積 |

**Mock モードでの主要保証：**
- ✅ ネットワーク呼び出しなし — 完全オフライン
- ✅ 同じ入力に対して決定論的出力（RetrospectiveSkillを除く）
- ✅ リアルモードと同じデータ構造（`DispatchResult`, `ReviewResult` 等）
- ⚠️ コンテンツはテンプレートベース — LLM生成ではない
- ⚠️ RetrospectiveSkill は ≥1回のリアルディスパッチ後にパターン表示

**リアルモードへの切り替え：**
```python
# Mock モード（デフォルト、設定不要）
result = skill.run("your task")

# リアルモード（APIキー必要）
import os
result = skill.run("your task", backend="openai",
                    api_key=os.environ["OPENAI_API_KEY"])
```

### クイックスタート

```python
# 方法1: 直接インポート
from skills.dispatch.handler import DispatchSkill
from skills.security.handler import SecuritySkill
from skills.intent.handler import IntentSkill

# 方法2: レジストリ経由で動的発見
from skills import get_skill, list_skills, discover_all
skills = discover_all()  # 全サブスキルインスタンスを取得
for name, skill in skills.items():
    print(f"{name}: {skill.info()['description']}")
```

### Dispatcherとの関係

サブスキルはDispatcherの**代替**ではなく**補完**です：

- **Dispatcher** = 完全なマルチエージェントコラボレーションフロー（検証→マッチング→スケジューリング→実行→コンセンサス→レポート）
- **サブスキル** = 単一能力のライトウェイトエントリ（1つの機能だけが必要な場合、エンジン全体を起動せずに済む）

典型的な組み合わせ：まず `IntentSkill.detect()` で意図を判断し、次に `DispatchSkill.run()` でコラボレーションを実行し、最後に `RetrospectiveSkill.summary()` で振り返りを行います。

---

## 🔄 制御論強化（V3.7.2）

> 上流 TraeMultiAgentSkill v2.5 の制御論アーキテクチャに着想。
> フィードバックループ、実行ガード、インテリジェンスを追加する5つの新モジュール。

| モジュール | ファイル | 目的 |
|-----------|---------|------|
| FeedbackControlLoop | `feedback_control_loop.py` | Sense→Decide→Act→Feedbackクローズドループ反復 |
| ExecutionGuard | `execution_guard.py` | リアルタイム中止ガード（タイムアウト/出力/キーワード） |
| PerformanceFingerprint | `performance_fingerprint.py` | 統一フィンガープリント+TF-IDF類似度検索 |
| SimilarTaskRecommender | `similar_task_recommender.py` | 履歴ベースタスク構成推奨 |
| AdaptiveRoleSelector | `adaptive_role_selector.py` | 成功率駆動適応型ロール選択 |

### クイックスタート

```python
from scripts.collaboration import (
    FeedbackControlLoop, PerformanceFingerprint,
    SimilarTaskRecommender, AdaptiveRoleSelector, ExecutionGuard
)

# フィードバックループ（品質ゲート通過まで自動リトライ）
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("認証システム設計", max_iterations=3)

# パフォーマンスフィンガープリント
fp = PerformanceFingerprint()
fp.record_execution(task, result, timing, roles)
similar = fp.find_similar("ログインページ追加")

# スマート推奨
recommender = SimilarTaskRecommender(fp)
rec = recommender.recommend("API実装")
print(rec["recommended_roles"])  # ["architect", "coder"]

# 適応型ロール選択
selector = AdaptiveRoleSelector(fp)
roles = selector.select_roles("セキュリティバグ修正", intent="bug_fix")
```
