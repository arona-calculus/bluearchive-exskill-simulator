# VPSデプロイ情報

exsim（webui）をConoHa VPS上で常時稼働・公開している構成のメモ。
VPS・Cloudflare・ファイアウォールはdoujin-dbと共用しているので、共通部分の詳細は
doujin-db側の`docs/vps_deployment.md`を参照。

## 接続情報

- **VPS**: ConoHa VPS（サーバー名: `lakeside-vps`、Ubuntu 24.04 LTS、doujin-dbと同居）
- **SSH接続**: `ssh conoha`（`~/.ssh/config`にエイリアス設定済み、ユーザー`sagamino`）
- **公開URL**: https://exsim.sagamino.dev/
  - リモートMCP: https://exsim.sagamino.dev/mcp （claude.ai / Claude アプリのカスタムコネクタ用）
  - アプリは`FastAPI(root_path="/exsim")`を指定しているため、`/exsim/`配下
    （`https://exsim.sagamino.dev/exsim/`）でも同じものが開ける。ただし正規のURLはドメイン直下。
    フロントエンドは`window.location.pathname`が`/exsim`で始まるかでAPIの前置きを切り替えるので、
    どちらのURLでも動く
  - DNS: Cloudflare（`exsim.sagamino.dev` → VPSのIP、プロキシ済み）
  - TLS: Cloudflare Origin証明書をVPS側 `/etc/ssl/cloudflare/exsim.sagamino.dev.{pem,key}` に設置し、
    nginxで終端（Cloudflare SSL/TLSモードはdoujin-dbと同じFull (strict)）

## サーバー構成

- **アプリ本体**: `/home/sagamino/bluearchive-exskill-simulator`
  （GitHubリポジトリ `arona-calculus/bluearchive-exskill-simulator` をHTTPSでclone、`main`ブランチを稼働）
- **データファイル**: 無し。生徒アイコン（`webui/assets/icons/`）もgit管理なので、
  doujin-dbのようなUnison同期は不要。`git pull`だけで最新状態になる。
- **セッション**: シミュレーションのセッションはプロセスのメモリ上（`sessions`辞書）にのみ保持される。
  再起動すると利用中のセッションは消える。リモートMCPはステートレス（`stateless_http`）なので、
  再起動をまたいでもそのまま呼べる。
- **常時稼働**: systemdサービス `exsim.service`（`/etc/systemd/system/exsim.service`、`enabled`済み）

  ```ini
  [Unit]
  Description=BA ExSkill Simulator FastAPI app
  After=network.target

  [Service]
  Type=simple
  User=sagamino
  Group=sagamino
  WorkingDirectory=/home/sagamino/bluearchive-exskill-simulator
  ExecStart=/home/sagamino/.local/bin/uv run --extra webui uvicorn webui.backend.main:app --host 127.0.0.1 --port 9001
  Restart=on-failure
  RestartSec=3
  Environment=HOME=/home/sagamino

  [Install]
  WantedBy=multi-user.target
  ```

  - `uv run --extra webui`でwebui用の依存（fastapi / uvicorn / mcp）を含めて起動。依存が変わっても
    起動時に`uv`が自動で同期するので、`uv sync`を手で叩く必要は基本的に無い
  - `mcp`パッケージが入っているので`/mcp`（リモートMCP）も同じプロセスで公開される
    （別プロセス・別ポートは無い）
  - `127.0.0.1:9001`で待受け（外部からは直接見えない。doujin-dbは`9000`）
  - `--reload`は付けていない（コードを更新したら手動で再起動する）
  - `Restart=on-failure`でクラッシュ時も3秒後に自動復帰
  - 環境変数は`HOME`のみ。`EXSIM_BASE_URL` / `EXSIM_MCP_ALLOWED_HOSTS`等は設定していない
    （共有リンクの宛先はリクエストの`Host`・`X-Forwarded-Proto`から推定される。各変数の意味は
    `docs/architecture.md`を参照）

## リバースプロキシ（nginx）

設定ファイル: `/etc/nginx/sites-available/exsim.sagamino.dev`（`sites-enabled`にシンボリックリンク）。
doujin-db（`circle.sagamino.dev`）とは別のserver blockで、同じnginxが`server_name`で振り分けている。

- 80番はHTTPSへの301リダイレクトのみ
- 443番（`ssl http2`）で全パスを`127.0.0.1:9001`にそのままproxy_pass（パスの書き換え無し）
- `client_max_body_size 20m`

```nginx
location / {
    proxy_pass http://127.0.0.1:9001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`X-Forwarded-Prefix`は送っていないので、MCPの共有リンクは「`/exsim/mcp`宛てに届いた時だけ`/exsim`を
付ける」判定になり、通常の`/mcp`経由ではドメイン直下（`https://exsim.sagamino.dev/`）を向く。

## アプリの更新方法

```bash
ssh conoha
cd ~/bluearchive-exskill-simulator
git pull
sudo systemctl restart exsim
```

`pyproject.toml` / `uv.lock`が変わった場合も、上記の再起動時に`uv run`が依存を同期する。

## 状態確認・ログ

```bash
sudo systemctl status exsim --no-pager   # アプリの起動状態
sudo journalctl -u exsim -f              # アプリのログをリアルタイム表示
systemctl cat exsim                      # ユニット定義の確認
ss -tlnp | grep 9001                     # 9001番で待受けているか
curl -s http://127.0.0.1:9001/api/specs | head -c 200   # VPS内からのAPI疎通確認
sudo nginx -t                            # nginx設定の構文チェック（変更後は必須）
```

ユニットファイルを編集した場合は`sudo systemctl daemon-reload`の後に`restart`する。
