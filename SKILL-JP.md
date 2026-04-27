---
name: devsquad
slug: devsquad
description: |
  V3.3.0 マルチエージェントコラボレーションプラットフォーム — Coordinator/Worker/Scratchpad
  パターンに基づく完全なマルチエージェントコラボレーションシステム。
  7コアロール（アーキテクト/PM/セキュリティ/テスター/コーダー/DevOps/UIデザイナー）、
  リアルLLMバックエンド（OpenAI/Anthropic）、CLI + MCP + Python API対応。
  99ユニットテスト全合格。中日英3ヶ国語対応。
---

# DevSquad V3.3.0 — マルチエージェントコラボレーションプラットフォーム

## コアポジショニング

このスキルは Trae を「単一AIアシスタント」から「マルチAIチーム」へアップグレードします。
タスクが提出されると、単一ロールで処理されるのではなく：

```
ユーザータスク → [入力検証] → [ロールマッチング] → [Coordinatorオーケストレーション]
             → [ThreadPoolExecutor並列Worker] → [Scratchpadリアルタイム共有]
             → [コンセンサス決定] → [レポート整形] → [構造化レポート]
```

## アーキテクチャ概要（27コアモジュール）

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
| 12 | **PromptAssembler** | `prompt_assembler.py` | 動的プロンプトアセンブル |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillifyクローズドループ |
| 14 | **MCEAdapter** | `mce_adapter.py` | MCE分類エンジンアダプター（v0.4対応） |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py`(class) | Claw読み取り専用ブリッジ |
| 16 | **RoleMatcher** | `role_matcher.py` | キーワードベースロールマッチング+エイリアス解決 |
| 17 | **ReportFormatter** | `report_formatter.py` | 構造化/コンパクト/詳細レポート生成 |
| 18 | **InputValidator** | `input_validator.py` | セキュリティ検証+16パターンPrompt注入検出 |
| 19 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM駆動セマンティックマッチング+バイリンガルフォールバック |
| 20 | **CheckpointManager** | `checkpoint_manager.py` | SHA256整合性、ハンドオフ文書、自動クリーンアップ |
| 21 | **WorkflowEngine** | `workflow_engine.py` | タスク→ワークフロー自動分割、ステップ実行、チェックポイント復元 |
| 22 | **TaskCompletionChecker** | `task_completion_checker.py` | 完了追跡+進捗永続化 |
| 23 | **CodeMapGenerator** | `code_map_generator.py` | Python ASTベースコード分析+依存グラフ |
| 24 | **DualLayerContext** | `dual_layer_context.py` | プロジェクト+タスクレベルコンテキスト（TTL付き） |
| 25 | **SkillRegistry** | `skill_registry.py` | スキル登録+発見+永続化 |
| 26 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic + ストリーミング + 120sタイムアウト |
| 27 | **ConfigManager** | `config_loader.py` | YAML設定+環境変数オーバーライド（16パラメータ） |

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
| **合計** | **99** | **✅ ALL PASS** |

---

## バージョン履歴

- **v3.3.0** (2026-04-27): リアルLLMバックエンド(OpenAI/Anthropic/Mock) + ThreadPoolExecutor並列実行 + InputValidator+16パターンPrompt注入検出 + RoleMatcher/ReportFormatter抽出 + AISemanticMatcherバイリンガルマッチング + CheckpointManager SHA256整合性 + WorkflowEngineタスク分割+チェックポイント復元 + TaskCompletionChecker完了追跡 + CodeMapGenerator AST分析 + DualLayerContext二層コンテキスト + SkillRegistryスキル登録 + ConfigManager YAML設定 + LLMBackendストリーミング + Docker + GitHub Actions CI + pipインストール対応 + 99ユニットテスト
- **v3.3** (2026-04-24): 7コアロール(security+devopsをコアに昇格) + RoleRegistry SSOT + TaskDefinition.role_prompt修正 + 環境変数のみAPI key入力 + InputValidator入力検証 + 3シナリオ検証完了
- **v3.3** (2026-04-17): WorkBuddy Claw統合 + MCE v0.4サポート + アノテーションEN化 + 多言語README
- **v3.2** (2026-04-17): MVP 3並行ライン (E2E Demo + Dispatcher UX + MCE Adapter)
- **v3.1** (2026-04-16): プロンプト最適化システム
- **v3.0** (2026-04-16): V3アーキテクチャ基盤
