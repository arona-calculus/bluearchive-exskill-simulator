from __future__ import annotations
from typing import Dict, Any
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec


class HanakoSwimsuitSpec(CharacterSpec):
    """
    水ゲージはハナコ本人の固有状態であり、コピーEX等からの代理実行では増減しない。
    """

    def __init__(self):
        super().__init__(name="Hanako")

    def required_state(self) -> Dict[str, Any]:
        # ゲージは整数で管理。100 = 1ゲージ分
        return {"hanako_gauge": 0}

    def on_active(self, state: State, k: int, target: str = "") -> State:
        """
        主作用。自身の実体が発動した時のみゲージを参照・消費する。
        """
        # 1. 代理実行（Delegate）の検知
        # 実際にスロットkにいるカード名が自分自身("Hanako")ではない場合、
        # これはAvantGarde等による代理実行であると判断できる。
        if state.cards[k] != self.name:
            # ゲージには一切干渉せず、通常のスキルとしてサイクルさせる
            return super().on_active(state, k, target)

        # 2. ハナコ本人による発動
        current_gauge = state.get_env("hanako_gauge", 0)

        # ゲージコストは1ゲージ分 (内部値100)
        if current_gauge >= 100:
            # ゲージ消費＆恒等写像（手札に留まる）
            new_gauge = current_gauge - 100
            return state.update(hanako_gauge=new_gauge)
        else:
            # ゲージ不足時は通常サイクル
            return super().on_active(state, k, target)

    def on_passive(self, state: State, active_char: str, k: int, target: str = "") -> State:
        """
        受動作用。自身以外のキャラクターがEXスキルを使った時にゲージが増加する。
        （コピーEXなどの仮想カードによる発動もゲージ増加のトリガーとして扱う）
        """
        if active_char == self.name:
            return state

        current_gauge = state.get_env("hanako_gauge", 0)

        # 40%チャージ (内部値+40), 最大値は2ゲージ相当 (内部値200)
        new_gauge = min(current_gauge + 40, 200)

        return state.update(hanako_gauge=new_gauge)
