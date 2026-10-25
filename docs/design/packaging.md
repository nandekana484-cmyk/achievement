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
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1 -Console   # ウィンドウを出す形を v<版>-console に作る(困ったときの確認用)
```

1. 画面のビルド(`npm run build`)
2. テスト(バックエンドの pytest と、画面の vitest。Playwright は時間がかかるので含めない。必要なら別に `npm run e2e`)
3. PyInstaller(`packaging/genba.spec`)。フォルダ形式(onedir)で `packaging\dist\v<版>\` に作る
4. zip(`packaging\dist\GenbaApp-v<版>.zip`。中は `v<版>\` のフォルダ)

- 版は `backend/app/__init__.py` の `__version__`。版を上げてからビルドする
- `packaging/build/`(作業用)と `packaging/dist/`(できたもの)は Git の対象外
- PyInstaller は requirements-dev.txt に入れる(ビルドのときだけ使う道具。作った exe には入らない)。ライセンスは GPL-2.0-or-later だが、ブートローダーに例外があり、作った exe には GPL が及ばない(開発指針 0-8 で、この条件のビルドの道具は使ってよいとしている)
- 同梱するもの(`genba.spec` の datas): 画面のビルド結果(`_internal\frontend_dist`)、マイグレーション(`_internal\app\db\migrations`。alembic はファイルとして読むため)、時刻帯のデータ(tzdata。Windows には無いため)
- 隠れた import(動的に読まれるもの): `app` のすべて、uvicorn、alembic(testing を除く)、SQLite の dialect
- 入口は `packaging/entry.py` → `backend/app/server.py` の `main()`(開発中も `python -m app.server` で同じ形に起動できる)。ログを整えてから、config.toml の host と port で uvicorn を起動する

### ウィンドウを出すか

- 標準はウィンドウを出さない形(`console=False`)。自動起動で動かしても、担当者の画面にウィンドウが出ない(閉じて止めてしまうこともない)
- 困ったときの確認用に、`build.ps1 -Console` でウィンドウ(コンソール)を出す形を `v<版>-console` に作れる。手で起動すると、ログが画面にも出る
- どちらの形でも、ログは `<基準>\logs\genba.log` に出る。ウィンドウを出さない形では標準出力・標準エラーが無いので、ログはファイルにだけ出す

### 起動の失敗をログに残す(app/server.py)

- 設定(config.toml)を読む前から、`<基準>\logs\genba.log` にログを出し始める(config.toml の log_dir の既定と同じ場所)。設定を読めたら、log_dir に切り替える
- 起動できないときは、理由をログに出して終了する(終了コード 0 以外)。タスクスケジューラの「最後の実行結果」にも 0 以外が出る
  - config.toml の書き方の誤り: 「起動できませんでした」と、ファイルの場所・行・理由(終了コード 1)
  - 同じフォルダでほかの GenbaApp が動いている: 「起動しません: ほかのプロセスが動いています」(終了コード 2)
  - ポートの使用中: 「起動しません: ポート … はほかのプログラムが使っています」(終了コード 4)
- 2つ目の起動は、起動処理(バックアップとDBの構造の更新)の前に止める。古い版を止め忘れて新しい版を起動しても、動いている古い版の下でDBの形が変わらないようにするため。判定は `data\genba.lock` の OS のファイルロック(プロセスが落ちると OS が外すので、ロックは残らない)と、ポートに bind できるか(`app/core/single_instance.py`)

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

## 開発用コマンド(GenbaCli.exe)

- exe のフォルダには、GenbaApp.exe と並んで GenbaCli.exe(開発用コマンド `python -m app.cli` と同じもの)を入れる。GenbaApp.exe はウィンドウを出さない形なので、入力の要るコマンドは GenbaCli.exe(いつもコンソールを出す形)で動かす
- 基準のフォルダ(GENBA_HOME)の決め方は GenbaApp.exe と同じ(exe の2つ上)。担当者PCでは C:\GenbaApp\data\genba.db が対象になる
- 管理者のパスワードの設定(最初とリセット)は、担当者PCで PowerShell かコマンドプロンプトを開いて実行する。入力した文字は画面に出ない

```powershell
C:\GenbaApp\app\v1.0.0\GenbaCli.exe admin set-password --worker-id K0042
```

- GenbaApp.exe が動いていても実行できる(書き込みは短く、ほかの書き込みと順番に行う)
- 注意: GenbaCli.exe の日本語の出力は、PowerShell 5.1 でパイプや変数に渡すと(`| Select-Object`、`> log.txt`、`$x = ...` など)文字化けする(2026-10-22・23、NANJYOU-H で確認。`[Console]::OutputEncoding` を UTF-8 にしても直らなかった)。コマンドの成否は終了コード(`$LASTEXITCODE`。0 なら成功)で確かめる。コンソールのウィンドウにそのまま出したときの表示は、まだ確かめていない

## 担当者PCで使うスクリプト(packaging/)

どれも管理者権限が要る(スクリプトの先頭に `#Requires -RunAsAdministrator`)。PowerShell を「管理者として実行」してから動かす。
PowerShell 5.1 が日本語を正しく読めるよう、.ps1 は UTF-8(BOM 付き)・改行 CRLF で保存する。

