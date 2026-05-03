# DevSquad — マルチロールAIタスクオーケストレーター

<p align="center">
  <strong>1つのタスク → マルチロールAIコラボレーション → 1つの結論</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-560%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.4.0-2026--05--02-orange" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

---

## DevSquadとは？

DevSquadは、**単一のAIタスクをマルチロールAIコラボレーションに変換**します。タスクを最適な専門ロールの組み合わせに自動ディスパッチし、共有ワークスペースで並行コラボレーションを編成し、重み付きコンセンサス投票で競合を解決し、統一された構造化レポートを提供します。

## クイックスタート

### インストール

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 方法 A: 直接実行（インストール不要）
# 依存関係なし、即時使用可能、設定ファイル機能は制限されます
python3 scripts/cli.py dispatch -t "ユーザー認証システムを設計"

# 方法 B: pip インストール（推奨）
# 全機能、設定ファイルサポートあり（pyyaml自動インストール）
pip install -e .
devsquad dispatch -t "ユーザー認証システムを設計"
```

> **どちらを選ぶ？** 方法 A はお試し向け — 依存関係なしですぐ使えますが、`~/.devsquad.yaml` 設定ファイルは読み込まれません。方法 B は全機能を有効にするパッケージインストールで、YAML設定、`devsquad` CLIコマンド、オプション連携（CarryMem、OpenAI、Anthropic）が利用可能です。

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

### セキュリティ
- **入力検証**: XSS、SQLインジェクション、コマンドインジェクション、HTMLインジェクション検出
- **Prompt注入防护**: 21+パターン（以前の指示無視、脱獄、DANモード、システムプロンプト抽出等）
- **APIキー保護**: 環境変数のみ使用、コマンドライン引数やログに露出しない
- **権限ガード**: 4レベルセーフティゲート（PLAN → DEFAULT → AUTO → BYPASS）

### パフォーマンス
- **ThreadPoolExecutor**: マルチロールディスパッチの真の並列実行
- **LLMキャッシュ**: TTLベースLRUキャッシュ + ディスク永続化（60-80%コスト削減）
- **LLMリトライ**: 指数バックオフ + サーキットブレーカー + マルチバックエンドフォールバック
- **ストリーミング出力**: `--stream` によるリアルタイムチャンク出力

### 信頼性
- **チェックポイント管理**: SHA256整合性、ハンドオフ文書、自動クリーンアップ
- **ワークフローエンジン**: タスク→ワークフロー自動分割、ステップ実行、チェックポイント復元、**11フェーズライフサイクルテンプレート**（full/backend/frontend/internal_tool/minimal）、要件変更管理
- **タスク完了チェッカー**: DispatchResult/ScheduleResult完了度追跡
- **コンセンサスエンジン**: 重み付け投票 + 拒否権 + 人間へのエスカレーション

### 自然言語ルール収集

ユーザーの自然言語入力からルールを自動検出・保存。設定ファイルの手動編集不要：

```python
# ユーザー：「ルールを覚えて：コードを書く時は必ずコメントを追加」
# DevSquadが自動的に：
# 1. ルール保存意図を検出
# 2. 抽出：trigger="コードを書く時", action="必ずコメントを追加", type="always"
# 3. 安全サニタイズ（危険パターン除去 + プロンプト注入防止）
# 4. 保存（CarryMem優先 + ローカルJSON代替）

# ルール一覧
# ユーザー：「ルール一覧」 → 保存済みルールを全件返却

# ルール削除
# ユーザー：「ルール削除 RULE-LOCAL-abc123」
```

**パイプライン**: ユーザー入力 → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage (CarryMem + ローカルJSON)

**機能**:
- 11の意図パターン（中国語・英語）
- 4つのルールタイプ：always / avoid / prefer / forbid
- ルール内容のプロンプト注入防止（14パターン）
- CarryMem優先 + ローカルJSON代替ストレージ
- Workerプロンプトへのルール自動注入

### プロジェクトライフサイクル（11フェーズモデル）

DevSquad V3.4.0は **11フェーズ（4つオプション）** のプロジェクトライフサイクルを定義。各フェーズには明確なロール、依存関係、ゲート条件があります：

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

| テンプレート | フェーズ | ユースケース |
|-------------|---------|-------------|
| `full` | P1-P11全フェーズ | 完全プロジェクト |
| `backend` | P5なし | バックエンドサービス |
| `frontend` | P4,P6なし | フロントエンドアプリ |
| `internal_tool` | P4,P5,P6,P11なし | 社内ツール |
| `minimal` | P1,P3,P7,P8,P9 | 最小セット |

詳細は [GUIDE_JP.md](GUIDE_JP.md) §4 を参照（ゲート条件と要件変更プロセス含む）。

### 開発者体験
- **設定ファイル**: プロジェクトルートの `.devsquad.yaml` + 環境変数オーバーライド
- **品質管理注入**: `.devsquad.yaml` 設定に基づき、QCルール（ハルシネーション防止、過信チェック、セキュリティガード、RACIプロトコル）をWorkerプロンプトに自動注入
- **Dockerサポート**: `docker build -t devsquad .`
- **GitHub Actions CI**: Python 3.9-3.12マトリックステスト
- **pipインストール可能**: `pip install -e .` + オプション依存関係

## 設定

```yaml
# ~/.devsquad.yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85
  ai_quality_control:
    enabled: true
    hallucination_check:
      enabled: true
    overconfidence_check:
      enabled: true
  ai_security_guard:
    enabled: true
    permission_level: "DEFAULT"
  ai_team_collaboration:
    enabled: true
    raci:
      mode: "strict"

llm:
  backend: openai
  base_url: ""
  model: ""
  timeout: 120
  log_level: WARNING
```

## テスト実行

```bash
# コアテスト（129ユニット + 234契約 + 7統合 = 370合計）
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py \
  tests/ test_v35_integration.py -v
```

## ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [GUIDE_JP.md](GUIDE_JP.md) | 完全ユーザーガイド（日本語） |
| [GUIDE_EN.md](GUIDE_EN.md) | 完全ユーザーガイド（英語） |
| [GUIDE.md](../../GUIDE.md) | 完全ユーザーガイド（中国語） |
| [README.md](../../README.md) | English |
| [README-CN.md](README_CN.md) | 中文 |
| [INSTALL.md](../../INSTALL.md) | インストールガイド |
| [SKILL.md](../../SKILL.md) | スキルマニュアル |

## バージョン履歴

| 日付 | バージョン | ハイライト |
|------|-----------|-----------|
| 2026-05-02 | **V3.4.0** | 🆕 11フェーズプロジェクトライフサイクル（full/backend/frontend/internal_tool/minimalテンプレート）、要件変更管理、ゲートメカニズム+ギャップレポート、560+テスト合格 |
| 2026-04-27 | V3.4.0 | リアルLLMバックエンド、並列実行、セキュリティ強化、チェックポイント、ワークフロー、ストリーミング、Docker、CI、CarryMem統合 |

## ライセンス

MIT License
