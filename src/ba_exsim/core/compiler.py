from __future__ import annotations
from typing import Callable, Dict, List, Tuple, Any
from ba_exsim.core.state import State

# 状態遷移関数の型定義: (現在の状態, 使用スロット) -> 次の状態
TransitionFunc = Callable[[State, int], State]


class CharacterSpec:
    """
    各キャラクターの代数的挙動を定義する基底クラス。
    """
    def __init__(self, name: str, is_proxy: bool = False):
        self.name = name
        self.is_proxy = is_proxy  # トークンや代理実行カードであるかを示す属性
        self.registry: Dict[str, CharacterSpec] = {}

    def bind_registry(self, registry: Dict[str, CharacterSpec]) -> None:
        """
        コンパイラから全Specの辞書を受け取り、紐付ける。
        コピーEX(AvantGarde)が他キャラのSpecを代理実行するために使用する。
        """
        self.registry = registry

    def required_state(self) -> Dict[str, Any]:
        """このキャラが要求する初期内部状態（ゲージ等）"""
        return {}

    def get_proxy_target(self, state: State) -> str | None:
        """
        このキャラクターがプロキシ（代理実行）である場合、現在誰の代理をしているかを返す。
        """
        return None

    def on_active(self, state: State, k: int, target: str = "") -> State:
        """
        自分がEXスキルを使用した際の主作用。
        引数に target を追加し、対象指定による状態遷移の分岐を可能にした。
        """
        cards = list(state.cards)
        L = state.get_env("L", len(cards))

        if L <= 3:
            return state

        used_card = cards[k]
        drawn_card = cards[3]
        deck_cards = cards[4:L]

        new_cards = cards[:3]
        new_cards[k] = drawn_card

        new_cards.extend(deck_cards)
        new_cards.append(used_card)

        if len(cards) > L:
            new_cards.extend(cards[L:])

        return state.update(cards=tuple(new_cards))

    def on_passive(
        self, state: State, active_char: str, k: int, target: str = ""
    ) -> State:
        """
        他人がEXスキルを使用した際の受動作用（フック）。
        他人のターゲット情報（誰を回復したか等）によって誘発するギミックに備え target を追加。
        """
        return state


class TimelineCompiler:
    """
    編成（Specs）を解析し、最適化された状態遷移関数をコンパイルする。
    """

    def __init__(self, specs: List[CharacterSpec]):
        self.specs: Dict[str, CharacterSpec] = {s.name: s for s in specs}

        for spec in self.specs.values():
            spec.bind_registry(self.specs)

    def build_initial_state(self, initial_cards: Tuple[str, ...]) -> State:
        """全キャラの要求状態をマージして初期状態を生成する"""
        combined_env = {"L": 6}
        for spec in self.specs.values():
            combined_env.update(spec.required_state())
        return State(cards=initial_cards, env=combined_env)

    def compile(self) -> TransitionFunc:
        """
        高階関数を用いて、高速な遷移関数を生成する。
        """
        specs = self.specs

        def transition(state: State, k: int, target: str = "") -> State:
            active_char_name = state.cards[k]
            active_spec = specs.get(active_char_name)

            if active_spec is None:
                raise ValueError(f"Character '{active_char_name}' not found in specs.")

            # 2. 主作用（Active Effect）の適用（targetを伝播）
            new_state = active_spec.on_active(state, k, target)

            # 3. 全受動作用（Passive Effects）の合成（targetを伝播）
            for name, spec in specs.items():
                if name != active_char_name:
                    new_state = spec.on_passive(new_state, active_char_name, k, target)

            return new_state

        return transition
