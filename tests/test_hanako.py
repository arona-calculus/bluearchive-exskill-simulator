from __future__ import annotations

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec

# 水着ハナコの基本挙動は tests/data/scenarios/hanako/ にある。ここには独自のSpecクラス
# (MockProxySpec)を使うためにデータ化できないテストだけを置く。


# --- テスト用のプロキシ（代理実行）Spec ---
class MockProxySpec(CharacterSpec):
    """
    AvantGardeのような「他キャラのスキルを代理実行する」仮想カードのモック。
    ハナコのテストをリオの実装から独立（疎結合）させるためにここで定義する。
    """
    def __init__(self, target_name: str):
        super().__init__(name="MockProxy", is_proxy=True)
        self.target_name = target_name

    def should_cycle(self, state: State, k: int, target: str = "") -> bool:
        """
        [新アーキテクチャ対応]
        代理実行対象（ハナコ）の「手札留まり」判定のみを模倣する。
        """
        if self.target_name == "Hanako_Swimsuit":
            gauge = state.get_env("hanako_gauge", 0)
            if gauge >= 100:
                # ゲージ十分な場合、破棄とドローのサイクルをスキップして手札に留まる
                return False
        return True

    def apply_effect(self, state: State, k: int, target: str = "") -> State:
        """
        代理実行対象の挙動を模倣する。
        ただし、代理実行時はハナコ本人のゲージは一切消費されないため、状態は更新しない。
        """
        # ※もし将来的に「プロキシカード自身の消費コスト」などがあればここで記述しますが、
        # ハナコのゲージには触れないため恒等写像（そのまま返す）となります。
        return state


def test_hanako_proxy_behavior():
    """
    仮想カード（コピーEX等）によってハナコの仕様が代理実行された場合の検証:
    代理実行時は、ハナコ本人のゲージは一切消費されず、また増加もしないこと。
    """
    specs = [
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"),
        GenericSpec("Haruka"),
        MockProxySpec(target_name="Hanako_Swimsuit"),  # ハナコを代理実行するカード
    ]
    # ハナコ本人と、プロキシカードが両方手札にある状態を作る
    initial_cards = ("Hanako_Swimsuit", "MockProxy", "Aru", "Mutsuki", "Kayoko", "Haruka")

    sim = Simulator(specs)
    # ゲージを最初から「200 (2ゲージ分)」持っている状態からスタート
    state_0 = sim.initialize_state(initial_cards, env={"hanako_gauge": 200})

    print("\n--- Testing Proxy Behavior ---")
    assert state_0.env["hanako_gauge"] == 200

    # --- Step 1: プロキシカードがハナコを代理実行 ---
    # 期待値: ゲージ200以上だが、代理実行なのでゲージは消費されず、プロキシカードは手札に留まる
    state_1 = sim.play_by_name("MockProxy")
    assert state_1.cards == ("Hanako_Swimsuit", "MockProxy", "Aru", "Mutsuki", "Kayoko", "Haruka")
    assert state_1.env["hanako_gauge"] == 200  # ゲージが消費されていないこと！
    print("[OK] プロキシによる代理実行時、ハナコのゲージは消費されず、プロキシは手札に維持されました。")

    # --- Step 2: 別の通常キャラがスキルを使用 ---
    # 期待値: ハナコ自身のパッシブが働き、ゲージが増加する（200のままキャップ）
    state_2 = sim.play_by_name("Aru")
    assert state_2.cards == ("Hanako_Swimsuit", "MockProxy", "Mutsuki", "Kayoko", "Haruka", "Aru")
    assert state_2.env["hanako_gauge"] == 200
    print("[OK] 通常キャラのスキル使用時、ハナコのゲージが正しくキャップされました。")

    # --- Step 3: ハナコ本人がスキルを使用 ---
    # 期待値: ゲージを100消費して手札に留まる
    state_3 = sim.play_by_name("Hanako_Swimsuit")
    assert state_3.cards == ("Hanako_Swimsuit", "MockProxy", "Mutsuki", "Kayoko", "Haruka", "Aru")
    assert state_3.env["hanako_gauge"] == 100
    print("[OK] ハナコ本人のスキル使用時、ゲージが正しく消費されました。")

    # --- Step 4: プロキシを再度使用 ---
    # 期待値: ゲージが100なので、プロキシは手札に留まる
    state_4 = sim.play_by_name("MockProxy")
    assert state_4.cards == ("Hanako_Swimsuit", "MockProxy", "Mutsuki", "Kayoko", "Haruka", "Aru")
    assert state_4.env["hanako_gauge"] == 100  # ゲージは消費されない
    print("[OK] プロキシの再使用時、ゲージ消費なしで手札に維持されました。")


if __name__ == "__main__":
    test_hanako_proxy_behavior()
