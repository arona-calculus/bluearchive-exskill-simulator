from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from webui.backend import mcp_server  # noqa: E402


def test_transport_security_defaults_to_sdk(monkeypatch) -> None:
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_ORIGINS", raising=False)

    assert mcp_server.transport_security() is None


def test_transport_security_allows_configured_hosts(monkeypatch) -> None:
    # リバースプロキシの後ろでは公開ドメインの Host ヘッダーで届く
    monkeypatch.setenv("EXSIM_MCP_ALLOWED_HOSTS", "exsim.example.com, www.example.com")
    monkeypatch.delenv("EXSIM_MCP_ALLOWED_ORIGINS", raising=False)

    settings = mcp_server.transport_security()

    assert settings.enable_dns_rebinding_protection
    assert {"exsim.example.com", "www.example.com", "localhost:*"} <= set(settings.allowed_hosts)
