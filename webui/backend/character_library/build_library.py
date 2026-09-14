"""キャラクターライブラリ生成スクリプト

SchaleDB由来のID/PathName/Nameデータ(bluearchive-timeline-simulator)と、
build_db.py(wikiruスクレイパー、scrape/配下。このリポジトリ内で完結し、
外部リポジトリには依存しない)が生成したキャラクターデータ・アイコン実体を
突き合わせ、webui用のキャラクターライブラリ(character_library/data/characters.json)
とアイコン(webui/assets/icons/)を生成する。

実行方法:
  cd bluearchive-exskill-simulator
  python webui/backend/character_library/scrape/build_db.py  # 先にwikiru.jpから再取得
  python -m webui.backend.character_library.build_library
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .key_aliases import GENERATED_KEY_ALIASES

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
_WEBUI_DIR = _BACKEND_DIR.parent
_SIMULATOR_DIR = _WEBUI_DIR.parent
_WORKSPACE_DIR = _SIMULATOR_DIR.parent  # millennium-science-school

DEFAULT_SCHALEDB_PATH = (
    _WORKSPACE_DIR / "bluearchive-timeline-simulator" / "data" / "student_db_from_schaledb.json"
)
DEFAULT_SCRAPE_PATH = _THIS_DIR / "scrape" / "characters.json"
DEFAULT_SCRAPE_ICON_DIR = _THIS_DIR / "scrape" / "icon"
DEFAULT_OUTPUT_DIR = _THIS_DIR / "data"
DEFAULT_ICONS_DIR = _WEBUI_DIR / "assets" / "icons"

ATTACK_KEYWORDS = ("attack", "dealer")
DEFENSE_KEYWORDS = ("defense", "defence", "tank")


def pathname_to_key(path_name: str) -> str:
    """SchaleDBのPathName(例: hoshino_battle_dealer)をBUILTINSキー形式(Hoshino_Battle_Dealer)に変換する。"""
    parts = re.split(r"[_\-]+", path_name.strip())
    return "_".join(p.capitalize() for p in parts if p)


def _keyword_score(path_name: str, candidate: Dict[str, Any]) -> int:
    """PathNameと候補(icon_label/class_type)のキーワード一致度。高いほど良い一致。"""
    text = (candidate.get("icon_label") or "") + (candidate.get("class_type") or "")
    lower_path = path_name.lower()
    score = 0
    if any(k in lower_path for k in ATTACK_KEYWORDS):
        score += 1 if ("攻撃" in text or candidate.get("class_type") == "アタッカー") else 0
        score -= 1 if ("防御" in text or candidate.get("class_type") == "タンク") else 0
    if any(k in lower_path for k in DEFENSE_KEYWORDS):
        score += 1 if ("防御" in text or candidate.get("class_type") == "タンク") else 0
        score -= 1 if ("攻撃" in text or candidate.get("class_type") == "アタッカー") else 0
    return score


def resolve_match(
    entry: Dict[str, Any], candidates: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """SchaleDBの1エントリに対し、同名のスクレイプ候補群から最適な1件を選ぶ。
    一意に決定できない場合は None を返す(=要手動確認)。
    """
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None

    # 1. PersonalNameがicon_labelに現れるものを優先(双子キャラ等、Name列が同一でも
    #    PersonalName/icon_labelでは区別できるケース)。base_nameはスクレイパー側の
    #    仕様で双子キャラ間でも同一値になることがあるため使わない。
    personal_name = entry.get("PersonalName") or ""
    by_personal = [
        c for c in candidates if personal_name and personal_name in (c.get("icon_label") or "")
    ]
    if len(by_personal) == 1:
        return by_personal[0]
    pool = by_personal if by_personal else candidates

    # 2. PathNameのキーワード(attack/dealer, tank/defense等)とicon_label/class_typeの一致度で選ぶ
    path_name = entry.get("PathName") or ""
    scored = sorted(pool, key=lambda c: _keyword_score(path_name, c), reverse=True)
    if len(scored) >= 2 and _keyword_score(path_name, scored[0]) > _keyword_score(path_name, scored[1]):
        return scored[0]
    if len(scored) == 1:
        return scored[0]
    return None


def build(
    schaledb_path: Path,
    scrape_path: Path,
    scrape_icon_dir: Path,
    output_dir: Path,
    icons_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    with schaledb_path.open(encoding="utf-8") as f:
        schaledb: Dict[str, Dict[str, Any]] = json.load(f)
    with scrape_path.open(encoding="utf-8") as f:
        scraped: List[Dict[str, Any]] = json.load(f)

    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for row in scraped:
        by_name.setdefault(row.get("name"), []).append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        icons_dir.mkdir(parents=True, exist_ok=True)

    library: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    copied = 0

    for entry in schaledb.values():
        name = entry.get("Name")
        path_name = entry.get("PathName") or ""
        key = pathname_to_key(path_name) if path_name else None
        if key:
            key = GENERATED_KEY_ALIASES.get(key, key)
        label = name or f"{entry.get('FamilyName', '')}{entry.get('PersonalName', '')}"

        candidates = by_name.get(name, [])
        match = resolve_match(entry, candidates)

        icon_copied = False
        if key and match and match.get("icon_file"):
            src = scrape_icon_dir / Path(match["icon_file"]).name
            dest = icons_dir / f"{key}.png"
            if src.is_file():
                if dest.is_file():
                    # 既存アイコン(手動キュレーション済みの24件を含む)は上書きしない
                    icon_copied = True
                elif not dry_run:
                    shutil.copyfile(src, dest)
                    icon_copied = True
                else:
                    icon_copied = True

        record = {
            "id": entry.get("Id"),
            "key": key,
            "label": label,
            "personal_name": entry.get("PersonalName") or "",
            "path_name": path_name,
            "base_name": match.get("base_name") if match else None,
            "costume": match.get("costume") if match else None,
            "role": match.get("role") if match else None,
            "icon_copied": icon_copied,
        }
        library.append(record)
        if not key or not match or not icon_copied:
            unmatched.append({**record, "candidate_count": len(candidates)})
        if icon_copied:
            copied += 1

    # ラベルの重複を解消する(例: 双子キャラ「シュン(水着)」「シュエリン(水着)」は
    # SchaleDBのName列がどちらも同じで、PersonalNameでしか区別できない)
    label_counts: Dict[str, int] = {}
    for r in library:
        label_counts[r["label"]] = label_counts.get(r["label"], 0) + 1
    for r in library:
        if label_counts.get(r["label"], 0) > 1 and r.get("personal_name"):
            r["label"] = f"{r['label']}[{r['personal_name']}]"

    if not dry_run:
        with (output_dir / "characters.json").open("w", encoding="utf-8") as f:
            json.dump(library, f, ensure_ascii=False, indent=2)
        with (output_dir / "unmatched.json").open("w", encoding="utf-8") as f:
            json.dump(unmatched, f, ensure_ascii=False, indent=2)

    return {
        "total": len(schaledb),
        "matched_and_copied": copied,
        "unmatched": len(unmatched),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schaledb-path", type=Path, default=DEFAULT_SCHALEDB_PATH)
    parser.add_argument("--scrape-path", type=Path, default=DEFAULT_SCRAPE_PATH)
    parser.add_argument("--scrape-icon-dir", type=Path, default=DEFAULT_SCRAPE_ICON_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--icons-dir", type=Path, default=DEFAULT_ICONS_DIR)
    parser.add_argument(
        "--dry-run", action="store_true", help="ファイルを書き込まず集計のみ行う"
    )
    args = parser.parse_args()

    stats = build(
        schaledb_path=args.schaledb_path,
        scrape_path=args.scrape_path,
        scrape_icon_dir=args.scrape_icon_dir,
        output_dir=args.output_dir,
        icons_dir=args.icons_dir,
        dry_run=args.dry_run,
    )
    print(f"schaledb総数: {stats['total']}")
    print(f"マッチ&アイコンコピー成功: {stats['matched_and_copied']}")
    print(f"要手動確認(unmatched): {stats['unmatched']}")


if __name__ == "__main__":
    main()
