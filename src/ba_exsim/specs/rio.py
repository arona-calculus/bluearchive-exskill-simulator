from __future__ import annotations
from typing import Dict, Any
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec
from ba_exsim.core.algebra import get_cycle_permutation, apply_permutation


class RioSpec(CharacterSpec):
    """
    リオの代数的仕様定義。

    主な特性:
    1. 状態空間の次元 'L' (6 or 7) を操作する。
    2. EXスキルを使用すると、通常の置換の後に L を 7 に設定する。
    3. これにより、スロット7にいたトークンが次回の山札ローテーションに組み込まれる。
    """

    def __init__(self):
        super().__init__(name="Rio")

    def required_state(self) -> Dict[str, Any]:
        """初期状態ではデッキ次元 L=6（トークンは不活性）から開始"""
        return {"L": 6}

    def on_active(self, state: State, k: int) -> State:
        """
        リオのEXスキル発動（主作用）。
        カードを回した直後、デッキの有効境界 L を 7 へ拡張する。
        """
        L_current = state.get_env("L", 6)

        # 1. 現在の次元 L で巡回置換を適用（自身は山札の最後尾へ）
        p = get_cycle_permutation(k, L_current)
        new_cards = apply_permutation(state.cards, p)

        # 2. 次元 L を 7 に書き換える（拡張）
        # これにより、次に誰かがスキルを撃つとき p = get_cycle_permutation(k, 7) となる
        return state.update(cards=new_cards, L=7)


class AvantGardeSpec(CharacterSpec):
    """
    リオによって召喚されるトークン（アバンギャルド君）の仕様定義。

    主な特性:
    1. 使用されると、自身の置換（π_k^7）の後に L を 6 に戻す。
    2. これにより、自身はスロット7（不活性領域）へ追いやられ、実質的に除外される。
    """

    def __init__(self):
        super().__init__(name="AvantGarde")

    def on_active(self, state: State, k: int) -> State:
        """
        トークンの使用（主作用）。
        自身を最後尾へ送った後、デッキ次元を縮小して自身を隔離する。
        """
        # トークンが存在する＝次元は 7 であるはず
        # 1. 強制的に長さ7の置換を行い、自身を index 6 (スロット7) へ送る
        p = get_cycle_permutation(k, 7)
        new_cards = apply_permutation(state.cards, p)

        # 2. 次元 L を 6 に戻す（縮小）
        # index 6 は不活性領域となり、通常のスキル回しから「見えなく」なる
        return state.update(cards=new_cards, L=6)
