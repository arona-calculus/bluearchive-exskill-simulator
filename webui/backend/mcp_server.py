"""
BA EX Skill Simulator - MCPサーバー

ラフに書かれたTLをLLM(Claude等)が解釈し、このサーバーのツールで厳密に実行・検証した上で、
webuiの共有リンク(#share=)としてexsimに読み込ませるためのもの。
状態は持たない(webuiの起動も不要。リンクを開く時だけwebuiが動いていればよい)。
ツールの中身と指示文は webuiのTL取り込みページと共有している(tl_tools.py)。

起動方法:
  cd bluearchive-exskill-simulator
  uv run --extra mcp python -m webui.backend.mcp_server          # stdio(手元の Claude Code 用)
  uv run --extra mcp python -m webui.backend.mcp_server --http   # HTTP単体(動作確認用。既定 127.0.0.1:8765/mcp)
リモートMCPとして公開する時は webui(main.py)に同居させる: webui を起動すれば /mcp で待ち受ける。

環境変数:
  EXSIM_BASE_URL            共有リンクの宛先。未設定なら、HTTPではリクエストの Host 等から推定し、
                            stdio では http://localhost:8000/ にする
  EXSIM_MCP_ALLOWED_HOSTS   HTTP時に受け付ける Host ヘッダー(カンマ区切り)。HTTP単体でリバースプロキシの
                            後ろに置く時は公開ドメインを指定しないと 421 で拒否される(webui同居では不要)
  EXSIM_MCP_ALLOWED_ORIGINS HTTP時に受け付ける Origin ヘッダー(カンマ区切り。ブラウザから直接呼ばれる場合のみ)
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from webui.backend import tl_import, tl_tools
from webui.backend.tl_tools import DESCRIPTIONS, INSTRUCTIONS, StepInput

mcp = MCPServer("ba-exsim", instructions=INSTRUCTIONS)


@mcp.tool(description=DESCRIPTIONS["list_characters"])
def list_characters(query: str = "") -> List[Dict[str, Any]]:
    return tl_tools.list_characters(query)


@mcp.tool(description=DESCRIPTIONS["find_initial_orders"])
def find_initial_orders(
    characters: List[str],
    steps: List[StepInput],
    hand_size: int = 3,
    max_results: int = 10,
) -> Dict[str, Any]:
    return tl_tools.find_initial_orders(characters, steps, hand_size, max_results)


@mcp.tool(description=DESCRIPTIONS["simulate_tl"])
def simulate_tl(
    characters: List[str],
    steps: List[StepInput],
    hand_size: int = 3,
    title: str = tl_tools.DEFAULT_TITLE,
    env: Optional[Dict[str, Any]] = None,
    ctx: Optional[Context] = None,
) -> Dict[str, Any]:
    out, save = tl_tools.simulate_tl(characters, steps, hand_size, title, env)
    if save is not None:
        out["share_url"] = tl_import.share_url(save, public_base_url(ctx))
    return out


WEBUI_PREFIX = "/exsim"


def public_base_url(ctx: Optional[Context]) -> Optional[str]:
    """HTTPで呼ばれた時に、共有リンクの宛先(webuiの公開URL)をリクエストから推定する。

    EXSIM_BASE_URL が設定されていればそちらを優先する(None を返し、share_url に任せる)。
    stdio ではリクエストヘッダーが無いので推定しない。パスの前置きは X-Forwarded-Prefix か、
    リクエストが /exsim/mcp 宛てに届いたかで決める(webuiは / と /exsim/ のどちらでも動く)。
    """
    if os.environ.get("EXSIM_BASE_URL") or ctx is None or not ctx.headers:
        return None
    headers = ctx.headers
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host:
        return None
    local = host.startswith(("localhost", "127.0.0.1", "[::1]"))
    scheme = headers.get("x-forwarded-proto", "").split(",")[0].strip() or ("http" if local else "https")
    prefix = headers.get("x-forwarded-prefix")
    if prefix is None:
        # FastAPI の root_path(/exsim)は公開時の前置きとは限らない(ドメイン直下で公開している場合もある)
        # ので、実際に /exsim/mcp 宛てに届いた時だけ前置きを付ける
        request = getattr(ctx.request_context, "request", None)
        path = request.scope.get("path", "") if request is not None else ""
        prefix = WEBUI_PREFIX if path.startswith(WEBUI_PREFIX + "/") else ""
    return f"{scheme}://{host}{prefix.rstrip('/')}/"


# TLは引数で受け取らず、利用者にチャットへそのまま貼ってもらう。引数で渡すと Claude Code では
# 空白で切れ、claude.ai の入力欄では改行が失われることがある(改行は「//」コメントの終わりなど解釈に効く)
@mcp.prompt()
def import_tl_from_text() -> str:
    """TLの読み込み手順を会話に添える(TLはチャットにそのまま貼る)"""
    return (
        f"{INSTRUCTIONS}\n"
        "チャットに貼られたTLをexsimに読み込んでください。"
        "TLがまだ無ければ、改行を保ったままチャットに貼るよう頼んでください。"
    )


def _env_list(name: str) -> List[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


def transport_security(in_webui: bool = False) -> Optional[TransportSecuritySettings]:
    """HTTP時の Host/Origin ヘッダーの検査(DNSリバインディング対策)。

    指定が無ければ、単体起動では SDK の既定(localhost で待ち受ける時は localhost 宛てだけを受け付ける)に任せる。
    webuiに同居する場合は公開サイトの一部なので検査しない(SDKの既定のままだと、リバースプロキシ経由の
    公開ドメイン宛てが 421 になる。ツールはシミュレーションだけで、秘密も副作用も無い)。
    """
    hosts, origins = _env_list("EXSIM_MCP_ALLOWED_HOSTS"), _env_list("EXSIM_MCP_ALLOWED_ORIGINS")
    if hosts or origins:
        return TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *hosts],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", *origins],
        )
    if in_webui:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return None


# ツールは状態を持たないので、セッションを持たない形にする
# (リバースプロキシの後ろでも、サーバーの再起動をまたいでも、そのまま呼べる)
HTTP_OPTIONS = {"stateless_http": True, "json_response": True}


def webui_routes() -> list:
    """webui(FastAPI)に同居させるための /mcp のルート。

    VPSでは webui をそのまま動かせばリモートMCPも公開される(プロセスもプロキシの経路も増やさない)。
    リクエストを捌くには mcp.session_manager.run() を webui の lifespan で回しておくこと。
    """
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp", transport_security=transport_security(in_webui=True), **HTTP_OPTIONS
    )
    return list(app.routes)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="exsim の MCPサーバー")
    parser.add_argument("--http", action="store_true", help="stdio ではなく HTTP(Streamable HTTP)で待ち受ける")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/mcp")
    args = parser.parse_args(argv)

    if not args.http:
        mcp.run()
        return
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path=args.path,
        transport_security=transport_security(),
        **HTTP_OPTIONS,
    )


if __name__ == "__main__":
    main()