### 自動起動は専用のアカウントで動かす(SYSTEM では動かさない)

- 実行するアカウントは `-User` で必ず指定する(指定しないとスクリプトが止まる)。**SYSTEM、LOCAL SERVICE、NETWORK SERVICE、Administrator は断る**。管理者権限を持たない、このアプリ専用のアカウント(例 `DOMAIN\genba-app`)を使う。Administrators のメンバーだと警告が出る
  - 理由: アプリが乗っ取られたとき(過去には画面の配信の S-01 があった)の被害を、そのアカウントが読み書きできる範囲に抑えるため。SYSTEM だとPC全体に及ぶ(詳細: security.md の S-05)
- そのアカウントが書ける共有フォルダにバックアップを書ける(共有フォルダの権限は、下の「フォルダの権限」)
- 「ユーザーがログオンしているかどうかにかかわらず実行する」タスクは、利用者の画面とは別に動くので、ウィンドウは出ない。ログオフしても止まらない
- 注意: そのアカウントのパスワードを変えたら、登録し直す(タスクスケジューラが古いパスワードで起動しようとして失敗する)。ドメインの設定で「バッチ ジョブとしてログオン」の権利が無いと登録・起動できないので、情報システムの担当に頼む

| スクリプト | すること |
| --- | --- |
| `install-autostart.ps1 -Version v1.0.0 -User <専用アカウント>` | タスクスケジューラに、PCの起動時に exe を起動するタスク(名前 GenbaApp)を、そのアカウントで「ユーザーがログオンしているかどうかにかかわらず実行する」形で登録する。パスワードは実行したときに入力する(スクリプトには書かない)。止まったら1分後に起動し直す |
| `uninstall-autostart.ps1` | 上のタスクを止めて外す |
| `firewall-allow.ps1 -Port 8000 [-RemoteAddress <相手>]` | 受信の TCP のそのポートだけを、**相手を絞って**許可する(ドメインとプライベートのプロファイル)。ポートは config.toml の server.port と合わせる。`-RemoteAddress` の既定は `LocalSubnet`(同じサブネット)。タブレットと管理用PCの固定のアドレス(`192.168.10.21,192.168.10.22` や `192.168.10.0/24`)に絞るのがよい |
| `firewall-remove.ps1` | 上の許可を消す |

(旧 `-RunAsSystem` は無くした。2026-10-25、AD-12)

### フォルダの権限(担当者PC。コードの変更なしにできる対策)

