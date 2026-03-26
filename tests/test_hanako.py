from __future__ import annotations
from ba_exsim.core.state import State
from ba_exsim.core.compiler import TimelineCompiler, CharacterSpec
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec


# --- テスト用のプロキシ（代理実行）Spec ---
class MockProxySpec(CharacterSpec):
    """
    AvantGardeのような「他キャラのスキルを代理実行する」仮想カードのモック。
    ハナコのテストをリオの実装から独立（疎結合）させるためにここで定義する。
    """
    def __init__(self, target_name: str):
        super().__init__(name="MockProxy", is_proxy=True)
        self.target_name = target_name

    def get_proxy_target(self, state: State) -> str | None:
        return self.target_name

    def on_active(self, state: State, k: int, target: str = "") -> State:
        # registryを介して対象のSpecを代理実行
        copied_spec = self.registry[self.target_name]
        return copied_spec.on_active(state, k, target)


# --- Test Cases ---

def test_hanako_full_behavior():
    """
    水着ハナコの代数的な基本挙動を検証する:
    1. ゲージ不足時の通常のカードサイクル。
    2. 他キャラのEX使用によるパッシブなゲージ増加（最大値キャップ付き）。
    3. ゲージ十分な場合、ゲージを消費して手札に留まる（恒等写像）。
    4. ゲージ量に応じたサイクルと恒等写像の動的切り替え。
    """
    specs = [
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"),
        GenericSpec("Haruka"),
        GenericSpec("Hoshino"),
    ]
    initial_cards = ("Hanako", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state = compiler.build_initial_state(initial_cards)

    # --- Initial State ---
    assert state.cards == ("Hanako", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state.env["hanako_gauge"] == 0
    print("\n[OK] Initial state is correct.")

    # --- Step 1: Use Hanako with insufficient gauge (0) ---
    state_1 = transition(state, 0)
    assert state_1.cards == ("Kayoko", "Aru", "Mutsuki", "Haruka", "Hoshino", "Hanako")
    assert state_1.env["hanako_gauge"] == 0
    print("[OK] Step 1: Hanako correctly cycled with insufficient gauge.")

    # --- Step 2: Passive gauge increase ---
    state_2 = transition(state_1, 1)  # Use Aru
    assert state_2.cards == ("Kayoko", "Haruka", "Mutsuki", "Hoshino", "Hanako", "Aru")
    assert state_2.env["hanako_gauge"] == 40
    print(f"[OK] Step 2: Gauge increased to {state_2.env['hanako_gauge']} after Aru's skill.")

    # --- Step 3: More passive gauge increase ---
    state_3 = transition(state_2, 2)  # Use Mutsuki
    assert state_3.cards == ("Kayoko", "Haruka", "Hoshino", "Hanako", "Aru", "Mutsuki")
    assert state_3.env["hanako_gauge"] == 80
    print(f"[OK] Step 3: Gauge increased to {state_3.env['hanako_gauge']} after Mutsuki's skill.")

    # --- Step 3.1: More passive gauge increase ---
    state_3_1 = transition(state_3, 0)  # Use Kayoko
    assert state_3_1.cards == ("Hanako", "Haruka", "Hoshino", "Aru", "Mutsuki", "Kayoko")
    assert state_3_1.env["hanako_gauge"] == 120
    print(f"[OK] Step 3.1: Gauge increased to {state_3_1.env['hanako_gauge']} after Kayoko's skill.")

    # --- Step 3.2: More passive gauge increase ---
    state_3_2 = transition(state_3_1, 1)  # Use Haruka
    assert state_3_2.cards == ("Hanako", "Aru", "Hoshino", "Mutsuki", "Kayoko", "Haruka")
    assert state_3_2.env["hanako_gauge"] == 160
    print(f"[OK] Step 3.2: Gauge increased to {state_3_2.env['hanako_gauge']} after Haruka's skill.")

    # --- Step 4: Reach max gauge (200) ---
    state_4 = transition(state_3_2, 2)  # Use Hoshino
    assert state_4.cards == ("Hanako", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state_4.env["hanako_gauge"] == 200
    print(f"[OK] Step 4: Gauge reached max ({state_4.env['hanako_gauge']}) and Hanako returned to hand.")

    # --- Step 5: Use Hanako with SUFFICIENT gauge (200) ---
    state_5 = transition(state_4, 0)
    assert state_5.cards == ("Hanako", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state_5.env["hanako_gauge"] == 100
    print(f"[OK] Step 5: Hanako stayed in hand, gauge consumed to {state_5.env['hanako_gauge']}.")

    # --- Step 6: Use Hanako again with just enough gauge (100) ---
    state_6 = transition(state_5, 0)
    assert state_6.cards == ("Hanako", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state_6.env["hanako_gauge"] == 0
    print(f"[OK] Step 6: Hanako stayed in hand again, gauge consumed to {state_6.env['hanako_gauge']}.")

    # --- Step 7: Use Hanako with insufficient gauge again (0) ---
    state_7 = transition(state_6, 0)
    assert state_7.cards == ("Kayoko", "Aru", "Mutsuki", "Haruka", "Hoshino", "Hanako")
    assert state_7.env["hanako_gauge"] == 0
    print("[OK] Step 7: Hanako correctly cycled again with insufficient gauge.")


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
        MockProxySpec(target_name="Hanako"),  # ハナコを代理実行するカード
    ]
    # ハナコ本人と、プロキシカードが両方手札にある状態を作る
    initial_cards = ("Hanako", "MockProxy", "Aru", "Mutsuki", "Kayoko", "Haruka")
    compiler = TimelineCompiler(specs)
    transition = compiler.compile()

    # ゲージを最初から「100 (1ゲージ分)」持っている状態からスタート
    state_0 = compiler.build_initial_state(initial_cards).update(hanako_gauge=100)

    print("\n--- Testing Proxy Behavior ---")
    assert state_0.env["hanako_gauge"] == 100

    # --- Step 1: プロキシカードがハナコを代理実行 ---
    # 期待値: ゲージ100以上だが、代理実行なのでゲージは消費されず、プロキシカードは通常通りサイクルする
    state_1 = transition(state_0, 1)  # Use MockProxy from slot 1

    assert state_1.cards == ("Hanako", "Mutsuki", "Aru", "Kayoko", "Haruka", "MockProxy")
    assert state_1.env["hanako_gauge"] == 100  # ゲージが消費されていないこと！
    print("[OK] プロキシによる代理実行時、ハナコのゲージは消費されず通常サイクルしました。")

    # --- Step 2: 別の通常キャラがスキルを使用 ---
    # 期待値: ハナコ自身のパッシブが働き、ゲージが増加する（100 -> 140）
    state_2 = transition(state_1, 2)  # Use Aru from slot 2

    assert state_2.env["hanako_gauge"] == 140
    print("[OK] 通常キャラのスキル使用時、ハナコのゲージが正しく増加しました。")
