from __future__ import annotations
from typing import Dict, Any
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec


class AliceBattleSpec(CharacterSpec):
    """
    アリス（臨戦）の代数的仕様定義。

    主な特性:
    1. 内部状態 'alice_charge' を要求する。
    2. 自身（発動しているカード自身）を対象にEXを使用した場合:
       - チャージを獲得し、手札に留まる（恒等写像）。
    3. それ以外（敵など）を対象にEXを使用した場合:
       - チャージを消費（リセット）し、通常通り山札へ回る（巡回置換）。
    """

    def __init__(self):
        super().__init__(name="Alice_Battle")

    def required_state(self) -> Dict[str, Any]:
        """アリス（臨戦）専用の次元（チャージ状態）を状態空間に追加"""
        return {"alice_charge": 0}

    def on_active(self, state: State, k: int, target: str = "") -> State:
        """
        主作用。ターゲット指定によって写像の性質（恒等か巡回か）が動的に分岐する。
        """
        # 発動スロットに存在するカード名を取得
        # （通常は "Alice_Battle" だが、コピーEX発動時は "AvantGarde" になる）
        active_card = state.cards[k]

        if target == active_card:
            # 【モード1：光の剣、スーパーノヴァ（自身対象）】
            # チャージを加算し、サイクル処理は行わない（手札に留まる＝恒等写像）
            current_charge = state.get_env("alice_charge", 0)

            # ※実際のゲーム内ではチャージ上限があるが、ここでは状態遷移の確認として+1する
            new_charge = min(current_charge + 1, 2)

            return state.update(alice_charge=new_charge)

        else:
            # 【モード2：エナジーバースト（敵対象など、自身以外）】
            # チャージをリセット（消費）し、基底クラスの通常サイクル処理を呼び出す（巡回置換）
            state = state.update(alice_charge=0)
            return super().on_active(state, k, target)

    def on_passive(
        self, state: State, active_char: str, k: int, target: str = ""
    ) -> State:
        """
        受動作用。アリス（臨戦）は他者のEX発動によって状態が変化するギミックを持たないため、
        基底クラスのデフォルト動作（何もしない）をそのまま使用するか、明示的に記述する。
        """
        return state
