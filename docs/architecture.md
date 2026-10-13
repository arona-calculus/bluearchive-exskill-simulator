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
8. `modify_cost` — 他の生徒のEXの消費コストを変化させる効果（ユズ(臨戦)のコスト半減など）。
   各カードの `get_cost` の後に全specへ順に問い合わせる（`SpecRegistry.evaluate_cost`）

サブクラスは必要なフックだけをオーバーライドする。

`owner` は「そのカードを使う生徒」で、通常は自分自身。リオ(コピー)は `owner="Rio"` で、
コピーの使用はリオのEXとして扱う（リオに付いたユズ(臨戦)のコスト半減が掛かり、回数も消費する）。

加えて、webui向けの表示・入力形式を宣言する（シミュレーションの挙動には影響しない。型は `display.py`）:

- `ENV_DISPLAYS`（クラス属性）— そのSpecが書き込む `env` キーを状態バッジとしてどう表示するか
  （ゲージ・生徒名・非表示など）。履歴の各ステップは `env` しか保存しないため、表示は宣言と
  `env` の値だけで決まる静的な宣言にしている。
- `CARD_DISPLAYS`（クラス属性）— そのSpecが生み出す、`BUILTINS` に無いカード（`Rio_Copy`）の
  表示名とアイコンの決め方。
- `target_input(state)` — 「今」使う場合の対象指定の形式（1人選択/複数選択/なし、必須か、
  候補から外す役割など）。イブキ(水着)のEX1/EX2のように状態で変わるためメソッドにしている。

フロントエンド（`index.html`）はこれらを汎用的に描画するだけで、生徒ごとの分岐を持たない。
新しい生徒の固有表示が必要になったら、Specにこれらを書けば足りる。

### `GameEngine`（`engine.py`）
`play_card(state, k, target)` が上記フックを固定順序で呼び出す。
`should_cycle` を**効果適用前の状態**で評価する点が実装上の要点で、
「使用する意思決定」と「効果適用後の結果」を明確に分離している。

### `SpecRegistry`（`registry.py`）
名前→`CharacterSpec` の辞書。初期化時に各 spec へ自分自身への参照を注入し
（`spec.registry`）、リオがコピー対象のspecを動的に引けるようにしている。
`evaluate_draw_intercepts` / `apply_passives` / `evaluate_cost` は全specに問い合わせるファンアウト処理。
消費コストは必ず `evaluate_cost` で求める（カード単体の `get_cost` だと他の生徒の効果が掛からない）。

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
| `yuzu_battle.py` | EXで自身以外の味方1人に「コスト半減（EXスキルの使用3回分、減少値は切り捨て）」を付与。生徒ごとに `{生徒: 残り回数}` で持ち、同じ生徒への掛け直しは3回に戻す。半減は `modify_cost`、回数の消費は `on_passive`。 |

固有ロジックを持つのはこの5体のみで、それ以外は全て `GenericSpec`
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
- 生徒のSpecは、固有Specを持つ5体（`CUSTOM_SPECS`）以外は `GenericSpec`。コスト・役割は
  シナリオの `[overrides.<生徒>]` で与え、生成データ（`characters.json`）には依存しない（再生成しても壊れない）。
- 期待値は書いた項目だけを照合する（`cards` / `hand` / `deck` / `hand_excludes` / `env` / `env_none` /
  `cost` / `cost_unknown` / `error`）。TOMLにはnullが無いので、Noneの検査は `env_none` / `cost_unknown` で書く。
  未知のキーは書き間違いとみなしてロード時にエラーにする。
- 全ステップ共通の不変条件として、カードの消失・重複が無いこと（代理カードは元の生徒に戻して比較）を毎回検査する。
- 独自のSpecクラスが必要なテスト（`test_hanako.py` の `MockProxySpec`）や、`State` 単体のテストは Python のまま残す。
- `tests/data/tl/` には実戦のラフTL（原文 `rough_tl` 付き、表示名混じり）を置く。webuiの実カタログを使い、
  `tl_import.run_tl` / MCP 経由で実行して `check_tl_result` で照合する。解釈が本人未確認のものは `verified = false` にする。
- `test_tl_import.py` は、エンジンの全シナリオを同じSpecで `run_tl` 経由でも実行し、エンジン直結と結果が一致することを確かめる。

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
3. `catalog.py` の import 時に `characters.json` を読み込み、固有Specを持つ生徒（上の表）はそちらを優先、
   それ以外は `role`/`cost`/`extra_cost` 付きの `GenericSpec` として `BUILTINS` を構成する。

