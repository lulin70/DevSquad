# DevSquad — マルチエージェントソフトウェア開発チーム

<p align="center">
  <strong>AI駆動の専門開発チームをオンデマンドで編成。</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-825%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3.0-2026--04--24-orange" />
</p>

---

## DevSquad とは？

DevSquad は**単一の AI コーディングアシスタントを、多ロールの専門開発チームへと変換**します。1 つの AI ですべてのタスクを処理するのではなく、最適な専門家ロールの組み合わせ（アーキテクト、プロダクトマネージャー、コーダー、テスター、セキュリティレビュアーなど）に自動ディスパッチし、共有ワークスペースを通じて並行コラボレーションを調整し、コンセンサス投票で競合を解決し、統一的な構造化レポートを届けます。

**まるで本物のエンジニアのように協力する AI エージェントによって駆動される、オンデマンドの仮想開発チームを想像してください。**

```
あなた: "マイクロサービス型 EC サイトのバックエンドを設計して"
           │
           ▼
┌─────────────────┐
│  意図分析 ──→ 自動マッチ: アーキテクト + DevOps + セキュリティ
└────────┬────────┘
           ▼
┌──────────┬──────────┬──────────┐
│ アーキテクト │   DevOps  │ セキュリティ │
│(システム設計)│(インフラ)  │(脅威モデル)│
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    スクラッチパッド  │ ← リアルタイム同期黒板
      │  (Scratchpad)     │
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   コンセンサスエンジン│ ← 加重投票 + 拒否権
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │  構造化レポート     │ ← 発見 + アクション項目 (高/中/低)
      └──────────────────┘
```

## クイックスタート

### 前提条件

- **Python 3.9+**（純 Python、コンパイル依存なし）
- **OS**: macOS / Linux / **Windows 10+**
- 外部依存不要（すべての統合はグレースフルデグラデーション）

詳細なインストール手順（Windows 含む）は [**INSTALL.md**](INSTALL.md) を参照

### 3 つの使用方法

**方法 1: CLI（推奨）**

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

python3 scripts/cli.py dispatch -t "ユーザ認証システムを設計"
python3 scripts/cli.py status
python3 scripts/cli.py roles
```

**方法 2: Python API**

```python
import sys
sys.path.insert(0, '/path/to/DevSquad')
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("RESTful ユーザ管理 API を設計")
print(result.to_markdown())
disp.shutdown()
```

**方法 3: クイックディスパッチ（3 出力フォーマット）**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# 構造化レポート（デフォルト表形式）
result = disp.quick_dispatch(task, output_format="structured")

# コンパクト（各ロール 1 行）
result = disp.quick_dispatch(task, output_format="compact")

# 詳細（完全な発見 + アクション項目）
result = disp.quick_dispatch(task, output_format="detailed",
                              include_action_items=True)

disp.shutdown()
```

## 7 のコアロール

| ロール | CLI ID | 最適な用途 |
|------|--------|-----------|
| アーキテクト | `arch` | システム設計、技術スタック、パフォーマンス/セキュリティ/データアーキテクチャ |
| PM | `pm` | 要件分析、ユーザストーリー、受諾基準 |
| セキュリティ専門家 | `sec` | 脅威モデル、脆弱性監査、コンプライアンス |
| テスト専門家 | `test` | テスト戦略、エッジケース、品質保証 |
| コーダー | `coder` | 実装、コードレビュー、パフォーマンス最適化、リファクタリング |
| DevOps | `infra` | CI/CD パイプライン、コンテナ化、モニタリング、インフラ |
| UIデザイナー | `ui` | UX フロー、インタラクション設計、アクセシビリティ |

**自動マッチ**: ロール未指定時、ディスパッチャがタスク意図に基づき自動マッチング。

## 16 のコアモジュール

| モジュール | 用途 |
|-----------|------|
| **MultiAgentDispatcher** | 統一エントリポイント — 1 回の呼び出しで全完了 |
| **Coordinator** | グローバルオーケストレーション: 分解 → 割当 → 収集 → 決定 |
| **Scratchpad** | 共有ブラドボード、Worker 間リアルタイム通信 |
| **Worker** | ロール実行エージェント — 各ロール独立インスタンス |
| **ConsensusEngine** | 加重投票 + 拒否権 + 人間エスカレーション |
| **BatchScheduler** | 並列/直列ハイブリッド、自動安全検知 |
| **ContextCompressor** | 4 レベル圧縮でコンテキストオーバーフロー防止 |
| **PermissionGuard** | 4 レベル安全ゲート (PLAN → DEFAULT → AUTO → BYPASS) |
| **Skillifier** | 成功パターンから学習、新スキル自動生成 |
| **WarmupManager** | 3 層起動プリロード (コールドスタート < 300ms) |
| **MemoryBridge** | セッション横断メモリ (7 種類、TF-IDF、忘却曲線) |
| **MCEAdapter** | メモリ分類エンジン統合 (v0.4、テナント対応) |
| **WorkBuddyClawSource** | 外部知識ブリッジ (転置インデックス検索、AI ニースフィード) |
| **PromptAssembler** | 動的プロンプト構築 (3 バリアント × 5 スタイル) |
| **PromptVariantGenerator** | A/B テストクローズドループプロンプト最適化 |
| **TestQualityGuard** | 自動テスト品質監査 |

## クロスプラットフォーム互換性

DevSquad は複数の AI コーディング環境でネイティブ動作:

| プラットフォーム | 統合方式 | ステータス |
|---------------|----------|----------|
| **Trae IDE** | `skill-manifest.yaml` ネイティブスキル | ✅ メイン |
| **Claude Code** | `CLAUDE.md` + `.claude/skills/` カスタムスキル | ✅ 対応 |
| **OpenClaw** | MCP Server (`scripts/mcp_server.py`, 6 ツール) | ✅ 対応 |
| **端末 / 任意 IDE** | CLI (`scripts/cli.py`) または Python インポート | ✅ 汎用 |

