from __future__ import annotations

from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec


def test_generic_cycle():
    char_names = ["A", "B", "C", "D", "E", "F"]

    # 1. 1行で環境を構築
    sim = Simulator([GenericSpec(name) for name in char_names])

    # 2. 状態の初期化
    state = sim.initialize_state(tuple(char_names))

    print("--- 初期状態 ---")
    assert state.cards == ("A", "B", "C", "D", "E", "F")

    print("\n--- Step 1: 'A' (スロット0) を使用 ---")
    state = sim.play(0)  # <- EngineやRegistryを意識する必要は一切なし！
    assert state.cards == ("D", "B", "C", "E", "F", "A")


if __name__ == "__main__":
    test_generic_cycle()
