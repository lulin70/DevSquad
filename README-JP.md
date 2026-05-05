# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>1つのタスク → マルチロールAIコラボレーション → 1つの結論</strong>
  <br>
  <em>本番運用可能 | V3.5.0</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-1478%20passing%20(98.4%25)-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.5.0--Prod-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 🚀 V3.5.0-Prod: 本番運用可能リリース

**DevSquadは現在、本番運用可能です！** 認証、REST API、アラート履歴データ保存を完全にサポートしています。

### 🎯 クイックスタート（3つの使用方法）

#### 1️⃣ インタラクティブWebダッシュボード（推奨）
```bash
# 認証付きStreamlitダッシュボードを起動
streamlit run scripts/dashboard.py

# http://localhost:8501 を開く
# admin / admin123 でログイン
```

#### 2️⃣ REST APIサーバー
```bash
# 依存関係をインストール
pip install fastapi uvicorn

# APIサーバーを起動
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

#### 3️⃣ コマンドラインインターフェース
```bash
# 標準的なCLI使用法
python scripts/cli.py lifecycle build

# 拡張されたビジュアル出力
python scripts/cli.py lifecycle build --visual --verbose
```

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
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │AuthManager  │ │AlertManager │ │HistoryMgr   │           │
│  │(RBAC認証)   │ │(マルチチャンネル)│ │(SQLite TSDB)│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
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

## ✨ コア機能 (V3.5.0)

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

- ✅ **RBAC認証システム**: Admin / Operator / Viewer 3段階の役割
- ✅ **入力バリデーション**: 16種類の攻撃パターン検出（XSS/SQL注入/プロンプト注入）
- ✅ **権限制御**: 4段階の権限（PLAN/DEFAULT/AUTO/BYPASS）
- ✅ **HTTPS対応**: TLS 1.2+ 暗号化通信
- ✅ **監査ログ**: 完全な操作追跡記録

### ⚡ パフォーマンス最適化

- ✅ **LLMキャッシュ**: メモリ+ディスク二重キャッシュ、API呼び出し60-80%削減
- ✅ **コンテキスト圧縮**: 4段階圧縮戦略でオーバーフロー防止
- ✅ **並列実行**: ThreadPoolExecutorによる複数Worker並行処理
- ✅ **起動ウォームアップ**: 3段階プリロードでコールドスタート遅延低減

---

## 📦 インストールと設定

### 前提条件

- Python 3.9+
- pip または pipenv

### インストール手順

```bash
# リポジトリをクローン
git clone https://github.com/your-org/devsquad.git
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
| **合計** | **1478** | **98.4%** |

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
│   ├── collaboration/          # コアコラボレーションモジュール (27個)
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
├── tests/                     # テストスイート (1478個)
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
