import sys
import datetime
import pytest
import pytz
import main

JST = pytz.timezone("Asia/Tokyo")

def test_extract_channel_id_plain():
    assert main.extract_channel_id("C123ABC") == "C123ABC"

def test_extract_channel_id_url():
    url = "https://example.slack.com/archives/C456DEF"
    assert main.extract_channel_id(url) == "C456DEF"

def test_convert_datetime_to_timestamp():
    ts = main.convert_datetime_to_timestamp("2023-01-01", "12:34:56")
    dt = datetime.datetime.fromtimestamp(ts, JST)
    assert dt.year == 2023 and dt.month == 1 and dt.day == 1
    assert dt.hour == 12 and dt.minute == 34 and dt.second == 56

def test_generate_output_filename_specified():
    assert main.generate_output_filename("C123ABC", "output.json") == "output.json"

def test_generate_output_filename_default(monkeypatch):
    class DummyDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return tz.localize(datetime.datetime(2023, 1, 2, 3, 4, 5))
    monkeypatch.setattr(main.datetime, "datetime", DummyDateTime)
    filename = main.generate_output_filename("C123ABC", None)
    assert filename == "C123ABC-20230102-030405.json"

def test_parse_args(monkeypatch):
    test_args = ["main.py", "C789GHI", "2023-02-03", "--end-date", "2023-02-04"]
    monkeypatch.setattr(sys, "argv", test_args)
    args = main.parse_args()
    assert args.channel_id == "C789GHI"
    assert args.start_date == "2023-02-03"
    assert args.end_date == "2023-02-04"

def test_fetch_messages_for_period(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.calls = 0
        def conversations_history(self, channel, limit, oldest, latest, cursor):
            self.calls += 1
            if self.calls == 1:
                return {"ok": True, "messages": [{"ts": "1"}], "has_more": True, "response_metadata": {"next_cursor": "cursor1"}}
            return {"ok": True, "messages": [{"ts": "2"}], "has_more": False}
    client = DummyClient()
    monkeypatch.setattr(main.time, "sleep", lambda x: None)
    messages = main.fetch_messages_for_period(client, "C123", "0", "10")
    assert [msg["ts"] for msg in messages] == ["1", "2"]

def test_fetch_thread_messages(monkeypatch):
    from slack_sdk.errors import SlackApiError
    class DummyClient:
        def conversations_replies(self, channel, ts):
            return {"ok": True, "messages": [{"ts": ts}, {"ts": "r1"}, {"ts": "r2"}]}
    client = DummyClient()
    # 正常系
    replies = main.fetch_thread_messages(client, "C123", "100")
    assert replies == [{"ts": "r1"}, {"ts": "r2"}]
    # エラー系: レスポンスを辞書として渡し、インデックスアクセス可能にする
    error_resp = {"error": "error", "headers": {}}
    def error_replies(self, channel, ts):
        raise SlackApiError("err", error_resp)
    monkeypatch.setattr(DummyClient, "conversations_replies", error_replies)
    replies = main.fetch_thread_messages(client, "C123", "100")
    assert replies == []

def test_fetch_user_info(monkeypatch):
    from slack_sdk.errors import SlackApiError
    class DummyClient:
        def users_info(self, user):
            if user == "U_err":
                # エラー系: レスポンスを辞書として渡し、インデックスアクセス可能にする
                resp = {"error": "e", "headers": {}}
                raise SlackApiError("err", resp)
            return {"ok": True, "user": {"name": f"name_{user}", "profile": {"real_name": f"Real_{user}"}}}
    client = DummyClient()
    result = main.fetch_user_info(client, {"U1", "U_err"})
    assert result["U1"].name == "name_U1"
    assert result["U1"].display_name == "Real_U1"
    assert result["U_err"].name == ""
    assert result["U_err"].display_name == "Unknown User"

def test_save_messages_to_file(tmp_path, monkeypatch):
    import json
    messages = [
        {"ts": "100", "user": "U1", "text": "hello", "thread_ts": "100"},
        {"ts": "200", "user": "U2", "text": "hi"}
    ]
    # スレッドメッセージとユーザー情報をスタブ
    monkeypatch.setattr(main, "fetch_thread_messages", lambda client, ch, ts: [{"ts": "101", "user": "U3", "text": "reply"}] if ts=="100" else [])
    dummy_info = {
        "U1": main.UserInfo(name="u1", display_name="User One"),
        "U2": main.UserInfo(name="u2", display_name="User Two"),
        "U3": main.UserInfo(name="u3", display_name="User Three")
    }
    monkeypatch.setattr(main, "fetch_user_info", lambda client, ids: dummy_info)
    filename = tmp_path / "out.json"
    start_date = "2023-01-01 00:00:00"
    end_date = "2023-01-02 23:59:59"
    main.save_messages_to_file(messages, None, "C123", str(filename), start_date, end_date)
    data = json.loads(filename.read_text(encoding="utf-8"))
    assert data["start_date"] == start_date
    assert data["end_date"] == end_date
    assert set(data["users"].keys()) == {"U1", "U2", "U3"}
    chat = data["chat"]
    assert len(chat) == 2
    first, second = chat
    # 保存順序は save_messages_to_file 内で reversed されるため最初に新しいメッセージが来る
    assert first["user"] == "U2"
    assert first["thread_replies"] == []
    assert second["user"] == "U1"
    assert second["thread_replies"][0]["text"] == "reply" 
