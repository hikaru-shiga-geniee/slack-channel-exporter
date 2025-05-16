import os
import time
import datetime
import json
import logging
import argparse
import re
import pytz
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pydantic import BaseModel, Field
from typing import Dict

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# 設定値
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
if not SLACK_TOKEN:
    logger.error("SLACK_TOKEN not found in environment variables")
    raise ValueError("SLACK_TOKEN must be set in .env file")

# 日本のタイムゾーンを設定
JST = pytz.timezone("Asia/Tokyo")


def extract_channel_id(channel_input: str) -> str:
    """
    チャンネルの入力からチャンネルIDを抽出します。
    URLの場合はURLからIDを抽出し、そうでない場合は入力をそのまま返します。

    Args:
        channel_input: チャンネルIDまたはSlackチャンネルURL

    Returns:
        str: 抽出されたチャンネルID
    """
    # Slackチャンネル URL のパターン
    url_pattern = r"https://[^/]+/archives/([A-Z0-9]+)"
    match = re.match(url_pattern, channel_input)

    if match:
        channel_id = match.group(1)
        logger.info(
            f"Extracted channel ID '{channel_id}' from Slack channel URL '{channel_input}'"
        )
        return channel_id

    return channel_input


def parse_args():
    """
    コマンドライン引数をパースします。
    CHANNEL_IDとSTART_DATE_STRは必須の位置引数です。
    END_DATE_STRは省略可能で、省略時は現在時刻が使用されます。
    CHANNEL_IDはIDまたはSlackチャンネルURLで指定可能です。
    すべての日付は日本時間（JST）として解釈されます。
    """
    parser = argparse.ArgumentParser(description="Slack メッセージ取得スクリプト")

    # 必須の位置引数
    parser.add_argument(
        "channel_id", help="取得対象のSlackチャンネルID または SlackチャンネルURL"
    )
    parser.add_argument("start_date", help="取得開始日 (YYYY-MM-DD形式、日本時間)")

    # オプショナルな引数
    parser.add_argument(
        "--end-date",
        "-e",
        help="取得終了日 (YYYY-MM-DD形式、日本時間、省略時は現在時刻まで)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="出力ファイル名 (省略時は 'チャンネルID-YYYYMMDD-HHMMSS.json')",
    )

    args = parser.parse_args()

    # チャンネルIDの抽出
    args.channel_id = extract_channel_id(args.channel_id)

    # 開始日の形式を検証
    try:
        datetime.datetime.strptime(args.start_date, "%Y-%m-%d")
    except ValueError:
        parser.error("開始日は YYYY-MM-DD 形式で指定してください")

    # 終了日が指定されている場合は形式を検証
    if args.end_date:
        try:
            datetime.datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            parser.error("終了日は YYYY-MM-DD 形式で指定してください")
    else:
        # 終了日が指定されていない場合は現在の日本時間を使用
        args.end_date = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        logger.info(
            f"Using current time {args.end_date} (JST) as end date was not specified"
        )

    return args


class ThreadReply(BaseModel):
    """スレッドの返信を表すPydanticモデル"""

    timestamp: str = Field(description="Slackのタイムスタンプ")
    readable_time: str = Field(description="人間が読める形式の時刻")
    user: str = Field(description="ユーザーID")
    text: str = Field(description="メッセージ本文")


class SlackMessage(BaseModel):
    """Slackのメッセージを表すPydanticモデル"""

    timestamp: str = Field(description="Slackのタイムスタンプ")
    readable_time: str = Field(description="人間が読める形式の時刻")
    user: str = Field(description="ユーザーID")
    text: str = Field(description="メッセージ本文")
    thread_replies: list[ThreadReply] = Field(
        default_factory=list, description="スレッドの返信一覧"
    )


# ユーザー情報を表すPydanticモデル
class UserInfo(BaseModel):
    """ユーザー情報を表すPydanticモデル"""
    name: str = Field(description="Slackのユーザー名")
    display_name: str = Field(description="ユーザーの氏名（実名）")


