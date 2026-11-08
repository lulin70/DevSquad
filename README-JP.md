# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>🎯 「単一のAIアシスタント」を「マルチロールAI専門チーム」にアップグレード</strong>
  <br>
  <em>7ロール · 12フェーズ · 10,656テスト<br>V4.10.0 — <a href="#-リリース履歴">リリース履歴</a> を参照</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Test quality" src="https://img.shields.io/badge/Test%20quality-0%20MAJOR-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V4.10.0-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 📑 目次

- [📖 長すぎる？まずこれを見て（30秒）](#-長すぎるまずこれを見て30秒)
- [🚀 インストール](#-インストール)
- [▶️ クイックスタート：最初のタスクを実行](#️-クイックスタート最初のタスクを実行)
- [⚙️ 設定](#️-設定)
- [👥 機能：7つのコアロール](#-機能7つのコアロール)
- [🏗️ 機能：5大能力ドメイン](#️-機能5大能力ドメイン)
- [🔬 Cybernetics Enhancement Modules（サイバネティクス拡張モジュール - V3.6.1）](#-cybernetics-enhancement-modulesサイバネティクス拡張モジュール---v361)
- [🏗️ アーキテクチャ概要（階層化設計）](#️-アーキテクチャ概要階層化設計)
- [🧩 Layered Sub-Skill Architecture（階層化サブスキルアーキテクチャ - V3.6.0）](#-layered-sub-skill-architecture階層化サブスキルアーキテクチャ---v360)
- [📋 Plan C Architecture（コアエンジン）](#-plan-c-architectureコアエンジン)
- [🧪 テスト](#-テスト)
- [📚 ドキュメント](#-ドキュメント)
- [📜 リリース履歴](#-リリース履歴)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 コントリビューション](#-コントリビューション)
- [📄 ライセンス](#-ライセンス)

## 📖 長すぎる？まずこれを見て（30秒）

### DevSquadとは？

**DevSquad**はマルチロールAIタスクオーケストレーターです。タスクを投入すると、単一のAI回答ではなく、タスクに応じて複数の専門ロールが協調し、多角的に審査された結論を最終的に提示します。

```
従来のAI:  あなた ──→ ChatGPT ──→ 1つの回答（網羅性に欠ける場合あり）
DevSquad:  あなた ──→ DevSquad ──→ [アーキテクト+セキュリティ+テスト+開発...] ──→ 多次元コンセンサス結論
```

### コアアドバンテージ（単一AIとの比較）

| 課題 | 従来の単一AI | DevSquad |
|------|----------|----------|
| **視点が単一** | 汎用視点のみ | タスクに応じて複数の専門ロールが協調 ✅ |
| **品質が制御不可** | セキュリティ問題を見落とす可能性 | 多次元交差検証 + コンセンサスメカニズム ✅ |
| **監査トレースなし** | 回答の根拠が不明 | 完全な監査チェーン + SHA256 完全性検証 ✅ |
| **複雑タスクで破綻** | 長時間タスクでコンテキスト消失しやすい | Checkpoint レジューム + ワークフローエンジン ✅ |

### 最速スタート（5分）

```bash
# インストール
pip install devsquad

# 実行 - AIチームに認証システムの設計を依頼
devsquad run "安全なユーザー認証システムを設計" --roles architect security tester coder

# 構造化レポートを出力：
# ✅ アーキテクト提案：JWT + Refresh Token 方式を採用...
# ✅ セキュリティ専門家審査：CSRF、XSS、SQLインジェクションを防止...
# ✅ テスト戦略：ユニットテストカバレッジ 90%+...
# ✅ 開発実装：完全なコードフレームワークを提供...
# 📊 コンセンサス結論：方式は実行可能、リスクは制御可能...
```

> **次のステップ** → [インストール](#-インストール) · [7つの実行方法](#️-クイックスタート最初のタスクを実行) · [設定](#️-設定)

### いつDevSquadを使うべきか？

| あなたのニーズ | 推奨ソリューション |
|---------|---------|
| 簡単なQ&A（"Python で for ループをどう書く？"） | ChatGPT/Claudeを直接使用 ✅ |
| コードスニペットレビュー | DevSquad 単一ロールモード ✅ |
| 複雑なシステム設計（多視点が必要） | **DevSquad マルチロール協調** 🎯 |
| 本番環境の自動化フロー | **DevSquad + REST API + Dashboard** 🎯 |

📚 **もっと深く知りたい？** → [完全クイックスタートガイド](QUICKSTART.md) | [218+ モジュール詳細リファレンス](SKILL.md)

---

## 🚀 インストール

### 前提条件
- **Python 3.10+**（3.10、3.11サポート、CIでテスト済み）
- パッケージ管理用 **pip** または **pipenv**

### Option A: PyPI インストール（推奨）
```bash
# PyPIからインストール — セットアップ不要、すぐ使用可能
pip install devsquad

# オプション依存関係付き
pip install "devsquad[api]"    # FastAPI + Streamlit dashboard
pip install "devsquad[all]"    # All optional features
```

### Option B: Git Clone + ローカルインストール
```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# コアパッケージをインストール（最小依存）
pip install -e .

# 使用準備完了！
devsquad dispatch -t "Design user authentication system"
```

### インストール検証
```bash
# バージョンを確認
devsquad --version
# Expected: DevSquad 4.10.0

# テストを実行
pytest tests/ -v --tb=short
# Expected: 9800+ collected（合格数は CI が権威）
```

---

## ▶️ クイックスタート：最初のタスクを実行

### Method 1: TRAE Skill（推奨 — すでに使用中）

DevSquadはTRAE Skillとして登録されています。TRAE IDEチャットでタスクを記述するだけで、7ロールチームが自動的にコラボレーションします。CLIやAPIの設定は不要です。

### Method 2: CLI（ターミナルユーザー推奨）

```bash
# インタラクティブセットアップウィザード（1-2分）
python scripts/cli.py init

# その後コラボレーションを開始！
devsquad dispatch -t "your task description"
```

### Method 3: MCP Server（IDE / ツール統合用）

```bash
# MCPサーバーを起動（stdioトランスポート、IDE統合用）
python3 -m scripts.mcp_server

# またはSSEトランスポート（リモートアクセス用）
python3 -m scripts.mcp_server --port 8080
```

完全な統合ガイド — インストール（`pip install "devsquad[mcp]" "mcp<2"`）、クライアント設定 JSON（Cursor / Claude Desktop）、9 ツールカタログ、RBAC / fail-closed 動作：[docs/integrations/MCP.md](docs/integrations/MCP.md)。

### Method 4: Web Dashboard（チーム推奨）

```bash
# 認証付きStreamlitダッシュボードを起動
streamlit run scripts/dashboard.py

# http://localhost:8501 を開く
# デフォルト開発用認証情報でログイン（INSTALL.md "Default credentials" 節を参照）
# 本番環境では必ずすべてのデフォルトを変更してください
```

### Method 5: REST API（統合推奨）

```bash
# 依存関係をインストール
pip install fastapi uvicorn

# APIサーバーを起動
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Swagger UIにアクセス: http://localhost:8000/docs
# ReDocにアクセス:      http://localhost:8000/redoc
```

### Method 6: Python API（開発者推奨）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
result = dispatcher.dispatch(
    task="Optimize database query performance",
    roles=["architect", "security", "tester"],
)
print(result.report)
print(result.consensus)
```

### Method 7: ワンクリック起動スクリプト（V3.9.2+）

```bash
# ワンクリック起動 — 4フェーズ：環境チェック → DB初期化 → フロントエンド構築 → サービス起動
./scripts/start.sh

# APIサーバーとStreamlitダッシュボードを同時に起動
./scripts/start.sh --dashboard

# APIポートを上書き
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# ヘルプを表示
./scripts/start.sh --help
```

`start.sh`はV3.9.2（P0-2）で導入された統合エントリポイントです。環境チェック、データベース初期化、フロントエンド構築、サービス起動を1コマンドで実行します。再現可能なビルドのために`requirements.lock`と組み合わせて使用してください（`pip install -r requirements.lock`）。V4.1.0は Loop Engineering、UI/UX 巡検、Adversarial 検証、DAG 可視化、Autonomous、プラグインホットロードを追加します。

---

## ⚙️ 設定

プロジェクトルートに`.devsquad.yaml`を作成:

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85

llm:
  backend: auto
  base_url: ""  # DEVSQUAD_OPENAI_BASE_URL 環境変数で設定
  model: ""     # DEVSQUAD_OPENAI_MODEL 環境変数で設定
  timeout: 120
```

または環境変数を使用（優先度が高い）:

```bash
# デフォルト: auto は最初にリアルバックエンドを試し、次に mock にフォールバック
export DEVSQUAD_LLM_BACKEND=auto
export DEVSQUAD_OPENAI_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_OPENAI_MODEL=gpt-4
export DEVSQUAD_OPENAI_API_KEY=sk-...
```

**環境変数リファレンス:**

| 変数 | 目的 | デフォルト |
|----------|---------|---------|
| `DEVSQUAD_LLM_BACKEND` | デフォルトバックエンドタイプ（auto\|mock\|trae\|openai\|anthropic\|fallback） | `auto` |
| `DEVSQUAD_OPENAI_API_KEY` | OpenAI/MOKA AI API key | None |
| `DEVSQUAD_OPENAI_BASE_URL` | OpenAI互換ベースURL | None |
| `DEVSQUAD_OPENAI_MODEL` | OpenAIモデル名 | `gpt-4` |
| `DEVSQUAD_ANTHROPIC_API_KEY` | Anthropic API key | None |
| `DEVSQUAD_ANTHROPIC_BASE_URL` | Anthropic互換ベースURL | None |
| `DEVSQUAD_ANTHROPIC_MODEL` | Anthropicモデル名 | `claude-sonnet-4-20250514` |
| `MOKA_TIMEOUT` | Moka LLM リクエストタイムアウト（秒、V4.10.0+） | `90.0` |
| `DEVSQUAD_LOG_LEVEL` | ログレベル | `WARNING` |

**Moka LLM 設定**：ローカル Moka サービスのチューニング（タイムアウト、リトライ）は [Moka チューニングガイド](docs/MOKA_TUNING_GUIDE.md) を参照。

---

## 👥 機能：7つのコアロール

| ロール | CLI ID | エイリアス | 重み | 最適用途 |
|------|--------|---------|--------|----------|
| 🏗️ **Architect** | `arch` | `architect` | 1.5 | システム設計、技術スタック、パフォーマンス/セキュリティアーキテクチャ |
| 📋 **Product Manager** | `pm` | `product-manager` | 1.2 | 要件、ユーザーストーリー、受け入れ基準 |
| 🛡️ **Security Expert** | `sec` | `security` | 1.1 | 脅威モデリング、脆弱性監査、コンプライアンス |
| 🧪 **Tester** | `test` | `tester`, `qa` | 1.0 | テスト戦略、品質保証、エッジケース |
| 💻 **Coder** | `coder` | `solo-coder`, `dev` | 1.0 | 実装、コードレビュー、パフォーマンス最適化 |
| 🔧 **DevOps** | `infra` | `devops` | 1.0 | CI/CD、コンテナ化、モニタリング、インフラ |
| 🎨 **UI Designer** | `ui` | `ui-designer` | 0.9 | UXフロー、インタラクション設計、アクセシビリティ |

**自動マッチ**: ロールが指定されない場合、ディスパッチャーがタスクキーワードに基づいて自動的にマッチングします。

---

## 🏗️ 機能：5大能力ドメイン

DevSquadの218+ モジュールは**5大能力ドメイン**に編成され、各ドメインが特定の問題を解決します：

### 🎯 Domain 1: Task Orchestration Engine（タスクオーケストレーションエンジン - コア）

> **複数の専門ロールが効率的に協調するための「指揮センター」**

| モジュール | 目的 | 使用タイミング |
|--------|---------|------------|
| **MultiAgentDispatcher** | 統一ディスパッチエントリポイント | すべてのタスクで自動的に |
| **Coordinator** | タスク分解 + ロール割り当て | 分解が必要な複雑なタスク |
| **Scratchpad** | リアルタイム情報交換用共有ブラックボード | ロール間協調 |
| **ConsensusEngine** | 重み付け投票 + 拒否権 + エスカレーションメカニズム | セキュリティ/アーキテクチャ紛争 |
| **BatchScheduler** | 並列/直列ハイブリッドスケジューリング | リソース制約環境 |

**コアワークフロー:**
```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [Sync/Async Worker Execution] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 🛡️ Domain 2: Quality Assurance System（品質保証システム）

> **AIの「サボり」や「ハルシネーション」を防止**

| モジュール | 目的 | 使用タイミング |
|--------|---------|------------|
| **InputValidator** | セキュリティ検証 + 40パターン検出（14禁止 + 21プロンプト注入 + 5疑わしい） | 本番環境 |
| **VerificationGate** | 必須エビデンス要件 + 7つの Red Flags 検出 | 重要な意思決定シナリオ |
| **AntiRationalizationEngine** | ロール別 言い訳→反論テーブルで品質ショートカットを防止 | 高品質要求 |
| **TestQualityGuard** | テスト品質監査（API検証 / アンチパターン検出 / 次元カバレッジ） | リリース前検証 |
| **PermissionGuard** | 4段階セーフティゲート（PLAN/DEFAULT/AUTO/BYPASS） | セキュリティセンシティブなタスク |

### ⚡ Domain 3: Performance & Reliability（パフォーマンスと信頼性）

> **システムをより速く、より安定、よりコスト効率よく**

| モジュール | 目的 | 使用タイミング |
|--------|---------|------------|
| **LLMCache** | TTLベース LRUキャッシュ + ディスク永続化（60-80%コスト削減） | 高頻度使用 |
| **LLMRetry** | 指数バックオフ + サーキットブレーカー + マルチバックエンドフォールバック | 不安定なネットワーク |
| **FeedbackControlLoop** | 品質しきい値達成まで自動反復する閉ループフィードバック制御 | 高品質出力の追求 |
| **ExecutionGuard** | 安全な実行のためのリアルタイム中止ガード（タイムアウト/出力/キーワード） | 長時間実行タスク |
| **FallbackBackend** | ヘルスモニタリング付き自動バックエンドフェイルオーバー | 高可用性要件 |

### 📊 Domain 4: Observability & Governance（可観測性とガバナンス）

> **システムが何をしているか、どう進んでいるかを把握**

| モジュール | 目的 | 使用タイミング |
|--------|---------|------------|
| **PerformanceMonitor** | P95/P99応答時間、CPU/メモリトラッキング、ボトルネック検出 | パフォーマンスチューニング |
| **UsageTracker** | Token/コスト使用量トラッキングとレポート | コスト制御 |
| **AuditLogger** | SHA256 完全性操作ログ + CSV/JSONエクスポート（Preview） | コンプライアンス監査 |
| **RBAC Engine** | 15+きめ細かい権限、5ロール（SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER）（Preview） | エンタープライズアクセス制御 |
| **Multi-Tenancy Manager** | 3分離レベル（strict/moderate/shared）、テナントスコープリソース（Preview） | マルチテナントSaaS |
| **Sensitive Data Masker** | PII検出とマスキング（メール/電話/IDカード/クレジットカード）、設定可能なルール（Preview） | データコンプライアンス |
| **HistoryManager** | SQLite時系列ストレージ：メトリクススナップショット、アラート履歴、APIログ | 振り返り分析 |

### 🔌 Domain 5: Integration & Extension（統合と拡張）

> **既存のツールチェーンに統合**

| モジュール | 目的 | 使用タイミング |
|--------|---------|------------|
| **CLI** | ライフサイクルコマンド付きコマンドラインインターフェース | 開発者の日常使用 |
| **REST API (FastAPI)** | OpenAPI/Swaggerドキュメント付き10+エンドポイント | マイクロサービス統合 |
| **Dashboard (Streamlit)** | 認証付きインタラクティブWebダッシュボード | 運用チームの可視化 |
| **MCP Protocol** | TRAE/Claude Code/Cursorとの統合 | AI Agentエコシステム |
| **Docker Support** | 本番デプロイ向けマルチステージビルド | コンテナ化環境 |
| **GitHub Actions CI** | Python 3.10-3.11マトリックステスト | CI/CDパイプライン |

---

## 🔬 Cybernetics Enhancement Modules（サイバネティクス拡張モジュール - V3.6.1）

> **非侵襲ラッパー設計 — オプションのスイッチ、既存コアロジックはゼロ変更**

5つのサイバネティクスモジュールは、既存のコアロジックを変更せずに独立または組み合わせて動作します：

```
User Task
    ↓
[SimilarTaskRecommender] ← Optional: 履歴からロールを提案
    ↓
[AdaptiveRoleSelector]   ← Optional: ロール選択を最適化
    ↓
[MultiAgentDispatcher]
    ↓
[FeedbackControlLoop]     ← 自動反復のためにディスパッチャーをラップ
    ↓ [each worker step]
[ExecutionGuard]          ← 各Worker実行をガード
    ↓
[PerformanceFingerprint]  ← ディスパッチ完了後に記録
```

### 1️⃣ FeedbackControlLoop（フィードバック閉ループコントローラー）
- 品質しきい値達成まで自動反復する閉ループフィードバック制御
- 設定可能な品質ゲート（`quality_gate`）と最大反復回数
- 軽量な品質評価（LLM呼び出しなし）、dry-runモードサポート

### 2️⃣ ExecutionGuard（実行ガード）
- リアルタイム実行監視 + 4つの中止条件：タイムアウト、出力サイズ、トークン数、重要キーワード
- 軽量チェック（<1ms）、外部依存ゼロ
- 動的に設定可能なしきい値

### 3️⃣ PerformanceFingerprint（パフォーマンスフィンガープリントシステム）
- 統一実行フィンガープリント記録（4データソース融合）
- 純Python TF-IDF実装（sklearn/numpy不要）、英語/中国語混在コンテンツ対応
- `.devsquad_data/fingerprints/`へのJSON永続化、gracefulなコールドスタート劣化

### 4️⃣ SimilarTaskRecommender（類似タスクレコメンダー）
- TF-IDFベースのタスク類似検索 + 履歴成功設定のレコメンド
- インテリジェントなロール組み合わせレコメンド、インテント予測、実行時間見積もり
- 信頼度スコアリング（high/medium/low）、gracefulなコールドスタート劣化

### 5️⃣ AdaptiveRoleSelector（適応型ロールセレクター）
- 履歴成功率に基づく3段階選択戦略
- 設定可能な最小成功率と最大ロール数
- 手動統計更新と包括的なロール有効性レポートをサポート

**推奨使用法**（段階的導入）:
```python
from scripts.collaboration import MultiAgentDispatcher, FeedbackControlLoop, ExecutionGuard, PerformanceFingerprint

dispatcher = MultiAgentDispatcher()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()

# Option 1: サイバネティクス完全スタック
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("Your task here")

# Option 2: Guardのみ（最小導入）
result = dispatcher.dispatch("Your task")
for w in result.worker_results:
    abort, reason = guard.check_abort(w.output, w.duration)
    if abort:
        print(f"Aborted: {reason}")

# Option 3: 学習のみ
fingerprint.record_execution("task", result, result.timing, result.matched_roles)
similar = fingerprint.find_similar("new task", top_k=3)
```

すべてのモジュールは**オプションのスイッチ**です — これらがなくてもDevSquadは完全に動作します。

---

## 🏗️ アーキテクチャ概要（階層化設計）

```
┌─────────────────────────────────────────────────────────────┐
│                    User Access Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Streamlit    │ │ FastAPI REST │ │ CLI/Notebook │        │
│  │ Dashboard    │ │ API Server   │ │ (Existing)   │        │
│  │ (Auth+HTTPS) │ │ (Swagger)    │ │              │        │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘        │
└─────────┼───────────────┼───────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                      │
│  ┌─────────────┐ ┌─────────────┐           │
│  │AuthManager  │ │HistoryMgr   │           │
│  │(RBAC Auth)  │ │(SQLite TSDB)│           │
│  └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────┐            │
│  │     LifecycleProtocol (11-Phase Engine)       │            │
│  │     UnifiedGateEngine + CheckpointManager     │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Persistence Layer                    │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐  │
│  │ SQLite DB  │ │ YAML Config│ │ Checkpoint Files       │  │
│  │ (History)  │ │ (Deploy)   │ │ (Lifecycle State)      │  │
│  └────────────┘ └────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 Layered Sub-Skill Architecture（階層化サブスキルアーキテクチャ - V3.6.0）

> DevSquadは**8つのアトミックサブスキル**を提供し、独立または組み合わせて使用できます。
> 各サブスキルは軽量ラッパー（約50行）で、既存のコアモジュールをインポート — 重複ロジックなし。

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7ロールオーケストレーション)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6インテント × 3言語)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5軸コードレビュー)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + テスト戦略生成
├── retrospective/  → RetroSkill    — RetrospectiveEngine + パターン抽出
├── prototype/      → PrototypeSkill — 高速プロトタイプスキャフォールディング (V4.5.0)
└── teach/          → TeachSkill     — 知識移転＆オンボーディング (V4.5.0)
```

### サブスキルクイックリファレンス

| Skill | コアメソッド | ラップ | Mockモード |
|-------|------------|-------|:---------:|
| `dispatch` | `run(task, roles, mode)` | MultiAgentDispatcher | ✅ |
| `intent` | `detect(text, lang)` | IntentWorkflowMapper | ✅ |
| `review` | `review(code)` | FiveAxisConsensusEngine | ✅ |
| `security` | `scan_input(text)` | InputValidator + OpClassifier | ✅ |
| `test` | `generate_strategy(module)` | TestQualityGuard | ✅ |
| `retrospective` | `run_retrospective(results)` | RetrospectiveEngine | ✅ |

### 使用例

```python
# 直接インポート（単一Skill推奨）
from skills.dispatch.handler import DispatchSkill

result = DispatchSkill().run("Fix login bug", roles=["coder", "tester"])

# レジストリ経由（動的発見）
from skills import get_skill, list_skills

print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
```

すべてのサブスキルは**API Keyなし**でMockモードで動作します。

---

## 📋 Plan C Architecture（コアエンジン）

**Unified Lifecycle Architecture** - CLI 6コマンド vs 12フェーズ（P0-P11）ライフサイクルを解決:

```
CLI View Layer (6 commands)          Core Engine (12 phases)
┌─────────────────────┐            ┌──────────────────────────┐
│ spec → P1, P2       │───View ──→│ P0: Discovery (optional) │
│ plan → P7           │   Mapping │ P1: Requirements         │
│ build → P8          │            │ P2: Architecture         │
│ test → P9           │            │ P3: Technical Design     │
│ review → P8,P6      │            │ ...                      │
│ ship → P10          │            │ P11: Operations          │
└─────────────────────┘            └──────────────────────────┘
        ↓                                    ↓
  UnifiedGateEngine                   CheckpointManager
  (Phase + Worker gates)              (Lifecycle state persistence)
```

**コアコンポーネント:**
- ✅ **LifecycleProtocol** - 統一ライフサイクル管理の抽象インターフェース
- ✅ **UnifiedGateEngine** - VerificationGate + フェーズ遷移ゲートを統合
- ✅ **FullLifecycleAdapter** - 依存関係解決付き完全12フェーズ（P0-P11）ライフサイクル
- ✅ **Enhanced CheckpointManager** - セッション間でライフサイクル状態を自動保存/復元

---

## 🧪 テスト

### クイックスモークテスト（< 30秒）
```bash
python3 scripts/cli.py --version       # Expected: DevSquad 4.10.0
python3 scripts/cli.py status          # Expected: System ready
python3 scripts/cli.py roles           # Expected: 7 core roles listed
```

### フルテストスイート
```bash
# 全テストを実行（9800+ collected）
python3 -m pytest tests/ -q --tb=line

# カバレッジレポート付き
python3 -m pytest tests/ --cov=scripts --cov-report=term-missing
```

### テスト階層化戦略

| 優先度 | スコープ | 例 | 件数 |
|----------|-------|----------|-------|
| **P0** | 品質フレームワークコア | AntiRationalization, VerificationGate, IntentWorkflowMapper, AuthManager | ~200 |
| **P1** | 拡張モジュール | FiveAxisConsensus, OperationClassifier, OutputSlicer | ~150 |
| **P1+** | サイバネティクス（V3.6.6） | FeedbackControlLoop, ExecutionGuard, PerformanceFingerprint 等 | **110** |
| **P2** | Integration & E2E | 完全ライフサイクルディスパッチ、クロスモジュール統合 | ~200 |
| **P3** | モジュール別ユニット | コアディスパッチャー、RoleMapping、MCEAdapter、LLMバックエンド | ~400+ |

**合計: 9800+ collected tests / 492 e2e（現在のローカルスキャン）**

優先度別に実行:
```bash
# P0のみ（クリティカルパス、< 10s）
python3 -m pytest tests/ -k "anti_ratif or verification or intent_workflow or auth" -q

# P0 + P1（品質 + 拡張、< 30s）
python3 -m pytest tests/ -k "anti_ratif or verification or intent or auth or five_axis or operation" -q

# フルスイート
python3 -m pytest tests/ -q --tb=line
```

---

## 📚 ドキュメント

| ドキュメント | 説明 | 言語 |
|----------|-------------|----------|
| [**QUICKSTART.md**](QUICKSTART.md) | **⭐ 30秒クイックスタートガイド（新規ユーザー推奨）** | 中文 |
| [SKILL.md](SKILL.md) | 完全スキルマニュアル + 218+ モジュールリファレンス | EN/CN/JP |
| [GUIDE.md](GUIDE.md) | 完全ユーザーガイド | 中文 |
| [INSTALL.md](INSTALL.md) | インストールガイド（Unix + Windows） | EN/CN |
| [EXAMPLES.md](EXAMPLES.md) | 実際の使用例 | EN |
| [CHANGELOG.md](CHANGELOG.md) | バージョン履歴記録 | EN |
| [README-CN.md](README-CN.md) | 中国語説明 | 中文 |
| [README-JP.md](README-JP.md) | 日本語説明 | 日本語 |
| [docs/prd/V4.6.1_cleanup_PRD.md](docs/prd/V4.6.1_cleanup_PRD.md) | 製品要件ドキュメント | 中文 |
| [docs/architecture/ARCHITECTURE_V4.md](docs/architecture/ARCHITECTURE_V4.md) | 技術アーキテクチャドキュメント | 中文 |
| [docs/planning/V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) | V4.3 統一推進計画 v1.2（7-Role コンセンサス達成） | 中文 |
| [docs/prd/V4.3.0_PRD.md](docs/prd/V4.3.0_PRD.md) | V4.3.0 PRD（要件/ユーザーストーリー/受け入れ基準） | 中文 |
| [docs/architecture/V4.3.0_ARCHITECTURE.md](docs/architecture/V4.3.0_ARCHITECTURE.md) | V4.3.0 アーキテクチャ設計（モジュール境界/インターフェース契約/依存グラフ） | 中文 |
| [docs/testing/V4.3.0_TEST_PLAN.md](docs/testing/V4.3.0_TEST_PLAN.md) | V4.3.0 テスト計画（テストピラミッド/E2E/実ユーザーシミュレーション） | 中文 |

---

## 📜 リリース履歴

### V4.10.0 — 2026-11-05
- ライフサイクル定義を単一の真実源に統合：`PHASE_TEMPLATES` が唯一の定義。
- P0（発見と実現可能性）を任意フェーズとして追加。
- ゲート条件を追加：依存関係とサプライチェーンのスキャン、NFR 目標と UAT 承認、データ移行と照合。
- P11 のロールを修正：DevOps が主導し、アーキテクトとセキュリティがレビュー。
- 記録後にロール参加を強制検証。

### V4.9.0 — 2026-10-27
- W1 欠陥台帳：アトミック書き込みの JSON 状態機械、読み込み失敗時は拒否、`devsquad defect` CLI。
- W2 シグナル書き込み側：`log_dispatch_end` が `findings` と `failure_class` を受け取る。
- W3 登録ゲート：必須シグナルの追跡、失敗時はクローズ。
- W4 フィーチャーゲート：SHA256 で固定したチェックリスト、改ざん検出。

それ以前のバージョン（V4.8.2 以前）は [CHANGELOG.md](CHANGELOG.md) を参照。


## 🗺️ Roadmap

### V4.3.0（進行中 — 7-Role コンセンサス達成、ドキュメント先行）

**バージョン戦略**: V4.3.0 プレリリース（全コード+ドキュメント+E2E 検証）→ ユーザー確認 → V4.3.0 正式版

**3つの入力を統合**:
1. 技術負債の継続ガバナンス（`todo_drift_monitor` + CI ブロック）
2. pickle→JSON 移行（dead code 削除 + fallback セキュリティ強化 + 削除）
3. 上流 TraeMultiAgentSkill v2.6-v2.8 精緻化インスピレーション（Ponytail デュアルモード / LoopKernel ロールバック / UIUX 監査 / Dashboard 可視化）

**V4.3.0 範囲（9項目）**:

| ID | 名称 | 優先度 |
|----|------|--------|
| P0-1 | pickle dead code 削除 + fallback セキュリティ強化 | P0 |
| P0-2 | `todo_drift_monitor.py` + CI ブロック + PR template | P0 |
| P1-1 | Ponytail lite/full デュアルモード + DebtCollector + RequirementTracer | P1 |
| P1-4 | LoopKernel RollbackStrategy + 独立ハードリミット | P1 |
| P1-5 | UIUXAnalyzer サブ項目監査 + 必要に応じて補完 | P1 |
| P1-6 | Dashboard 状態可視化 | P1 |
| P2-1 | pickle fallback 削除 | P2 |
| P2-2 | Autonomous SmartConfirmation ドキュメント補完 | P2 |
| P2-4 | V4.3.0 リリースドキュメント同期 | P2 |

**7-Role コンセンサス**: 7/7 APPROVE_WITH_CONCERNS、10項目の調整改訂後にコンセンサス達成。詳細は [V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) v1.2 を参照。

**プロジェクトライフサイクル**: 11-Phase モデルで推進（P1 要件 → P2 アーキテクチャ → P3 技術設計 → P7 テスト計画 → P8 実装 → P9 テスト実行 → P10 デプロイリリース）

**テストピラミッド保証**: unit ≥60% / integration 15-25% / e2e ≤10% / contract 5-10% / smoke ≤5%

---

## 🤝 コントリビューション

1. リポジトリをFork
2. 機能ブランチを作成（`git checkout -b feature/amazing-feature`）
3. 変更をコミット（`git commit -m 'Add amazing feature'`）
4. ブランチにプッシュ（`git push origin feature/amazing-feature`）
5. Pull Requestを作成

---

## 📄 ライセンス

このプロジェクトはMITライセンスの下で提供されています - 詳細は [LICENSE](LICENSE) ファイルをご覧ください。

---

<p align="center">
  <strong>⭐ DevSquadがお役に立ちましたら、Starをお願いします！⭐</strong>
  <br>
  <em>より多くの開発者に「AIチーム協調」の力を</em>
  <br>
  <br>
  <strong>🙏 謝辞</strong>
  <br>
  <a href="https://github.com/weiransoft/TraeMultiAgentSkill">TraeMultiAgentSkill</a> 上流プロジェクトにインスパイア
  <br>
  DevSquadチームが ❤️ で構築
</p>

---

*最終更新: 2026-11-08 | バージョン: V4.10.0 — 変更履歴は [リリース履歴](#-リリース履歴) を参照。*
