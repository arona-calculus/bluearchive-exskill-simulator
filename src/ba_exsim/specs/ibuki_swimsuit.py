from __future__ import annotations
from typing import Dict, Optional, Tuple
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State

SHELLS_PER_TRIGGER = 3
SHELLS_FOR_FLOWER = 12


class IbukiSwimsuitSpec(CharacterSpec):
    """
    イブキ(水着)

    EX1「イブキのお友達！」(未指定時): 味方ストライカー最大2人を「お友達」に指定し、
    以降このカードはEX2「どれがいいかな？」として振る舞う。イブキ自身は次のドローで
    即座に手札へ戻る(ハナコ水着のpending_force_draw同様の仕組みだが、キーを分離して
    衝突を避ける)。

    EX2「どれがいいかな？」(指定済み時): 「お友達」に会心ダメージ増加バフを付与する
    (数値バフはこのシミュレーターの対象外なので状態変化なし)。「貝殻のお花」保有時は
    強化版になる(このシミュレーター上は状態変化なし、フレーバーのみ)。

    パッシブ: 「お友達」がカードを使用する度に「貝殻」を3個獲得。12個で「貝殻のお花」
    を獲得し、以降貝殻は増えない。

    character_roles: 名前 -> "STRIKER"/"SPECIAL" の対応表(webui側でBUILTINSから構築)。
    セッション中は変化しない静的情報なので、可変なstate.envではなくSpec自身が保持する。
    """

    def __init__(self, character_roles: Optional[Dict[str, str]] = None):
        super().__init__("Ibuki_Swimsuit")
        self.character_roles = character_roles or {}

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        friends = state.get_env("ibuki_friends")

        if not friends:
            # EX1: お友達を指定する(最大2人、カンマ区切り、ストライカーのみ)
            new_friends = tuple(name for name in target.split(",") if name)
            non_strikers = [
                name for name in new_friends if self.character_roles.get(name) == "SPECIAL"
            ]
            if non_strikers:
                raise ValueError(
                    f"{'、'.join(non_strikers)} はストライカーではないため「お友達」に指定できません"
                )
            return state.update(
                ibuki_friends=new_friends,
                ibuki_shells=0,
                ibuki_shell_flower=False,
                ibuki_pending_force_draw=self.name,
            )

        # EX2: 指定済みのお友達へバフ(数値状態は変化しない)
        return state

    def on_draw_intercept(
        self, state: State, trigger: str
    ) -> Tuple[Optional[str], State]:
        if state.get_env("ibuki_pending_force_draw") == self.name:
            return self.name, state.update(ibuki_pending_force_draw=None)
        return None, state

    def on_passive(self, state: State, active_char: str, target: str = "") -> State:
        friends = state.get_env("ibuki_friends") or ()
        if active_char not in friends:
            return state

        if state.get_env("ibuki_shell_flower", False):
            return state  # 貝殻のお花獲得後は貝殻を獲得しない

        shells = state.get_env("ibuki_shells", 0) + SHELLS_PER_TRIGGER
        if shells >= SHELLS_FOR_FLOWER:
            return state.update(ibuki_shells=0, ibuki_shell_flower=True)
        return state.update(ibuki_shells=shells)
