"""
生徒ごとの表示・入力形式の宣言(webui等のフロントエンドが参照する)。

シミュレーションの挙動には一切影響しない。各 CharacterSpec が自分の持つ env キーや
対象指定の形式をここの型で宣言し、フロントエンドはそれを汎用的に描画するだけにすることで、
生徒固有の表示をフロントエンドに直書きしないようにする。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class EnvDisplay:
    """
    state.env の1キーを状態バッジとしてどう表示するか。

    履歴の各ステップ(セーブ・共有リンク含む)は env しか保存しないため、表示は
    この宣言と env の値だけで決まるようにする(状態に依存する計算はさせない)。

    kind:
      - "gauge": 値/max のゲージ。complete_key の env が真なら満タン + complete_text で表示する
        (イブキの貝殻のように、上限到達で別フラグに移り値自体は0に戻るもの用)。
      - "characters": 値は生徒キー(またはそのリスト)。表示名に変換して表示する。
      - "text": 値をそのまま表示する(宣言の無いキーもこれ)。
      - "hidden": 表示しない(保留フラグや、他のバッジに統合して表示するキー)。
    color: ゲージと値の色。None ならフロントエンドの既定色。
    """

    key: str
    label: str = ""
    kind: str = "text"
    max: Optional[int] = None
    color: Optional[str] = None
    complete_key: Optional[str] = None
    complete_text: str = ""


@dataclass(frozen=True)
class CardDisplay:
    """
    BUILTINS に無い、Specが生み出すカード(リオ(コピー)等)の表示。

    icon_env_key: アイコンを、この env キーが指す生徒のアイコンで代用する(コピー先など)。
    grayscale: アイコンをグレースケールで表示する。
    """

    card: str
    label: str
    icon_env_key: Optional[str] = None
    grayscale: bool = False


@dataclass(frozen=True)
class TargetInput:
    """
    カードを使う時の対象指定の形式。状態によって変わり得る(イブキのEX1/EX2等)ため、
    CharacterSpec.target_input(state) が「今」の形式を返す。

    mode:
      - "single": 1人を選ぶ(未選択は空文字列)。
      - "multi": count 人まで選ぶ(カンマ区切りで渡す)。
      - "none": 対象指定なし。
    required: single なら未選択を、multi なら count 人ちょうどでない選択を許さない。
    error: required を満たさない時のメッセージ。
    include_self: 自分自身を「(自身)」付きで候補の先頭に加える。
    exclude_roles: 候補から外す役割("SPECIAL" 等)。役割が不明な生徒は外さない。
    """

    mode: str = "single"
    label: str = "ターゲット"
    required: bool = False
    error: str = ""
    count: int = 1
    include_self: bool = False
    exclude_roles: Tuple[str, ...] = ()
