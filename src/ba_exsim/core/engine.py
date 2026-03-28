from .state import State
from .registry import SpecRegistry


class GameEngine:
    """スキル実行のパイプライン（順序）を統括するシステム"""

    def __init__(self, registry: SpecRegistry):
        self.registry = registry

    def play_card(self, state: State, k: int, target: str = "") -> State:
        char_name = state.cards[k]
        spec = self.registry.specs[char_name]

        # 1. サイクル判定フェーズ（apply_effect前のstateで評価する）
        # should_cycleは「使用時点でサイクルするか」という意思決定であり、
        # 効果適用後の状態に依存すべきではない。
        do_cycle = spec.should_cycle(state, k, target)

        # 2. 効果適用フェーズ（ここでリオは手札の自分自身を書き換える）
        state = spec.apply_effect(state, k, target)

        # 3. サイクルフェーズ（do_cycle が True の場合のみ破棄とドローを行う）
        if do_cycle:
            # 破棄
            discard_transform = spec.get_discard_transform(state)
            state = state.discard_card(k, transform_to=discard_transform)

            # 置換ドロー判定（ハナコ等の割り込み）
            intercept_card, state = self.registry.evaluate_draw_intercepts(
                state, trigger=char_name
            )

            # ドロー
            state = state.draw_card(k, force_card=intercept_card)

        # 4. パッシブフェーズ
        state = self.registry.apply_passives(
            state, active_char=char_name, target=target
        )

        return state