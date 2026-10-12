from typing import Optional
from ba_exsim.core.display import CardDisplay, EnvDisplay, TargetInput
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State


class RioSpec(CharacterSpec):
    ENV_DISPLAYS = (
        EnvDisplay("rio_copy_target", "コピー先", kind="characters"),
    )
    # 使用すると手札の自分自身が Rio_Copy に変わる。アイコンはコピー先の生徒をグレースケールで表示する
    CARD_DISPLAYS = (
        CardDisplay("Rio_Copy", "リオ(コピー)", icon_env_key="rio_copy_target", grayscale=True),
    )

    def __init__(self, cost: Optional[int] = None):
        super().__init__("Rio", cost=cost)

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

    def target_input(self, state: State) -> TargetInput:
        return TargetInput(
            label="コピー先", required=True, error="リオのコピー先を選択してください"
        )


class RioCopySpec(CharacterSpec):
    def __init__(self):
        # コピーの使用はリオのEXとして扱う(ユズ(臨戦)のコスト半減など、リオに付いた効果が掛かる)
        super().__init__("Rio_Copy", is_proxy=True, owner="Rio")

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

    def get_cost(self, state: State) -> Optional[int]:
        # コピー先キャラの消費コスト - 1 (最低0)。
        # rio_copy_targetはapply_effectで自分自身がクリアするため、
        # 必ずプレイ前のstateで呼び出すこと。
        target_spec = self._get_target_spec(state)
        if not target_spec:
            return None
        target_cost = target_spec.get_cost(state)
        if target_cost is None:
            return None
        return max(0, target_cost - 1)