生徒固有のEXスキル実装（新規Specクラス）が必要になった場合は `catalog.py` の `BUILTINS` に
直接追記する。それ以外のメタデータ（アイコン・役割・コスト）は再生成で追従する。

## インタラクティブUI（`webui/`）

生徒カタログ（`BUILTINS` / `build_specs`）と、1手実行して `history` エントリを作る
`play_and_record` は `webui/backend/catalog.py` にあり、FastAPIに依存しない（MCPサーバーと共有するため）。

`webui/backend/main.py`（FastAPI）が `Simulator` をセッションベースのHTTP APIとして公開し、
`webui/frontend/index.html` から生徒アイコン付きで手動操作できる。生徒固有の表示は
`/api/specs` の `env_displays`・`card_displays`（各Specの `ENV_DISPLAYS`・`CARD_DISPLAYS` を集めたもの）に、
対象指定の形式はカード選択時に `/api/session/{id}/target_input/{slot}`（`CharacterSpec.target_input`）に従う。
消費コスト・累計消費コストは `/play` 実行時にバックエンド側
（`SpecRegistry.evaluate_cost`）で計算し、`history` の各エントリに保存する。
webui自体は**人間が1手ずつ操作するための確認ツール**であり、探索・最適化の機能は持たない。

## MCPサーバー（`webui/backend/mcp_server.py`）

LLMエージェント（Claude Code等）からexsimを呼ぶための入口。ラフに書かれたTLの解釈はLLMに任せ、
サーバーは正規化済みの手順列を厳密に実行して結果を返す。状態は持たない。

```
uv run --extra mcp python -m webui.backend.mcp_server          # stdio。リポジトリ直下の .mcp.json にも登録済み
uv run --extra mcp python -m webui.backend.mcp_server --http   # HTTP単体(動作確認用)。既定 127.0.0.1:8765/mcp
```

**リモートMCP（webuiに同居）**: webui（`main.py`）は `mcp` パッケージがあれば `/mcp` で MCP を Streamable HTTP で
公開する。VPSでは webui をそのまま動かすだけで、claude.ai / Claude アプリのカスタムコネクタとして
`https://<ドメイン>/mcp`（`/exsim` の下で公開しているなら `/exsim/mcp`）を登録できる（常駐プロセスもリバースプロキシの経路も増やさない）。
TLの解釈は利用者自身の Claude が行い、サーバーはシミュレーションしかしないので、Claude の費用はかからない。
ツールは状態を持たないため、セッションを持たない形（stateless・JSON応答）で待ち受ける。
同期関数のツールはSDKがスレッドで実行するので、重い探索でも webui の応答は止まらない。

共有リンクの宛先は、`EXSIM_BASE_URL` が無ければリクエストから推定する（`X-Forwarded-Proto`・`Host`、
パスの前置きは `X-Forwarded-Prefix` か、`/exsim/mcp` 宛てに届いたなら `/exsim`。localhost 宛てなら `http://`）。

| 環境変数 | 内容 |
|---|---|
| `EXSIM_BASE_URL` | 共有リンクの宛先を固定する（例: `https://example.com/exsim/`）。推定が合わない時だけ設定する |
| `EXSIM_MCP_ALLOWED_HOSTS` | 受け付ける Host ヘッダー（カンマ区切り）。HTTP単体で localhost に待ち受けると SDK が localhost 宛て以外を 421 で拒否するため、プロキシの後ろに置くなら公開ドメインを指定する。webui同居では Host を検査しない（指定すれば検査する） |
| `EXSIM_MCP_ALLOWED_ORIGINS` | 受け付ける Origin ヘッダー（ブラウザから直接呼ばれる場合のみ必要） |

`GET /mcp` はサーバーからの通知用のストリームを開いたままにするため、死活監視には使えない
（`POST` で `{"jsonrpc":"2.0","id":1,"method":"ping"}` を送る）。

| ツール | 内容 |
|---|---|
| `list_characters(query)` | 生徒カタログの検索（キー・表示名の部分一致）。ラフな名前を正規のキーに対応付けるのに使う |
| `simulate_tl(characters, steps, ...)` | 初期の手札+山札順と手順列を実行し、各ステップの手札・ゲージ・コスト、破綻地点、webuiの共有リンクを返す |
| `find_initial_orders(characters, steps, ...)` | 手順列と矛盾しない初期順を総当りで探す（8枚まで。手札内の並びは同一視する） |

