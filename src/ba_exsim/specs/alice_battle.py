from __future__ import annotations
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State


class AliceBattleSpec(CharacterSpec):
    def __init__(self):
        super().__init__(name="Alice_Battle")

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
