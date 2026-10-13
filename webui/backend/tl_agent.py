"""
webuiの「TL取り込み」ページの中身: ラフに書かれたTLを Claude API に解釈させ、exsimに読み込める形にする。

チャットから MCP(mcp_server.py) で使うのと同じツールと指示文(tl_tools.py)を、
サーバー側のループで Claude に使わせる。APIキーはサーバーの持ち主のもの(ANTHROPIC_API_KEY)を
全利用者で共有するため、1回あたりの往復回数と出力トークンに上限を設ける
(利用回数の制限は main.py 側で行う)。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

from webui.backend import tl_import, tl_tools
from webui.backend.tl_tools import StepInput

logger = logging.getLogger(__name__)

MODEL = os.environ.get("EXSIM_TL_IMPORT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("EXSIM_TL_IMPORT_EFFORT", "medium")
# 1回の取り込みで Claude に投げるリクエスト数の上限(費用の上限にもなる)
MAX_TURNS = int(os.environ.get("EXSIM_TL_IMPORT_MAX_TURNS", "12"))
MAX_TOKENS = 32000
# list_characters を絞り込みなしで呼ばれた時に、全生徒(約280件)を返して入力トークンを浪費しないようにする
LIST_LIMIT = 40
DEFAULT_TITLE = "TL取り込み"

# 安全性の判定で断られた場合に、Anthropic推奨の別モデルでサーバー側で再試行させる
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = tl_tools.INSTRUCTIONS + """
あなたは exsim の webui の「TL取り込み」ページから呼ばれている。利用者に質問はできない。
- 曖昧な点(衣装違い・対象・初期順など)は最も妥当な解釈で進め、仮定したことを最後の報告に書く。
  利用者の補足があればそれに従う。
- 必ず simulate_tl を実行して終える。最後に実行した simulate_tl の結果がそのまま利用者に渡る
  (この環境では share_url は返らない)。
- TLとして読めない入力なら、ツールを使わずにその旨を短く返す。
- 最後の返答は利用者向けの短い日本語の報告にする: 読み込めたか、仮定した点、止まった場合はその手順と理由。
  手順の一覧やリンクは書かない(画面に別に表示される)。
