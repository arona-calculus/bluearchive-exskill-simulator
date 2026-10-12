from __future__ import annotations
from typing import Optional
from ba_exsim.core.display import EnvDisplay, TargetInput
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State


class AliceBattleSpec(CharacterSpec):
    ENV_DISPLAYS = (
        EnvDisplay("alice_charge", "チャージ", kind="gauge", max=2, color="#f87f7f"),
    )

    def __init__(self, cost: Optional[int] = None):
        super().__init__(name="Alice_Battle", cost=cost)

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        return target != self.name

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        current_charge = state.get_env("alice_charge", 0)
        if target == self.name:
            # 自身対象：チャージ獲得（上限2）
            return state.update(alice_charge=min(current_charge + 1, 2))
        else:
            # それ以外：チャージ消費（リセット）
            return state.update(alice_charge=0)

    def target_input(self, state: State) -> TargetInput:
        # 自身対象でチャージ、それ以外(未選択 = 敵対象)でチャージ消費
        return TargetInput(include_self=True)
