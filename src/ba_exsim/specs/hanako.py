from __future__ import annotations
from typing import Dict, Any
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec


class HanakoSwimsuitSpec(CharacterSpec):
    """
    水着ハナコの代数的仕様定義。
    水ゲージはハナコ本人の固有状態であり、コピーEX等からの代理実行では増減しない。
    """

    def __init__(self):
        super().__init__(name="Hanako")

    def required_state(self) -> Dict[str, Any]:
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

        if current_gauge >= 3:
            # ゲージ消費＆恒等写像（手札に留まる）
            new_gauge = current_gauge - 3
            return state.update(hanako_gauge=new_gauge)
        else:
            # ゲージ不足時は通常サイクル
            return super().on_active(state, k, target)

    def on_passive(
        self, state: State, active_char: str, k: int, target: str = ""
    ) -> State:
        """
        受動作用。他の「生徒」がスキルを使った時のみゲージが増加する。
        """
        # 自身のアクションの場合はスキップ
        if active_char == self.name:
            return state

        # 3. 仮想ユニット（AvantGarde等）の除外
        # コピーEXの発動は「味方のEX使用」としてカウントされない仕様の再現
        if active_char == "AvantGarde":
            return state

        # ハナコ本人以外の通常の生徒がEXを使用した場合のみゲージ加算
        current_gauge = state.get_env("hanako_gauge", 0)
        new_gauge = min(current_gauge + 2, 6)

        return state.update(hanako_gauge=new_gauge)
