# Slack Channel Exporter

指定したSlackチャンネルの過去のメッセージを取得し、スレッドの返信を含めてJSONファイルに保存するツールです。
日付範囲を指定して取得でき、すべての時刻は日本時間（JST）で処理されます。

## 環境構築

このプロジェクトは[uv](https://github.com/astral-sh/uv)を使用して依存関係を管理します。

```bash
uv sync
```

## 環境設定

`.env`ファイルをプロジェクトルートに作成し、以下の内容を設定してください：

```env
SLACK_TOKEN="xoxb-your-slack-bot-token"
```

Slack APIトークンは以下の権限（スコープ）が必要です：
- `channels:history`
- `groups:history`
- `im:history`
- `mpim:history`

## 使用方法

基本的な使用方法：

```bash
uv run ./main.py CHANNEL_ID START_DATE [options]
```

### 引数

- `CHANNEL_ID`: SlackチャンネルのチャンネルまたはチャンネルのURL
  - 例: `C0123456789`
  - 例: `https://your-workspace.slack.com/archives/C0123456789`
- `START_DATE`: 取得開始日（YYYY-MM-DD形式、JST）
  - 例: `2024-03-01`

### オプション

- `-e, --end-date`: 取得終了日（YYYY-MM-DD形式、JST）
  - 省略時は現在時刻まで
  - 例: `-e 2024-03-31`
- `-o, --output`: 出力ファイル名
  - 省略時は `チャンネルID-YYYYMMDD-HHMMSS.json`
  - 例: `-o output.json`

### 使用例

```bash
# 基本的な使用方法（本日まで）
uv run ./main.py C0123456789 2024-03-01

# 期間を指定
uv run ./main.py C0123456789 2024-03-01 -e 2024-03-31

# チャンネルURLを使用
uv run ./main.py https://your-workspace.slack.com/archives/C0123456789 2024-03-01

# カスタム出力ファイル名を指定
uv run ./main.py C0123456789 2024-03-01 -o custom_output.json
```

## 出力形式

出力されるJSONファイルは以下のスキーマに従います：

```typescript
interface ThreadReply {
  timestamp: string;      // Slackメッセージのタイムスタンプ
  readable_time: string;  // 人間が読める形式の時刻（JST）
  user: string;           // ユーザーID
  text: string;           // メッセージ本文
}

interface SlackMessage {
  timestamp: string;      // Slackメッセージのタイムスタンプ
  readable_time: string;  // 人間が読める形式の時刻（JST）
  user: string;           // ユーザーID
  text: string;           // メッセージ本文
  thread_replies: ThreadReply[];  // スレッドの返信一覧
}

interface SlackExport {
  start_date: string;     // エクスポート開始日時（JST）
  end_date: string;       // エクスポート終了日時（JST）
  users: { [userId: string]: { name: string; display_name: string } }; // ユーザーIDとユーザー情報のマッピング
  chat: SlackMessage[];   // チャットメッセージ一覧
}
```

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "start_date": {
      "type": "string",
      "description": "エクスポート開始日時（JST）",
      "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"
    },
    "end_date": {
      "type": "string",
      "description": "エクスポート終了日時（JST）",
      "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"
    },
    "users": {
      "type": "object",
      "description": "ユーザーIDとユーザー情報のマッピング",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "display_name": { "type": "string" }
        },
        "required": ["name", "display_name"]
      }
    },
    "chat": {
      "type": "array",
      "description": "チャットメッセージ一覧",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": {
            "type": "string",
            "description": "Slackメッセージのタイムスタンプ",
            "pattern": "^[0-9]+\\.[0-9]+$"
          },
          "readable_time": {
            "type": "string",
            "description": "人間が読める形式の時刻（JST）",
            "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"
          },
          "user": {
            "type": "string",
            "description": "ユーザーID"
          },
          "text": {
            "type": "string",
            "description": "メッセージ本文"
          },
          "thread_replies": {
            "type": "array",
            "description": "スレッドの返信一覧",
            "items": {
              "type": "object",
              "properties": {
                "timestamp": {
                  "type": "string",
                  "description": "Slackメッセージのタイムスタンプ",
                  "pattern": "^[0-9]+\\.[0-9]+$"
                },
                "readable_time": {
                  "type": "string",
                  "description": "人間が読める形式の時刻（JST）",
                  "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"
                },
                "user": {
                  "type": "string",
                  "description": "ユーザーID"
                },
                "text": {
                  "type": "string",
                  "description": "メッセージ本文"
                }
              },
              "required": ["timestamp", "readable_time", "user", "text"]
            }
          }
        },
        "required": ["timestamp", "readable_time", "user", "text", "thread_replies"]
      }
    }
  },
  "required": ["start_date", "end_date", "users", "chat"]
}
```

出力例：

```json
{
  "start_date": "2024-03-01 00:00:00",
  "end_date": "2024-03-31 23:59:59",
  "users": {
    "U0123456789": { "name": "bot", "display_name": "Bot User" },
    "U9876543210": { "name": "alice", "display_name": "Alice" }
  },
  "chat": [
    {
      "timestamp": "1647824400.123456",
      "readable_time": "2024-03-21 10:00:00",
      "user": "U0123456789",
      "text": "Hello, world!",
      "thread_replies": [
        {
          "timestamp": "1647824500.123456",
          "readable_time": "2024-03-21 10:01:40",
          "user": "U9876543210",
          "text": "Hi there!"
        }
      ]
    }
  ]
}
```

すべての時刻は日本時間（JST）で表示されます。

## `jq`を用いた出力JSONのフィルタリング

出力されるJSONデータを`jq`コマンドラインJSONプロセッサを用いてフィルタリングする方法について説明します。`jq`を使用することで、特定の条件に一致するメッセージを抽出したり、データの形式を変換したりできます。

### jqのインストール方法

`jq`のインストール方法はOSによって異なります。各OSのパッケージマネージャー（例: macOSのHomebrew, Debian/Ubuntuのapt, Windowsのchocoなど）を利用するか、公式サイト（[https://stedolan.github.io/jq/download/](https://stedolan.github.io/jq/download/)）を参照してください。

例（macOSの場合）:

```bash
brew install jq
```

### メッセージのフィルタリング例

以下に、エクスポートしたJSONファイル（`your_file.json`とする）から特定のメッセージを抽出する例を示します。

*   **特定のユーザーIDのメッセージを抽出**
    ユーザーID `U9876543210` が発信したメッセージ（スレッドの返信含む）を抽出します。

    ```bash
    TARGET_USER_ID="U9876543210" jq --arg specified_user_id "$TARGET_USER_ID" \
      '[.chat[] | (select(.user == $specified_user_id), (.thread_replies[] | select(.user == $specified_user_id)))]' \
      your_file.json
    ```

*   **ユーザー名が特定の名前のメッセージを抽出**
    ユーザー名 `alice` が発信したメッセージ（スレッドの返信含む）を抽出します。まず`users`情報からユーザーIDを特定し、そのIDを使ってフィルタリングします。

    ```bash
    TARGET_NAME="alice" jq --arg specified_name "$TARGET_NAME" \
      '(.users | to_entries[] | select(.value.name == $specified_name) | .key) as $target_user_id |
      [
        .chat[] |
        (
          select(.user == $target_user_id),
          (.thread_replies[] | select(.user == $target_user_id))
        )
      ]' \
      your_file.json
    ```

*   **ユーザー表示名が特定の表示名のメッセージを抽出**
    ユーザー表示名 `Alice` が発信したメッセージ（スレッドの返信含む）を抽出します。ユーザー名の場合と同様に、`users`情報からユーザーIDを特定し、そのIDを使ってフィルタリングします。

    ```bash
    TARGET_DISPLAY_NAME="Alice" jq --arg specified_display_name "$TARGET_DISPLAY_NAME" \
      '(.users | to_entries[] | select(.value.display_name == $specified_display_name) | .key) as $target_user_id |
      [
        .chat[] |
        (
          select(.user == $target_user_id),
          (.thread_replies[] | select(.user == $target_user_id))
        )
      ]' \
      your_file.json
    ```
