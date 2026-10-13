"""
ラフなTLをexsimに読み込むためのツール(生徒の照合・初期順の探索・TLの実行)と、その使い方の指示文。

チャットから使う MCPサーバー(mcp_server.py)と、webuiのTL取り込みページ(tl_agent.py)が同じものを使う。
MCP・Claude API のどちらにも依存しない。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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
   アリス(臨戦)の「チャージ」は自身対象(target=Alice_Battle)、敵(部位名など)を狙う使用は targetなし。
   「×2」のような回数の指定は、同じ手順を回数分並べる。
3. 初期の手札+山札順は「開始スキル」の行や名前に付いた番号で示されていることが多い。
   書かれていなければ find_initial_orders で候補を探す。
4. simulate_tl で実行し、返ってきた share_url をユーザーに渡す(開くとexsimに読み込まれる)。
   途中で破綻した場合は error に手札状況が入るので、TLの読み違いかTL自体の誤りかを判断して報告する。
   生徒の退場(「〇〇落ち」)はexsimで表現できないため、その手前までを実行し、残りは最後の手順の note に書く。
"""

DESCRIPTIONS = {
    "list_characters": """\
exsimに登録されている生徒の一覧を返す。

query を指定するとキー・表示名の部分一致で絞り込む(例: "イロハ" で通常/水着などの衣装違いが全て出る)。
custom_spec=True の生徒は固有のEX挙動(ゲージ・コピー等)が実装済み、False は常にサイクルするだけ。
needs_target=True の生徒は対象指定が必要。
""",
    "find_initial_orders": """\
手順列と矛盾しない初期の手札+山札順を総当りで探す(8枚まで)。

手札内の並びはサイクルに影響しないので、手札部分の並べ替えは同一視して数える。
完走する順が無い場合は best_partial に最も先まで進めた順と、止まった地点の手札を返す。
""",
    "simulate_tl": """\
TLを実行し、各ステップの手札・ゲージ・コストと、exsimで開ける共有リンクを返す。

characters は初期の手札+山札の順(先頭 hand_size 枚が手札)。
途中で破綻した場合もそこまでの履歴で share_url を返す(exsim上で続きを手動で確認できる)。
env は初期のゲージ等(例: {"hanako_gauge": 100})を与える場合のみ。
""",
}

DEFAULT_TITLE = "MCPで取り込んだTL"


class StepInput(BaseModel):
    card: str = Field(
        "", description="使用する生徒のキー(例: Hanako_Swimsuit)または表示名(例: ハナコ(水着))"
    )
    target: str = Field(
        "",
        description=(
            "対象。リオのコピー先、アリス(臨戦)のチャージ(自身=Alice_Battle。敵対象なら空)、"
            "イブキ(水着)のお友達(カンマ区切り最大2人)など"
        ),
    )
    slot: Optional[int] = Field(
        None, description="手札スロット(0始まり)を明示する場合のみ。通常は card で指定する"
    )
    note: str = Field("", description="時刻・AUTO/ASAP・メモなど。exsimのコメント欄に入る")


def _to_steps(steps: List[StepInput]) -> List[Step]:
    return [Step(card=s.card, target=s.target, slot=s.slot, note=s.note) for s in steps]


def list_characters(query: str = "", limit: Optional[int] = None) -> Any:
    found = tl_import.list_characters(query)
    if limit is not None and len(found) > limit:
        return {
            "total": len(found),
            "characters": found[:limit],
            "note": f"{len(found)}件中{limit}件のみ。query で絞り込むこと",
        }
    return found


def find_initial_orders(
    characters: List[str], steps: List[StepInput], hand_size: int = 3, max_results: int = 10
) -> Dict[str, Any]:
    try:
        chars, resolved = tl_import.normalize_inputs(characters, _to_steps(steps), hand_size)
        return tl_import.find_initial_orders(chars, resolved, hand_size, max_results=max_results)
    except TLError as e:
        return {"error": str(e)}


def simulate_tl(
    characters: List[str],
    steps: List[StepInput],
    hand_size: int = 3,
    title: str = DEFAULT_TITLE,
    env: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """(ツールの結果, webuiのセーブデータ) を返す。入力が不正で実行できなかった場合のセーブデータは None。

    共有リンク(share_url)は呼び出し側で付ける(webuiのページでは、リンクをClaudeに返す必要がない)。
    """
    try:
        chars, resolved = tl_import.normalize_inputs(characters, _to_steps(steps), hand_size)
    except TLError as e:
        return {"ok": False, "error": {"reason": str(e)}}, None

    result = tl_import.run_tl(chars, resolved, hand_size, env)
    out = {
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
    }
    return out, tl_import.build_save(result, title)
