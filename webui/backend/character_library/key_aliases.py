"""SchaleDBのPathName由来キーと、webui側で手動キュレーション済みのキーとで
表記が異なるために同一キャラが重複登録されてしまうものの対応表。

build_library.py(アイコンコピー時の重複防止)と main.py(BUILTINSマージ時の
重複防止)の両方から参照する、唯一の対応表。

キー: build_library.py が PathName から機械的に生成するキー
値: webui/backend/main.py の BUILTINS で手動定義されているキー
"""

from __future__ import annotations

from typing import Dict

GENERATED_KEY_ALIASES: Dict[str, str] = {
    # 英語圏コミュニティ表記 "Alice" vs SchaleDB公式ローマ字 "Aris"
    "Aris_Battle": "Alice_Battle",
    "Kei": "Key",
    "Hoshino_Battle_Dealer": "Hoshino_Battle_Attack",
    "Hoshino_Battle_Tank": "Hoshino_Battle_Defence",
}
