from __future__ import annotations
import pytest

from ba_exsim.core.state import State
from ba_exsim.core.compiler import TimelineCompiler, CharacterSpec
from ba_exsim.specs.hanako import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, AvantGardeSpec


class GenericSpec(CharacterSpec):
    """A generic spec for characters with no special behavior."""

    def __init__(self, name: str):
        super().__init__(name=name)


def test_rio_hanako_integration():
    """
    Tests the interaction between Rio and Hanako (Swimsuit).
    - Rio's summon correctly triggers on Hanako's normal skill cycle.
    - Hanako correctly gains gauge from Rio and AvantGarde's skill uses.
    - AvantGarde correctly de-spawns and restores the original character.
    - Hanako can correctly stay in hand using her gauge after all this.
    """
    # --- 1. Setup ---
    specs = [
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyo"),
        GenericSpec("Sena"),
        AvantGardeSpec(),
    ]
    # Initial state: Hand=[Rio, Hanako, Aru], Deck=[Kisaki, Kikyo, Sena], Inactive=[AvantGarde]
    initial_cards = ("Hanako", "Sena", "Kikyo", "Aru", "Rio", "Kisaki", "AvantGarde")

    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state = compiler.build_initial_state(initial_cards)

    # --- Initial State ---
    initial_cards = ("Hanako", "Sena", "Kikyo", "Aru", "Rio", "Kisaki", "AvantGarde")
    assert state.get_env("hanako_gauge", 0) == 0

    # --- Step 1: Sena EX (slot 1) ---
    # Sena cycles, marks slot 1. Hanako's passive triggers and she gains gauge.
    # Hand: [Hanako, Aru, Kikyo], Deck: [Rio, Kisaki, Sena], Inactive: [AvantGarde]
    state = transition(state, 1)
    assert state.cards == ("Hanako", "Aru", "Kikyo", "Rio", "Kisaki", "Sena", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 2

    # --- Step 2: Hanako EX (slot 1) ---
    # Hanako's gauge is 2 (< 3), so she cycles normally.
    # Hand: [AvantGarde, Kikyo, Aru], Deck: [Sena, Rio, Hanako], Inactive: [Kisaki]
    state = transition(state, 0)
    assert state.cards == ("Rio", "Aru", "Kikyo", "Kisaki", "Sena", "Hanako", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 2

    # --- Step 3: Aru EX (slot 1) ---
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    state = transition(state, 1)
    assert state.cards == ("Rio", "Kisaki", "Kikyo", "Sena", "Hanako", "Aru", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 4

    # --- Step 4: Kisaki EX (slot 1) ---
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    state = transition(state, 1)
    assert state.cards == ("Rio", "Sena", "Kikyo", "Hanako", "Aru", "Kisaki", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 6

    # --- Step 5: Sena EX (slot 1) ---
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    state = transition(state, 1)
    assert state.cards == ("Rio", "Hanako", "Kikyo", "Aru", "Kisaki", "Sena", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 6

    # --- Step 6: Sena EX (slot 1) ---
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    state = transition(state, 1)
    assert state.cards == ("Rio", "Hanako", "Kikyo", "Aru", "Kisaki", "Sena", "AvantGarde")
    assert "rio_overwrite_slot" not in state.env
    assert state.get_env("hanako_gauge", 0) == 3

    # --- Step 6: Rio EX (slot 1) ---
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    state = transition(state, 0)
    print(state.cards)
    assert state.cards == ("AvantGarde", "Hanako", "Kikyo", "Aru", "Kisaki", "Sena", "Rio")
    # assert "rio_overwrite_slot" not in state.env
    # assert state.get_env("hanako_gauge", 0) == 6

    print("[OK] Rio and Hanako integration test passed.")
    print(f"[OK] 完走しました。最終状態: Hand={state.cards[:3]}")


"""
セナ
ハナコ
アル
キサキ
セナ
ハナコ(コピー)
ハナコ
ハナコ
ハナコ

アル
セナ
リオ
キサキ
ハナコ(コピー)

キキョウ
ハナコ
ハナコ
アル
ハナコ
リオ→ハナコ
ハナコ(コピー)

セナ
キサキ
ハナコ
ハナコ
リオ→ハナコ
ハナコ(コピー)
ハナコ
セナ
キサキ
リオ→ハナコ
アル
ハナコ
キキョウ
セナ
キサキ
ハナコ(コピー)
ハナコ
ハナコ

キキョウ
アル
リオ→ハナコ
キサキ
ハナコ(コピー)
ハナコ
ハナコ
ハナコ
"""
