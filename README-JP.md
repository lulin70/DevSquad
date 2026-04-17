# Trae Multi-Agent Skill

🎭 **V3.3** — 16のコアモジュール、約828のテスト、100%合格率を持つマルチエージェントコラボレーションプラットフォーム。
タスクタイプに基づき、適切なエージェントロール（アーキテクト、プロダクトマネージャー、テストエキスパート、UIデザイナー、コーダー）に動的にディスパッチします。
マルチエージェントコラボレーション、コンセンサスメカニズム、外部統合（MCE + WorkBuddy Claw）付きメモリブリッジ、プロンプト最適化、構造化レポートをサポートします。
中日英3ヶ国語対応。

## 🎉 2026年4月 — V3 進化履歴

### V3.3 (2026-04-17) — WorkBuddy Claw 統合
- ✅ **WorkBuddyClawSource**（約404行）— `/Users/lin/WorkBuddy/Claw/.memory/` への読み取り専用ブリッジ
- ✅ **Plan A: メモリブリッジ** — INDEX転置インデックス検索、コアファイルマッピング、日次ログ
- ✅ **Plan B: AIニュースフィード** — automation memory.md 解析による最新AI業界情報
- ✅ **Dispatcher 自動注入** — キーワードトリガーで Scratchpad へAIニュース自動注入
- ✅ **33件の新テスト** — Claw 統合テストスイート（T-A01~A08 / T-B01~B04 / T-D01~D02）

### V3.2 (2026-04-17) — MVP 並行3ライン
- ✅ **E2E 完全デモ**（`e2e_full_demo.py`）— CLI付き本番級10ステップフローデモ
- ✅ **MCE アダプター**（`mce_adapter.py`）— メモリ分類エンジンアダプター（遅延ロード/グレースフルデグラデ）
- ✅ **Dispatcher UX 強化** — 構造化レポート（structured / compact / detailed フォーマット）
- ✅ **47件の新テスト** — MCE(23) + Dispatcher UX(24)
- ✅ **デリバリーワークフロー鉄則** — 実装→テスト→ウォークスルー→注釈→ドキュメント→Git ループ

### V3.1 (2026-04-16) — プロンプト最適化システム
- ✅ **PromptAssembler** — 動的アセンブル（TaskComplexity検出、3バリアント、5スタイル）
- ✅ **PromptVariantGenerator** — Skillifyクローズドループ（A/B プロモーションライフサイクル）
- ✅ **59件の新テスト** — プロンプト最適化スイート

### V3.0 (2026-04-16) — V3 アーキテクチャ基盤
- ✅ **完全再設計** — Coordinator/Worker/Scratchpad パターン、11コアモジュール
- ✅ **約710ベースラインテスト** — 全て合格

---

## 🏗️ アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MultiAgentSkill v3                          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │Coordinator│←→│Compressor│←→│   Guard  │←→│ Skillify │←→│Warmup │ │
│  │ コーディネータ│  │ 圧縮器    │  │ 権限ガード │  │ スキル生成  │  │予熱   │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └────┬─────┘  └───┬───┘ │
│       │                                      │            │       │
│       ▼                                      ▼            ▼       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              MemoryBridge (メモリブリッジ)                   │   │
│  │  MCE + WorkBuddy Claw 外部統合                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 モジュール一覧（16コアモジュール）

| # | モジュール | ファイル | テスト数 | 説明 |
|---|-----------|---------|----------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 54+24 | 統一ディスパッチ入口 |
| 1 | **Coordinator** | `coordinator.py` | (E2E) | マルチエージェント調整 |
| 2 | **Scratchpad** | `scratchpad.py` | (E2E) | 共有ブラックボード |
| 3 | **Worker** | `worker.py` | (E2E) | ロール実行者 |
| 4 | **ConsensusEngine** | `consensus.py` | (E2E) | 重み付け投票+拒否権 |
| 5 | **BatchScheduler** | `batch_scheduler.py` | (E2E) | 並列/直列ハイブリッド |
| 6 | **ContextCompressor** | `context_compressor.py` | 72 | 4段階圧縮 |
| 7 | **PermissionGuard** | `permission_guard.py` | 105 | 4レベル権限モデル |
| 8 | **Skillifier** | `skillifier.py` | 96 | パターン→スキル自動生成 |
| 9 | **WarmupManager** | `warmup_manager.py` | 103 | 3層起動予熱 |
| 10 | **MemoryBridge** | `memory_bridge.py` | 96+33 | 7タイプ記憶+外部統合 |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | 42 | 3層品質保証 |
| 12 | **PromptAssembler** | `prompt_assembler.py` | 59 | 動的プロンプトアセンブル |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | - | A/Bプロモーション |
| 14 | **MCEAdapter** | `mce_adapter.py` | 23 | MCE分類エンジンアダプター |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py`(class) | 33 | Claw読み取り専用ブリッジ |
| **合計** | — | — | **~828** | |

## 🚀 クイックスタート

### 基本インポート

```python
from scripts.collaboration import (
    MultiAgentDispatcher,
    Coordinator, Scratchpad, Worker,
    ConsensusEngine, BatchScheduler,
)

