from __future__ import annotations
from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec


class RioSpec(CharacterSpec):
    """
    ゲーム内仕様のリオ:
    EXを使用すると、指定した対象(target)のEXをコピーし、
    手札の自身が即座に「AvantGarde（コピーEX）」に置換される。
    この時点ではデッキのドロー・サイクルは発生しない。
    """

    def __init__(self, decoy_name: str = "AvantGarde"):
        super().__init__(name="Rio")
        self.decoy_name = decoy_name

    def on_active(self, state: State, k: int, target: str = "") -> State:
        cards = list(state.cards)
        env = dict(state.env)

        # アバンギャルド（不活性領域の仮想カード）を探す
        try:
            ag_index = cards.index(self.decoy_name)
        except ValueError:
            return state

        # 1. コピー先のターゲット情報を保存
        # （対象のSpecをAvantGardeが後で代理実行するために必要）
        if target:
            env["avant_garde_copied_target"] = target

        # [重要] super().on_active() は呼ばない！ (デッキは回さない)
        # 手札のリオと、不活性領域のアバンギャルドを即座にスワップする
        cards[k], cards[ag_index] = cards[ag_index], cards[k]

        # 2. 不活性領域に退避された「本来のリオ」のインデックスを記憶
        env["rio_parked_index"] = ag_index

        return state.update(cards=tuple(cards), **env)


class AvantGardeSpec(CharacterSpec):
    """
    コピーEX（AvantGarde）の仕様:
    """
    def __init__(self):
        # 自身がプロキシ（仮想カード）であることを明示する
        super().__init__(name="AvantGarde", is_proxy=True)

    def on_active(self, state: State, k: int, target: str = "") -> State:
        env = dict(state.env)
        copied_name = env.get("avant_garde_copied_target")

        # --- 1. 代理実行（Delegate） ---
        if copied_name and copied_name in self.registry:
            copied_spec = self.registry[copied_name]
            new_state = copied_spec.on_active(state, k, target)
        else:
            new_state = super().on_active(state, k, target)

        # --- 2. 事後評価（Post-evaluation） ---
        if new_state.cards[k] == self.name:
            # 手札に留まった場合はそのまま終了
            return new_state

        # --- 3. 帰還処理（リオをデッキ最後尾へ） ---
        current_env = dict(new_state.env)

        # pop() を用いて環境からフラグを完全に取り除く
        rio_parked_index = current_env.pop("rio_parked_index", None)

        if rio_parked_index is not None:
            cards = list(new_state.cards)
            L = current_env.get("L", 6)
            last_pos = L - 1

            # リオとAvantGardeをスワップ
            cards[last_pos], cards[rio_parked_index] = (
                cards[rio_parked_index],
                cards[last_pos],
            )

            # コピー先のターゲット情報も役割を終えたので削除
            current_env.pop("avant_garde_copied_target", None)

            # 【修正ポイント】
            # State.update() は「辞書の結合」でありキーを消せないため、
            # 不要なキーをpopした current_env を用いて State を再生成する
            new_state = State(cards=tuple(cards), env=current_env)

        return new_state
