from __future__ import annotations
from typing import Optional, Tuple

from .display import CardDisplay, EnvDisplay, TargetInput
from .state import State


class CharacterSpec:
    """
    スキル実行のパイプラインに対するフックを提供する基底クラス。
    子クラス（各キャラ）は必要なフックだけをオーバーライド（上書き）して実装する。

    ENV_DISPLAYS / CARD_DISPLAYS / target_input は webui 向けの表示・入力形式の宣言で、
    シミュレーションの挙動には影響しない（display.py 参照）。
    """

    # このSpecが書き込む env キーの表示方法
    ENV_DISPLAYS: Tuple[EnvDisplay, ...] = ()
    # このSpecが生み出す、BUILTINSに無いカード（リオ(コピー)等）の表示方法
    CARD_DISPLAYS: Tuple[CardDisplay, ...] = ()

    def __init__(
        self,
        name: str,
        is_proxy: bool = False,
        cost: Optional[int] = None,
        owner: Optional[str] = None,
    ):
        self.name = name
        self.is_proxy = is_proxy
        self.cost = cost  # このカードの基本消費コスト(lv5時点、不明ならNone)
        # このカードを使う生徒。通常は自分自身だが、リオ(コピー)はリオのEXとして扱う
        # (生徒に付く効果、例えばユズ(臨戦)のコスト半減の判定に使う)
        self.owner = owner or name

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

    def modify_cost(self, state: State, student: str, cost: int) -> int:
        """
        生徒 student のEXの消費コスト cost を、このSpecの効果で変化させる（ユズ(臨戦)の
        コスト半減など、他の生徒のコストに掛かる効果用）。student はカードの owner。
        各カードの get_cost の後に、Registry が全Specに順に問い合わせる。
        """
        return cost

    def target_input(self, state: State) -> TargetInput:
        """
        このカードを「今」使う場合の対象指定の形式を返す（形態によって変わる
        イブキ(水着)等はオーバーライドする）。既定は任意の1人選択。
        """
        return TargetInput()
