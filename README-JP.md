# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>1つのタスク → マルチロールAIコラボレーション → 1つの結論</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-129%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3.0-2026--04--27-orange" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

---

## DevSquadとは？

DevSquadは、**単一のAIタスクをマルチロールAIコラボレーションに変換**します。タスクを最適な専門ロールの組み合わせに自動ディスパッチし、共有ワークスペースで並行コラボレーションを編成し、重み付きコンセンサス投票で競合を解決し、統一された構造化レポートを提供します。

## クイックスタート

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# モックモード（デフォルト）— APIキー不要
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計"

# pip インストール
pip install -e .
devsquad dispatch -t "ユーザー認証システムを設計"
```

### リアルAI出力

```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "認証システムを設計" --backend openai

# ロール指定（短縮ID: arch/pm/sec/test/coder/infra/ui）
python3 scripts/cli.py dispatch -t "認証システムを設計" -r arch sec --backend openai

# ストリーミング出力
python3 scripts/cli.py dispatch -t "認証システムを設計" -r arch --backend openai --stream
```

## 7つのコアロール

| ロール | CLI ID | 重み | 最適な用途 |
|--------|--------|------|-----------|
| アーキテクト | `arch` | 1.5 | システム設計、技術選定 |
| プロダクトマネージャー | `pm` | 1.2 | 要件分析、ユーザーストーリー |
| セキュリティ専門家 | `sec` | 1.1 | 脅威モデリング、脆弱性監査 |
| テスター | `test` | 1.0 | テスト戦略、品質保証 |
| コーダー | `coder` | 1.0 | 実装、コードレビュー |
| DevOps | `infra` | 1.0 | CI/CD、コンテナ化、監視 |
| UIデザイナー | `ui` | 0.9 | UX設計、インタラクション |

## 主な機能

- **セキュリティ**: 入力検証、Prompt注入検出（16パターン）、APIキー保護
- **パフォーマンス**: ThreadPoolExecutor並列実行、LLMキャッシュ、ストリーミング出力
- **信頼性**: チェックポイント管理、ワークフローエンジン、タスク完了チェッカー
- **DX**: 設定ファイル（~/.devsquad.yaml）、Docker、GitHub Actions CI、pip インストール

## 設定

```yaml
# ~/.devsquad.yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
```

## テスト実行

```bash
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py -v
```

## ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [README.md](README.md) | English |
| [README-CN.md](README-CN.md) | 中文 |
| [INSTALL.md](INSTALL.md) | インストールガイド |
| [EXAMPLES.md](EXAMPLES.md) | 使用例 |

## バージョン履歴

| 日付 | バージョン | ハイライト |
|------|-----------|-----------|
| 2026-04-27 | **V3.3.0** | リアルLLMバックエンド、並列実行、セキュリティ強化、チェックポイント、ワークフロー、ストリーミング、Docker、CI、CarryMem統合、129テスト |

## ライセンス

MIT License
