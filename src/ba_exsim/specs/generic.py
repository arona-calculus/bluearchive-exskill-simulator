from __future__ import annotations
from ba_exsim.core.spec import CharacterSpec


class GenericSpec(CharacterSpec):
    def __init__(self, name: str):
        super().__init__(name=name)
