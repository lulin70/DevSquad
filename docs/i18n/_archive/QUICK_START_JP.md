# DevSquad クイックスタートガイド

> **バージョン**: V3.6.0 | **5分で始める**
>
> 5分でDevSquadをセットアップ。完全なドキュメントは [REFERENCE_GUIDE_JP.md](REFERENCE_GUIDE_JP.md) を参照。

---

## DevSquadとは？

DevSquadは**単一のAIタスクをマルチロールAI協調に変換**します。アーキテクト、プロダクトマネージャー、コーダー、テスター、セキュリティレビュアー、DevOpsなどの専門ロールの適切な組み合わせにタスクを自動ディスパッチし、共有ワークスペースを通じて並列協調をオーケストレーション、加重投票コンセンサスで競合を解決し、統合された構造化レポートを提供します。

**1つのタスク → マルチロールAI協調 → 1つの結論**

---

## インストール

### 前提条件

- **Python 3.10+**（3.10, 3.11対応）
- **pip** または **pipenv**

### 方法 A: クイックスタート（インストール不要）

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 直接実行（依存関係不要）
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計する"
```

### 方法 B: 完全インストール（推奨）

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 全機能付きでインストール
pip install -e .

# CLIコマンドを使用
devsquad dispatch -t "ユーザー認証システムを設計する"
```

### インストール確認

```bash
devsquad --version
# 期待値: devsquad 3.6.0
```

---

## 最初のディスパッチ（3行のコード）

### Python API

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("ユーザー認証システムを設計する")
print(result.to_markdown())
disp.shutdown()
```

### コマンドライン

```bash
# Mockモード（API Key不要）
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計する"

# ロール指定
python3 scripts/cli.py dispatch -t "データベースパフォーマンスを最適化" -r arch coder

# LLMバックエンド使用
python3 scripts/cli.py dispatch -t "REST APIを設計" --backend openai --stream
```

---

## CLI クイックリファレンス

| コマンド | 説明 | 例 |
|---------|------|-----|
| `dispatch` | マルチエージェントタスク実行 | `dispatch -t "タスク" -r arch coder` |
| `spec` | 要件定義 | `spec -t "ユーザー認証システム"` |
| `plan` | タスク分解 | `plan -t "OAuth2実装"` |
| `build` | TDD規律での実装 | `build -t "パスワードリセット追加"` |
| `test` | テスト実行 | `test -t "全ユニットテスト実行"` |
| `review` | コードレビュー | `review -t "PR #123レビュー"` |
| `ship` | 本番デプロイ | `ship -t "v2.0をデプロイ"` |
| `status` | システムステータス | `status` |
| `roles` | 利用可能なロール一覧 | `roles` |

**ロール短縮ID**: `arch`（アーキテクト）、`pm`（PM）、`sec`（セキュリティ）、`test`（テスター）、`coder`（コーダー）、`infra`（DevOps）、`ui`（UIデザイナー）

---

## クイックデモ

インタラクティブなデモでDevSquadを実体験：

```bash
python examples/quick_demo.py
```

以下をデモンストレーション：
- ✅ バグ修正シーン（中国語意図検出）
- ✅ コードレビュー（コンセンサスモード + 5軸レビュー）
- ✅ 新機能設計（マルチロール協調）

---

## 設定（オプション）

プロジェクトルートに `.devsquad.yaml` を作成：

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85

llm:
  backend: mock  # mock、openai、またはanthropic
  timeout: 120
```

または環境変数を使用：

```bash
export OPENAI_API_KEY="sk-..."
export DEVSQUAD_LLM_BACKEND=openai
```

---

## サブスキル (V3.6.0)

DevSquadは **6つの原子サブスキル** (`skills/` パッケージ) を独立利用可能として提供しています：
`dispatch`、`intent`、`review`、`security`、`test`、`retrospective`。各スキルはコアモジュールの約50行ラッパーで、API KeyなしのMockモードで動作します。

```python
from skills import get_skill, list_skills
from skills.security.handler import SecuritySkill
risk = SecuritySkill().scan_input("不審な入力")
```

詳細は [SKILL.md](../SKILL.md) § "Layered Sub-Skill Architecture" を参照してください。

---

## 次のステップ

📚 **完全ドキュメント**
- [REFERENCE_GUIDE_JP.md](REFERENCE_GUIDE_JP.md) - 完全ユーザーガイド（全機能、高度な使用法）

🚀 **サンプル**
- [examples/quick_demo.py](../../examples/quick_demo.py) - インタラクティブデモ（3シーン）
- [examples/quick_start.py](../../examples/quick_start.py) - ライフサイクル例
- [examples/full_project_workflow.py](../../examples/full_project_workflow.py) - 完全プロジェクトワークフロー

🌐 **Web ダッシュボード**
```bash
streamlit run scripts/dashboard.py
# http://localhost:8501 を開く
```

🔌 **REST API サーバー**
```bash
pip install fastapi uvicorn
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload
# Swagger UI: http://localhost:8000/docs
```

☸️ **Kubernetes デプロイ**
```bash
helm install devsquad ./helm/devsquad
kubectl port-forward svc/devsquad-api 8000:8000
```

---

## ヘルプが必要ですか？

- **FAQ**: [REFERENCE_GUIDE_JP.md §16](REFERENCE_GUIDE_JP.md#16-よくある質問)
- **課題**: [GitHub Issues](https://github.com/lulin70/DevSquad/issues)
- **バージョン履歴**: [CHANGELOG.md](../CHANGELOG.md)

---

*DevSquad V3.6.0 — 5分で始めましょう ⏱️*
