from __future__ import annotations
import pytest

from ba_exsim.core.state import State
from ba_exsim.core.compiler import TimelineCompiler, CharacterSpec
from ba_exsim.specs.hanako import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, AvantGardeSpec
from ba_exsim.specs.generic import GenericSpec


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
    initial_cards = ("Rio", "Hanako", "Aru", "Kisaki", "Kikyo", "Sena", "AvantGarde")

    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state = compiler.build_initial_state(initial_cards)

    # --- Initial State ---
    assert state.cards == (
        "Rio",
        "Hanako",
        "Aru",
        "Kisaki",
        "Kikyo",
        "Sena",
        "AvantGarde",
    )
    assert state.get_env("hanako_gauge", 0) == 0

    # --- Step 1: Rio EX (slot 0) ---
    # Rio cycles, marks slot 0. Hanako's passive triggers and she gains gauge.
    # Hand: [Kisaki, Hanako, Aru], Deck: [Kikyo, Sena, Rio], Inactive: [AvantGarde]
    state = transition(state, 0)
    assert state.cards == (
        "Kisaki",
        "Hanako",
        "Aru",
        "Kikyo",
        "Sena",
        "Rio",
        "AvantGarde",
    )
    assert state.env.get("rio_overwrite_slot") == 0
    assert state.get_env("hanako_gauge", 0) == 2

    # --- Step 2: Hanako EX (slot 1) ---
    # Hanako's gauge is 2 (< 3), so she cycles normally.
    # Rio's passive catches the skill use and summons AvantGarde into slot 0.
    # Hand: [AvantGarde, Kikyo, Aru], Deck: [Sena, Rio, Hanako], Inactive: [Kisaki]
    state = transition(state, 1)
    assert state.cards == (
        "AvantGarde",
        "Kikyo",
        "Aru",
        "Sena",
        "Rio",
        "Hanako",
        "Kisaki",
    )
    assert "rio_overwrite_slot" not in state.env
    assert state.env.get("avant_garde_origin_char") == "Kisaki"
    assert state.get_env("hanako_gauge", 0) == 2  # No gain from own skill

    # --- Step 3: Kikyo EX (slot 1) ---
    # Kikyo cycles. Hanako gains gauge.
    # Hand: [AvantGarde, Sena, Aru], Deck: [Rio, Hanako, Kikyo], Inactive: [Kisaki]
    state = transition(state, 1)
    assert state.cards == (
        "AvantGarde",
        "Sena",
        "Aru",
        "Rio",
        "Hanako",
        "Kikyo",
        "Kisaki",
    )
    assert state.get_env("hanako_gauge", 0) == 4

    # --- Step 4: Aru EX (slot 2) ---
    # Aru cycles. Hanako gains gauge (max 6).
    # Hand: [AvantGarde, Sena, Rio], Deck: [Hanako, Kikyo, Aru], Inactive: [Kisaki]
    state = transition(state, 2)
    assert state.cards == (
        "AvantGarde",
        "Sena",
        "Rio",
        "Hanako",
        "Kikyo",
        "Aru",
        "Kisaki",
    )
    assert state.get_env("hanako_gauge", 0) == 6

    # --- Step 5: AvantGarde EX (slot 0) ---
    # AvantGarde de-spawns, bringing Kisaki back from inactive slot. Hanako's gauge stays at 6.
    # Hand: [Hanako, Sena, Rio], Deck: [Kikyo, Aru, Kisaki], Inactive: [AvantGarde]
    state = transition(state, 0)
    assert state.cards == (
        "Hanako",
        "Sena",
        "Rio",
        "Kikyo",
        "Aru",
        "Kisaki",
        "AvantGarde",
    )
    assert "avant_garde_origin_char" not in state.env
    assert state.get_env("hanako_gauge", 0) == 6

    # --- Step 6: Hanako EX (slot 0) ---
    # Hanako gauge is 6 (>= 3), so she stays in hand and consumes 3 gauge. No cycling occurs.
    # Hand: [Hanako, Sena, Rio], Deck: [Kikyo, Aru, Kisaki], Inactive: [AvantGarde]
    state = transition(state, 0)
    assert state.cards == (
        "Hanako",
        "Sena",
        "Rio",
        "Kikyo",
        "Aru",
        "Kisaki",
        "AvantGarde",
    )
    assert state.get_env("hanako_gauge", 0) == 3
    print("[OK] Rio and Hanako integration test passed.")