class SlackExport(BaseModel):
    """Slackエクスポートデータを表すPydanticモデル"""

    start_date: str = Field(description="エクスポート開始日時（JST）")
    end_date: str = Field(description="エクスポート終了日時（JST）")
    users: Dict[str, UserInfo] = Field(description="ユーザーIDとユーザー情報のマッピング")
    chat: list[SlackMessage] = Field(description="チャットメッセージ一覧")


def convert_datetime_to_timestamp(date_str, time_str="00:00:00"):
    """
    YYYY-MM-DD形式の日付文字列とHH:MM:SS形式の時刻文字列を
    Unixタイムスタンプ（エポック秒）に変換します。
    入力された日付は日本時間（JST）として解釈されます。
    """
    try:
        # 日本時間として日付を解釈
        dt_naive = datetime.datetime.strptime(
            f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"
        )
        dt_jst = JST.localize(dt_naive)
        return dt_jst.timestamp()
    except ValueError as e:
        logger.error(f"Date/time format error: {e}")
        return None


def fetch_messages_for_period(client, channel_id, oldest_ts, latest_ts):
    """
    指定されたチャンネルから指定期間のメッセージを取得します。
    """
    all_messages = []
    cursor = None
    message_count = 0

    logger.info(f"Starting to fetch messages from channel '{channel_id}'...")
    logger.info(
        f"Period: {datetime.datetime.fromtimestamp(float(oldest_ts), JST)} to {datetime.datetime.fromtimestamp(float(latest_ts), JST)} (JST)"
    )

    while True:
        try:
            response = client.conversations_history(
                channel=channel_id,
                limit=200,
                oldest=str(oldest_ts),
                latest=str(latest_ts),
                cursor=cursor,
            )

            if response["ok"]:
                messages = response["messages"]
                all_messages.extend(messages)
                message_count += len(messages)
                logger.info(
                    f"Retrieved {len(messages)} messages. Total: {message_count}"
                )

                if response.get("has_more"):
                    cursor = response["response_metadata"]["next_cursor"]
                    time.sleep(1)  # Rate limit avoidance
                else:
                    logger.info(
                        "Successfully retrieved all messages for the specified period."
                    )
                    break
            else:
                logger.error(f"API Error: {response['error']}")
                break

        except SlackApiError as e:
            logger.error(f"Slack API Error: {e.response['error']}")
            if e.response.headers.get("Retry-After"):
                retry_after = int(e.response.headers["Retry-After"])
                logger.info(f"Rate limited. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                break
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            break

    return all_messages


def fetch_thread_messages(client, channel_id, thread_ts):
    """
    特定のスレッドからメッセージを取得します。
    """
    try:
        response = client.conversations_replies(channel=channel_id, ts=thread_ts)
        if response["ok"]:
            return response["messages"][1:]
    except SlackApiError as e:
        logger.error(
            f"Error occurred while fetching thread messages: {e.response['error']}"
        )
    return []


def fetch_user_info(client: WebClient, user_ids: set[str]) -> Dict[str, UserInfo]:
    """
    ユーザーIDのリストからユーザー情報を取得します。

    Args:
        client: Slack WebClient
        user_ids: ユーザーIDのセット

    Returns:
        Dict[str, UserInfo]: ユーザーIDとユーザー情報のマッピング
    """
    user_info: Dict[str, UserInfo] = {}
    for user_id in user_ids:
        try:
            response = client.users_info(user=user_id)
            if response["ok"]:
                user = response["user"]
                profile = user.get("profile", {})
                user_name = user.get("name", "") or ""
                # real_nameを優先し、存在しない場合にdisplay_nameを使用
                display_name_val = profile.get("real_name") or profile.get("display_name") or ""
                user_info[user_id] = UserInfo(name=user_name, display_name=display_name_val)
            time.sleep(1)  # Rate limit avoidance
        except SlackApiError as e:
            logger.error(f"Error fetching user info for {user_id}: {e.response['error']}")
            user_info[user_id] = UserInfo(name="", display_name="Unknown User")
    return user_info


def save_messages_to_file(messages, client, channel_id, filename, start_date, end_date):
    """
    取得したメッセージをスレッドメッセージを含めてJSON形式でファイルに保存します。
    すべての時刻は日本時間（JST）で表示されます。
    """
    try:
        # ユーザーIDを収集
        user_ids = set()
        for msg in messages:
            user_ids.add(msg.get("user", "Unknown User"))
            if msg.get("thread_ts") and msg.get("thread_ts") == msg.get("ts"):
                thread_messages = fetch_thread_messages(client, channel_id, msg["ts"])
                for reply in thread_messages:
                    user_ids.add(reply.get("user", "Unknown User"))

        # ユーザー情報を取得
        user_info = fetch_user_info(client, user_ids)

        # メッセージデータの準備
        chat_data = []
        for msg in reversed(messages):
            thread_replies = []

            if msg.get("thread_ts") and msg.get("thread_ts") == msg.get("ts"):
                thread_messages = fetch_thread_messages(client, channel_id, msg["ts"])
                for reply in thread_messages:
                    dt_utc = datetime.datetime.fromtimestamp(
                        float(reply.get("ts", "0")), pytz.UTC
                    )
                    dt_jst = dt_utc.astimezone(JST)
                    reply_data = ThreadReply(
                        timestamp=reply.get("ts", ""),
                        readable_time=dt_jst.strftime("%Y-%m-%d %H:%M:%S"),
                        user=reply.get("user", "Unknown User"),
                        text=reply.get("text", ""),
                    )
                    thread_replies.append(reply_data)

            dt_utc = datetime.datetime.fromtimestamp(
                float(msg.get("ts", "0")), pytz.UTC
            )
            dt_jst = dt_utc.astimezone(JST)
            message_data = SlackMessage(
                timestamp=msg.get("ts", ""),
                readable_time=dt_jst.strftime("%Y-%m-%d %H:%M:%S"),
                user=msg.get("user", "Unknown User"),
                text=msg.get("text", ""),
                thread_replies=thread_replies,
            )
            chat_data.append(message_data)

        # Pydanticモデルを使用してデータを構造化
        export_data = SlackExport(
            start_date=start_date,
            end_date=end_date,
            users=user_info,
            chat=chat_data
        )

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved messages to '{filename}' in JSON format")
    except OSError as e:
        logger.error(f"Error occurred while writing to file: {e}")


def generate_output_filename(
    channel_id: str, specified_output: str | None = None
) -> str:
    """
    出力ファイル名を生成します。
    指定された出力ファイル名がある場合はそれを使用し、
    ない場合はチャンネルIDと現在の日本時間のタイムスタンプに基づいて生成します。

    Args:
        channel_id: チャンネルID
        specified_output: 指定された出力ファイル名（オプション）

    Returns:
        str: 出力ファイル名
    """
    if specified_output:
        return specified_output

    current_time = datetime.datetime.now(JST).strftime("%Y%m%d-%H%M%S")
    return f"{channel_id}-{current_time}.json"


if __name__ == "__main__":
    # コマンドライン引数の解析
    args = parse_args()

    token = SLACK_TOKEN
    channel_id_to_fetch = args.channel_id
    start_date = args.start_date
    end_date = args.end_date

    if not token or not channel_id_to_fetch:
        logger.error("Error: SLACK_TOKEN and CHANNEL_ID must be configured")
    else:
        oldest_timestamp = convert_datetime_to_timestamp(start_date, "00:00:00")
        latest_timestamp = convert_datetime_to_timestamp(end_date, "23:59:59")

        if oldest_timestamp is None or latest_timestamp is None:
            logger.error("Failed to convert dates. Aborting process.")
        else:
            # タイムスタンプを日本時間で表示
            start_dt_jst = datetime.datetime.fromtimestamp(oldest_timestamp, JST)
            end_dt_jst = datetime.datetime.fromtimestamp(latest_timestamp, JST)
            start_date_str = start_dt_jst.strftime("%Y-%m-%d %H:%M:%S")
            end_date_str = end_dt_jst.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Start time (JST): {start_date_str}")
            logger.info(f"End time (JST): {end_date_str}")

            client = WebClient(token=token)
            all_messages = fetch_messages_for_period(
                client, channel_id_to_fetch, oldest_timestamp, latest_timestamp
            )

            if all_messages:
                output_filename = generate_output_filename(
                    channel_id_to_fetch, args.output
                )
                save_messages_to_file(
                    all_messages, client, channel_id_to_fetch, output_filename,
                    start_date_str, end_date_str
                )