# 一発ディスパッチ（推奨）
dispatcher = MultiAgentDispatcher()
result = dispatcher.quick_dispatch(
    "ユーザー認証システムを設計してください",
    output_format="structured",
)
print(result)
```

### E2E デモ実行

```bash
python3 scripts/demo/e2e_full_demo.py \
    --task "マイクロサービスアーキテクチャの設計" \
    --roles architect product_manager coder tester ui-designer \
    --json
```

## 🎭 サポートするエージェントロール

| ロールID | 名前 | 主な責任 |
|----------|------|-----------|
| `architect` | アーキテクト | システム設計、技術選定、インターフェース定義 |
| `product_manager` | PM | 要件分析、ユーザーストーリー、優先順位決定 |
| `solo-coder` | 開発者 | 実装、コードレビュー、技術的詳細 |
| `tester` | テスター | テスト戦略、品質保証、エッジケース |
| `ui-designer` | UIデザイナー | インタラクションデザイン、UXフロー |

## 🔌 外部統合

| 統合 | タイプ | パス | ステータス |
|-------|--------|------|----------|
| **MCE (Memory Classification Engine)** | オプションアダプター | `/Users/lin/trae_projects/memory-classification-engine` | ✅ 統合済（遅延ロード） |
| **WorkBuddy (Claw)** | 読み取り専用ブリッジ | `/Users/lin/WorkBuddy/Claw` | ✅ 統合済（自動検出） |

## 📊 テスト結果

```
MemoryBridge Test:        96/96   ✅
Dispatcher Test:          54/54   ✅
MCE Adapter Test:         23/23   ✅
Dispatcher UX Test:       24/24   ✅
Claw Integration Test:    33/33   ✅
Prompt Optimization:       59/59   ✅
Enhanced E2E:             46/46   ✅
─────────────────────────────────
Total:                   ~828    ✅ ALL PASS
```

## 📁 プロジェクト構造

```
MultiAgentSkill/
├── SKILL.md                          # スキル定義（EN）
├── README.md                         # プロジェクト概要（EN）← デフォルト
├── README-CN.md                      # プロジェクト概要（中文）
├── README-JP.md                      # プロジェクト概要（日本語）
├── CHANGELOG.md                      # バージョン履歴
├── IMPLEMENTATION_STATUS.md         # 実装ステータス
├── CONFIGURATION.md                  # 設定ガイド
├── scripts/
│   ├── collaboration/               # コアモジュール（16ファイル）
│   │   ├── dispatcher.py            # 統一エントリポイント
│   │   ├── coordinator.py           # グローバルオーケストレーター
│   │   ├── scratchpad.py            # 共有ブラックボード
│   │   ├── worker.py                # ロール実行者
│   │   ├── consensus.py             # コンセンサスエンジン
│   │   ├── batch_scheduler.py       # ハイブリッドスケジューラ
│   │   ├── context_compressor.py    # コンテキスト圧縮
│   │   ├── permission_guard.py      # 権限ガード
│   │   ├── skillifier.py            # スキル学習
│   │   ├── warmup_manager.py        # 起動予熱マネージャ
│   │   ├── memory_bridge.py         # 記憶ブリッジ (+ WorkBuddyClawSource)
│   │   ├── prompt_assembler.py      # プロンプトアセンブラ
│   │   ├── prompt_variant_generator.py # プロンプトバリアント
│   │   ├── mce_adapter.py           # MCEアダプター
│   │   └── *_test.py                # 各モジュールのテスト
│   └── demo/
│       └── e2e_full_demo.py         # 本番級E2Eデモ
├── docs/
│   ├── architecture/                # アーキテクチャ文書
│   ├── spec/                       # 仕様書
│   └── planning/                   # 計画文書
└── data/                           # ランタイムデータ
```

## 🌍 多言語サポート

このスキルは中日英3ヶ国語対応です：

- **README.md** — English (デフォルト)
- **README-CN.md** — 中文（簡体字）
- **README-JP.md** — 日本語（本ファイル）

## 📄 関連ドキュメント

| ドキュメント | パス | 用途 |
|------------|------|------|
| スキル定義 | `SKILL.md` | スキルルールと鉄則 |
| 変更ログ | `CHANGELOG.md` | V3.0~V3.3 完全履歴 |
| 実装ステータス | `IMPLEMENTATION_STATUS.md` | モバージョン・モジュール・テスト |
| アーキテクチャ | `docs/architecture/v3-upgrade-proposal.md` | 進化計画 |
| Claw仕様 | `docs/spec/WORKBUDDY_CLAW_INTEGRATION_SPEC.md` | Claw統合仕様（実装済） |
| 設定ガイド | `CONFIGURATION.md` | 外部統合設定 |

## 📝 Annotation Standards (v3.3)

| カテゴリ | 言語 |
|----------|------|
| ドキュメント (SKILL.md / README.md) | **English** |
| README-CN.md | **中文（簡体字）** |
| README-JP.md | **日本語** |
| コード docstring | **English** (Args / Returns / Example) |
| 行内コメント | **English** (ビジネスロジック説明) |

## 📜 License

MIT License — 詳細は LICENSE ファイルを参照してください。
