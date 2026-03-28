from typing import Optional, Tuple
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State


class RioSpec(CharacterSpec):
    def __init__(self):
        super().__init__("Rio")

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        # 手札の中でトークンに変化するため、破棄・ドローを行わない
        return False

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        # 手札の自分自身（スロットk）を Rio_Copy に直接書き換える
        cards = list(state.cards)
        cards[k] = "Rio_Copy"

        # ターゲット情報を環境変数に保存しつつ、カード配列を更新
        return state.update(
            cards=tuple(cards), rio_copy_target=target if target else None
        )


class RioCopySpec(CharacterSpec):
    def __init__(self):
        super().__init__("Rio_Copy", is_proxy=True)

    def _get_target_spec(self, state: State) -> Optional[CharacterSpec]:
        # 環境変数に記録されたターゲット名から、Registry経由で動的にSpecを取得する。

        target_name = state.get_env("rio_copy_target")
        if target_name and self.registry:
            return self.registry.get(target_name)
        return None

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        # コピーが使用された時は、通常通り破棄・ドローのサイクルを行う
        return True

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        target_spec = self._get_target_spec(state)

        if target_spec:
            # コピー先のキャラの効果を実行する
            state = target_spec.apply_effect(state, k, target)

        if self.should_cycle(state, k, target):
            state = state.update(rio_copy_target=None)

        return state

    def get_discard_transform(self, state: State) -> Optional[str]:
        return "Rio"
