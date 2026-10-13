from __future__ import annotations

import base64
import gzip
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from webui.backend import main, tl_agent, tl_import_jobs

CHARS = ["Aru", "Kisaki", "Sena", "Mutsuki"]


# ---------------------------------------------------------------------------
# Claude API の代わり(client.beta.messages.stream(...) の形だけ真似る)
# ---------------------------------------------------------------------------


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        # messages はループ中に追記されるので、呼ばれた時点の中身を残す
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        message = self.responses.pop(0)

        class _Stream:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get_final_message(self):
                return message

        return _Stream()


def _message(*blocks, stop_reason="tool_use"):
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=50
    )
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=usage)


def _tool(tool_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool_results(request):
    return request["messages"][-1]["content"]


def _decode_share(share: str) -> dict:
    data = share[1:]
    return json.loads(gzip.decompress(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))))


SIMULATE_INPUT = {
    "characters": CHARS,
    "steps": [{"card": "アル", "note": "3:50"}, {"card": "Kisaki"}],
    "title": "テスト",
}


# ---------------------------------------------------------------------------
# tl_agent: Claude とのやり取りのループ
# ---------------------------------------------------------------------------


def test_import_runs_tools_and_returns_last_simulation() -> None:
    client = FakeClient(
        [
            _message(_tool("t1", "list_characters", {"query": "アル"})),
            _message(_tool("t2", "simulate_tl", SIMULATE_INPUT)),
            _message(_text("最後まで読み込めました。"), stop_reason="end_turn"),
        ]
    )
    progress = []
    result = tl_agent.import_rough_tl("TL本文", notes="補足", client=client, on_progress=progress.append)

    assert result.simulated and result.ok
    assert result.summary == "最後まで読み込めました。"
    save = _decode_share(result.share)
    assert save["name"] == "テスト"
    assert [h["card"] for h in save["history"]] == ["Aru", "Kisaki"]
    assert save["frame_comments"]["0"] == "3:50"
    assert result.usage["requests"] == 3 and result.usage["cache_read"] == 150
    assert any("シミュレーション" in p for p in progress)

    first = client.requests[0]
    assert first["model"] == tl_agent.MODEL
    assert first["fallbacks"] == "default" and tl_agent.FALLBACK_BETA in first["betas"]
    assert "<notes>" in first["messages"][0]["content"]
    # ツールの結果は同じ tool_use_id で返り、共有リンク(share_url)は含めない
    listed = _tool_results(client.requests[1])[0]
    assert listed["tool_use_id"] == "t1" and not listed["is_error"]
    simulated = json.loads(_tool_results(client.requests[2])[0]["content"])
    assert simulated["ok"] and "share_url" not in simulated


def test_invalid_tool_input_is_returned_as_error_without_running() -> None:
    client = FakeClient(
        [
            _message(_tool("t1", "simulate_tl", {"characters": CHARS, "steps": "アル→キサキ"})),
            _message(_text("読み込めませんでした。"), stop_reason="end_turn"),
        ]
    )
    result = tl_agent.import_rough_tl("TL本文", client=client)

    error = _tool_results(client.requests[1])[0]
    assert error["is_error"] and "INVALID_INPUT" in error["content"]
    assert not result.simulated and result.share is None


def test_unknown_student_is_an_error_result() -> None:
    client = FakeClient(
        [
            _message(_tool("t1", "simulate_tl", {"characters": CHARS[:3] + ["カジコ"], "steps": []})),
            _message(_text("カジコが分かりませんでした。"), stop_reason="end_turn"),
        ]
    )
    result = tl_agent.import_rough_tl("TL本文", client=client)

    error = _tool_results(client.requests[1])[0]
    assert error["is_error"] and "未知の生徒名" in error["content"]
    assert not result.simulated


def test_list_characters_without_query_is_limited() -> None:
    client = FakeClient(
        [
            _message(_tool("t1", "list_characters", {})),
            _message(_text("..."), stop_reason="end_turn"),
        ]
    )
    tl_agent.import_rough_tl("TL本文", client=client)

    listed = json.loads(_tool_results(client.requests[1])[0]["content"])
    assert len(listed["characters"]) == tl_agent.LIST_LIMIT and listed["total"] > tl_agent.LIST_LIMIT


def test_refusal_stops_without_running_tools() -> None:
    client = FakeClient([_message(_tool("t1", "simulate_tl", SIMULATE_INPUT), stop_reason="refusal")])

    with pytest.raises(tl_agent.TLImportError):
        tl_agent.import_rough_tl("TL本文", client=client)


def test_stops_after_max_turns(monkeypatch) -> None:
    monkeypatch.setattr(tl_agent, "MAX_TURNS", 2)
    client = FakeClient([_message(_tool(f"t{i}", "list_characters", {"query": "アル"})) for i in range(2)])

    result = tl_agent.import_rough_tl("TL本文", client=client)

    assert "上限" in result.summary and len(client.requests) == 2


# ---------------------------------------------------------------------------
# webuiのエンドポイント: ジョブと利用制限
# ---------------------------------------------------------------------------


def _fake_runner(tl_text, notes, on_progress):
    on_progress("シミュレーションしています(2手)")
    if "断る" in tl_text:
        raise tl_agent.TLImportError("ClaudeがこのTLの処理を断りました。")
    return tl_agent.ImportResult(
        summary="読み込めました", simulated=True, ok=True, error=None, share="zSHARE"
    )


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(main, "tl_jobs", tl_import_jobs.JobStore(runner=_fake_runner))
    return TestClient(main.app)


def _wait(api, job_id):
    for _ in range(100):
        job = api.get(f"/api/tl_import/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_import_job_returns_share(api) -> None:
    res = api.post("/api/tl_import", json={"tl_text": "TL本文"})
    job = _wait(api, res.json()["job_id"])

    assert job["status"] == "done"
    assert job["result"]["share"] == "zSHARE" and job["result"]["ok"]
    assert job["progress"] == ["シミュレーションしています(2手)"]


def test_import_job_reports_user_facing_error(api) -> None:
    res = api.post("/api/tl_import", json={"tl_text": "断るTL"})
    job = _wait(api, res.json()["job_id"])

    assert job["status"] == "error" and "断りました" in job["error"]


def test_import_rejects_empty_and_too_long(api) -> None:
    assert api.post("/api/tl_import", json={"tl_text": "  "}).status_code == 400
    too_long = "あ" * (tl_import_jobs.MAX_CHARS + 1)
    assert api.post("/api/tl_import", json={"tl_text": too_long}).status_code == 400


def test_import_is_rate_limited_per_ip(api, monkeypatch) -> None:
    monkeypatch.setattr(tl_import_jobs, "PER_IP_PER_HOUR", 1)
    first = api.post("/api/tl_import", json={"tl_text": "TL本文"})
    _wait(api, first.json()["job_id"])

    second = api.post("/api/tl_import", json={"tl_text": "TL本文"})
    assert second.status_code == 429 and "1時間に1回" in second.json()["detail"]


def test_import_disabled_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    api = TestClient(main.app)

    assert api.get("/api/tl_import/status").json()["enabled"] is False
    assert api.post("/api/tl_import", json={"tl_text": "TL本文"}).status_code == 503
