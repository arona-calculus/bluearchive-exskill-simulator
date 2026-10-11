# 現状のアーキテクチャ

`ba_exsim` は、ブルーアーカイブの EXスキル運用（手札のサイクル、ゲージ、対象指定、パッシブ誘発など）を
コードとして再現する**フォワードシミュレータ**である。ある局面 `State` に対してある操作（誰の
EXを誰に使うか）を適用すると、ゲーム内実装に沿った次の `State` が一意に決まる、という
純粋な状態遷移関数として実装されている。

コアパイプライン（`ba_exsim/core/`）は完成しており、新しい生徒を追加する場合も
基本的には `CharacterSpec` のサブクラスを1つ書けば足りる設計になっている。
一方で `ba_exsim/specs/` に実装済みの生徒は現時点でごく一部にとどまる。

## コアモジュール（`ba_exsim/core/`）

### `State`（`state.py`）
- `frozen=True` の immutable dataclass。
- `cards: Tuple[Optional[str], ...]` — 手札 + 山札を1本のタプルで表現する。
- `hand_size: int`（デフォルト3）— 手札枚数。`cards`上の手札/山札の境界はこの値に基づく。
- `hand` / `deck` — `cards[:hand_size]` / `cards[hand_size:]` を返す導出プロパティ。
  手札/山札の境界が必要な箇所は**必ずこちらを使い、`cards`を生でスライスしない**こと
  （過去に`cards[:3]`等の決め打ちが複数箇所に重複し、`hand_size!=3`でカードが消失する
  バグを生んだため）。
- `env: Dict[str, Any]` — ゲージ・対象・保留フラグなど生徒固有の状態を自由に持たせる汎用領域
  （例: `alice_charge`, `hanako_gauge`, `rio_copy_target`, `pending_force_draw`）。
- ミューテーションは `update()` / `discard_card()` / `draw_card()` の3メソッドのみを経由し、
  常に新しい `State` を返す。

### `CharacterSpec`（`spec.py`）
生徒ごとの挙動を差し込むためのフックを定義する基底クラス。パイプライン順に:

1. `should_cycle` — 効果適用前の状態で判定する「破棄・ドローを行うか」の意思決定
2. `get_in_hand_transform` — 手札にいる状態での変身（現状未使用）
3. `apply_effect` — ゲージ増減・バフなど効果本体
4. `get_discard_transform` — 山札の底に捨てられる際の変身先
5. `on_draw_intercept` — ドローへの割り込み（置換ドロー）
6. `on_passive` — 他キャラのEX使用時に誘発するパッシブ
7. `get_cost` — 「今」使った場合の消費コストを返す（コピー元に応じて変わるリオ(コピー)や、
   形態によって変わるイブキ(水着)のEX2などはオーバーライドする。既定値は `self.cost`）

サブクラスは必要なフックだけをオーバーライドする。

### `GameEngine`（`engine.py`）
`play_card(state, k, target)` が上記フックを固定順序で呼び出す。
`should_cycle` を**効果適用前の状態**で評価する点が実装上の要点で、
「使用する意思決定」と「効果適用後の結果」を明確に分離している。

### `SpecRegistry`（`registry.py`）
名前→`CharacterSpec` の辞書。初期化時に各 spec へ自分自身への参照を注入し
（`spec.registry`）、リオがコピー対象のspecを動的に引けるようにしている。
`evaluate_draw_intercepts` / `apply_passives` は全specに問い合わせるファンアウト処理。

### `Simulator`（`simulator.py`）
Registry + Engine の配線を隠すファサード。`initialize_state` / `play` / `play_by_name` を提供し、
テストコードや将来の探索アルゴリズムから直接叩ける高レベルAPIになっている。

## 実装済みの生徒（`ba_exsim/specs/`）

| ファイル | 内容 |
|---|---|
| `generic.py` | 特殊効果なしの生徒のデフォルト実装（常にサイクルするだけ）。webuiやテストで残りの編成枠を埋めるのに使う。 |
| `alice_battle.py` | 自己対象でチャージ蓄積（上限2）、他対象でチャージリセット。 |
| `rio.py` | `RioSpec`（自己を `Rio_Copy` に書き換え、非サイクル）+ `RioCopySpec`（`is_proxy=True`。Registry経由でコピー対象のspecを引き、その `apply_effect` を代理実行し、破棄時に `Rio` へ戻る）。コピースキルの中核ロジック。 |
| `hanako_swimsuit.py` | ゲージ制の居座り（自己使用時: ゲージ100以上で消費して手札維持）、Rioコピー等の代理実行時は「保留強制ドロー」を発行、他キャラのEX使用（非proxy限定）でゲージ+40（上限200）のパッシブ加算。 |
| `ibuki_swimsuit.py` | 2段階EX。EX1でお友達（味方ストライカー最大2人）を指定し即時再ドロー、以降EX2として振る舞う。お友達がカードを使用する度に「貝殻」蓄積のパッシブ（12個で以降増加しない）。コストもEX1/EX2で異なる（`get_cost`）。 |

