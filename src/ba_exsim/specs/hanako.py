from __future__ import annotations
from typing import Dict, Any
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec
from ba_exsim.core.algebra import get_cycle_permutation, apply_permutation


class HanakoSwimsuitSpec(CharacterSpec):
    """
    水着ハナコの代数的仕様定義。

    主な特性:
    1. 内部状態 'hanako_gauge' (0-6) を要求する。
    2. 他人がEXを使うとゲージが +2 (2/3相当) される。
    3. 自身がEXを使う際、ゲージが3以上あれば消費して「恒等写像」として振る舞う。
    4. ゲージが3未満なら「通常の巡回置換」として振る舞う。
    """

    def __init__(self):
        super().__init__(name="Hanako")

    def required_state(self) -> Dict[str, Any]:
        """ハナコ専用の次元を状態空間に追加"""
        return {"hanako_gauge": 0}

    def on_active(self, state: State, k: int) -> State:
        """
        ハナコ自身のEXスキル発動（主作用）。
        ゲージ量によって、カードの置換が発生するかどうかが分岐する。
        """
        current_gauge = state.get_env("hanako_gauge", 0)

        if current_gauge >= 3:
            # 【ケース1】ゲージを消費して手札に留まる
            # 数学的にはカード順列に対する「恒等写像 (e)」
            new_gauge = current_gauge - 3
            return state.update(hanako_gauge=new_gauge)
        else:
            # 【ケース2】ゲージが足りず、通常通り山札へ回る
            # 数学的には「巡回置換 (π_k^L)」
            L = state.get_env("L", 6)
            p = get_cycle_permutation(k, L)
            new_cards = apply_permutation(state.cards, p)
            return state.update(cards=new_cards)

    def on_passive(self, state: State, active_char: str, k: int) -> State:
        """
        他者がEXスキルを発動した際の挙動（受動作用）。
        ハナコのゲージを増加させる。
        """
        # 他人のスキル発動1回につき、ゲージを2（2/3相当）増加させる（最大6）
        current_gauge = state.get_env("hanako_gauge", 0)
        new_gauge = min(current_gauge + 2, 6)

        return state.update(hanako_gauge=new_gauge)
