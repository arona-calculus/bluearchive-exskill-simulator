from __future__ import annotations
from typing import Optional
from ba_exsim.core.spec import CharacterSpec


class GenericSpec(CharacterSpec):
    def __init__(self, name: str, cost: Optional[int] = None):
        super().__init__(name=name, cost=cost)
