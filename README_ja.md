# ccjournal

Claude Code のコンバーセーションログを Git リポジトリに同期するツール。

[English](README.md)

## 動作要件

### 必須

- **Python 3.11+**
- **Git** - ログのコミットとプッシュに使用
- **Claude Code** - このツールは Claude Code が生成するログを同期します

### オプション

- **GitHub CLI (`gh`)** - publicリポジトリの検出に必要
  - インストール: `brew install gh` (macOS) または [GitHub CLI インストール](https://cli.github.com/)
  - 認証: `gh auth login`

## 機能

- Claude Code セッションログを Git リポジトリに自動同期
- 日付別またはプロジェクト別にログを整理
- worktree 対応（Git リモート URL でグループ化）
- 自動コミット・プッシュ
- TOML 形式で設定可能

## インストール

```bash
pipx install ccjournal
# または
uv tool install ccjournal
```

## クイックスタート

```bash
# 設定を初期化
ccjournal init

# 手動でログを同期
ccjournal sync

# 設定を表示
ccjournal config show
```

## 設定

設定ファイルは `~/.config/ccjournal/config.toml` に配置されます。

**クイックリファレンス:**

```toml
[output]
repository = "~/Documents/claude-logs"
structure = "date"                    # "date" または "project"
auto_push = true
allow_public_repository = false       # セキュリティ: publicリポジトリへのpushをブロック
allow_unknown_visibility = false      # セキュリティ: visibility不明時のpushをブロック

[sync]
interval = 300                        # 秒（デーモン用）
exclude_system = true                 # システムメッセージを除外
exclude_tool_messages = true          # [Tool: XXX] のみのメッセージを除外

[projects.aliases]
"/path/to/project" = "custom-name"    # オプション: プロジェクト名をカスタマイズ
```

完全な設定リファレンスは **[docs/configuration_ja.md](docs/configuration_ja.md)** を参照してください。

## セキュリティ

### フェールセーフ設計

ccjournal は機密情報の漏洩を防ぐため、複数のセキュリティレイヤーを備えています：

1. **publicリポジトリ保護** - デフォルトでpublicリポジトリへのpushをブロック
2. **unknown visibility保護** - visibility判定不能時（非GitHubリポジトリなど）のpushをブロック
3. **機密情報マスク** - APIキー、トークン、パスワードを出力時に自動マスク

### publicリポジトリ保護

デフォルトで、ccjournal は **publicリポジトリへのpushをブロック** します。これは、セッションログに含まれる可能性のある機密情報の漏洩を防ぐためです：

- プロンプトに記載されたAPIキーやパスワード
- 社内URL（Notion、Confluenceなど）
- 機密性の高い議論内容

出力先リポジトリがGitHubでpublicと検出された場合、同期はエラーで失敗します：

```
Error: Refusing to push to public repository: /path/to/repo
```

**注意:** publicリポジトリの検出には GitHub CLI (`gh`) が必要です。非GitHubリポジトリの場合は、リポジトリがprivateであることを確認した上で `allow_unknown_visibility = true` を設定してください。

### ディレクトリ構造

**日付ベース（デフォルト）:**
```
claude-logs/
└── 2026/01/16/
    ├── my-project.md
    └── another-repo.md
```

**プロジェクトベース:**
```
claude-logs/
└── github.com-user-my-project/
    ├── 2026-01-16.md
    └── 2026-01-15.md
```

## コマンド

| コマンド | 説明 |
|---------|------|
| `ccjournal init` | 設定をインタラクティブに初期化 |
| `ccjournal sync` | ログをリポジトリに同期 |
| `ccjournal sync --dry-run` | 同期内容をプレビュー |
| `ccjournal sync --date 2026-01-16` | 特定日付のログを同期 |
| `ccjournal config show` | 現在の設定を表示 |
| `ccjournal config edit` | エディタで設定を編集 |
| `ccjournal list` | 最近の同期済みログを一覧表示 |
| `ccjournal daemon install` | デーモンをシステムサービスとしてインストール |
| `ccjournal daemon uninstall` | デーモンサービスをアンインストール |

## 自動同期

### macOS (launchd)

```bash
ccjournal daemon install
```

表示される手順に従って、5分ごとの自動同期を設定できます。

### Linux (systemd)

定期同期用のユーザーサービスを作成します。詳細は `ccjournal daemon install` を参照してください。

### cron

```bash
# 5分ごとに同期
*/5 * * * * /usr/local/bin/ccjournal sync
```

## 開発

```bash
# リポジトリをクローン
git clone https://github.com/TAKEDA-Takashi/ccjournal.git
cd ccjournal

# 依存関係をインストール
uv sync --dev

# テスト実行
uv run pytest

# 型チェック
uv run pyright

# Lint
uv run ruff check
```

## ライセンス

MIT
