# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>1つのタスク → マルチロールAIコラボレーション → 1つの結論</strong>
  <br>
  <em>エンタープライズ対応 | V4.0.10</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-4600%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V4.0.10-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 🚀 V4.0.0: Loop Engineering + UI/UX 巡検 + Adversarial 検証 + DAG 可視化 + Autonomous + プラグインホットロード

**DevSquad V4.0.0** は上流 TraeMultiAgentSkill v2.7 の理念を参考に、6 つの機能（P1-P3）を追加し、dispatch pipeline に完全統合、ゴースト機能なし：
- **P1-1 Loop Engineering**: Discovery → Handoff → Verification → Persistence → Scheduling の5ステップ閉ループ
- **P1-2 UI/UX 巡検**: 4 次元監査（a11y/interaction/layout/ux）+ PIL ピクセル diff ビジュアルリグレッション
- **P2-1 Adversarial 検証**: レッドチーム攻撃 + ブルーチーム防御 + 審判仲裁の3段階対抗検証
- **P2-2 DAG 可視化**: Mermaid / JSON / DOT の3形式依存グラフ可視化
- **P3-1 Autonomous**: plan → dev → verify → fix の4段階自律反復、LoopKernel 再利用、コンセンサスゲートをバイパスしない
- **P3-2 プラグインホットロード**: 3つのロードパス + パストラバーサル3層防护 + reload ロールバック + 監査ログ

3600+ tests passing。

### 🔄 V3.9.2 エンタープライズ機能詳細

### 🎯 クイックスタート（5つの使用方法）

#### 1️⃣ コマンドラインインターフェース
```bash
# 標準的なCLI使用法
python scripts/cli.py lifecycle build

# 拡張されたビジュアル出力
python scripts/cli.py lifecycle build --visual --verbose
```

#### 2️⃣ インタラクティブWebダッシュボード（推奨）
```bash
# 認証付きStreamlitダッシュボードを起動
streamlit run scripts/dashboard.py

# http://localhost:8501 を開く
# admin / admin123 でログイン
```

#### 3️⃣ REST APIサーバー
```bash
# 依存関係をインストール
pip install fastapi uvicorn

# APIサーバーを起動
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

#### 4️⃣ Python API（開発者推奨）
```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
result = dispatcher.dispatch(
    task="データベースクエリのパフォーマンスを最適化",
    roles=["architect", "security", "tester"],
)
print(result.report)
print(result.consensus)
```

#### 5️⃣ ワンクリック起動スクリプト（V3.9.2+）
```bash
# ワンクリック起動 — 4フェーズ：環境チェック → DB初期化 → フロントエンド構築 → サービス起動
./scripts/start.sh

# APIサーバーの代わりにStreamlitダッシュボードを起動
./scripts/start.sh --dashboard