"""


class ListCharactersArgs(BaseModel):
    query: str = Field("", description="キー・表示名の部分一致で絞り込む文字列")


class FindInitialOrdersArgs(BaseModel):
    characters: List[str]
    steps: List[StepInput]
    hand_size: int = 3
    max_results: int = 10


class SimulateTLArgs(BaseModel):
    characters: List[str]
    steps: List[StepInput]
    hand_size: int = 3
    title: str = Field(DEFAULT_TITLE, description="exsimに表示するTLの名前(編成など)")
    env: Optional[Dict[str, Any]] = None


_ARGS = {
    "list_characters": ListCharactersArgs,
    "find_initial_orders": FindInitialOrdersArgs,
    "simulate_tl": SimulateTLArgs,
}

# 順序・内容を固定してプロンプトキャッシュを効かせる
TOOLS = [
    {
        "name": name,
        "description": tl_tools.DESCRIPTIONS[name],
        "input_schema": model.model_json_schema(),
        # ストリーミング時は入力を逐次受け取る。その代わり入力の検証はこちらで行う(_run_tool)
        "eager_input_streaming": True,
    }
    for name, model in _ARGS.items()
]


class TLImportError(Exception):
    """利用者にそのまま見せてよい失敗(Claudeが断った、応答が長すぎた等)"""


@dataclass
class ImportResult:
    summary: str  # Claudeから利用者への報告
    simulated: bool  # simulate_tl が1回以上実行できたか
    ok: bool  # 最後の simulate_tl が最後まで破綻なく回ったか
    error: Optional[Dict[str, Any]]  # 最後の simulate_tl が止まった地点
    share: Optional[str]  # webuiの #share= に渡す文字列
    usage: Dict[str, int] = field(default_factory=dict)


def import_rough_tl(
    tl_text: str,
    notes: str = "",
    client: Optional[anthropic.Anthropic] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> ImportResult:
    """ラフなTLを Claude に解釈・実行させ、最後に実行した simulate_tl の結果を返す。"""
    client = client or anthropic.Anthropic()
    progress = on_progress or (lambda message: None)
    messages: List[Dict[str, Any]] = [{"role": "user", "content": _user_message(tl_text, notes)}]
    usage = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "requests": 0}
    last_out: Optional[Dict[str, Any]] = None
    last_save: Optional[Dict[str, Any]] = None
    summary = ""

    for _ in range(MAX_TURNS):
        progress("Claudeが考えています")
        response = _request(client, messages)
        _add_usage(usage, response.usage)

        # 断られた・途中で切れた応答のツール呼び出しは入力が不完全な可能性があるので実行しない
        if response.stop_reason == "refusal":
            raise TLImportError("ClaudeがこのTLの処理を断りました。")
        if response.stop_reason == "max_tokens":
            raise TLImportError("Claudeの応答が長すぎて途中で切れました。TLを分けて試してください。")

        messages.append({"role": "assistant", "content": response.content})
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            summary = "\n".join(b.text for b in response.content if b.type == "text").strip()
            break

        results = []
        for block in tool_uses:
            content, is_error, simulated = _run_tool(block.name, block.input, progress)
            if simulated is not None:
                last_out, last_save = simulated
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        # 並列のツール呼び出しの結果は1つのメッセージにまとめて返す
        messages.append({"role": "user", "content": results})
    else:
        summary = "Claudeとのやり取りが上限回数に達したため、途中で打ち切りました。"

    logger.info("TL取り込み: model=%s usage=%s", MODEL, usage)
    return ImportResult(
        summary=summary,
        simulated=last_save is not None,
        ok=bool(last_out and last_out["ok"]),
        error=last_out["error"] if last_out else None,
        share=tl_import.encode_share(last_save) if last_save is not None else None,
        usage=usage,
    )


def _user_message(tl_text: str, notes: str) -> str:
    text = f"以下のTLをexsimに読み込んでください。\n\n<tl>\n{tl_text}\n</tl>"
    if notes.strip():
        text += f"\n\n利用者の補足:\n<notes>\n{notes}\n</notes>"
    return text


def _request(client: anthropic.Anthropic, messages: List[Dict[str, Any]]):
    for attempt in range(2):
        try:
            with client.beta.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": EFFORT},
                cache_control={"type": "ephemeral"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                return stream.get_final_message()
        except ValueError:
            # ツール入力のJSONが読めないほど壊れていた(eager_input_streaming)。1回だけ再リクエストする
            if attempt:
                raise TLImportError("Claudeの応答を読み取れませんでした。もう一度試してください。")
    raise AssertionError("unreachable")


def _run_tool(name: str, raw_input: Any, progress: Callable[[str], None]):
    """(tool_resultの内容, is_error, simulate_tl の (結果, セーブデータ) または None) を返す。"""
    model = _ARGS.get(name)
    if model is None:
        return f"未知のツールです: {name}", True, None
    try:
        args = model.model_validate(raw_input)
    except ValidationError as e:
        # 入力が壊れている・スキーマに合わない場合は実行せず、Claudeに直させる
        return _dump({"INVALID_INPUT": raw_input, "errors": e.errors(include_url=False)}), True, None

    if isinstance(args, ListCharactersArgs):
        progress(f"生徒を照合しています: {args.query or '(全員)'}")
        return _dump(tl_tools.list_characters(args.query, limit=LIST_LIMIT)), False, None
    if isinstance(args, FindInitialOrdersArgs):
        progress("初期の手札順を探しています")
        out = tl_tools.find_initial_orders(args.characters, args.steps, args.hand_size, args.max_results)
        return _dump(out), False, None

    progress(f"シミュレーションしています({len(args.steps)}手)")
    out, save = tl_tools.simulate_tl(args.characters, args.steps, args.hand_size, args.title, args.env)
    if save is None:  # 生徒名が不明など、実行前に弾かれた
        return _dump(out), True, None
    return _dump(out), False, (out, save)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _add_usage(total: Dict[str, int], usage: Any) -> None:
    total["requests"] += 1
    total["input"] += usage.input_tokens or 0
    total["output"] += usage.output_tokens or 0
    total["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
    total["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
