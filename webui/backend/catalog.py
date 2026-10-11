"""
webuiとMCPサーバーで共有する生徒カタログ(名前→Spec対応表)とSpec構築処理。

FastAPIに依存しないため、webui/backend/main.py 以外(mcp_server.py等)からも import できる。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.specs.alice_battle import AliceBattleSpec
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.ibuki_swimsuit import IbukiSwimsuitSpec
from ba_exsim.specs.rio import RioCopySpec, RioSpec
from ba_exsim.specs.yuzu_battle import YuzuBattleSpec


class BuiltinEntry(NamedTuple):
    label: str
    spec: type
    role: Optional[str] = None  # "STRIKER" / "SPECIAL" (character_library由来、不明ならNone)
    cost: Optional[int] = None  # EXスキル消費コスト(lv5時点、character_library由来、不明ならNone)
    extra_cost: Optional[int] = None  # 変身後スキル(ExtraSkills)の消費コスト。無いキャラはNone


BUILTINS: Dict[str, BuiltinEntry] = {
    "Alice_Battle":    BuiltinEntry("アリス(臨戦)", AliceBattleSpec),
    "Aru":             BuiltinEntry("アル",         GenericSpec),
    "Aru_Dress":       BuiltinEntry("アル(ドレス)",   GenericSpec),
    "Eri":             BuiltinEntry("エリ",           GenericSpec),
    "Kayoko_Newyear":  BuiltinEntry("カヨコ(正月)",    GenericSpec),
    "Kisaki":          BuiltinEntry("キサキ",         GenericSpec),
    "Key":             BuiltinEntry("ケイ",           GenericSpec),
    "Shiroko_Swimsuit":  BuiltinEntry("シロコ(水着)",   GenericSpec),
    "Seia":            BuiltinEntry("セイア",         GenericSpec),
    "Seia_Swimsuit":   BuiltinEntry("セイア(水着)",   GenericSpec),
    "Hanako_Swimsuit": BuiltinEntry("ハナコ(水着)",   HanakoSwimsuitSpec),
    "Hare_Camp":       BuiltinEntry("ハレ(キャンプ)", GenericSpec),
    "Hikari":          BuiltinEntry("ヒカリ",         GenericSpec),
    "Nagisa":          BuiltinEntry("ナギサ",         GenericSpec),
    "Nagisa_Swimsuit": BuiltinEntry("ナギサ(水着)",   GenericSpec),
    "Michiru_Dress":   BuiltinEntry("ミチル(ドレス)", GenericSpec),
    "Hoshino":         BuiltinEntry("ホシノ",         GenericSpec),
    "Hoshino_Swimsuit":BuiltinEntry("ホシノ(水着)",   GenericSpec),
    "Hoshino_Battle_Attack": BuiltinEntry("ホシノ(臨戦)[攻撃型]",   GenericSpec),
    "Hoshino_Battle_Defence": BuiltinEntry("ホシノ(臨戦)[防御型]",   GenericSpec),
    "Ibuki_Swimsuit":  BuiltinEntry("イブキ(水着)",     IbukiSwimsuitSpec),
    "Mine":            BuiltinEntry("ミネ",           GenericSpec),
    "Miyako":          BuiltinEntry("ミヤコ",         GenericSpec),
    "Miyako_Swimsuit": BuiltinEntry("ミヤコ(水着)",   GenericSpec),
    "Rio":             BuiltinEntry("リオ",          RioSpec),
    "Yuzu_Battle":     BuiltinEntry("ユズ(臨戦)",     YuzuBattleSpec),
}

_LIBRARY_PATH = Path(__file__).parent / "character_library" / "data" / "characters.json"


def _load_generated_builtins() -> Dict[str, BuiltinEntry]:
    """character_library/build_library.py が生成したキャラライブラリを読み込む。
    未実装の生徒は GenericSpec を割り当てる(固有のEXスキル実装が必要な生徒は
    上の BUILTINS に手動で追記し、専用の Spec クラスを割り当てること)。
    """
    if not _LIBRARY_PATH.exists():
        return {}
    with _LIBRARY_PATH.open(encoding="utf-8") as f:
        entries = json.load(f)
    return {
        e["key"]: BuiltinEntry(
            e["label"], GenericSpec,
            role=e.get("role"), cost=e.get("ex_cost_max"), extra_cost=e.get("ex_extra_cost_max"),
        )
        for e in entries
        if e.get("key") and e.get("label")
    }


# 手動でカスタムSpecを割り当てた上のエントリを優先し、生成分で不足を補う
_GENERATED_BUILTINS = _load_generated_builtins()
BUILTINS = {**_GENERATED_BUILTINS, **BUILTINS}

# 手動定義24件にはrole/costが無いため、生成データ側から補完する
for _key, _entry in list(BUILTINS.items()):
    if _key in _GENERATED_BUILTINS:
        _generated_entry = _GENERATED_BUILTINS[_key]
        BUILTINS[_key] = _entry._replace(
            role=_entry.role if _entry.role is not None else _generated_entry.role,
            cost=_entry.cost if _entry.cost is not None else _generated_entry.cost,
            extra_cost=_entry.extra_cost if _entry.extra_cost is not None else _generated_entry.extra_cost,
        )

NEEDS_TARGET: List[str] = ["Rio", "Alice_Battle", "Ibuki_Swimsuit"]


def build_specs(characters: List[str]) -> List[CharacterSpec]:
    specs: List[CharacterSpec] = []
    seen: set = set()
    character_roles = {
        name: BUILTINS[name].role
        for name in characters
        if name in BUILTINS and BUILTINS[name].role
    }
    for name in characters:
        if name in seen:
            continue
        seen.add(name)
        if name in BUILTINS:
            entry = BUILTINS[name]
            spec_cls = entry.spec
            if spec_cls is GenericSpec:
                specs.append(spec_cls(name, cost=entry.cost))
            elif spec_cls is IbukiSwimsuitSpec:
                specs.append(spec_cls(
                    character_roles=character_roles, cost=entry.cost, extra_cost=entry.extra_cost,
                ))
            else:
                specs.append(spec_cls(cost=entry.cost))
        else:
            specs.append(GenericSpec(name))
    if "Rio" in seen:
        specs.append(RioCopySpec())
    return specs


def state_to_dict(state) -> Dict[str, Any]:
    return {
        "hand": list(state.hand),
        "deck": list(state.deck),
        "env": {k: v for k, v in state.env.items() if v is not None},
    }


def play_and_record(
    sim: Simulator, slot: int, target: str, history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """スロットslotのカードを使用し、webuiのhistory形式のエントリを返す(historyへの追加は呼び出し側)。

    sim.play が例外を投げた場合は sim.state を変更せずにそのまま送出する。
    """
    state_before = state_to_dict(sim.state)
    played_card = sim.state.cards[slot]

    # コストはプレイ前のstateに対して評価する(リオ(コピー)はapply_effect自身が
    # rio_copy_targetをクリアするため、プレイ後では参照できなくなるキャラがいる)
    step_cost = sim.registry.evaluate_cost(sim.state, played_card)

    new_state = sim.play(slot, target=target)

    prev_cumulative_cost = history[-1]["cumulative_cost"] if history else 0
    return {
        "step": len(history) + 1,
        "card": played_card,
        "slot": slot,
        "target": target,
        "state_before": state_before,
        "state_after": state_to_dict(new_state),
        "cost": step_cost,
        "cumulative_cost": prev_cumulative_cost + (step_cost or 0),
    }