# APIポートを上書き
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# ヘルプを表示
./scripts/start.sh --help
```

`start.sh`はV3.9.2（P0-2）で導入された統合エントリポイントです。環境チェック、データベース初期化、フロントエンド構築、サービス起動を1コマンドで実行します。`requirements.lock`と組み合わせて再現可能なビルドを実現できます（`pip install -r requirements.lock`）。

---

## 🏗️ アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│                    ユーザーアクセス層                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Streamlit    │ │ FastAPI REST │ │ CLI/Notebook │        │
│  │ ダッシュボード│ │ APIサーバー  │ │ (既存)       │        │
│  │ (Auth+HTTPS) │ │ (Swagger)    │ │              │        │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘        │
└─────────┼───────────────┼───────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   ビジネスロジック層                       │
│  ┌─────────────┐ ┌─────────────┐           │
│  │AuthManager  │ │HistoryMgr   │           │
│  │(RBAC認証)   │ │(SQLite TSDB)│           │
│  └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────┐            │
│  │     LifecycleProtocol (11フェーズエンジン)    │            │
│  │     UnifiedGateEngine + CheckpointManager     │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    データ永続化層                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐  │
│  │ SQLite DB  │ │ YAML設定   │ │ チェックポイントファイル │  │
│  │ (履歴)     │ │ (デプロイ)  │ │ (ライフサイクル状態)     │  │
│  └────────────┘ └────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ コア機能 (V4.0.0)

### 🏗️ 5大能力ドメインアーキテクチャ（V4.0.0）

DevSquad の 149+ モジュールは **5大能力ドメイン** に編成され、各ドメインが特定の問題を解決します：

| 能力ドメイン | コアモジュール | 解決する問題 |
|--------------|----------------|--------------|
| **タスクオーケストレーションエンジン** | MultiAgentDispatcher / Coordinator / Scratchpad / ConsensusEngine / BatchScheduler | 7ロール協調の「指揮センター」 |
| **品質保証システム** | InputValidator / VerificationGate / AntiRationalizationEngine / TestQualityGuard / PermissionGuard | AIの「サボり」や「ハルシネーション」を防止 |
| **パフォーマンスと信頼性** | LLMCache / LLMRetry / FeedbackControlLoop / ExecutionGuard / FallbackBackend | より速く、より安定、よりコスト効率よく |
| **可観測性とガバナンス** | PerformanceMonitor / UsageTracker / AuditLogger / RBAC Engine / Multi-Tenancy Manager | システムが何をしているか把握 |
| **統合と拡張** | CLI / REST API / Dashboard / MCP Protocol / Docker / GitHub Actions | 既存ツールチェーンへの統合 |

### 🧩 コンサーンパック (NEW)
タスク内容に基づいてAIロールプロンプトを自動強化するドメイン固有ナレッジパック：
- **パーミッション設計パック** — RBAC/ABAC/ReBAC/ACL意思決定フレームワーク、行/列レベル権限パターン、7つのよくある落とし穴（IDOR、権限昇格、キャッシュ古び...）
- **Web API設計パック** — REST/GraphQL/gRPCスタイル選択、JWT/OAuth2/API Key認証、バージョニング戦略、レート制限、RFC 7807エラー処理
- **データパイプラインパック** — バッチ/ストリーミング/CDCパイプラインパターン、冪等性保証、データ品質フレームワーク、スキーマ進化、増分同期戦略

パックはキーワードで**自動マッチ**し、**組み合わせ可能** — 「マルチテナントAPI権限」タスクはパーミッション+Web APIパックを同時に有効化します。

### 🎯 インタラクティブセットアップウィザード (NEW)
```bash
devsquad init    # 5ステップガイド付きセットアップ（1-2分）
# Step 1: プロジェクトタイプ（Web API / フルスタック / CLI / ML / ライブラリ / 汎用）
# Step 2: AIバックエンド（Mock / OpenAI / Anthropic）
# Step 3: デフォルトロール（プロジェクトタイプに基づく自動推奨）
# Step 4: 言語と機能
# Step 5: ~/.devsquad.yaml に保存
```

### 💬 ユーザーフレンドリーなエラーメッセージ (NEW)
技術的エラーが人間が読めるメッセージに翻訳され、修正提案と使用例が付きます：
```
❌ 変更前: "Input validation failed: Task too short (min 5 chars, got 2)"
✅ 変更後: "タスク説明が短すぎます。もう詳しく説明してください"
           "💡 良いタスク説明には：何をするか + なぜ + 特別な要件を含めましょう"
           "📝 例: devsquad dispatch -t '電話番号とメールでログインできるユーザー認証システムを設計する'"