中核ロジックはMCPに依存しない `webui/backend/tl_import.py` に、ツールの中身と指示文は
下のTL取り込みページと共有する `webui/backend/tl_tools.py` にあり、`mcp_server.py` は薄いアダプタである。
- 名前は キー / 表示名（全角括弧・空白の揺れも許容）のどちらでも受け付け、未知の名前には候補を返す。
- リオのコピー使用は元の名前（`Rio`）で指定してよい（手札上の代理カード `Rio_Copy` に解決する）。
- 対象が必須か（`list_characters` の `needs_target`、対象未指定の警告）は webui と同じく
  `CharacterSpec.target_input(state).required` に従う（アリス(臨戦)の未指定 = 敵対象は警告しない）。
- 結果は webui の既存の共有リンク形式（`#share=` + gzip + base64url）にして返すので、開けばそのままwebuiに読み込まれる
  （リンク先は環境変数 `EXSIM_BASE_URL`、既定は `http://localhost:8000/`）。手順の `note` はwebuiのコメント欄に入る。

実際にサーバーをstdioで起動しての確認は `uv run --extra mcp python scripts/mcp_smoke.py`
（`tests/data/tl/` の全ケースを `simulate_tl` に流して期待値と照合し、各ケースの share_url を表示する）。
起動済みのHTTPサーバーには `--url http://127.0.0.1:8765/mcp` を付けて同じ確認ができる。

## TL取り込みページ（`webui/frontend/import.html`）

チャットを使わずに、webui上でラフなTLを貼るだけでexsimに読み込むためのページ。
サーバー（`webui/backend/tl_agent.py`）が Claude API に上のMCPと同じツール・指示文（`tl_tools.py`）を使わせ、
最後に実行した `simulate_tl` の結果を共有リンクの形でページに返す。利用者には質問できないため、
曖昧な点は Claude が妥当な解釈で進め、仮定した点を報告に書く（ページの「補足」欄で前提を渡せる）。

- APIキーはサーバーの持ち主のもの（`ANTHROPIC_API_KEY`）を全利用者で共有する。未設定ならページは無効表示になる。
- 解釈には数十秒〜数分かかるので、`POST /api/tl_import` はジョブを作って即座に返し、
  ページは `GET /api/tl_import/{job_id}` で進捗と結果をポーリングする（`tl_import_jobs.py`）。
- 費用の上限として、入力の長さ・IPごとの回数・1日の総数・同時実行数・1回あたりの往復回数を制限する。
  制限はプロセス内にしか持たないため、uvicorn はワーカー1つで動かす。リバースプロキシの後ろでは
  `--proxy-headers` を付けないと、IPごとの制限が利用者全員で共通になる。

| 環境変数 | 既定値 | 内容 |
|---|---|---|
| `ANTHROPIC_API_KEY` | （なし） | Claude APIのキー。未設定なら取り込みは無効 |
| `EXSIM_TL_IMPORT_MODEL` | `claude-opus-5-5` | 使うモデル |
| `EXSIM_TL_IMPORT_EFFORT` | `medium` | 考える深さ（`low`〜`max`）。上げるほど正確だが高くなる |
| `EXSIM_TL_IMPORT_MAX_TURNS` | `12` | 1回の取り込みで Claude に投げるリクエスト数の上限 |
| `EXSIM_TL_IMPORT_MAX_CHARS` | `6000` | TLと補足の合計文字数の上限 |
| `EXSIM_TL_IMPORT_PER_IP_PER_HOUR` | `10` | IPごとの1時間あたりの回数 |
| `EXSIM_TL_IMPORT_PER_DAY` | `100` | サーバー全体の1日あたりの回数 |
| `EXSIM_TL_IMPORT_MAX_CONCURRENT` | `2` | 同時に実行する取り込みの数 |

安全性の判定で断られた場合は、Anthropic推奨の別モデルでサーバー側で再試行させている（`fallbacks: "default"`）。
1回の取り込みで使ったトークン数はサーバーのログ（`webui.backend.tl_agent`）に出る。

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
探索する機能は持たない。`ba_exsim`（とそれをMCP経由で使うLLMエージェント）が今後担うのはその部分であり、
役割は重複しない（[roadmap.md](roadmap.md) 参照）。
