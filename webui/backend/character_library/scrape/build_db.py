"""
bluearchive.wikiru.jp の「星1/星2/星3キャラクター一覧」ページから生徒データと
アイコン画像を取得し、kivotos_db/characters.csv, characters.json,
kivotos_db/icon/*.png を生成する。

再実行すれば最新のページ内容で上書きされる(新規生徒の追加に追従できる)。
標準ライブラリのみで完結(requests/bs4等は使わない)。
"""

from __future__ import annotations

import csv
import html
import json
import re
import time
import urllib.request
from pathlib import Path

PAGE_URLS = [
    "https://bluearchive.wikiru.jp/?%E2%98%851",
    "https://bluearchive.wikiru.jp/?%E2%98%852",
    "https://bluearchive.wikiru.jp/?%E2%98%853",
]
BASE_URL = "https://bluearchive.wikiru.jp/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; kivotos_db-builder/1.0)"}

ROOT_DIR = Path(__file__).resolve().parent
ICON_DIR = ROOT_DIR / "icon"

COLUMNS = [
    "rarity",
    "image",
    "name",
    "weapon_type",
    "cover",
    "role",
    "position",
    "class_type",
    "school",
    "attack_type",
    "defense_type",
    "street_adaptation",
    "outdoor_adaptation",
    "indoor_adaptation",
    "range",
    "equipment1",
    "equipment2",
    "equipment3",
    "recruit_type",
    "obtain_type",
]

TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r'<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]*)"')
A_HREF_RE = re.compile(r'<a[^>]*href="([^"]+)"')
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def cell_text(cell_html: str) -> str:
    return html.unescape(TAG_RE.sub("", cell_html)).strip()


def sanitize_filename(name: str) -> str:
    # NTFS予約文字だけ念のため置換(通常の日本語名では発生しない想定)
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def parse_rows(page_html: str) -> list[dict]:
    table_start = page_html.index('<table id="sortabletable1"')
    table_end = page_html.index("</table>", table_start)
    table_html = page_html[table_start:table_end]

    tbody_start = table_html.index("<tbody>")
    tbody_html = table_html[tbody_start:]

    rows = []
    for tr_html in TR_RE.findall(tbody_html):
        tds = TD_RE.findall(tr_html)
        if len(tds) != len(COLUMNS):
            continue  # ヘッダ崩れ・想定外行はスキップ

        record = {}
        for col, td_html in zip(COLUMNS, tds):
            if col == "image":
                m = IMG_RE.search(td_html)
                record["icon_src"] = m.group(1) if m else ""
                icon_alt = html.unescape(m.group(2)) if m else ""
                icon_alt = re.sub(r"(_icon)?\.png$", "", icon_alt)
                record["icon_label"] = icon_alt
            elif col == "name":
                record["name"] = cell_text(td_html)
                m = A_HREF_RE.search(td_html)
                record["wiki_url"] = BASE_URL + m.group(1).lstrip("./") if m else ""
            else:
                record[col] = cell_text(td_html)

        name = record["name"]
        if "（" in name and name.endswith("）"):
            base_name, costume = name.split("（", 1)
            record["base_name"] = base_name
            record["costume"] = costume[:-1]
        else:
            record["base_name"] = name
            record["costume"] = ""

        rows.append(record)
    return rows


def download_icons(rows: list[dict]) -> None:
    ICON_DIR.mkdir(exist_ok=True)
    used_filenames: dict[str, int] = {}

    for i, record in enumerate(rows, start=1):
        src = record.pop("icon_src", "")
        if not src:
            record["icon_file"] = ""
            continue

        # icon_label(画像altに埋め込まれた実際のラベル)を優先。
        # 名前セルのテキストだけだと、ホシノ(臨戦)の防御型/攻撃型のように
        # 同名で別画像の行が衝突し、片方の画像を取りこぼす。
        label = record["icon_label"] or record["name"]
        stem = sanitize_filename(label)
        if stem in used_filenames:
            used_filenames[stem] += 1
            stem = f"{stem}_{used_filenames[stem]}"
            print(f"[warn] icon_label collision for no={i} name={record['name']!r}, using {stem}")
        else:
            used_filenames[stem] = 1

        filename = stem + ".png"
        dest = ICON_DIR / filename
        record["icon_file"] = f"icon/{filename}"

        if dest.exists():
            continue

        url = BASE_URL + src
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        print(f"[{i}/{len(rows)}] downloaded {filename}")
        time.sleep(0.3)  # サーバ負荷軽減


def write_outputs(rows: list[dict]) -> None:
    field_order = [
        "no",
        "name",
        "base_name",
        "costume",
        "rarity",
        "weapon_type",
        "cover",
        "role",
        "position",
        "class_type",
        "school",
        "attack_type",
        "defense_type",
        "street_adaptation",
        "outdoor_adaptation",
        "indoor_adaptation",
        "range",
        "equipment1",
        "equipment2",
        "equipment3",
        "recruit_type",
        "obtain_type",
        "icon_file",
        "icon_label",
        "wiki_url",
    ]
    for i, record in enumerate(rows, start=1):
        record["no"] = i

    ordered = [{k: r.get(k, "") for k in field_order} for r in rows]

    csv_path = ROOT_DIR / "characters.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_order)
        writer.writeheader()
        writer.writerows(ordered)

    json_path = ROOT_DIR / "characters.json"
    json_path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"wrote {csv_path} ({len(ordered)} rows)")
    print(f"wrote {json_path} ({len(ordered)} rows)")


def main() -> None:
    rows: list[dict] = []
    for url in PAGE_URLS:
        page_html = fetch(url)
        page_rows = parse_rows(page_html)
        print(f"parsed {len(page_rows)} characters from {url}")
        rows.extend(page_rows)
        time.sleep(0.3)  # サーバ負荷軽減
    download_icons(rows)
    write_outputs(rows)


if __name__ == "__main__":
    main()
