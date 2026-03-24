from __future__ import annotations
from typing import List, Tuple, Callable

from ba_exsim.core.state import State
from ba_exsim.core.compiler import CharacterSpec
from ba_exsim.core.algebra import Permutation, find_char


class RioSpec(CharacterSpec):
    """
    Rio's character specification based on the `get_actions` pattern.
    Her EX skill summons a decoy unit, "AvantGarde".
    """
    def __init__(self, decoy_name: str = "AvantGarde"):
        super().__init__(name="Rio")
        self.decoy_name = decoy_name

    def get_actions(self, spec_idx: int, L: int, hand_size: int) -> List[Tuple[Callable, Callable]]:
        return [
            self._get_action_on_self(hand_size),
            self._get_action_on_others(hand_size),
        ]

    def _get_action_on_self(self, hand_size: int):
        """Action when Rio's own skill is used."""
        def condition(state: State, action_slot: int) -> bool:
            my_slot, _ = find_char(state.cards, self.name)
            return my_slot is not None and my_slot == action_slot

        def effect(state: State) -> State:
            """Marks the current slot for a future overwrite by the summon."""
            my_slot, _ = find_char(state.cards, self.name)
            new_env = state.env.copy()
            new_env['rio_overwrite_slot'] = my_slot
            return state._replace(env=new_env)

        return (condition, effect)

    def _get_action_on_others(self, hand_size: int):
        """Action when another character's skill is used."""
        def condition(state: State, action_slot: int) -> bool:
            my_slot, _ = find_char(state.cards, self.name)
            return 'rio_overwrite_slot' in state.env and (my_slot is None or my_slot != action_slot)

        def effect(state: State) -> State:
            """
            Performs the summon. Swaps the character in the marked slot
            with the AvantGarde decoy from the deck.
            """
            env = state.env.copy()
            overwrite_slot = env.pop('rio_overwrite_slot')
            cards = state.cards

            # Find the decoy and the character to be replaced
            decoy_slot, _ = find_char(cards, self.decoy_name)
            char_to_replace = cards[overwrite_slot]

            if decoy_slot is None:
                # Should not happen if specs are set up correctly
                return state._replace(env=env)

            # Store the original character's name for de-spawning
            env['avant_garde_origin_char'] = char_to_replace
            env['avant_garde_origin_slot'] = decoy_slot # Store where decoy was

            # Swap the character with the decoy
            swap_perm = Permutation.swap(overwrite_slot, decoy_slot)
            new_cards = swap_perm.apply(cards)

            return state._replace(cards=new_cards, env=env)

        return (condition, effect)


class AvantGardeSpec(CharacterSpec):
    """
    Specification for Rio's summon, AvantGarde.
    Its skill use causes it to de-spawn.
    """
    def __init__(self):
        super().__init__(name="AvantGarde")

    def get_actions(self, spec_idx: int, L: int, hand_size: int) -> List[Tuple[Callable, Callable]]:
        return [
            self._get_action_on_self(hand_size),
        ]

    def _get_action_on_self(self, hand_size: int):
        """Action when AvantGarde's own skill is used."""
        def condition(state: State, action_slot: int) -> bool:
            my_slot, _ = find_char(state.cards, self.name)
            return my_slot is not None and my_slot == action_slot

        def effect(state: State) -> State:
            """
            De-spawns by swapping itself back with the original character
            it replaced.
            """
            env = state.env.copy()
            cards = state.cards

            origin_char_name = env.pop('avant_garde_origin_char', None)
            origin_char_original_slot = env.pop('avant_garde_origin_slot', None)

            if not origin_char_name:
                return state # Nothing to swap back to

            # Find AvantGarde's current position and the original character's position
            my_slot, _ = find_char(cards, self.name)
            origin_char_current_slot, _ = find_char(cards, origin_char_name)

            if my_slot is None or origin_char_current_slot is None:
                return state._replace(env=env)

            # Swap back
            swap_perm = Permutation.swap(my_slot, origin_char_current_slot)
            new_cards = swap_perm.apply(cards)

            return state._replace(cards=new_cards, env=env)

        return (condition, effect)