固有ロジックを持つのはこの4体のみで、それ以外は全て `GenericSpec`
（挙動は常にサイクルするだけだが、`cost`/`role` は後述の `character_library` 由来の実データを持つ）。
`rio.py` × `hanako_swimsuit.py` の組み合わせシナリオ（`rio_hanako/`, `kurokage/`）
まで揃っており、フック機構が複数生徒の相互作用（パッシブ誘発・代理実行・割り込みドローの重なり）
に耐えることは検証済み。`kurokage/` は特定ボス（黒影/Kurokage）の実際のTLをそのまま
再現する回帰シナリオ。似た総当り探索ツール `scripts/d33_kurokage_elastic_search.py` は
pytestの回帰テストではなく、TL候補を広く探索するためのスクリプトなので `tests/` には置いていない。

## テストと検証データ（`tests/`）

動作検証に使うデータ（編成・初期の手札+山札順・手順・各ステップの期待値）は、テストコードに直接書かず
`tests/data/scenarios/` 以下にTOMLで置く（1ファイル = 1シナリオ）。`test_scenarios.py` が全ファイルを
1件ずつのテストとして実行するので、**シナリオの追加はTOMLを1つ置くだけ**でよい。

- 実行と照合は `tests/scenario.py`。`slot` のステップは `Simulator.play`、`card` だけのステップは
  `Simulator.play_by_name` で実行する。消費コストは使用前の状態で評価する（webuiの `/play` と同じ規約）。
- 生徒のSpecは、固有Specを持つ4体（`CUSTOM_SPECS`）以外は `GenericSpec`。コスト・役割は
  シナリオの `[overrides.<生徒>]` で与え、生成データ（`characters.json`）には依存しない（再生成しても壊れない）。
- 期待値は書いた項目だけを照合する（`cards` / `hand` / `deck` / `hand_excludes` / `env` / `env_none` /
  `cost` / `cost_unknown` / `error`）。TOMLにはnullが無いので、Noneの検査は `env_none` / `cost_unknown` で書く。
  未知のキーは書き間違いとみなしてロード時にエラーにする。
- 全ステップ共通の不変条件として、カードの消失・重複が無いこと（代理カードは元の生徒に戻して比較）を毎回検査する。
- 独自のSpecクラスが必要なテスト（`test_hanako.py` の `MockProxySpec`）や、`State` 単体のテストは Python のまま残す。

## キャラクターライブラリ生成（`webui/backend/character_library/`）

`BUILTINS`（生徒名→spec対応表）の大部分は手動実装ではなく、外部データから自動生成している。

1. `scrape/build_db.py` — wikiru.jp からアイコン・役割（STRIKER/SPECIAL）等をスクレイプする
   （このリポジトリ内で完結し、外部リポジトリに依存しない）。
2. `build_library.py` — 1の結果を SchaleDB 由来の生徒データ（PathName/ID/EXコスト等、
   `bluearchive-timeline-simulator/data/student_db_from_schaledb.json`）と名前で突き合わせ、
   `role`・`ex_cost_max`・`ex_extra_cost_max`（lv5時点のコスト、`Skills.Ex.Cost`/
   `ExtraSkills[0].Cost` の末尾）を抽出して `character_library/data/characters.json` に書き出す。
   同時にアイコン本体を `webui/assets/icons/` にコピーする（既存アイコンは上書きしない。
   手動キュレーション済みの生徒を保護するため）。
3. `main.py` 起動時に `characters.json` を読み込み、固有Specを持つ生徒（上の表）はそちらを優先、
   それ以外は `role`/`cost`/`extra_cost` 付きの `GenericSpec` として `BUILTINS` を構成する。

生徒固有のEXスキル実装（新規Specクラス）が必要になった場合は `main.py` の `BUILTINS` に
直接追記する。それ以外のメタデータ（アイコン・役割・コスト）は再生成で追従する。

## インタラクティブUI（`webui/`）

`webui/backend/main.py`（FastAPI）が `Simulator` をセッションベースのHTTP APIとして公開し、
`webui/frontend/index.html` から生徒アイコン付きで手動操作できる。対象指定が必要な生徒は
`NEEDS_TARGET` に列挙する。消費コスト・累計消費コストは `/play` 実行時にバックエンド側
（`CharacterSpec.get_cost`）で計算し、`history` の各エントリに保存する。
現状は**人間が1手ずつ操作するための確認ツール**であり、探索・最適化の機能は持たない。

## 姉妹リポジトリとの関係

同じ `millennium-science-school` 配下に以下があるが、扱っている問題が異なる。

- `bluearchive-timeline-simulator`: ダメージ確率分布・コスト整合性検証
  (`core/cost_validator.py`)・TLの完走確率計算 (`core/calc_tl_prob.py`) など、
  **既に組み立てられたTL**を数値的に評価/検証する側のツール群。
  `core/tl_optimizer.py` はダメージ足切りラインという**連続パラメータ**を
  Nelder-Meadで最適化する。
- `restart-opt-readme-minimal/minimal_tl`: 同種の閾値最適化をより最小構成で
  再実装したもの（Powell法）。

いずれも「操作列（どの手をどの順で打つか）」という**離散的な組み合わせ**を
探索する機能は持たない。`ba_exsim` が今後担うのはその部分であり、
役割は重複しない（[roadmap.md](roadmap.md) 参照）。
