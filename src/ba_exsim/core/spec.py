from __future__ import annotations
from typing import Optional, Tuple

from .state import State


class CharacterSpec:
    """
    スキル実行のパイプラインに対するフックを提供する基底クラス。
    子クラス（各キャラ）は必要なフックだけをオーバーライド（上書き）して実装する。
    """

    def __init__(self, name: str, is_proxy: bool = False, cost: Optional[int] = None):
        self.name = name
        self.is_proxy = is_proxy
        self.cost = cost  # このカードの基本消費コスト(lv5時点、不明ならNone)

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        """
        [フェーズ0] サイクルを行うか？
        Falseの場合、破棄とドローを行わず手札に留まる。
        """
        return True

    def get_in_hand_transform(self, state: State) -> Optional[str]:
        """
        [フェーズ1] 手札にいる状態で変身するか？（T.S.キャラ用）
        戻り値: 変身後のカード名。変身しない場合は None
        """
        return None

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        """
        [フェーズ2] 効果の適用（ゲージの増減、バフ・デバフなど）
        戻り値: 更新されたState
        """
        return state

    def get_discard_transform(self, state: State) -> Optional[str]:
        """
        [フェーズ3] 山札の底に捨てられる時に変身するか？（リオ、アバンギャルド用）
        戻り値: 捨てられる際のカード名。変身しない場合は None
        """
        return None

    def on_draw_intercept(
        self, state: State, trigger: str
    ) -> Tuple[Optional[str], State]:
        """
        [フェーズ4] ドローに割り込むか？（ハナコの即ドロー用）
        戻り値: (割り込んで引くカード名, 更新されたState)。割り込まない場合は (None, state)
        """
        return None, state

    def on_passive(self, state: State, active_char: str, target: str = "") -> State:
        """
        [フェーズ5] 他キャラのEX使用時に誘発するパッシブ（ハナコの水ゲージ増加など）
        戻り値: 更新されたState
        """
        return state

    def get_cost(self, state: State) -> Optional[int]:
        """
        このカードを「今」使った場合の消費コストを返す（コピー元に応じて変わる
        リオ(コピー)や、形態によって変わるイブキ(水着)のEX2等はオーバーライドする）。
        不明な場合は None。
        """
        return self.cost
