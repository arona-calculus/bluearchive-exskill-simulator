from __future__ import annotations
from typing import Optional, Tuple
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State


class HanakoSwimsuitSpec(CharacterSpec):
    def __init__(self):
        super().__init__("Hanako_Swimsuit")

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        # 代理実行時（スロットkが自分でない）はRio_Copy側のshould_cycleに委ねる
        if state.cards[k] != self.name:
            return True

        return state.get_env("hanako_gauge", 0) < 100

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        gauge = state.get_env("hanako_gauge", 0)

        if state.cards[k] == self.name:
            # 直接使用: ゲージが十分なら消費して手札に留まる（should_cycleが保証）
            if gauge < 100:
                return state
            return state.update(hanako_gauge=gauge - 100)

        else:
            # 代理実行（Rio_Copy等）: 自身が手札にいない かつ ゲージ十分なら即ドロー要請
            hanako_in_hand = self.name in state.cards[:3]
            if hanako_in_hand or gauge < 100:
                return state
            return state.update(
                hanako_gauge=gauge - 100,
                pending_force_draw=self.name,
            )

    def on_draw_intercept(
        self, state: State, trigger: str
    ) -> Tuple[Optional[str], State]:
        pending_draw = state.get_env("pending_force_draw")
        if pending_draw == self.name:
            return self.name, state.update(pending_force_draw=None)
        return None, state

    def on_passive(self, state: State, active_char: str, target: str = "") -> State:
        if active_char == self.name:
            return state

        if self.registry:
            active_spec = self.registry.get(active_char)
            if active_spec and active_spec.is_proxy:
                return state

        gauge = state.get_env("hanako_gauge", 0)
        return state.update(hanako_gauge=min(gauge + 40, 200))
