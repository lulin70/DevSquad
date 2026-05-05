# DevSquad 使用例

> 最終検証: 2026-05-03, DevSquad V3.4.0-Prod, backend=openai, model=gpt-4
>
> **生産レディ**: 認証 ✅ | REST API ✅ | アラート ✅ | 履歴データ ✅

## クイックスタート

```bash
# モックモード（デフォルト）— APIキー不要
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計"

# 実AI出力 — 環境変数を先に設定
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.moka-ai.com/v1"
export OPENAI_MODEL="moka/claude-sonnet-4-6"
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計" --backend openai

# ロール指定（短縮ID: arch/pm/test/coder/ui/infra/sec）
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計" -r arch pm test --backend openai

# ストリーミング出力（リアルタイムでLLMレスポンスを確認）
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計" -r arch --backend openai --stream

# ドライラン（実行せずシミュレーション）
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計" --dry-run
```

## 実出力例

### 例1：アーキテクチャ設計（単一ロール）

```bash
python3 scripts/cli.py dispatch \
    -t "OAuth2と2FAを備えたユーザー認証システムを設計" \
    -r arch --backend openai
```

**実出力** (2026-04-24検証, 91秒, architectロール):

```
# OAuth2 + 2FA ユーザー認証システムアーキテクチャ設計

## 主要知見

1. **階層分離がセキュリティの基盤** - OAuth2認可レイヤーと2FA検証レイヤーは
   独立してデプロイする必要がある。単一攻撃面を回避し、
   トークンストレージと検証ロジックを物理的に分離。
2. **パフォーマンスとセキュリティのバランス** - Redisクラスタでトークンを
   キャッシュ（TTL 15分）+ データベースでリフレッシュトークンを永続化（30日）、
   レートリミットでブルートフォース攻撃を防止。
```

### 例2：マルチロールコラボレーション

```bash
python3 scripts/cli.py dispatch \
    -t "SaaSプラットフォーム向けリアルタイムチャット機能を構築" \
    -r arch pm test --backend openai
```

**実出力** (2026-04-24検証, 144秒, 3ロール):

- **アーキテクト**: WebSocket + Redis Pub/Subアーキテクチャ、100万レベルの
  同時接続対応、レイテンシ<50ms、メッセージ永続化とリアルタイム配信を分離
- **PM**: リアルタイムチャットPRD、コアビジネス価値（コラボレーション効率向上、
  プラットフォーム定着率向上）、ターゲットユーザー（B2B SaaSチームコラボレーション）
- **テスター**: テスト計画、主要リスクポイント（WebSocket安定性、メッセージレイテンシ<500ms、
  同時負荷）、多層データ整合性検証、早期セキュリティコンプライアンス参画

### 例3：セキュリティ監査

```bash
python3 scripts/cli.py dispatch \
    -t "ユーザー決済と個人データを扱うREST APIのセキュリティ監査" \
    -r sec --backend openai
```

**実出力** (2026-04-24検証, 48秒, securityロール):

```
決済と個人データを扱うREST APIの包括的セキュリティ監査を実施します。
実際のコードベースへのアクセスがないため、実行可能な監査フレームワークを提供します...
```

### 例4：ストリーミング出力（V3.4.0新機能）

```bash
python3 scripts/cli.py dispatch \
    -t "マイクロサービスECバックエンドを設計" \
    -r arch --backend openai --stream
```

ストリーミングモードでは、LLMレスポンスがチャンク単位でリアルタイム出力されます。
長時間実行される生成タスクで、結果を随時確認したい場合に最適。

### 例5：コンセンサスモード

```bash
python3 scripts/cli.py dispatch \
    -t "分析プラットフォームのデータベースを選択" \
    -r arch sec \
    --mode consensus
```

コンセンサスモードは、ロール間の意見不一致時に投票を強制します。
各ロールが重み付け投票を行い、拒否権が尊重され、デッドロック時は人間へのエスカレーションが可能。

### 例6：自動化用JSON出力

```bash
python3 scripts/cli.py dispatch \
    -t "コードベースのパフォーマンス問題をレビュー" \
    -r arch coder \
    --format json
```

JSON出力はマシンリーダブルで、CI/CDパイプラインや後続処理に適しています。

## Docker使用方法

```bash
# イメージビルド
docker build -t devsquad .

# モックモードで実行
docker run devsquad dispatch -t "認証システムを設計"

# APIキー付きで実行
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "認証システムを設計" --backend openai

# インタラクティブシェル
docker run -it devsquad /bin/bash
```

## 設定ファイル

`~/.devsquad.yaml` を作成：

```yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
  strict_validation: false
  checkpoint_enabled: true
  cache_enabled: true
  log_level: WARNING
```

優先順位：環境変数 > 設定ファイル > デフォルト

```bash
# 設定ファイル設定後、--backendの指定が不要に
python3 scripts/cli.py dispatch -t "認証システムを設計"
# 設定ファイルのopenaiバックエンドを自動使用
```

## システムコマンド

```bash
# 利用可能なロール一覧
python3 scripts/cli.py roles

# システムステータス表示
python3 scripts/cli.py status

# JSON形式でロール一覧
python3 scripts/cli.py roles --format json

# バージョン表示
python3 scripts/cli.py --version    # 3.4.0-Prod
```

## Python API使用例

### 基本ディスパッチ（実LLMバックエンド使用）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),
    model=os.environ.get("OPENAI_MODEL", "gpt-4"),
)

disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch(
    "ユーザー認証システムを設計",
    roles=["architect", "pm", "tester"],
    mode="auto",
)

print(result.summary)
print(result.to_markdown())
disp.shutdown()
```

### モックモード（APIキー不要）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(
    "ユーザー認証システムを設計",
    roles=["architect", "pm", "tester"],
)

print(result.summary)
disp.shutdown()
```

### ストリーミング出力（Python API）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend("openai", api_key=os.environ["OPENAI_API_KEY"])
disp = MultiAgentDispatcher(llm_backend=backend)

from scripts.collaboration.worker import Worker
worker = Worker(role="architect", backend=backend, stream=True)

result = disp.dispatch("認証システムを設計", roles=["architect"])
disp.shutdown()
```

### ConfigManager使用

```python
from scripts.collaboration.config_loader import ConfigManager

config_mgr = ConfigManager()
config = config_mgr.load()
print(f"Backend: {config.backend}")
print(f"Model: {config.model}")
print(f"Timeout: {config.timeout}")
```

### CheckpointManager使用

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

ckpt_mgr = CheckpointManager(storage_dir="/tmp/checkpoints")

checkpoint = ckpt_mgr.create_checkpoint_from_dispatch(dispatch_result)

checkpoints = ckpt_mgr.list_checkpoints()

restored = ckpt_mgr.load_checkpoint(checkpoint.checkpoint_id)
```

## ロールリファレンス

| ロール | CLI ID | エイリアス | 最適な用途 |
|--------|--------|-----------|-----------|
| アーキテクト | `arch` | `architect` | システム設計、技術スタック、パフォーマンス/セキュリティ/データアーキテクチャ |
| プロダクトマネージャー | `pm` | `product-manager` | 要件、ユーザーストーリー、受入基準 |
| セキュリティ専門家 | `sec` | `security` | 脅威モデリング、脆弱性監査、コンプライアンス |
| テスター | `test` | `tester`, `qa` | テスト戦略、品質保証、エッジケース |
| コーダー | `coder` | `solo-coder`, `dev` | 実装、コードレビュー、パフォーマンス最適化 |
| DevOps | `infra` | `devops` | CI/CD、コンテナ化、モニタリング、インフラ |
| UIデザイナー | `ui` | `ui-designer` | UXフロー、インタラクションデザイン、アクセシビリティ |

## CLIオプション

| オプション | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `--task`, `-t` | string | 必須 | タスク記述 |
| `--roles`, `-r` | list | auto | 参加ロール（短縮ID: arch/pm/test/coder/ui/infra/sec） |
| `--mode`, `-m` | enum | auto | 実行モード: auto/parallel/sequential/consensus |
| `--backend`, `-b` | enum | mock | LLMバックエンド: mock/trae/openai/anthropic |
| `--base-url` | string | env | カスタムAPIベースURL（またはOPENAI_BASE_URL環境変数） |
| `--model` | string | env | モデル名（またはOPENAI_MODEL/ANTHROPIC_MODEL環境変数） |
| `--stream` | flag | false | LLM出力をリアルタイムストリーミング（--backend必須） |
| `--format`, `-f` | enum | markdown | 出力形式: markdown/json/compact/structured/detailed |
| `--dry-run` | flag | false | 実行せずシミュレーション |
| `--quick`, `-q` | flag | false | quick_dispatch使用（3形式） |
| `--action-items` | flag | false | H/M/Lアクションアイテムを含む |
| `--timing` | flag | false | タイミング情報を含む |
| `--persist-dir` | string | auto | カスタムスクラッチパッドディレクトリ |
| `--no-warmup` | flag | false | スタートアップウォームアップ無効 |
| `--no-compression` | flag | false | コンテキスト圧縮無効 |
| `--skip-permission` | flag | false | パーミッションチェックスキップ |
| `--no-memory` | flag | false | メモリブリッジ無効 |
| `--no-skillify` | flag | false | スキル学習無効 |
| `--permission-level` | enum | DEFAULT | PLAN/DEFAULT/AUTO/BYPASS |

## 環境変数

| 変数 | 説明 | 必須 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI互換バックエンド用APIキー | `--backend openai`使用時 |
| `OPENAI_BASE_URL` | カスタムAPIエンドポイント（例：`https://api.moka-ai.com/v1`） | 任意 |
| `OPENAI_MODEL` | モデル名（例：`gpt-4`、`moka/claude-sonnet-4-6`） | 任意 |
| `ANTHROPIC_API_KEY` | Anthropic Claude用APIキー | `--backend anthropic`使用時 |
| `ANTHROPIC_MODEL` | モデル名（例：`claude-sonnet-4-20250514`） | 任意 |
| `DEVSQUAD_LLM_BACKEND` | デフォルトバックエンド（mock/openai/anthropic） | 任意 |
| `DEVSQUAD_LOG_LEVEL` | ログレベル | 任意 |

## MCPサーバー（OpenClaw / Cursor用）

```bash
# MCPパッケージインストール（任意）
pip install mcp

# stdioモードで起動
python3 scripts/mcp_server.py

# SSEモードで起動
python3 scripts/mcp_server.py --port 8080
```

6ツール提供：`multiagent_dispatch`、`multiagent_quick`、`multiagent_roles`、
`multiagent_status`、`multiagent_analyze`、`multiagent_shutdown`。
