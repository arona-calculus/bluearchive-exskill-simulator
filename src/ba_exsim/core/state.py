from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Dict, Any, Tuple, Optional


@dataclass(frozen=True)
class State:
    """
    盤面の状態を保持するイミュータブルなデータクラス。
    frozen=True により、インスタンス化後のプロパティ変更を禁止する。
    """

    cards: Tuple[Optional[str], ...]
    env: Dict[str, Any] = field(default_factory=dict)

    def get_env(self, key: str, default: Any = None) -> Any:
        return self.env.get(key, default)

    def update(self, cards: Tuple[Optional[str], ...] = None, **kwargs) -> State:
        """
        cardsとenvを同時に、または個別に更新し、新しいStateを返すヘルパー。
        例: state.update(cards=new_cards, hanako_gauge=100)
        """

        new_state = self
        if cards is not None:
            new_state = replace(new_state, cards=cards)

        if kwargs:
            new_env = new_state.env.copy()
            new_env.update(kwargs)
            new_state = replace(new_state, env=new_env)

        return new_state

    def discard_card(self, k: int, transform_to: Optional[str] = None) -> State:
        """フェーズ1: カードを消費し、一時的な空き(None)を作る"""
        cards_list = list(self.cards)
        discarded = cards_list.pop(k)

        cards_list.insert(k, None)  # Holeを作成
        cards_list.append(transform_to if transform_to else discarded)

        return replace(self, cards=tuple(cards_list))

    def draw_card(self, k: int, force_card: Optional[str] = None) -> State:
        """フェーズ2: 空き(None)を山札から補充する"""
        cards_list = list(self.cards)

        if force_card and force_card in cards_list:
            cards_list.remove(force_card)
            cards_list[k] = force_card
        else:
            top_card = cards_list.pop(3)
            cards_list[k] = top_card

        return replace(self, cards=tuple(cards_list))
