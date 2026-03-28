from typing import List, Tuple
from .state import State
from .spec import CharacterSpec
from .registry import SpecRegistry
from .engine import GameEngine


class Simulator:
    """
    ユーザーやテストスクリプトが直接操作するための高レベルAPI (Facade)。
    内部の面倒な配線（RegistryやEngineの構築）を隠蔽する。
    """

    def __init__(self, specs: List[CharacterSpec]):
        self.registry = SpecRegistry(specs)
        self.engine = GameEngine(self.registry)
        self.state = None

    def initialize_state(
        self, initial_cards: Tuple[str, ...], env: dict = None
    ) -> State:
        """初期盤面をセットアップする"""
        self.state = State(cards=initial_cards, env=env or {})
        return self.state

    def play(self, k: int, target: str = "") -> State:
        """スロットkのカードを使用し、内部状態を更新する"""
        if self.state is None:
            raise ValueError(
                "状態が初期化されていません。先に initialize_state を呼んでください。"
            )

        self.state = self.engine.play_card(self.state, k, target)
        return self.state

    def play_by_name(self, char_name: str, target: str = "") -> State:
        """(テスト用便利関数) 手札の中から名前で探して使用する"""
        hand = self.state.cards[:3]
        if char_name not in hand:
            raise ValueError(f"{char_name} は手札 {hand} にありません！")

        k = hand.index(char_name)
        return self.play(k, target)
