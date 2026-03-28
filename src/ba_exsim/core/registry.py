from typing import List, Optional, Tuple

from .state import State
from .spec import CharacterSpec


class SpecRegistry:
    def __init__(self, specs: List[CharacterSpec]):
        self.specs = {spec.name: spec for spec in specs}

        # 初期化時に、各SpecにRegistry自身への参照を渡す（依存性の注入）
        for spec in self.specs.values():
            spec.registry = self

    def get(self, name: str) -> Optional[CharacterSpec]:
        """名前からSpecを取得するヘルパー"""
        return self.specs.get(name)

    def evaluate_draw_intercepts(
        self, state: State, trigger: str
    ) -> Tuple[Optional[str], State]:
        """全キャラに「ドローに割り込むか？」を尋ねる（置換効果）"""
        for spec in self.specs.values():
            intercept_card, new_state = spec.on_draw_intercept(state, trigger)
            if intercept_card:
                return intercept_card, new_state
        return None, state

    def apply_passives(self, state: State, active_char: str, target: str = "") -> State:
        for spec in self.specs.values():
            state = spec.on_passive(state, active_char, target)
        return state
