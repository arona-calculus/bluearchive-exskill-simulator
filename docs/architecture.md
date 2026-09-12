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
- `cards: Tuple[Optional[str], ...]` — 手札3枚 + 山札を1本のタプルで表現する。
  慣習として `cards[:3]` が手札、`cards[3]` が次にドローされる山札の一番上。
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

対応済みなのはこの3体のみで、それ以外は全て `GenericSpec` 扱い。ただし
`rio.py` × `hanako_swimsuit.py` の組み合わせテスト（`test_rio_hanako.py`, `test_kurokage_tl.py`,
`test_d33_kurokage_elastic.py`）まで揃っており、フック機構が複数生徒の相互作用
（パッシブ誘発・代理実行・割り込みドローの重なり）に耐えることは検証済み。
`test_kurokage_tl.py` / `test_d33_kurokage_elastic.py` は特定ボス（黒影/Kurokage）の
実際のTLをそのまま再現する回帰テストになっている。

## インタラクティブUI（`webui/`）

`webui/backend/main.py`（FastAPI）が `Simulator` をセッションベースのHTTP APIとして公開し、
`webui/frontend/index.html` から生徒アイコン付きで手動操作できる。`BUILTINS` に
生徒名→specクラスの対応表があり、対象指定が必要な生徒は `NEEDS_TARGET` に列挙する。
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
