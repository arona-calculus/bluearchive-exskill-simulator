from __future__ import annotations

import asyncio
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


def test_prompt_takes_no_tl_argument() -> None:
    # TLを引数で渡すと空白や改行で崩れるため、プロンプトは手順を添えるだけにする
    prompts = asyncio.run(mcp_server.mcp.list_prompts())
    assert [(p.name, p.arguments or []) for p in prompts] == [("import_tl_from_text", [])]

    result = asyncio.run(mcp_server.mcp.get_prompt("import_tl_from_text"))
    assert mcp_server.INSTRUCTIONS in result.messages[0].content.text


def test_tool_descriptions_carry_tl_reading_rules() -> None:
    # 指示文を渡さないクライアントでも、TLの読み方がツールの説明から伝わる
    tools = {t.name: t.description for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert "「リオ → X」がコピー" in tools["simulate_tl"]
    assert "略記" in tools["list_characters"]


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
        at_root = client.post("/mcp", json=SIMULATE_CALL, headers=headers)
        under_exsim = client.post("/exsim/mcp", json=SIMULATE_CALL, headers=headers)

    def share_url(res):
        out = json.loads(res.json()["result"]["content"][0]["text"])
        assert out["ok"]
        return out["share_url"]

    # ドメイン直下で公開している場合と、/exsim/ の下で公開している場合
    assert share_url(at_root).startswith("https://exsim.example.com/#share=")
    assert share_url(under_exsim).startswith("https://exsim.example.com/exsim/#share=")