### MCP Server (OpenClaw / Cursor / MCP クライアント用)

```bash
pip install mcp          # オプション
python3 scripts/mcp_server.py              # stdio モード
python3 scripts/mcp_server.py --port 8080  # SSE モード
```

6 ツール公開: `multiagent_dispatch`、`multiagent_quick`、`multiagent_roles`、
`multiagent_status`、`multiagent_analyze`、`multiagent_shutdown`

## 外部統合

| コンポーネント | ステータス | フォールバック |
|---------------|----------|-------------|
| **MCE v0.4** (メモリ分類エンジン) | オプション: テナント/権限対応 | 利用不可時グレースフルデグラデ |
| **WorkBuddy Claw** | 外部知識ベース読取専用ブリッジ | パス不存在時スキップ |

すべての統合はオプション — DevSquad は単独でも完全に動作可能です。

## テスト実行

```bash
cd /path/to/DevSquad

# コアコラボレーションテスト
python3 -m pytest scripts/collaboration/ -v
# 期待値: ~41 テストケース、全て通過

# クイックステータスチェック
python3 scripts/cli.py status
# 期待値: {"name": "DevSquad", "status": "ready", ...}

# ドラン検証
python3 scripts/cli.py dispatch -t "テスト" --dry-run
```

## 使用例

### シナリオ 1: 設計セッション

```
ユーザ: "マイクロサービス型 EC サイトのバックエンドを設計"
→ DevSquad 自動マッチ: アーキテクト + DevOps + セキュリティ
→ 出力: 技術スタック推奨 + サービス境界 + セキュリティモデル
```

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("マイクロサービス型 EC サイトのバックエンドを設計")
print(result.to_markdown())
disp.shutdown()
```

### シナリオ 2: セキュリティフォーカスのコードレビュー

```python
result = disp.quick_dispatch(
    "auth.py のセキュリティ脆弱性をレビュー",
    output_format="detailed",
    include_action_items=True,
)
```

### シナリオ 3: フルスタック分析

```python
result = disp.dispatch("プロジェクトの本番環境準備状況を評価")
```

### シナリオ 4: コンパクト出力 (端末/パイプ)

```bash
python3 scripts/cli.py quick -t "DB クエリ最適化" -f compact
```

### シナリオ 5: JSON 出力 (連携用)

```bash
python3 scripts/cli.py dispatch -t "API インターフェース分析" -f json
```

## プロジェクト構造

```
DevSquad/
├── scripts/
│   ├── cli.py                    # メイン CLI エントリ
│   ├── mcp_server.py             # MCP Server (OpenClaw/Cursor)
│   ├── trae_agent.py             # レガシーラッパー (/dss コマンド)
│   ├── trae_agent_dispatch_v2.py # コアディスパッチャ (レガシー)
│   └── collaboration/            # ★ 16 コアモジュール
│       ├── dispatcher.py         # MultiAgentDispatcher
│       ├── coordinator.py        # グローバルオーケストレーター
│       ├── scratchpad.py         # 共有ブラドボード
│       ├── worker.py             # ロール実行エージェント
│       ├── consensus.py          # 加权投票 + 拒否
│       ├── memory_bridge.py      # セッション横断メモリ
│       ├── mce_adapter.py        # MCE v0.4 アダプタ
│       └── *_test.py             # テストスイート (~41 ケース)
├── SKILL.md                      # 英語スキルマニュアル
├── SKILL-CN.md                   # 中国語スキルマニュアル
├── SKILL-JP.md                   # 日本語スキルマニュアル
├── CLAUDE.md                     # Claude Code プロジェクト指示
├── INSTALL.md                    # インストールガイド (Unix + Windows)
├── CHANGELOG.md                  # 完全なバージョン履歴
└── docs/                         # アーキテクチャ仕様書、計画
```

## フィロソフィー

> **「AI 1 つはツール。AI 協作者 10 つはチーム。」**

ソフトウェア開発は本質的に学際的です。いかなる単一視点も、調整の取れた多様な専門知識を持つチームの品質には及びません。DevSquad はそのようなチームをオンデマンドで、数秒で、あらゆるソフトウェアタスクのために利用可能にします。

## バージョン履歴

| 日付 | バージョン | 要点 |
|------|-----------|------|
| 2026-04-17 | **V3.3** | ブランド変更 → DevSquad、WorkBuddy Claw 統合、クロスプラットフォーム (CLI/MCP/ClaudeCode)、MAS→DSS |
| 2026-04-17 | V3.2 | E2E デモ、MCE アダプター、ディスパッチャ UX 強化 |
| 2026-04-16 | V3.1 | プロンプト最適化システム (A/B バリアントテスト) |
| 2026-04-16 | V3.0 | 完全再設計 — Coordinator/Worker/Scratchpad アーキテクチャ |
| 2026年3月 | V2.x | 双層コンテキスト、Vibe Coding、MCE 統合 |

## ライセンス

MIT License — [LICENSE](LICENSE) を参照

## リンク

| リンク | URL |
|--------|-----|
| **GitHub (本リポ)** | https://github.com/lulin70/DevSquad |
| **オリジナル / 上流** | https://github.com/weiransoft/TraeMultiAgentSkill |
| **インストール** | [INSTALL.md](INSTALL.md) |
| **スキルマニュアル** | [SKILL.md](SKILL.md) / [SKILL-CN.md](SKILL-CN.md) / [SKILL-JP.md](SKILL-JP.md) |
| **英語 Readme** | [README.md](README.md) |
| **中国語 Readme** | [README-CN.md](README-CN.md) |
