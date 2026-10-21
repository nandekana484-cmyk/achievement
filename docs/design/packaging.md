# 本番の形(exe)とバックアップの設計メモ

開発指針(docs/spec.md)の 9(バックアップ・ログ・常時稼働)と 10(配布・運用)の、実装の判断の理由と手順の細かい内容。
対象は `packaging/`、`backend/app/server.py`、`backend/app/core/config.py`、`backend/app/services/backup.py`。

## フォルダと基準のフォルダ(GENBA_HOME)

```
C:\GenbaApp\                  ← 基準のフォルダ(GENBA_HOME)
  app\v1.0.0\GenbaApp.exe     ← 版ごとのフォルダ(zip を C:\GenbaApp\app\ に展開する)
  app\v1.0.0\_internal\       ← exe が使うファイル(Python、ライブラリ、画面、マイグレーション、tzdata)
  data\config.toml
  data\genba.db               ← 本番DB(config.toml の paths.database。既定 data/genba.db)
  exchange\                   ← 連携フォルダ(paths.exchange_dir)
  logs\genba.log              ← ログ(paths.log_dir)。日ごとに genba.log.2026-10-21 などに分かれる
```

- 基準のフォルダ: exe では環境変数 `GENBA_HOME`、無ければ exe の2つ上(`app\v1.0.0\` の上の上)。版のフォルダを増やしても、データは版の外に1つだけ置ける
- config.toml は `<基準>\data\config.toml`(環境変数 `GENBA_CONFIG` で変えられる)。中の相対パスは、基準のフォルダから見た位置にする。絶対パス(`C:/...`、`//server/share/...`)はそのまま
- 開発中(exe でないとき)は、`GENBA_HOME` があればそれ、無ければ今までどおり起動したフォルダ(backend)が基準。exe と同じ形を開発中に試すときは `GENBA_HOME` を設定する
- config.toml は BOM 付きの UTF-8 でも読める(メモ帳の「UTF-8(BOM 付き)」や PowerShell 5.1 の `Out-File -Encoding utf8` は BOM を付けるため)。書き方に誤りがあれば、ファイルの場所と行を出して起動しない

## ビルド(packaging/build.ps1)

開発者PCで、リポジトリ直下から実行する。

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1            # テストも行う
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1 -SkipTests # テストを省く(作り直すときだけ)
```

1. 画面のビルド(`npm run build`)
2. テスト(バックエンドの pytest と、画面の vitest。Playwright は時間がかかるので含めない。必要なら別に `npm run e2e`)
3. PyInstaller(`packaging/genba.spec`)。フォルダ形式(onedir)で `packaging\dist\v<版>\` に作る
4. zip(`packaging\dist\GenbaApp-v<版>.zip`。中は `v<版>\` のフォルダ)

- 版は `backend/app/__init__.py` の `__version__`。版を上げてからビルドする
- `packaging/build/`(作業用)と `packaging/dist/`(できたもの)は Git の対象外
- PyInstaller は requirements-dev.txt に入れる(ビルドのときだけ使う道具。作った exe には入らない)。ライセンスは GPL-2.0-or-later だが、ブートローダーに例外があり、作った exe には GPL が及ばない(開発指針 4 で採用済み)
- 同梱するもの(`genba.spec` の datas): 画面のビルド結果(`_internal\frontend_dist`)、マイグレーション(`_internal\app\db\migrations`。alembic はファイルとして読むため)、時刻帯のデータ(tzdata。Windows には無いため)
- 隠れた import(動的に読まれるもの): `app` のすべて、uvicorn、alembic(testing を除く)、SQLite の dialect
- 入口は `packaging/entry.py` → `backend/app/server.py` の `main()`(開発中も `python -m app.server` で同じ形に起動できる)。ログを整えてから、config.toml の host と port で uvicorn を起動する

### コンソールを出すか

- 今はコンソールを出す形(`console=True`)。手で起動したときに、ログを画面でも確かめられるため
- タスクスケジューラで SYSTEM として動かすと、利用者の画面にはウィンドウは出ない(別のセッションで動く)。ログは `logs\genba.log` で確かめる
- 利用者として動かす(`install-autostart.ps1 -User`)とコンソールのウィンドウが出る。閉じるとアプリが止まるので、そうする場合は `console=False` でビルドする形を検討する

## テスト用の時計

- exe(`sys.frozen`)では、`GENBA_CLOCK_START` と `GENBA_TEST_MODE` を設定しても無視し、本物の時計を使う(警告をログに出す。`app/core/clock.py`)。本番で誤って設定されても、実績の時刻がずれないようにするため

## バックアップ(app/services/backup.py)

- SQLite のバックアップ機能(`sqlite3.Connection.backup`)で取る。起動中のDBのファイルのコピーは、書き込みの途中を写すおそれがあるのでしない
- 保存先は config.toml の `paths.backup_dir`(共有フォルダを想定)。未設定・書き込めないときは、警告をログに出してアプリは止めない
- 取るとき
  - 起動したとき(`main.py` の lifespan。DBの構造の更新(マイグレーション)の前)。更新に失敗したときに、更新の前のDBに戻せるようにするため。DBがまだ無い(初めての起動)ときは取らない
  - 毎日 `backup.daily_at`(既定 12:30)。昼休みなど、記録の少ない時刻にする
- ファイル名: `genba_<年月日>_<時分秒>_<startup|daily>.db`。書き終えるまでは `.tmp` の名前で書き、書き終えてから改名する(書きかけのファイルをバックアップと取り違えないように)
- 世代: `backup.keep`(既定 30)を超えたら古い順に消す。消すのは、保存先の中の、上の名前の形のファイルだけ(共有フォルダにほかのファイルがあっても消さない)
- 戻すとき: アプリを止める → `data\genba.db` を、選んだバックアップのファイルで置き換える(`genba.db-wal`、`genba.db-shm` があれば消す)→ 起動する

## 担当者PCで使うスクリプト(packaging/)

どれも管理者権限が要る(スクリプトの先頭に `#Requires -RunAsAdministrator`)。PowerShell を「管理者として実行」してから動かす。
PowerShell 5.1 が日本語を正しく読めるよう、.ps1 は UTF-8(BOM 付き)・改行 CRLF で保存する。

| スクリプト | すること |
| --- | --- |
| `install-autostart.ps1 -Version v1.0.0` | タスクスケジューラに、PCの起動時に exe を起動するタスク(名前 GenbaApp)を登録する。SYSTEM で動かす(ログオンしていなくても動く)。止まったら1分後に起動し直す |
| `install-autostart.ps1 -Version v1.0.0 -User <利用者>` | 指定した利用者で動かす(パスワードを聞く)。共有フォルダにこのPCのコンピューターアカウントの書き込み権限が無いときに使う |
| `uninstall-autostart.ps1` | 上のタスクを止めて外す |
| `firewall-allow.ps1 -Port 8000` | 受信の TCP のそのポートだけを許可する(ドメインとプライベートのプロファイル)。ポートは config.toml の server.port と合わせる |
| `firewall-remove.ps1` | 上の許可を消す |

## 初めて置くとき(担当者PC)

1. `C:\GenbaApp\app\` に zip を展開する(`C:\GenbaApp\app\v1.0.0\GenbaApp.exe` になる)
2. `C:\GenbaApp\data\config.toml` を作る(リポジトリの `config.example.toml` をもとに、`legacy_app_dir`、`backup_dir`、ポートを書く)
3. 管理者の PowerShell で `install-autostart.ps1 -Version v1.0.0` と `firewall-allow.ps1 -Port <ポート>`
4. `Start-ScheduledTask -TaskName GenbaApp` で起動し、ブラウザで `http://<担当者PC>:<ポート>/api/health` が ok を返すことを確かめる

## 版を更新するとき(担当者PC)

1. `Stop-ScheduledTask -TaskName GenbaApp`(止める)
2. 新しい版の zip を `C:\GenbaApp\app\` に展開する(旧版のフォルダは残す)
3. `install-autostart.ps1 -Version <新しい版>` で登録し直す
4. `Start-ScheduledTask -TaskName GenbaApp`。起動時にバックアップ(`*_startup.db`)を取ってから、DBの構造を更新する
5. `/api/health` の version が新しい版になっていることを確かめる
6. 問題があれば、止める → 旧版で登録し直す → `data\genba.db` を更新の前のバックアップ(`*_startup.db`)に戻す → 起動する

## このPCでの確認の結果(2026-10-21、MSI)

- 一時フォルダを `GENBA_HOME` にして起動し、/api/health(ok)と画面(ライン選択)を確かめた。DBは `GENBA_HOME\data\genba.db` に作られ、開発用DBには触れなかった
- 2回目の起動で、`backup\genba_<日時>_startup.db` ができた
- `GENBA_TEST_MODE=1` と `GENBA_CLOCK_START` を設定しても、本物の時計を使った
- 大きさ: フォルダ 39.3 MB(GenbaApp.exe 単体 13.0 MB)、zip 23.3 MB。起動(/api/health が返るまで)は約1.5秒
