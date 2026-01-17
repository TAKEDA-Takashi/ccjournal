# Configuration Reference

ccjournal の設定ファイルリファレンスです。

## 設定ファイルの場所

```
~/.config/ccjournal/config.toml
```

## 設定ファイルの作成

```bash
# インタラクティブに設定を作成
ccjournal init

# または手動で作成
mkdir -p ~/.config/ccjournal
touch ~/.config/ccjournal/config.toml
```

## 完全な設定例

```toml
[output]
repository = "~/Documents/claude-logs"
structure = "date"
remote = "origin"
branch = "main"
auto_push = true
allow_public_repository = false
allow_unknown_visibility = false

[sync]
interval = 300
exclude_system = true
exclude_tool_messages = true

[projects.aliases]
"/path/to/project" = "custom-name"
```

---

## [output] セクション

出力先とGit操作に関する設定です。

### repository

| 項目 | 値 |
|------|-----|
| 型 | パス（文字列） |
| デフォルト | `~/Documents/claude-logs` |
| 必須 | いいえ |

ログを出力するGitリポジトリのパス。`~`（ホームディレクトリ）の展開に対応しています。

```toml
repository = "~/Documents/claude-logs"
```

### structure

| 項目 | 値 |
|------|-----|
| 型 | `"date"` または `"project"` |
| デフォルト | `"date"` |
| 必須 | いいえ |

ログファイルのディレクトリ構造を指定します。

**`"date"` (日付ベース)**
```
claude-logs/
└── 2026/
    └── 01/
        └── 17/
            ├── github.com-user-project-a.md
            └── github.com-user-project-b.md
```

**`"project"` (プロジェクトベース)**
```
claude-logs/
├── github.com-user-project-a/
│   ├── 2026-01-16.md
│   └── 2026-01-17.md
└── github.com-user-project-b/
    └── 2026-01-17.md
```

### remote

| 項目 | 値 |
|------|-----|
| 型 | 文字列 |
| デフォルト | `"origin"` |
| 必須 | いいえ |

Git push先のリモート名。

```toml
remote = "origin"
```

### branch

| 項目 | 値 |
|------|-----|
| 型 | 文字列 |
| デフォルト | `"main"` |
| 必須 | いいえ |

Git push先のブランチ名。

```toml
branch = "main"
```

### auto_push

| 項目 | 値 |
|------|-----|
| 型 | 真偽値 |
| デフォルト | `true` |
| 必須 | いいえ |

コミット後に自動でリモートにpushするかどうか。

```toml
auto_push = true   # コミット後にpush
auto_push = false  # コミットのみ（pushしない）
```

### allow_public_repository

| 項目 | 値 |
|------|-----|
| 型 | 真偽値 |
| デフォルト | `false` |
| 必須 | いいえ |

**セキュリティ設定**: publicリポジトリへのpushを許可するかどうか。

セッションログにはAPIキーや社内URLなどの機密情報が含まれる可能性があるため、デフォルトではpublicリポジトリへのpushをブロックします。

```toml
allow_public_repository = false  # publicリポジトリへのpushをブロック（推奨）
allow_public_repository = true   # publicリポジトリへのpushを許可（注意して使用）
```

> **Note**: publicリポジトリの検出には GitHub CLI (`gh`) が必要です。

### allow_unknown_visibility

| 項目 | 値 |
|------|-----|
| 型 | 真偽値 |
| デフォルト | `false` |
| 必須 | いいえ |

**セキュリティ設定**: リポジトリのvisibilityが判定できない場合にpushを許可するかどうか。

以下の場合にvisibilityが「不明」となります：
- GitHub以外のホスティングサービス（GitLab、Bitbucketなど）
- GitHub CLI (`gh`) がインストールされていない
- GitHub CLI が認証されていない

```toml
allow_unknown_visibility = false  # 不明な場合はpushをブロック（推奨）
allow_unknown_visibility = true   # 不明な場合もpushを許可
```

