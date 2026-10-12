from __future__ import annotations
from typing import Optional
from ba_exsim.core.display import EnvDisplay, TargetInput
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State

COST_DOWN_USES = 3


class YuzuBattleSpec(CharacterSpec):
    """
    ユズ(臨戦)

    EX「ゆ、ユズ、発進！」: 自身を除く味方1人のEXスキルコストを50%減少(EXスキルの使用3回分)。
    減少値は小数点以下切り捨て(コスト5なら減少2で3、コスト1なら減少0で1)。
    効果保有者のEX使用時の攻撃力バフは数値バフなので、このシミュレーターの対象外。

    - 効果は生徒ごとに持つ。別の生徒に使っても前の生徒の残り回数はそのまま残り、
      同じ生徒に使い直すと残り回数は3回に戻る(上書き)。
    - 効果を持つ生徒がEXを使うと、必ず半減され回数を1消費する。リオ(コピー)の使用は
      リオのEXとして扱い(owner)、「コピー元のコスト-1」を求めてから半減する。
    - 残り回数は env["yuzu_cost_down"] に {生徒: 残り回数} で持ち、0回になった生徒は消す。
    """

    ENV_DISPLAYS = (
        EnvDisplay("yuzu_cost_down", "コスト半減", kind="counts"),
    )

    def __init__(self, cost: Optional[int] = None):
        super().__init__("Yuzu_Battle", cost=cost)

    def _student(self, card: str) -> str:
        # カード名を、そのカードを使う生徒に直す(Rio_Copy → Rio)
        spec = self.registry.get(card) if self.registry else None
        return spec.owner if spec else card

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        if not target:
            raise ValueError("ユズ(臨戦)のEXには対象(自身以外の味方1人)が必要です")
        # 代理実行(リオ(コピー))なら、使っているのはリオ
        user = self._student(state.cards[k])
        student = self._student(target)
        if student == user:
            raise ValueError("ユズ(臨戦)のEXは自身を対象にできません")

        remaining = dict(state.get_env("yuzu_cost_down") or {})
        remaining[student] = COST_DOWN_USES
        return state.update(yuzu_cost_down=remaining)

    def on_passive(self, state: State, active_char: str, target: str = "") -> State:
        remaining = state.get_env("yuzu_cost_down") or {}
        student = self._student(active_char)
        if not remaining.get(student):
            return state

        # 効果を持つ生徒がEXを使った: 回数を1消費する(半減自体は使用前のコストに反映済み)
        remaining = dict(remaining)
        remaining[student] -= 1
        if remaining[student] <= 0:
            del remaining[student]
        return state.update(yuzu_cost_down=remaining or None)

    def modify_cost(self, state: State, student: str, cost: int) -> int:
        if (state.get_env("yuzu_cost_down") or {}).get(student):
            return cost - cost // 2
        return cost

    def target_input(self, state: State) -> TargetInput:
        return TargetInput(
            label="半減の対象", required=True, error="ユズのEXの対象を選択してください"
        )
