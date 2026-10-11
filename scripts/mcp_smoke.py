"""
MCPサーバーを stdio で実際に起動し、tests/data/tl/*.toml の実戦TLを simulate_tl に流して
期待値と照合する動作確認スクリプト。各ケースの share_url も表示する(開くとwebuiに読み込まれる)。

pytestの対象ではない(サーバーを子プロセスで起動するため)。実行方法:
  uv run --extra mcp python scripts/mcp_smoke.py            # 全ケース
  uv run --extra mcp python scripts/mcp_smoke.py d37_shirokuro_chuka
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from scenario import TL_DIR, check_tl_result, load, step_inputs  # noqa: E402


async def main(names: list[str]) -> int:
    paths = [p for p in sorted(TL_DIR.glob("*.toml")) if not names or p.stem in names]
    if not paths:
        print(f"ケースが見つかりません: {names or TL_DIR}")
        return 1

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "webui.backend.mcp_server"], cwd=str(ROOT)
    )
    failed = 0
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        print(f"tools: {tools}")

        for path in paths:
            scenario = load(path)
            args = {
                "characters": scenario.cards,
                "steps": step_inputs(scenario),
                "hand_size": scenario.hand_size,
                "title": scenario.title,
            }
            if scenario.env:
                args["env"] = scenario.env
            res = await session.call_tool("simulate_tl", args)
            out = json.loads(res.content[0].text)

            steps = [
                {"cost": s["cost"], "hand": s["hand_after"], "deck": s["deck_after"], "env": s["env_after"]}
                for s in out.get("steps", [])
            ]
            try:
                check_tl_result(scenario, out["ok"], out["error"], steps, out["final_state"])
                status = "OK"
            except (AssertionError, KeyError) as e:
                status = f"NG: {e}"
                failed += 1
            verified = "" if scenario.verified is not False else " (解釈は未確認)"
            print(f"[{status}] {scenario.id}{verified}")
            if out.get("share_url"):
                print(f"  share_url: {out['share_url']}")

    return failed


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main(sys.argv[1:])) else 0)
