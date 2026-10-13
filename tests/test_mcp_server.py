from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")

from fastapi.testclient import TestClient  # noqa: E402

from webui.backend import main, mcp_server  # noqa: E402

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
SIMULATE_CALL = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "simulate_tl",
        "arguments": {"characters": ["Aru", "Kisaki", "Sena", "Mutsuki"], "steps": [{"card": "アル"}]},
    },
}


def test_transport_security_defaults_to_sdk(monkeypatch) -> None:
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_ORIGINS", raising=False)

    assert mcp_server.transport_security() is None
    # webuiに同居する時は公開サイトの一部なので Host を検査しない
    assert not mcp_server.transport_security(in_webui=True).enable_dns_rebinding_protection


def test_transport_security_allows_configured_hosts(monkeypatch) -> None:
    # リバースプロキシの後ろでは公開ドメインの Host ヘッダーで届く
    monkeypatch.setenv("EXSIM_MCP_ALLOWED_HOSTS", "exsim.example.com, www.example.com")
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_ORIGINS", raising=False)

    settings = mcp_server.transport_security()

    assert settings.enable_dns_rebinding_protection
    assert {"exsim.example.com", "www.example.com", "localhost:*"} <= set(settings.allowed_hosts)


def test_webui_serves_mcp_with_public_share_url(monkeypatch) -> None:
    # VPSでは webui に同居した /mcp がリバースプロキシ経由で呼ばれる。共有リンクは公開URLを向く
    # (MCPのセッションマネージャーは1プロセスで1回しか起動できないため、lifespan を回すのはこのテストだけ)
    monkeypatch.delenv("EXSIM_BASE_URL", raising=False)
    headers = {**MCP_HEADERS, "Host": "exsim.example.com", "X-Forwarded-Proto": "https"}

    with TestClient(main.app) as client:
        res = client.post("/mcp", json=SIMULATE_CALL, headers=headers)

    out = json.loads(res.json()["result"]["content"][0]["text"])
    assert out["ok"]
    assert out["share_url"].startswith("https://exsim.example.com/exsim/#share=")