---

## [sync] セクション

同期動作に関する設定です。

### interval

| 項目 | 値 |
|------|-----|
| 型 | 整数（秒） |
| デフォルト | `300`（5分） |
| 必須 | いいえ |

デーモンモードでの同期間隔（秒）。

```toml
interval = 300   # 5分ごと
interval = 3600  # 1時間ごと
```

### exclude_system

| 項目 | 値 |
|------|-----|
| 型 | 真偽値 |
| デフォルト | `true` |
| 必須 | いいえ |

システムメッセージ（`<system-reminder>`タグなど）を出力から除外するかどうか。

```toml
exclude_system = true   # システムメッセージを除外（推奨）
exclude_system = false  # システムメッセージを含める
```

### exclude_tool_messages

| 項目 | 値 |
|------|-----|
| 型 | 真偽値 |
| デフォルト | `true` |
| 必須 | いいえ |

ツール呼び出しのみのメッセージ（`[Tool: Read]`など）を出力から除外するかどうか。

```toml
exclude_tool_messages = true   # ツールのみのメッセージを除外（推奨）
exclude_tool_messages = false  # すべてのメッセージを含める
```

---

## [projects.aliases] セクション

プロジェクトパスのエイリアス設定です。

### 形式

```toml
[projects.aliases]
"/full/path/to/project" = "alias-name"
```

### 使用例

```toml
[projects.aliases]
"/Users/user/work/my-long-project-name" = "my-project"
"/Users/user/ghq/github.com/org/repo" = "org-repo"
```

エイリアスを設定すると、出力ファイル名がエイリアス名になります：

```
# エイリアスなし
claude-logs/2026/01/17/github.com-org-repo.md

# エイリアスあり（"short-name"を設定）
claude-logs/2026/01/17/short-name.md
```

---

## セキュリティ設定のまとめ

| 設定 | デフォルト | 推奨 | 説明 |
|-----|-----------|------|------|
| `allow_public_repository` | `false` | `false` | publicリポジトリへのpush許可 |
| `allow_unknown_visibility` | `false` | `false` | visibility不明時のpush許可 |

### 推奨設定（プライベート用途）

```toml
[output]
allow_public_repository = false
allow_unknown_visibility = false
```

### GitLab/Bitbucketを使用する場合

GitHub以外のホスティングサービスを使用する場合、visibilityの自動検出ができないため、以下の設定が必要です：

```toml
[output]
allow_unknown_visibility = true  # 必須
```

> **警告**: この設定を有効にする前に、リポジトリがprivateであることを手動で確認してください。

---

## 機密情報の自動マスク

ccjournalは以下のパターンを自動的にマスクします：

- APIキー（`sk-xxx`、`AKIA...`など）
- GitHubトークン（`ghp_xxx`、`github_pat_xxx`）
- Bearerトークン
- パスワード（`password=xxx`パターン）
- 環境変数のシークレット

これはフェールセーフとして機能しますが、機密情報の完全な除去を保証するものではありません。セッションログには機密情報を含めないよう注意してください。

---

## トラブルシューティング

### 設定ファイルが読み込まれない

```bash
# 設定ファイルの場所を確認
ccjournal config show

# 設定ファイルが存在するか確認
ls -la ~/.config/ccjournal/config.toml
```

### TOML構文エラー

```bash
# 構文チェック（Pythonで確認）
python3 -c "import tomllib; tomllib.load(open('$HOME/.config/ccjournal/config.toml', 'rb'))"
```

### publicリポジトリエラー

```
Error: Refusing to push to public repository
```

対処法：
1. リポジトリをprivateに変更する（推奨）
2. `allow_public_repository = true`を設定する（リスクを理解した上で）

### visibility不明エラー

```
Error: Repository visibility cannot be determined
```

対処法：
1. GitHub CLI をインストール・認証する
2. `allow_unknown_visibility = true`を設定する（リポジトリがprivateであることを確認した上で）
