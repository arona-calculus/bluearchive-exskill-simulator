from __future__ import annotations
from typing import Callable, Dict, List, Tuple, Any
from ba_exsim.core.state import State
from ba_exsim.core.algebra import get_cycle_permutation, apply_permutation

# 状態遷移関数の型定義: (現在の状態, 使用スロット) -> 次の状態
TransitionFunc = Callable[[State, int], State]


class CharacterSpec:
    """
    各キャラクターの代数的挙動を定義する基底クラス。
    ミレニアムの全生徒（および他校の生徒）はこのインターフェースを実装する。
    """

    def __init__(self, name: str):
        self.name = name

    def required_state(self) -> Dict[str, Any]:
        """このキャラが要求する初期内部状態（ゲージ等）"""
        return {}

    def on_active(self, state: State, k: int) -> State:
        """
        自分がEXスキルを使用した際の主作用。
        デフォルトは通常通りの巡回置換 π_k^(L)。
        """
        L = state.get_env("L", 6)
        p = get_cycle_permutation(k, L)
        return state.update(cards=apply_permutation(state.cards, p))

    def on_passive(self, state: State, active_char: str, k: int) -> State:
        """
        他人がEXスキルを使用した際の受動作用（フック）。
        """
        return state


class TimelineCompiler:
    """
    編成（Specs）を解析し、最適化された状態遷移関数をコンパイルする。
    """

    def __init__(self, specs: List[CharacterSpec]):
        # キャラ名からSpecへのマッピング
        self.specs: Dict[str, CharacterSpec] = {s.name: s for s in specs}

    def build_initial_state(self, initial_cards: Tuple[str, ...]) -> State:
        """全キャラの要求状態をマージして初期状態を生成する"""
        combined_env = {"L": 6}  # デフォルトのデッキ次元
        for spec in self.specs.values():
            combined_env.update(spec.required_state())
        return State(cards=initial_cards, env=combined_env)

    def compile(self) -> TransitionFunc:
        """
        高階関数を用いて、高速な遷移関数を生成する。
        """
        specs = self.specs

        def transition(state: State, k: int) -> State:
            # 1. 発動したスキルの持ち主を特定
            active_char_name = state.cards[k]
            active_spec = specs.get(active_char_name)

            if active_spec is None:
                raise ValueError(f"Character '{active_char_name}' not found in specs.")

            # 2. 主作用（Active Effect）の適用
            # 例: ハナコなら「手札に留まるか否か」の分岐がここで行われる
            new_state = active_spec.on_active(state, k)

            # 3. 全受動作用（Passive Effects）の合成
            # 例: 他人が撃つたびにハナコのゲージを増やす、コスト回復速度を変える等
            for name, spec in specs.items():
                if name != active_char_name:
                    new_state = spec.on_passive(new_state, active_char_name, k)

            return new_state

        return transition