`C:\` の直下に作ったフォルダは、既定で `Authenticated Users` に「変更」の権限が付くことがある。そのままだと、PCにログオンできる誰でも exe の置き換え、config.toml の書き換え、DBの読み取りができてしまう(security.md の S-05)。展開したあと、管理者の PowerShell で次のように絞る。`DOMAIN\genba-app` は自動起動の専用アカウント。

```powershell
# 1. 継承を切って、必要な人だけにする(Administrators と SYSTEM は全権、専用アカウントは「変更」)
icacls C:\GenbaApp /inheritance:r
icacls C:\GenbaApp /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "DOMAIN\genba-app:(OI)(CI)M"
# 2. exe のフォルダは、専用アカウントには「読み取りと実行」だけにする(exe を置き換えられないように)
icacls C:\GenbaApp\app /inheritance:r
icacls C:\GenbaApp\app /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "DOMAIN\genba-app:(OI)(CI)RX"
# 確かめる
icacls C:\GenbaApp
icacls C:\GenbaApp\app
```

- 管理者の操作(パスワードの設定 `GenbaCli.exe`)をする担当者は、Administrators のメンバーか、`data` に書けるアカウントで実行する
- `C:\GenbaApp\data`(config.toml、DB)と `logs`、`exchange` は、専用アカウントが書けて、ほかの一般ユーザーは読めない状態にする(上の 1 のとおり)
- **バックアップ先の共有フォルダ**(`paths.backup_dir`)も同じ考え方にする。バックアップは本アプリのDBの完全な複製で、**管理者のパスワードのハッシュ、全員の氏名・作業者ID、全実績が入っている**。共有フォルダの権限は、専用アカウント(書き込み)と、担当者・管理者(読み取り)だけにして、「Everyone」「Domain Users」は外す。共有の権限(共有のアクセス許可)と、NTFS の権限の両方を確かめる
- 既存アプリのフォルダ(`legacy_app_dir`)は、専用アカウントに「読み取り」だけを与える(本アプリは読み取り専用で開く。書き込みの権限は要らない)
- 確かめ方: 専用ではない一般ユーザーで `C:\GenbaApp\data\config.toml` を開けないこと、`C:\GenbaApp\app\v1.0.0\GenbaApp.exe` を上書きできないことを試す

### アクセス制限との二重の守り

- ファイアウォールの `-RemoteAddress` は、アプリ側のアクセス制限(管理画面の「アクセス制限」、`GenbaCli.exe ip add`)と**併用する**。外側(ファイアウォール)が内側(アプリの一覧)を含むようにし、足すときは先にファイアウォール、外すときは先にアプリ。手順と確かめ方は security.md の「アクセス制限」の「二重の守りの運用手順」
- 管理画面に入れなくなったときは、サーバーのPCで `GenbaCli.exe ip disable-all`(最大5秒で効く)
- 開発サーバー(Vite の 5173)では効かない。本番の 8000 番に直接つなぐときだけ効く

### 管理画面の通信(HTTPのみ)の運用

HTTP のままでは、管理画面のパスワードとセッションが平文で流れる(security.md の S-04、5.3)。コードを変えずにできる対策:

1. 管理画面のパスワードは、ほかのシステムと使い回さない。12文字以上にする(アプリの下限は8文字)
2. 管理用PCは有線のLAN、または他と分けたネットワークに置く。タブレットの Wi-Fi の鍵を管理用PCと共有しない
3. ファイアウォールの `-RemoteAddress` を、タブレットと管理用PCのアドレスだけにする。アプリ側のアクセス制限にも同じ端末を登録する(上の「アクセス制限との二重の守り」)
4. 管理画面を使うときは、担当者PCのブラウザで `http://localhost:<ポート>/admin` を開く方法もある(LANに流れない)

### パスワードの設定の注意

- `GenbaCli.exe admin set-password --worker-id <ID>` は、画面に出ない入力で2回聞く。手で打つときは、これを使う
- `--stdin` は自動化のときだけ。`echo パスワード | GenbaCli.exe ...` のように書くと、PowerShell のコマンド履歴(PSReadLine)にパスワードが残る

## 初めて置くとき(担当者PC)

1. `C:\GenbaApp\app\` に zip を展開する(`C:\GenbaApp\app\v1.0.0\GenbaApp.exe` になる)
2. `C:\GenbaApp\data\config.toml` を作る(リポジトリの `config.example.toml` をもとに、`legacy_app_dir`、`backup_dir`、ポートを書く。`expose_docs` は書かない = 本番は `/docs` を開かない)
3. 専用アカウントを用意し、上の「フォルダの権限」で `C:\GenbaApp` とバックアップ先の権限を絞る
4. 管理者の PowerShell で `install-autostart.ps1 -Version v1.0.0 -User <専用アカウント>`(パスワードを入力する)と `firewall-allow.ps1 -Port <ポート> -RemoteAddress <タブレットと管理用PCのアドレス>`。起動したあと、管理画面の「アクセス制限」(または `GenbaCli.exe ip add`)に同じアドレスを登録する
5. `Start-ScheduledTask -TaskName GenbaApp` で起動し、ブラウザで `http://<担当者PC>:<ポート>/api/health` が ok を返すことを確かめる。`http://<担当者PC>:<ポート>/docs` が開かない(画面の表示か 404)ことも確かめる

## 版を更新するとき(担当者PC)

