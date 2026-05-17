# DevSquad リファレンスガイド

> **バージョン**: V3.6.0 | **更新日**: 2026-05-05
>
> DevSquad機能の深い理解が必要な開発者向けの完全機能マニュアル。
> クイックスタートは [QUICK_START_JP.md](QUICK_START_JP.md) を参照。

---

## 目次

- [1. コアアーキテクチャ](#1-コアアーキテクチャ)
- [2. タスクディスパッチ](#2-タスクディスパッチ)
- [3. フルライフサイクル開発](#3-フルライフサイクル開発)
- [4. マルチロール協調](#4-マルチロール協調)
- [5. レビューとコンセンサス](#5-レビューとコンセンサス)
- [6. プロンプト最適化](#6-プロンプト最適化)
- [7. エージェント間連携](#7-エージェント間連携)
- [8. ルール注入とセキュリティ](#8-ルール注入とセキュリティ)
- [9. 品質保証](#9-品質保証)
- [10. パフォーマンスモニタリング](#10-パフォーマンスモニタリング)
- [11. ロールテンプレートマーケット](#11-ロールテンプレートマーケット)
- [12. 設定システム](#12-設定システム)
- [13. デプロイ方法](#13-デプロイ方法)
- [14. エージェントスキル品質フレームワーク](#14-エージェントスキル品質フレームワーク)
- [15. よくある質問](#15-よくある質問)
- [付録A：CarryMem連携](#付録acarrymem連携)
- [付録B：完全モジュール一覧](#付録b完全モジュール一覧)

---

## 1. コアアーキテクチャ

DevSquadは **Coordinator/Worker/Scratchpad** の3層アーキテクチャに基づいています：

```
ユーザータスク → [InputValidator セキュリティチェック]
              → [RoleMatcher ロールマッチング]
              → [Coordinator グローバル編成]
                ├─ [preload_rules ルール事前読み込み]
                ├─ [ThreadPoolExecutor 並列Workers]
                │   └─ Worker(ロール指示 + ルール注入 + 関連発見 + QC注入)
                │       ├─ [PromptAssembler 動的アセンブル]
                │       ├─ [EnhancedWorker 拡張：キャッシュ/リトライ/モニタ/ルール]
                │       └─ [Scratchpad リアルタイム共有]
                ├─ [ConsensusEngine 重み付きコンセンサス]
                └─ [ReportFormatter レポート整形]
              → 構造化レポート
```

**7つのコアロール**：

| ロール | 短縮ID | 責任 |
|--------|--------|------|
| アーキテクト | `arch` | システム設計、技術選定、アーキテクチャ決定 |
| プロダクトマネージャー | `pm` | 要件分析、ユーザーストーリー、優先順位付け |
| セキュリティ専門家 | `sec` | 脅威モデリング、脆弱性監査、コンプライアンス |
| テスター | `test` | テスト戦略、品質保証、カバレッジ |
| コーダー | `coder` | 実装、コードレビュー、パフォーマンス最適化 |
| DevOps専門家 | `infra` | CI/CD、コンテナ化、モニタリング、インフラ |
| UIデザイナー | `ui` | インタラクション設計、ユーザー体験、アクセシビリティ |

> 💡 **クイックインストールガイド**: [QUICK_START_JP.md](QUICK_START_JP.md#インストール) を参照。

### ロール詳細と典型的なシーン

**🏗️ アーキテクト (arch)** — 重み3.0、拒否権あり

システムの「総設計者」。

- **シーン1**: SaaSプラットフォーム構築 — モノリスvsマイクロサービス評価
- **シーン2**: パフォーマンスボトルネック — 根本原因分析と解決策提案
- **シーン3**: 技術選定 — 長期保守性に基づく決定

**📋 プロダクトマネージャー (pm)** — 重み2.0

ユーザーの「代弁者」。

**🔒 セキュリティ専門家 (sec)** — 重み2.5、拒否権あり

システムの「門番」。

**🧪 テスター (test)** — 重み1.5

品質の「把关者」。

**💻 コーダー (coder)** — 重み1.5

ソリューションの「実装者」。

**🔧 DevOps専門家 (infra)** — 重み1.0

インフラの「責任者」。

**🎨 UIデザイナー (ui)** — 重み0.9

体験の「形成者」。

### ロール選択クイックリファレンス

| タスクタイプ | 推奨ロール | 説明 |
|-------------|-----------|------|
| クイックコードレビュー | `coder` | 単一ロールで十分 |
| API設計 | `arch coder` | 方針決定＋インターフェース定義 |
| セキュリティ監査 | `sec coder` | 脆弱性発見＋修正 |
| 新機能開発 | `arch pm coder test` | 設計→要件→実装→検証 |
| 完全プロジェクト | 全7ロール | フルライフサイクルカバレッジ |

---

## 2. タスクディスパッチ

> **利用シーン**: マルチロール協調分析が必要な開発タスク。

### ディスパッチ方式比較

| 方式 | 適したシーン | ロール数 | 所要時間 |
|------|------------|---------|---------|
| 基本ディスパッチ | 単一問題の迅速分析 | 1-3 | 秒単位 |
| バッチディスパッチ | 複数独立タスク並列 | 各1-3 | 並列 |
| ワークフローエンジン | 複雑プロジェクト段階的推進 | 各フェーズ2-5 | 分単位 |

### 2.1 基本ディスパッチ

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# 自動ロールマッチング
result = disp.dispatch("マイクロサービスアーキテクチャを設計")

# ロール指定
result = disp.dispatch("APIパフォーマンス最適化", roles=["architect", "coder"])

# クイックディスパッチ
result = disp.quick_dispatch("データベース設計", output_format="structured")
```

> 📖 **サンプル例**: [examples/quick_demo.py](../../examples/quick_demo.py) を参照。

### 2.2 3つの出力フォーマット

- **structured**（デフォルト）: 完全な分析レポート
- **compact**: コア結論＋アクションアイテム
- **detailed**: 分析プロセス＋リスク評価

### 2.3 バッチディスパッチ

```python
from scripts.collaboration.batch_scheduler import BatchScheduler

scheduler = BatchScheduler()
results = scheduler.schedule([
    "ユーザー認証システム設計",
    "データベースクエリ最適化",
    "REST API実装",
])
```

### 2.4 ワークフローエンジン

```python
from scripts.collaboration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.create_workflow("ECプラットフォーム構築")
result = engine.execute(workflow, checkpoint_dir="./checkpoints")
```

---

## 3. フルライフサイクル開発

### 11フェーズモデル

```
P1 要件 ──→ P2 アーキテクチャ ──┬──→ P3 技術設計 ──→ ... ──→ P11 運用
     [pm]         [arch]           │     [arch+coder]
                                ├──→ P4 データ設計(オプション)
                                └──→ P5 インタラクション設計(オプション)
```

| # | フェーズ | 主導 | ゲート |
|---|---------|------|--------|
| P1 | 要件分析 | pm | 受入基準が定量的・明確 |
| P2 | アーキテクチャ設計 | arch | コンセンサス通過 |
| P3 | 技術設計 | arch+coder | API仕様が明確 |
| P4-P6 | オプションフェーズ | 各種 | 条件付き |
| P7 | テスト計画 | test | レビュー通過 |
| P8 | 実装 | coder | コードレビュー通過 |
| P9 | テスト実行 | test | カバレッジ≥80% |
| P10 | デプロイ | infra | ロールバック検証 |
| P11 | 運用保障 | infra+sec | アラート100% |

### 5つの定義済みテンプレート

| テンプレート | フェーズ | 利用シーン |
|-------------|---------|-----------|
| `full` | P1-P11 | 完全プロジェクト |
| `backend` | P5なし | バックエンド |
| `frontend` | P4,P6なし | フロントエンド |
| `internal_tool` | P4,P5,P6,P11なし | 内部ツール |
| `minimal` | P1,P3,P7,P8,P9 | 最小セット |

### 3.1 チェックポイント管理

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

cm = CheckpointManager()
cm.save("architecture_complete", {"task_id": "t1", "phase": "architecture"})
state = cm.load("architecture_complete")
```

### 3.2 タスク完了度トラッキング

```python
from scripts.collaboration.task_completion_checker import TaskCompletionChecker

checker = TaskCompletionChecker()
report = checker.check(task_definition, worker_results)
```

---

## 4. マルチロール協調

### 4.1 スクラッチパッド（共有ワークスペース）

```python
from scripts.collaboration.scratchpad import Scratchpad

sp = Scratchpad()
sp.write("architect", "decision", "マイクロサービスを採用")
sp.write_shared("consensus", "final_decision", "承認: マイクロサービス")
sp.write_private("security", "vulnerability_found", "/api/usersにSQLインジェクション")
```

| 領域 | 用途 | ルール |
|------|------|--------|
| READONLY | 他エージェントの出力 | 読み取り専用 |
| WRITE | 自分の出力 | 分離名前空間 |
| SHARED | コンセンサス結論 | 投票で書き込み |
| PRIVATE | 機密データ | 他には不可視 |

### 4.2 エージェントブリーフィング

前段エージェントの出力を自動注入。

### 4.3 デュアルレイヤーコンテキスト

- **プロジェクトレベル**: 長期情報（技術スタックなど）
- **タスクレベル**: 一時情報（タスク完了後に期限切れ）

---

## 5. レビューとコンセンサス

### 5.1 加重投票コンセンサス

```python
from scripts.collaboration.consensus import ConsensusEngine

engine = ConsensusEngine()
views = {
    "architect": {"decision": "microservice", "confidence": 0.9},
    "security": {"decision": "monolith", "confidence": 0.7},
}
result = engine.resolve(views)
```

**重み**: architect=3.0, security=2.5, pm=2.0, coder/tester=1.5, devops/ui=1.0

### 5.2 拒否権

セキュリティとアーキテクトは拒否権を持つ。

### 5.3 5軸コンセンサスエンジン

```python
from scripts.collaboration.five_axis_consensus import FiveAxisConsensusEngine

engine = FiveAxisConsensusEngine()
# 5軸: 正確性、安全性、パフォーマンス、保守性、テストカバレッジ
```

---

## 6. プロンプト最適化

### 6.1 動的プロンプトアセンブル

タスク複雑さに応じてテンプレート自動選択（SIMPLE/MEDIUM/COMPLEX）。

### 6.2 QC設定注入

ハルシネーション防止、過信防止、代替案強制。

---

## 7. エージェント間連携

### 7.1 コーディネーター

実行順序とコンテキスト受け渡しを管理。

### 7.2 EnhancedWorker

キャッシュ、リトライ、モニタリング、ルール注入の4機能強化。

### 7.3 スキルレジストリ

分析パターンの登録と再利用。

---

## 8. ルール注入とセキュリティ

### 8.1 自然言語ルール収集

4種類: `always`, `forbid`, `avoid`, `prefer`

### 8.2 入力検証（21+パターン）

SQLインジェクション、XSS、コマンドインジェクション等を検出。

### 8.3 パーミッションガード

4レベル: PLAN → DEFAULT → AUTO → BYPASS

---

## 9. 品質保証

### 9.1 信頼度スコアリング

5因子評価（完全性、確実性、特定性等）。

### 9.2 テスト品質ガード

カバレッジ、エラーケース比率、モック妥当性を検証。

---

## 10. パフォーマンスモニタリング

P95/P99メトリクス、ボトルネック検出。

---

## 11. ロールテンプレートマーケット

カスタムロールプロンプトの公開・共有・再利用。

---

## 12. 設定システム

### 12.1 .devsquad.yaml

> 📖 **完全設定例**: [QUICK_START_JP.md](QUICK_START_JP.md#設定オプション) を参照。

### 12.2 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `OPENAI_API_KEY` | なし | OpenAI APIキー |
| `ANTHROPIC_API_KEY` | なし | Anthropic APIキー |
| `DEVSQUAD_LLM_BACKEND` | mock | LLMバックエンドタイプ |
| `DEVSQUAD_LOG_LEVEL` | WARNING | ログレベル |

---

## 13. デプロイ方法

### CLI / Python API / MCP / Docker

> 📖 **クイックスタートコマンド**: [QUICK_START_JP.md](QUICK_START_JP.md#最初のディスパッチ3行のコード)

### Kubernetes (Helm)

```bash
helm install devsquad ./helm/devsquad
kubectl port-forward svc/devsquad-api 8000:8000
```

> 📖 **完全Helmドキュメント**: [helm/devsquad/README.md](../../helm/devsquad/README.md)

---

## 14. エージェントスキル品質フレームワーク

### 14.1 反合理化エンジン

「これは小さな変更」等の言い訳をブロック。

### 14.2 検証ゲート

「完了」として受け入れるための強制的証拠要件。

### 14.3 イントント→ワークフローマッパー

自然言語意図を構造化ワークフローチェーンにマッピング（6意図×3言語）。

### 14.4 CLI ライフサイクルコマンド

| コマンド | 説明 |
|---------|------|
| `spec` | 仕様書生成 |
| `plan` | タスク分解 |
| `build` | TDD実装 |
| `test` | 証拠要件付きテスト |
| `review` | 5軸コードレビュー |
| `ship` | 事前起動チェック＋デプロイ |

---

## 14.5 サブスキル (V3.6.0)

DevSquadは完全なオーケストレーションパイプラインから独立して使用可能な **6つの原子サブスキル** (`skills/` パッケージ) を提供します：

| サブスキル | 用途 | モジュール |
|-----------|------|----------|
| `dispatch` | タスクディスパッチ | `skills.dispatch.handler.DispatchSkill` |
| `intent` | 意図検出 | `skills.intent.handler.IntentSkill` |
| `review` | コードレビュー | `skills.review.handler.ReviewSkill` |
| `security` | 入力スキャン | `skills.security.handler.SecuritySkill` |
| `test` | テスト生成 | `skills.test.handler.TestSkill` |
| `retrospective` | レトロスペクティブ分析 | `skills.retrospective.handler.RetrospectiveSkill` |

各サブスキルはコアモジュールの約50行ラッパーで、API KeyなしのMockモードで動作します。

```python
from skills import get_skill, list_skills
from skills.security.handler import SecuritySkill
risk = SecuritySkill().scan_input("不審な入力")
```

詳細は [SKILL.md](../SKILL.md) § "Layered Sub-Skill Architecture" を参照してください。

---

## 15. よくある質問

**Q: API Keyなしで使用できますか？**
はい。MockモードはAPI Keyなしで動作します。

**Q: CarryMem未インストール時の影響は？**
ありません。NullProviderへのグレースフルデグラデーション。

**Q: ロールの選び方は？**
単純: 1-2、複雑: 3-5、フル: 全7ロール。

**Q: 出力言語の切り替え？**
CLI: `--lang en`、Python: `MultiAgentDispatcher(lang="en")`

**Q: ロールプロンプトのカスタマイズ？**
ロールテンプレートマーケットまたは `ROLE_TEMPLATES` 直接変更。

---

## 付録A：CarryMem連携

オプションのクロスセッションメモリシステム。

```bash
pip install carrymem[devsquad]>=0.2.8
```

---

## 付録B：完全モジュール一覧

| # | モジュール | 機能 |
|---|----------|------|
| 1 | MultiAgentDispatcher | 統一エントリ |
| 2 | Coordinator | グローバル編成 |
| 3 | Scratchpad | 共有ワークスペース |
| 4 | Worker | ロール実行器 |
| 5 | ConsensusEngine | 加重投票＋拒否権 |
| 6 | BatchScheduler | バッチスケジューリング |
| 7 | ContextCompressor | コンテキスト圧縮 |
| 8 | PermissionGuard | パーミッション制御 |
| 9 | Skillifier | スキル学習 |
| 10 | WarmupManager | ウォームアップ |
| 11 | MemoryBridge | クロスセッションメモリ |
| 12 | TestQualityGuard | テスト品質ガード |
| 13 | PromptAssembler | プロンプトアセンブル＋QC |
| 14 | MCEAdapter | CarryMem連携 |
| 15 | RoleMatcher | キーワードマッチング |
| 16 | ReportFormatter | レポート生成 |
| 17 | InputValidator | 入力検証 |
| 18 | AISemanticMatcher | セマンティックマッチング |
| 19 | CheckpointManager | 状態永続化 |
| 20 | WorkflowEngine | ワークフロー＋ライフサイクル |
| 21 | TaskCompletionChecker | 完了度トラッキング |
| 22 | CodeMapGenerator | コード分析 |
| 23 | DualLayerContextManager | 二層コンテキスト |
| 24 | SkillRegistry | スキルレジストリ |
| 25 | IntentWorkflowMapper | 意図マッピング |
| 26 | OperationClassifier | 操作分類 |
| 27 | FiveAxisConsensusEngine | 5軸コンセンサス |
| 28-35 | LLM関連 | バックエンド/キャッシュ/リトライ |
| 36-47 | 拡張モジュール | Async/Enhanced/etc |

---

*DevSquad V3.6.0 — 完全リファレンスガイド*