```

### 📊 パフォーマンスモニタリング (NEW)
スライディングウィンドウ統計、しきい値アラート、回帰検出を備えた組み込みパフォーマンスモニタリング：
- 毎回のディスパッチでメトリクスを自動収集（11ステップタイミング明細）
- P50/P95/P99レイテンシ分析
- パフォーマンス回帰検出（>20%劣化でアラート発報）
- 外部ダッシュボード用JSONエクスポート

### 🤖 マルチロールコラボレーションシステム

| ロール | 責任 | トリガーキーワード |
|------|------|------------------|
| **アーキテクト** | アーキテクチャ設計、技術選定 | architecture, design, performance |
| **プロダクトマネージャー** | 要件分析、PRD作成 | requirements, PRD, user story |
| **セキュリティ専門家** | 脅威モデリング、セキュリティ監査 | security, vulnerability, audit |
| **テスト専門家** | テスト戦略、品質保証 | test, quality, automation |
| **開発者** | 機能実装、コードレビュー | implementation, code, fix |
| **DevOpsエンジニア** | CI/CD、デプロイ、モニタリング | CI/CD, deploy, Docker, monitoring |
| **UIデザイナー** | UIデザイン、インタラクションプロトタイプ | UI, interface, prototype |

### 🔒 セキュリティ機能

- ✅ **RBAC認証システム** (プレビュー): Admin / Operator / Viewer 3段階の役割
- ✅ **入力バリデーション**: 16種類の攻撃パターン検出（XSS/SQL注入/プロンプト注入）
- ✅ **権限制御**: 4段階の権限（PLAN/DEFAULT/AUTO/BYPASS）
- ✅ **HTTPS対応**: TLS 1.2+ 暗号化通信
- ✅ **監査ログ** (プレビュー): 完全な操作追跡記録
- ✅ **マルチテナントマネージャー** (プレビュー): 3段階の分離（厳格/適度/共有）、テナントスコープリソース
- ✅ **機密データマスキング** (プレビュー): PII検出とマスキング（メール/電話/IDカード/クレジットカード）、設定可能なルール

### ⚡ パフォーマンス最適化

- ✅ **LLMキャッシュ**: メモリ+ディスク二重キャッシュ、API呼び出し60-80%削減
- ✅ **コンテキスト圧縮**: 4段階圧縮戦略でオーバーフロー防止
- ✅ **並列実行**: ThreadPoolExecutorによる複数Worker並行処理
- ✅ **起動ウォームアップ**: 3段階プリロードでコールドスタート遅延低減

---

## 🧩 レイヤードサブスキルアーキテクチャ (V3.6.0)

> DevSquadは **6つの原子サブスキル** を提供し、独立または組み合わせて使用できます。
> 各サブスキルは軽量ラッパー（約50行）で、既存のコアモジュールをインポート — 重複ロジックなし。

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7ロールオーケストレーション)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6インテント × 3言語)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5軸コードレビュー)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + テスト戦略生成
└── retrospective/  → RetroSkill    — RetrospectiveEngine + パターン抽出
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
result = DispatchSkill().run("ログインバグ修正", roles=["coder", "tester"])

# レジストリ経由（動的発見）
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
```

すべてのサブスキルは**API Keyなし**のMockモードで動作します。

---

## 📦 インストールと設定

### 前提条件

- Python 3.10+
- pip または pipenv

### インストール手順

```bash
# リポジトリをクローン
git clone https://github.com/lulin70/DevSquad.git
cd devsquad

# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# または venv\Scripts\activate  # Windows

# 依存関係をインストール
pip install -r requirements.txt

# テストを実行
pytest tests/ -v

# アプリケーションを起動
python scripts/cli.py dispatch -t "テストタスク"
```

---

## 🧪 テストカバレッジ

| カテゴリ | テスト数 | 通過率 |
|----------|----------|--------|
| コアモジュール (Dispatcher/Coordinator/Worker) | 39 | 100% |
| ロールマッチング (RoleMatcher/Semantic) | 25 | 100% |
| 上流モジュール (Checkpoint/Workflow) | 35 | 100% |
| MCEAdapter (CarryMem統合) | 30 | 100% |
| CLI ライフサイクル | 28 | 100% |
| UX レポート形式 | 24 | 100% |
| P0 品質フレームワーク (AntiRationalization/VerificationGate/IntentWorkflow) | 139 | 100% |
| P1 拡張モジュール (OperationClassifier/FiveAxisConsensus等) | 133 | 100% |
| V3.6.0 新モジュール (AnchorChecker/RetrospectiveEngine等) | 45 | 100% |
| V3.9.2 拡張モジュール (LLM フォールバック/Dashboard 分割/監査永続化) | 588 | 100% |
| **合計** | **2857+ (収集 2864)** | **100%** |

---

## 📚 ドキュメントリソース

| ドキュメント | 言語 | 説明 |
|------------|------|------|
| [README.md](./README.md) | English | メインドキュメント |
| [README-CN.md](./README-CN.md) | 中文 | 中国語ドキュメント |
| [README-JP.md](./README-JP.md) | 日本語 | 本ドキュメント |
| [SKILL.md](./SKILL.md) | English | Skill使用ガイド |
| [CHANGELOG.md](./CHANGELOG.md) | English | 変更ログ |
| [docs/](./docs/) | English | 詳細技術ドキュメント |

---

## 🎮 使用例

