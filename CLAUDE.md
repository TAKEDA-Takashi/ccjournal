# ccjournal

Claude Codeのコンバーセーションログを Git リポジトリに自動同期する Python ツール。

## 技術スタック

- **言語**: Python 3.11+
- **パッケージマネージャー**: uv
- **CLIフレームワーク**: click
- **ビルドシステム**: hatchling
- **型チェック**: pyright (standard mode)
- **Linter/Formatter**: ruff

## 開発コマンド

```bash
# 依存関係インストール
uv sync

# テスト実行（カバレッジ計測付き）
uv run pytest

# 型チェック
uv run pyright

# Lint
uv run ruff check

# フォーマット
uv run ruff format
```

## ディレクトリ構造

```
src/ccjournal/
├── __init__.py    # パッケージ初期化、バージョン情報
├── cli.py         # CLIコマンド定義（click）
├── config.py      # 設定管理（TOML形式）
├── daemon.py      # デーモンプロセス管理
├── parser.py      # セッションログパーサー
└── sync.py        # 同期ロジック

tests/
├── test_config.py  # 設定機能テスト
├── test_daemon.py  # デーモン機能テスト
├── test_parser.py  # パーサー機能テスト
└── test_sync.py    # 同期機能テスト
```

## アーキテクチャ

### データフロー

```
Claude Code セッション (.jsonl)
    ↓ discover_sessions()
全セッションファイル検出
    ↓ collect_sessions()
メッセージ抽出・フィルタリング
    ↓ format_session_markdown()
Markdown 形式化
    ↓ write_markdown_file()
ファイル出力
    ↓ git_commit_and_push()
Git コミット・プッシュ
```

### 主要コンポーネント

- **parser.py**: Claude Code の `.jsonl` セッションファイルをパース
  - `decode_project_path()`: エンコード済みパスをデコード
  - `normalize_remote_url()`: Git Remote URL の正規化
  - `parse_session_file()`: セッションファイルのパース

- **config.py**: TOML 形式の設定管理
  - 設定ファイル: `~/.config/ccjournal/config.toml`
  - 出力構造: `date`（日付ベース）または `project`（プロジェクトベース）

- **sync.py**: 同期ロジック
  - `generate_output_path()`: 出力パス生成
  - `sync_logs()`: メイン同期処理
  - `check_repository_visibility()`: GitHub リポジトリの public/private 判定
  - `check_push_permission()`: push 権限チェック（visibility + 設定）
  - `PublicRepositoryError`: public リポジトリへの push 拒否時の例外

- **daemon.py**: デーモンプロセス管理
  - `DaemonProcess`: 定期同期を行うデーモンクラス
  - `start_daemon()`: デーモン起動
  - `stop_daemon()`: デーモン停止
  - `get_daemon_status()`: デーモン状態取得

- **cli.py**: CLI コマンド
  - `init`: インタラクティブ設定
  - `sync`: ログ同期（`--dry-run`, `--date`, `--no-commit`, `--no-push`）
  - `config show/edit`: 設定管理
  - `list`: ログ一覧
  - `daemon install`: 自動同期設定

## CLIエントリーポイント

```
ccjournal = "ccjournal.cli:main"
```

## 設定ファイル例

```toml
[output]
repository = "~/ccjournal-logs"
structure = "date"  # "date" or "project"
auto_push = true
allow_public_repository = false  # public リポジトリへの push をブロック
allow_unknown_visibility = false  # visibility 不明時の push をブロック

[sync]
interval = 3600
exclude_system = true
exclude_tool_messages = true  # [Tool: XXX] のみのメッセージを除外

[project_aliases]
"/path/to/project" = "my-project"
```

## セキュリティ

### フェールセーフ設計

- **public リポジトリ保護**: デフォルトで public リポジトリへの push をブロック
  - GitHub CLI (`gh`) でリポジトリの visibility を検出
  - `allow_public_repository = true` で明示的に許可可能
- **unknown visibility 保護**: visibility が判定できない場合もデフォルトでブロック
  - 非 GitHub リポジトリ（GitLab、Bitbucket等）や `gh` CLI 未インストール時
  - `allow_unknown_visibility = true` で明示的に許可可能
- **デーモンモードでも保護**: CLI と同様の visibility チェックをデーモンでも実行

### 機密情報マスク化

セッションログに含まれる可能性のある機密情報を自動的にマスク:

- API キー（OpenAI `sk-xxx`、AWS `AKIA...`、GitHub `ghp_xxx` 等）
- Bearer トークン、Authorization ヘッダー
- パスワード（`password=xxx` パターン）
- 環境変数のシークレット（`export API_KEY=xxx`）

### セキュリティ設定オプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `allow_public_repository` | `false` | public リポジトリへの push を許可 |
| `allow_unknown_visibility` | `false` | visibility 不明時の push を許可 |
