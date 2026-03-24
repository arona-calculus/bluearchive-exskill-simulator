from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Mapping


@dataclass(frozen=True)
class State:
    """
    ブルーアーカイブのEXスキル回しにおける代数的状態空間 X を表現するクラス。
    X = S_n (カード順列) × Env (拡張された内部状態の直積)
    """

    # カードの並び（置換群の元を表現するタプル）
    # index 0,1,2: 手札 / 3...L-1: 山札 / L...: 不活性領域
    cards: Tuple[str, ...]

    # 各キャラクターの特殊ギミックが要求する内部状態の辞書（ゲージ、次元Lなど）
    # 不変性を保つため、Mapping(読み取り専用辞書)として保持
    env: Mapping[str, Any] = field(default_factory=dict)

    def update(self, cards: Tuple[str, ...] | None = None, **env_updates: Any) -> State:
        """
        現在の状態に作用を適用し、新しい状態（点）を返す遷移関数。
        数学的には s' = s・g を計算する。
        """
        new_cards = cards if cards is not None else self.cards

        # 新しい環境状態の構築
        new_env_dict = dict(self.env)
        new_env_dict.update(env_updates)

        return State(cards=new_cards, env=new_env_dict)

    def get_hand(self) -> Tuple[str, ...]:
        """現在の手札（スロット 1, 2, 3）を取得"""
        return self.cards[:3]

    def get_env(self, key: str, default: Any = None) -> Any:
        """環境状態から特定の次元の値を取得"""
        return self.env.get(key, default)

    def __repr__(self) -> str:
        hand = " / ".join(self.get_hand())
        return f"State(Hand=[{hand}], Env={dict(self.env)})"