### 例1: クイックコラボレーション（Mockモード）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("ユーザー認証システムを設計")
print(result.to_markdown())
disp.shutdown()
```

### 例2: 実際のLLMバックエンドを使用

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    model="gpt-4",
)

disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("マイクロサービスアーキテクチャを実装", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

### 例3: CLI ライフサイクルコマンド

```bash
# 仕様フェーズ
python scripts/cli.py lifecycle spec -t "ECサイト要件"

# 計画フェーズ
python scripts/cli.py lifecycle plan -t "データベース設計案"

# 構築フェーズ
python scripts/cli.py lifecycle build -t "決済インターフェース実装"

# テストフェーズ
python scripts/cli.py lifecycle test -t "単体テストスイート"

# レビューフェーズ
python scripts/cli.py lifecycle review -t "コードレビュー"

# リリースフェーズ
python scripts/cli.py lifecycle ship -t "v2.0リリース"
```

---

## 🛠️ 開発ガイド

### プロジェクト構造

```
DevSquad/
├── scripts/
│   ├── collaboration/          # コアコラボレーションモジュール (149+ 個)
│   │   ├── dispatcher.py       # 統一ディスパッチャー
│   │   ├── coordinator.py      # グローバルオーケストレーター
│   │   ├── worker.py           # Worker実行者
│   │   ├── scratchpad.py       # 共有ブラックボード
│   │   ├── consensus.py        # コンセンサスエンジン
│   │   ├── permission_guard.py # 権限管理
│   │   ├── llm_cache.py        # キャッシュシステム
│   │   ├── input_validator.py  # 入力バリデーション
│   │   └── ...
│   ├── cli.py                 # コマンドラインインターフェース
│   ├── dashboard.py           # Streamlitダッシュボード
│   └── api_server.py          # FastAPIサーバー
├── tests/                     # テストスイート (2857+ 個)
├── docs/                      # ドキュメント
├── SKILL.md                   # Skill定義
├── CHANGELOG.md              # 変更ログ
└── README.md                 # 英語メインドキュメント
```

### コーディング規約

- **型アノテーション**: Python 3.8+ 型ヒント
- **ドックストリング**: Googleスタイル docstring
- **例外処理**: 具体的な例外タイプ + 例外チェーン保持
- **ログレベル**: DEBUG/INFO/WARNING/ERROR/CRITICAL

---

## 📈 パフォーマンス基準

| 操作 | 平均時間 | P99 | 目標 |
|------|----------|-----|------|
| Dispatcher 初期化 | ~1.3s | 2.5s | <2s |
| 単発Dispatch (Mock) | ~120ms | 250ms | <500ms |
| Worker実行 | ~80ms | 150ms | <200ms |
| コンセンサス決定 | ~45ms | 90ms | <100ms |
| メモリ使用量 | ~85MB | 150MB | <200MB |

---

## 🤝 コントリビューションガイド

コミュニティからの貢献を歓迎します！以下の手順に従ってください：

1. リポジトリをFork
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

### 開発ワークフロー

```bash
# 開発依存関係をインストール
pip install -e ".[dev]"

# コードチェックを実行
flake8 scripts/
mypy scripts/

# 全テストを実行
pytest tests/ -v --cov=scripts/collaboration

# パフォーマンスベンチマークを実行
pytest tests/test_performance_benchmarks.py --benchmark-only
```

---

## 📄 ライセンス

このプロジェクトはMITライセンスを採用しています - 詳細は [LICENSE](LICENSE) ファイルをご覧ください。

---

## 🙏 謝辞

以下のオープンソースプロジェクトに感謝いたします：
- [FastAPI](https://fastapi.tiangolo.com/) - モダンWeb APIフレームワーク
- [Streamlit](https://streamlit.io/) - データサイエンスWebアプリケーションフレームワーク
- [Pydantic](https://pydantic-docs.helpmanual.io/) - データバリデーションライブラリ
- [Click](https://click.palletsprojects.com/) - コマンドラインツールライブラリ

---

<p align="center">
  <strong>Made with ❤️ by DevSquad Team</strong>
  <br>
  <em>マルチロールAIコラボレーション、すべてのタスクに専門的処理を</em>
</p>

<p align="center">
  <a href="#top">トップに戻る ↑</a>
</p>
