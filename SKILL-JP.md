---
name: multi-agent-team-v3
slug: multi-agent-team-v3
description: |
  V3.3 マルチエージェントコラボレーションプラットフォーム — Coordinator/Worker/Scratchpad
  パターンに基づく完全なマルチエージェントコラボレーションシステム。
  16のコアモジュール：Coordinator + Scratchpad + Worker + ConsensusEngine +
  BatchScheduler + ContextCompressor + PermissionGuard +
  Skillifier + WarmupManager + MemoryBridge (MCE+Claw) +
  PromptAssembler + PromptVariantGenerator + MCEAdapter + WorkBuddyClawSource。
  ~825+テスト全合格。中日英3ヶ国語対応。
---

# Multi-Agent Team V3.3 — マルチエージェントコラボレーションプラットフォーム

## コアポジショニング

このスキルは Trae を「単一AIアシスタント」から「マルチAIチーム」へアップグレードします。
タスクが提出されると、単一ロールで処理されるのではなく：

```
ユーザータスク → [意図分析] → [ロールマッチング] → [Coordinatorオーケストレーション]
             → [Worker並列実行] → [Scratchpadリアルタイム共有]
             → [コンセンサス決定] → [MCE分類強化] → [結果集約]
```

## アーキテクチャ概要（16コアモジュール）

| # | モジュール | ファイル | 責任 |
|---|-----------|--------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 統一ディスパッチ入口（全モジュール統合） |
| 1 | **Coordinator** | `coordinator.py` | グローバルオーケストレーター：タスク分解、Worker割り当て、結果収集、競合解決 |
| 2 | **Scratchpad** | `scratchpad.py` | 共有ブラックボード、Worker間リアルタイム情報交換 |
| 3 | **Worker** | `worker.py` | 実行者：各ロール1インスタンス、独立実行+Scratchpad書き込み |
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

## ロールシステム（5ビルトインロール）

| ロールID | 名前 | キーワード | 主な責任 |
|----------|------|-----------|---------|
| `architect` | アーキテクト | 設計,選定,性能 | システム設計,技術選定 |
| `product-manager` | PM | 要求,PRD | 要件分析,製品企画 |
| `tester` | テスト専門家 | テスト,品質 | テスト戦略,品質保証 |
| `solo-coder` | 開発者 | 実装,開発 | 機能開発,コーディング |
| `ui-designer` | UIデザイナー | UI,画面 | UI/UX設計 |

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
| 全16モジュール | **~825+** | **✅ ALL PASS** |

---

## バージョン履歴

- **v3.3** (2026-04-17): WorkBuddy Claw統合 + MCE v0.4サポート + アノテーションEN化 + 多言語README
- **v3.2** (2026-04-17): MVP 3並行ライン (E2E Demo + Dispatcher UX + MCE Adapter)
- **v3.1** (2026-04-16): プロンプト最適化システム
- **v3.0** (2026-04-16): V3アーキテクチャ基盤
