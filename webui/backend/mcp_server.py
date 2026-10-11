"""
BA EX Skill Simulator - MCPサーバー

ラフに書かれたTLをLLM(Claude等)が解釈し、このサーバーのツールで厳密に実行・検証した上で、
webuiの共有リンク(#share=)としてexsimに読み込ませるためのもの。
状態は持たない(webuiの起動も不要。リンクを開く時だけwebuiが動いていればよい)。

起動方法(stdio):
  cd bluearchive-exskill-simulator
  uv run --extra mcp python -m webui.backend.mcp_server

共有リンクの宛先は環境変数 EXSIM_BASE_URL で変更できる(既定: http://localhost:8000/)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from webui.backend import tl_import
from webui.backend.tl_import import Step, TLError

INSTRUCTIONS = """\
ブルーアーカイブのEXスキル手札サイクル(exsim)のシミュレータ。ラフなTLをexsimに読み込むときの手順:
1. TLに登場する生徒を list_characters で正規のキーに対応付ける
   (「Cイロハ」「水着ハナコ」のような略記は query に素の名前を入れて候補から選ぶ)。
2. TLを「誰のEXを・誰を対象に使うか」の手順列に直す。時刻・AUTO/ASAP・コメント等は note に残す。
   EX使用でない行(デバフ付与タイミングのメモ等)は直前の手順の note にまとめる。
   リオは「リオ → X」がコピー(target=X)、その後の単なる「リオ」はコピーの使用(targetなし)。
3. 初期の手札+山札順が書かれていなければ find_initial_orders で候補を探す。
4. simulate_tl で実行し、返ってきた share_url をユーザーに渡す(開くとexsimに読み込まれる)。
   途中で破綻した場合は error に手札状況が入るので、TLの読み違いかTL自体の誤りかを判断して報告する。
"""

mcp = MCPServer("ba-exsim", instructions=INSTRUCTIONS)


class StepInput(BaseModel):
    card: str = Field(
        "", description="使用する生徒のキー(例: Hanako_Swimsuit)または表示名(例: ハナコ(水着))"
    )
    target: str = Field(
        "",
        description="対象。リオのコピー先、アリス(臨戦)の対象、イブキ(水着)のお友達(カンマ区切り最大2人)など",
    )
    slot: Optional[int] = Field(
        None, description="手札スロット(0始まり)を明示する場合のみ。通常は card で指定する"
    )
    note: str = Field("", description="時刻・AUTO/ASAP・メモなど。exsimのコメント欄に入る")


def _to_steps(steps: List[StepInput]) -> List[Step]:
    return [Step(card=s.card, target=s.target, slot=s.slot, note=s.note) for s in steps]


@mcp.tool()
def list_characters(query: str = "") -> List[Dict[str, Any]]:
    """exsimに登録されている生徒の一覧を返す。

    query を指定するとキー・表示名の部分一致で絞り込む(例: "イロハ" で通常/水着などの衣装違いが全て出る)。
    custom_spec=True の生徒は固有のEX挙動(ゲージ・コピー等)が実装済み、False は常にサイクルするだけ。
    needs_target=True の生徒は対象指定が必要。
    """
    return tl_import.list_characters(query)


@mcp.tool()
def find_initial_orders(
    characters: List[str],
    steps: List[StepInput],
    hand_size: int = 3,
    max_results: int = 10,
) -> Dict[str, Any]:
    """手順列と矛盾しない初期の手札+山札順を総当りで探す(8枚まで)。

    手札内の並びはサイクルに影響しないので、手札部分の並べ替えは同一視して数える。
    完走する順が無い場合は best_partial に最も先まで進めた順と、止まった地点の手札を返す。
    """
    try:
        chars, resolved = tl_import.normalize_inputs(characters, _to_steps(steps), hand_size)
        return tl_import.find_initial_orders(chars, resolved, hand_size, max_results=max_results)
    except TLError as e:
        return {"error": str(e)}


@mcp.tool()
def simulate_tl(
    characters: List[str],
    steps: List[StepInput],
    hand_size: int = 3,
    title: str = "MCPで取り込んだTL",
    env: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """TLを実行し、各ステップの手札・ゲージ・コストと、exsimで開ける共有リンクを返す。

    characters は初期の手札+山札の順(先頭 hand_size 枚が手札)。
    途中で破綻した場合もそこまでの履歴で share_url を返す(exsim上で続きを手動で確認できる)。
    env は初期のゲージ等(例: {"hanako_gauge": 100})を与える場合のみ。
    """
    try:
        chars, resolved = tl_import.normalize_inputs(characters, _to_steps(steps), hand_size)
    except TLError as e:
        return {"ok": False, "error": {"reason": str(e)}}

    result = tl_import.run_tl(chars, resolved, hand_size, env)
    save = tl_import.build_save(result, title)
    return {
        "ok": result.ok,
        "error": result.error,
        "steps": [
            {
                "step": h["step"],
                "card": h["card"],
                "target": h["target"],
                "cost": h["cost"],
                "cumulative_cost": h["cumulative_cost"],
                "hand_after": h["state_after"]["hand"],
                "deck_after": h["state_after"]["deck"],
                "env_after": h["state_after"]["env"],
            }
            for h in result.history
        ],
        "final_state": result.current_state,
        "share_url": tl_import.share_url(save),
    }


@mcp.prompt()
def import_rough_tl(tl_text: str) -> str:
    """ラフに書いたTLをexsimに読み込む"""
    return f"{INSTRUCTIONS}\n以下のTLをexsimに読み込んでください。\n\n```\n{tl_text}\n```"


if __name__ == "__main__":
    mcp.run()
