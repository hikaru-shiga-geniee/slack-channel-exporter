#!/bin/bash

# jqがインストールされているか確認
if ! command -v jq &> /dev/null
then
    echo "エラー: jqがインストールされていません。jqをインストールしてください。" >&2
    exit 1
fi

# 引数の数の確認
if [ "$#" -lt 2 ]; then
    echo "使い方: $0 <jsonファイル> [--user_id <id> | --name <名前> | --display_name <表示名>]" >&2
    exit 1
fi

JSON_FILE="$1"
OPTION="$2"
VALUE="$3"

JQ_FILTER=""
TARGET_VAR_NAME=""

# オプションに応じたjqフィルターと変数名を設定
case "$OPTION" in
    --user_id)
        if [ -z "$VALUE" ]; then
            echo "エラー: --user_idには値を指定してください。" >&2
            echo "使い方: $0 <jsonファイル> --user_id <id>" >&2
            exit 1
        fi
        TARGET_VAR_NAME="TARGET_USER_ID"
        JQ_FILTER='[.chat[] | (select(.user == $specified_user_id), (.thread_replies[] | select(.user == $specified_user_id)))]'
        ;;
    --name)
        if [ -z "$VALUE" ]; then
            echo "エラー: --nameには値を指定してください。" >&2
            echo "使い方: $0 <jsonファイル> --name <名前>" >&2
            exit 1
        fi
        TARGET_VAR_NAME="TARGET_NAME"
        JQ_FILTER='(.users | to_entries[] | select(.value.name == $specified_name) | .key) as $target_user_id |
        [
          .chat[] |
          (
            select(.user == $target_user_id),
            (.thread_replies[] | select(.user == $target_user_id))
          )
        ]'
        ;;
    --display_name)
        if [ -z "$VALUE" ]; then
            echo "エラー: --display_nameには値を指定してください。" >&2
            echo "使い方: $0 <jsonファイル> --display_name <表示名>" >&2
            exit 1
        fi
        TARGET_VAR_NAME="TARGET_DISPLAY_NAME"
         JQ_FILTER='(.users | to_entries[] | select(.value.display_name == $specified_display_name) | .key) as $target_user_id |
         [
           .chat[] |
           (
             select(.user == $target_user_id),
             (.thread_replies[] | select(.user == $target_user_id))
           )
         ]'
        ;;
    *)
        echo "エラー: 不明なオプションです: $OPTION" >&2
        echo "使い方: $0 <jsonファイル> [--user_id <id> | --name <名前> | --display_name <表示名>]" >&2
        exit 1
        ;;
esac

# 変数をエクスポートしてjqコマンドを実行
export "$TARGET_VAR_NAME"="$VALUE"
jq --arg specified_user_id "$TARGET_USER_ID" \
   --arg specified_name "$TARGET_NAME" \
   --arg specified_display_name "$TARGET_DISPLAY_NAME" \
   "$JQ_FILTER" "$JSON_FILE"

exit 0 
