"""
BA EX Skill Simulator - FastAPI Backend

起動方法:
  cd bluearchive-exskill-simulator
  uv run --extra webui uvicorn webui.backend.main:app --reload --port 8000
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State
from ba_exsim.specs.alice_battle import AliceBattleSpec
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioCopySpec, RioSpec
# main.py の app 定義部分
app = FastAPI(title="BA ExSkill Simulator API", root_path="/exsim")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Dict] = {}


class BuiltinEntry(NamedTuple):
    label: str
    spec: type


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
    "Mine":            BuiltinEntry("ミネ",           GenericSpec),
    "Miyako":          BuiltinEntry("ミヤコ",         GenericSpec),
    "Miyako_Swimsuit": BuiltinEntry("ミヤコ(水着)",   GenericSpec),
    "Rio":             BuiltinEntry("リオ",          RioSpec),
}

NEEDS_TARGET: List[str] = ["Rio", "Alice_Battle"]


def build_specs(characters: List[str]) -> List[CharacterSpec]:
    specs: List[CharacterSpec] = []
    seen: set = set()
    for name in characters:
        if name in seen:
            continue
        seen.add(name)
        if name in BUILTINS:
            spec_cls = BUILTINS[name].spec
            specs.append(spec_cls(name) if spec_cls is GenericSpec else spec_cls())
        else:
            specs.append(GenericSpec(name))
    if "Rio" in seen:
        specs.append(RioCopySpec())
    return specs


def state_to_dict(state, hand_size: int = 3) -> Dict[str, Any]:
    return {
        "hand": list(state.cards[:hand_size]),
        "deck": list(state.cards[hand_size:]),
        "env": {k: v for k, v in state.env.items() if v is not None},
    }


class SessionCreate(BaseModel):
    characters: List[str]
    # NOTE: コアエンジン (state.draw_card) は現在 hand_size=3 を前提とした実装。
    # 他の値を指定した場合の動作保証はエンジン側の対応待ち。
    hand_size: int = 3
    env: Optional[Dict[str, Any]] = None
    # セーブデータからの復元用
    restore_current: Optional[Dict[str, Any]] = None
    restore_initial: Optional[Dict[str, Any]] = None
    restore_history: Optional[List[Dict[str, Any]]] = None


class RewindRequest(BaseModel):
    frame: int  # 0 = 初期状態, N = step N 実行後の状態


class PlayRequest(BaseModel):
    slot: int
    target: str = ""


@app.get("/api/specs")
def get_specs():
    return {
        "builtin": [
            {"value": k, "label": v.label}
            for k, v in BUILTINS.items()
        ],
        "needs_target": NEEDS_TARGET,
    }


@app.get("/api/icons")
def get_icons():
    icons_dir = Path(__file__).parent.parent / "assets" / "icons"
    if not icons_dir.exists():
        return {"available": []}
    return {"available": [p.stem for p in sorted(icons_dir.glob("*.png"))]}


@app.post("/api/session")
def create_session(body: SessionCreate):
    if body.hand_size < 1:
        raise HTTPException(status_code=400, detail="hand_size は1以上が必要です")
    if len(body.characters) <= body.hand_size:
        raise HTTPException(status_code=400, detail=f"デッキにカードが必要です (総数 > hand_size={body.hand_size})")

    specs = build_specs(body.characters)
    sim = Simulator(specs)

    if body.restore_current:
        # セーブデータからの復元: まず仮初期化してからstateを上書き
        sim.initialize_state(tuple(body.characters), env={})
        cards = tuple(body.restore_current["hand"] + body.restore_current["deck"])
        sim.state = State(cards=cards, env=body.restore_current.get("env", {}))
        initial_state = body.restore_initial or state_to_dict(sim.state, body.hand_size)
        history = body.restore_history or []
    else:
        state = sim.initialize_state(tuple(body.characters), env=body.env or {})
        initial_state = state_to_dict(state, body.hand_size)
        history = []

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "sim": sim,
        "characters": body.characters,
        "hand_size": body.hand_size,
        "initial_state": initial_state,
        "history": history,
    }
    return {
        "session_id": session_id,
        "state": state_to_dict(sim.state, body.hand_size),
        "characters": body.characters,
        "hand_size": body.hand_size,
        "initial_state": initial_state,
        "history": history,
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]
    return {
        "session_id": session_id,
        "state": state_to_dict(sim.state, hand_size),
        "characters": session["characters"],
        "hand_size": hand_size,
        "initial_state": session["initial_state"],
        "history": session["history"],
    }


@app.post("/api/session/{session_id}/play")
def play_card(session_id: str, body: PlayRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]

    if not (0 <= body.slot < hand_size):
        raise HTTPException(status_code=400, detail=f"スロットは0~{hand_size - 1}の範囲です")

    state_before = state_to_dict(sim.state, hand_size)
    played_card = sim.state.cards[body.slot]

    try:
        new_state = sim.play(body.slot, target=body.target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    entry = {
        "step": len(session["history"]) + 1,
        "card": played_card,
        "slot": body.slot,
        "target": body.target,
        "state_before": state_before,
        "state_after": state_to_dict(new_state, hand_size),
    }
    session["history"].append(entry)
    return {
        "state": state_to_dict(new_state, hand_size),
        "history": session["history"],
        "played_card": played_card,
    }


@app.post("/api/session/{session_id}/rewind")
def rewind_session(session_id: str, body: RewindRequest):
    """指定フレームの状態に巻き戻す (frame=0: 初期状態, frame=N: step N 実行後)"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]
    history = session["history"]

    if body.frame == 0:
        s = session["initial_state"]
        new_history = []
    elif 1 <= body.frame <= len(history):
        s = history[body.frame - 1]["state_after"]
        new_history = history[:body.frame]
    else:
        raise HTTPException(status_code=400, detail="無効なフレーム番号です")

    cards = tuple(s["hand"] + s["deck"])
    sim.state = State(cards=cards, env=s.get("env", {}))
    session["history"] = new_history

    return {
        "state": state_to_dict(sim.state, hand_size),
        "history": new_history,
        "initial_state": session["initial_state"],
    }


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    sessions.pop(session_id, None)
    return {"ok": True}


_assets_dir = Path(__file__).parent.parent / "assets"
_icons_dir = _assets_dir / "icons"


@app.get("/assets/icons/{filename}")
def serve_icon(filename: str):
    file_path = (_icons_dir / filename).resolve()
    if not str(file_path).startswith(str(_icons_dir.resolve())):
        raise HTTPException(status_code=403)
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
