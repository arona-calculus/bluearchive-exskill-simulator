from __future__ import annotations
from ba_exsim.core.compiler import CharacterSpec


class GenericSpec(CharacterSpec):
    """
    特殊な状態遷移ギミックを持たない、通常の生徒のための汎用仕様クラス。
    デフォルトのEXスキル発動（最後尾への移動、1枚ドローの巡回置換）のみを行う。
    """

    def __init__(self, name: str):
        super().__init__(name=name)