1. `Stop-ScheduledTask -TaskName GenbaApp`(止める)
2. 新しい版の zip を `C:\GenbaApp\app\` に展開する(旧版のフォルダは残す)
3. `install-autostart.ps1 -Version <新しい版> -User <専用アカウント>` で登録し直す
4. `Start-ScheduledTask -TaskName GenbaApp`。起動時にバックアップ(`*_startup.db`)を取ってから、DBの構造を更新する
5. `/api/health` の version が新しい版になっていることを確かめる
6. 問題があれば、止める → 旧版で登録し直す → `data\genba.db` を更新の前のバックアップ(`*_startup.db`)に戻す → 起動する

## このPCでの確認の結果(2026-10-21、MSI)

- 一時フォルダを `GENBA_HOME` にして起動し、/api/health(ok)と画面(ライン選択)を確かめた。DBは `GENBA_HOME\data\genba.db` に作られ、開発用DBには触れなかった
- 2回目の起動で、`backup\genba_<日時>_startup.db` ができた
- `GENBA_TEST_MODE=1` と `GENBA_CLOCK_START` を設定しても、本物の時計を使った
- 大きさ: フォルダ 39.3 MB(GenbaApp.exe 単体 13.0 MB)、zip 23.3 MB。起動(/api/health が返るまで)は約1.5秒
  - GenbaCli.exe を足したあと(2026-10-21): フォルダ 51.8 MB(GenbaCli.exe 12.5 MB)、zip 35.6 MB
- GenbaCli.exe で管理者を足し、PowerShell から `--stdin` でパスワードを設定して、GenbaApp.exe の管理画面にログインできた
- ウィンドウを出さない形: ウィンドウは出ずに起動し、/api/health が ok を返した。同じポートでもう1つ起動すると止まり、config.toml の書き方を誤らせると終了コード 1 で止まり、どちらも理由が `logs\genba.log` に残った
- 1つ目が動いている間に同じフォルダで2つ目を起動すると、終了コード 2 で止まり、バックアップのファイルは増えなかった。1つ目を強制終了したあとは起動し直せた(ロックは残らない)。ほかのプログラムがポートを使っているときは終了コード 4 で止まり、バックアップは増えなかった

## このPCでの確認の結果(2026-10-22、NANJYOU-H。依存を更新したあと)

依存の更新(vite 7.3.7、vitest 5.0.3、react-router-dom 7.18.4、httpx2)のあとに `build.ps1` で作り直し、確認用の別のフォルダ(`C:\work\tools\genba-check`。本番と同じ `app\v0.1.0\` の形、ポート 8791)で確かめた。確認後にフォルダは消した。

- 大きさ: フォルダ 53.5 MB(GenbaApp.exe 13.8 MB、GenbaCli.exe 13.1 MB)、zip 36.2 MB。起動(/api/health が返るまで)は約1.6秒。httpx・httpx2・pytest は同梱されていない
- `/field`、`/admin`、`/admin/login`、`/field/lines/S` と画面の js が 200 を返した
- 2つ目を起動すると終了コード 2 で止まり、バックアップは増えず、1つ目は動き続けた。理由は `logs\genba.log` に残った
- GenbaCli.exe で管理者を足し(DBができる)、GenbaApp.exe の動いている間に `admin set-password --stdin` でパスワードを設定して、`/api/admin/login` に通った(誤ったパスワードは 401)
- バックアップ: 起動のたびに `backup\genba_<日時>_startup.db` ができた。毎日の時刻(12:30)のバックアップは、時刻を待つ必要があるため確かめていない
- 自動起動とファイアウォール: 管理者の PowerShell で、確認用の名前(タスク・規則とも `GenbaApp-Check`)と確認用のフォルダを指定して流した。確認後に `uninstall-autostart.ps1` と `firewall-remove.ps1` で消し、本番の名前(`GenbaApp`)のタスク・規則が無いままであることを確かめた
  - `install-autostart.ps1 -RunAsSystem`: PCの起動時のトリガー、止まったら1分後に起動し直す(999回)、実行時間の上限なし、で登録された。`Start-ScheduledTask` で起動し、/api/health が ok、プロセスの所有者は SYSTEM だった。解除するとプロセスも止まった
  - 担当者のアカウントで動かす標準の形(`-User`)は、パスワードの入力が要るため流していない(担当者PCに置くときに確かめる)
  - `firewall-allow.ps1`: 受信・許可・TCP 8791・ドメインとプライベート、の規則ができた
- `build.ps1` の zip の段階で1回、`base_library.zip` が「ほかのプロセスが使用中」で失敗した。zip だけをやり直すと通った(作った直後のファイルを、ウイルス対策などが一時的に開いていたためと考えられる)
