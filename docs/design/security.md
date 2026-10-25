# セキュリティの調査(AD-9)

開発指針(docs/spec.md)の 9(非機能要件)の認証・HTTPS と、10(配布・運用)にかかわる調査の結果。**コードは変えていない。報告だけ**。直す作業は、下の「直す順番の案」を見て別の指示書で行う。

- 調査日: 2026-10-25(PC: MSI、Python 3.14.4、Node.js 22.23.2)。対象は main の 058e8f5
- 方法:
  - コードを読む(`backend/app/` の全API・認証・CSV・設定・バックアップ・既存DBの読み取り、`frontend/src/`、`packaging/*.ps1`)
  - **使い捨ての環境で本物のサーバーを起動して確かめた**(一時フォルダに空のDBと config.toml を置いた。本番のDB・実データには触れていない。確かめたあとサーバーは止め、一時ファイルはリポジトリの外にある)
  - `npm audit`、`pip-audit`(リポジトリの外に入れた。venv には入れていない)、ライセンスの集計
  - Git の全履歴(101コミット、全ブランチ)を検索
- 重大度の目安: **高** = 認証なしで、または社内LANの誰でも、重大な被害に届く。**中** = 条件がそろうと被害が出る、または運用で防ぐ前提のもの。**低** = 影響が小さい、または多層防御の不足
- 前提(開発指針 3、9): 社内LANだけで使う。現場端末は認証なし(PIN は未確定事項)。管理画面だけがログインを要る。HTTP のみ

## 問題の一覧

| ID | 重大度 | 内容 | 場所 |
| --- | --- | --- | --- |
| S-01 | **高** | 画面を配信する処理が、認証なしで **フォルダの外のファイルを読ませる**(パストラバーサル)。config.toml、本アプリのDB(管理者のパスワードのハッシュと全実績)、既存アプリのDBまで取れる | `backend/app/main.py` の `spa()` |
| S-02 | 中 | 本番でも `/docs`・`/redoc`・`/openapi.json` が開く | `backend/app/main.py`(`FastAPI(...)`) |
| S-03 | 中 | CSV インジェクション。書き出す CSV のセルが `= + - @` で始まっても無害化していない。現場の画面から入れた自由入力(付帯作業の「理由の記入」)が区間の CSV に出る | `services/report_csv.py`、`services/actuals_export.py` |
| S-04 | 中 | HTTP のみ・全NIC待ち受け(`0.0.0.0`)・ファイアウォールの規則に相手の範囲(RemoteAddress)が無い。管理画面のパスワードが平文で流れる | `config.example.toml`、`packaging/firewall-allow.ps1` |
| S-05 | 中 | 自動起動を SYSTEM にできる。`C:\GenbaApp` のフォルダの権限(ACL)の指示が無い。S-01 と重なると、SYSTEM の権限で任意のファイルが読める。exe の置き換えで権限昇格もできる | `packaging/install-autostart.ps1`、`docs/design/packaging.md` |
| S-06 | 中 | 現場のAPI(認証なし)が、作業者の名前・作業者ID・役割(admin)を返す。管理画面のログインIDは作業者IDなので、「ID を知る」ところまでは誰でも届く。記録者のなりすましも誰でもできる(設計上の前提。PIN は未確定事項) | `GET /api/masters`、`GET /api/operators/lookup` |
| S-07 | 低 | ログイン失敗の制限が作業者IDごとだけ。管理者のIDを知る人が、5分ごとに5回失敗させ続けると正しい管理者が入れない。存在しないIDの行も増え続ける | `services/admin_auth.py` の `login()` |
| S-08 | 低 | パスワードを変えても、ほかのセッションが残る(12時間まで)。期限切れのセッションの行は、次のログインのときの最長時間でしか消えない | `services/admin_auth.py` |
| S-09 | 低 | パスワードのハッシュ(scrypt)のコストが OWASP の推奨より低い(N=2^14、p=1。推奨は N=2^17、r=8、p=1 など)。古いハッシュを強いものに替える処理も無い | `domain/passwords.py` |
| S-10 | 低 | セキュリティヘッダー(X-Content-Type-Options、frame の禁止、Referrer-Policy、CSP)が無い。管理画面を別のページの iframe に入れられる(クリックジャッキング) | `backend/app/main.py` |
| S-11 | 低 | リクエストの大きさの上限が無い(20MB の本文を受けて解析した)。現場のAPIは認証なしなので、`api_requests`(冪等性の記録)やDBを増やし続けられる。計画の検索は毎回全件を読む | `backend/app/main.py`、`services/idempotency.py`、`services/plan_search.py` |
| S-12 | 低 | `GET /api/sync/status`(認証なし)が、同期の失敗の例外の文をそのまま返す。既存アプリのフォルダのパスなどが入る | `services/plan_sync.py` の `_record_error`、`api/plans.py` |
| S-13 | 低 | アクセスログ(`logs\genba.log`、90日分)に、`/api/operators/lookup?worker_id=…` の作業者IDがクエリごと残る | `backend/app/server.py`(`log_config=None`) |
| S-14 | 低 | 管理者のAPIの認証が、ルートごとの `Admin` 引数に頼っている。いまは漏れが無いが、新しいルートで付け忘れても気づく仕組みが無い | `api/admin_*.py` |
| S-15 | 低 | 知らない `/api/...` が 404 ではなく 200 で index.html を返す(画面用の受け皿が API のパスも受ける) | `backend/app/main.py` の `spa()` |
| S-16 | 情報 | Git の履歴に、パスワード・config.toml・DB・実データらしきものは見つからなかった。ただし、テストや文書に実データから取ったかもしれないキッティングNo.の例がある(要確認)。開発PC名とメールアドレスが履歴にある | 6 を参照 |
| S-17 | 情報 | 依存: `npm audit` 0件、`pip-audit` 0件。ライセンスは製品に入るものに GPL・AGPL なし | 6 を参照 |

## 直す順番の案

1. **S-01(最優先)**。小さな直しで済む(解決したパスが `STATIC_DIR` の中にあるか確かめる)。テストも付ける。**直すまでは、担当者PCに置かない・実データを読む設定で外部から届く場所では動かさない**
2. S-02(本番で `/docs` などを閉じる)と S-15(`/api/` の下の未知のパスは 404)。S-01 と同じ `main.py` の変更で、一緒にできる
3. S-05 の運用の決め(SYSTEM で動かさない、`C:\GenbaApp` の権限を絞る)と S-04 のファイアウォール(RemoteAddress)。コードを変えずに、手順書(`packaging.md`)とスクリプトの引数で済む
4. S-03(CSV の無害化)。「理由の記入」など自由入力の列だけを対象にする。既存アプリの取込口に影響する列(ロットNo. など)は別に扱う(2.2 を参照)
5. S-12(同期のエラーの文は管理者だけに)、S-06 のうち役割(role)を現場のAPIから外すこと
6. S-07〜S-11、S-13、S-14(全ルートが管理者か現場かを数えるテストを足す)
7. S-06 の本題(現場の端末にPINを付けるか)は未確定事項のまま。試用で決める

---

## 1. 認証と権限

### 1.1 管理者のAPIの一覧

`/openapi.json` から全ルートを取り出し、**ログインなしで**(書き込みには `X-Genba-Admin: 1` を付けて)呼んだ。21ルートのうち、ログイン(`POST /api/admin/login`)とログアウト(`POST /api/admin/logout`。意図どおり、ログインしていなくても呼べる)以外の **19ルートは、すべて 401 だった**。漏れは無い。

| メソッドとパス | ログインなしの結果 |
| --- | --- |
| GET `/api/admin/me` | 401 |
| PUT `/api/admin/password` | 401 |
| GET / POST `/api/admin/equipment`、PATCH `/api/admin/equipment/{id}` | 401 |
| GET / POST `/api/admin/reasons`、PATCH `/api/admin/reasons/{id}` | 401 |
| GET `/api/admin/lines`、PATCH `/api/admin/lines/{code}` | 401 |
| GET / POST `/api/admin/operators` | 401 |
| GET `/api/admin/reports/daily`、GET `/api/admin/reports/intervals.csv` | 401 |
| GET `/api/admin/actuals`、POST `/api/admin/actuals/export`、GET `/api/admin/actuals/exports`、GET `/api/admin/actuals/exports/{id}/file`、POST `/api/admin/actuals/links` | 401 |
| POST `/api/admin/login` | 本文が無いので 422(ログイン前に呼ぶもの) |
| POST `/api/admin/logout` | 204(ログインしていなくてもよい) |

- 書き込み(POST・PUT・PATCH・DELETE)は、`X-Genba-Admin: 1` が無いと Cookie があっても 403。ログイン自体にも要る。確かめた(`require_header_for_writes`)
- 認証は各ルートの `Admin` 引数(`Depends(current_admin)`)で付けている。ルーター全体には付けていない。**新しいルートで付け忘れても、検出するテストは無い**(`tests/` に全ルートを数えるテストは無い)→ S-14。直し方の案: `APIRouter(dependencies=[Depends(current_admin)])` にして、ログインとログアウトだけ別のルーターに分ける。または、テストで `app.routes` を数えて「`/api/admin/` の下で、ログインなしで 401 にならないのは login と logout だけ」を確かめる
- 管理者かどうかは、リクエストごとに確かめている(`authenticate` が `is_admin` を見る)。管理者でなくなった(無効にした、役割が変わった)人のセッションは、次の要求で切れる

### 1.2 セッションの Cookie

実際の応答の `Set-Cookie`:

```
genba_admin=<43文字>; HttpOnly; Path=/api/admin; SameSite=strict
```

| 項目 | 結果 |
| --- | --- |
| HttpOnly | 付いている |
| SameSite | Strict |
| Secure | 付いていない(HTTP で使うため。開発指針 9 に書いてある) |
| Path | `/api/admin` に限っている |
| 有効期限 | Cookie には Max-Age が無い(ブラウザを閉じると消える)。サーバー側で、操作が無い30分・最長12時間(config.toml の `[admin]`)で切る |
| 値 | `secrets.token_urlsafe(32)`。サーバーには SHA-256 のハッシュだけを持つ(DBが漏れても Cookie の値は分からない) |

- 問題なし。ただし S-08: パスワードを変えても、同じ人のほかのセッションを消していない(`change_own_password` → `_store` はセッションに触れない)。ログインのたびに最長時間を過ぎたものを消すが、操作が無くて切れた(idle)ものの行は、最長時間を過ぎるまで残る(使えはしない)。直し方の案: パスワードの変更・リセットのときに、その人のセッションを(いまのもの以外)消す

### 1.3 ログイン失敗の制限

確かめた結果: 同じ作業者IDで5回続けて間違えると、6回目は 429「しばらくログインできません(あと約5分)」。**そのあと正しいパスワードを送っても 429**。

- 制限は作業者IDごとだけ(IPアドレスごとの制限は無い)。作業者IDは S-06 のとおり誰でも知れる → **S-07: 管理者のIDを知る人が、5分ごとに5回失敗させ続けると、正しい管理者がログインできない**(締め出しの悪用)。社内LANでの影響は小さい。逆に、このくらいの制限でも、パスワードが8文字以上なら、総当たりは1日に1,440回ほど(1IDあたり)に抑えられる
- 存在しないIDでも `admin_login_attempts` に行ができる(キーは 64 文字まで、無制限)。ID が無いことは時間でも応答の文でも区別できない(ダミーのハッシュで同じ時間をかけ、応答の文も同じ)。これは良い
- 直し方の案: 管理者のIDを現場のAPIから見えなくする(S-06)のが一番効く。そのうえで、失敗と締め出しをログに残して気づけるようにする。行が増える件は、存在しないIDは数えない(または古い行を消す)。締め出し中に正しいパスワードを通す案は、総当たりの回数の制限が無くなるので採らない

### 1.4 パスワードの保存(scrypt)

- 標準ライブラリの `hashlib.scrypt`。ソルトは16バイトを `secrets` で作る。保存の形は `scrypt$n$r$p$<ソルト>$<ハッシュ>`。比較は `hmac.compare_digest`。最大256文字(長い入力で時間をかけさせない)。問題なし
- **S-09: N=2^14、r=8、p=1**(約16MB)。OWASP の推奨(scrypt: N=2^17、r=8、p=1 など)より低い。パスワードのハッシュがDBから漏れたとき(S-01 で漏れる)の総当たりが速い。保存した値にパラメータを含めてあるので、強くするのは、`_N` を上げて、ログイン成功のときにハッシュを作り直すだけ。メモリは増える(2^17 で128MB)ので、担当者PCで実測してから決める
- 平文は、DB・監査ログ(audit_log は `"(変更)"` とだけ記録)・ログのどこにも出ていない。ログイン要求の本文はアクセスログに出ない(出るのは URL のクエリだけ)ことを確かめた

### 1.5 CLI でのパスワード設定

- `GenbaCli.exe admin set-password --worker-id <ID>`: 画面に出ない入力(`getpass`、2回)。標準の経路で、これでよい
- `--stdin` は標準入力から読む。スクリプト用。`echo パスワード | GenbaCli.exe ...` のように書くと、**PowerShell のコマンド履歴(PSReadLine)にパスワードが残る**。運用の注意として、手順書(packaging.md)に「`--stdin` は自動化のときだけ。手で打つときは使わない」と書くのがよい(低)
- CLI には認証が無い。DBのファイルに書ける人はパスワードを替えられる。これは「担当者PCに触れる人は信頼する」という前提(開発指針 3)の中のこと。S-05 のフォルダの権限を絞れば、触れる人も絞れる
- 管理者になれる人は、既存アプリの `workers.role = admin` で決まる(`worker_sync`)。既存アプリのDBに書ける人が管理者の候補を増やせるが、パスワードを設定する経路は CLI だけなので、それだけでは入れない(情報)
- 開発用の `operators add --admin` は、`legacy_app_dir` を設定していると断る(本番で管理者が作れない)。確認した

### 1.6 現場の画面(ログインなし)から呼べるAPI

認証が無いルート(全部で 23。`/api/health` を含む)。

| ルート | 何が分かる・変えられるか |
| --- | --- |
| GET `/api/health` | 版、サーバー時刻、`db_journal_mode`。害は小さい |
| GET `/api/masters` | ライン、**作業者(名前・作業者ID・役割)**、設備、理由。→ S-06 |
| GET `/api/operators/lookup?worker_id=` | 作業者IDで1人(名前・ID・役割)。IDを総当たりできる(回数の制限なし) |
| GET `/api/lines/{line}/plans`、`/board`、`/operator`、GET `/api/plans/search`、GET `/api/runs/{kitting_no}` | 計画(キッティングNo.、ロットNo.、機種、数量、品名)、実績、今の担当者の名前 |
| GET `/api/sync/status` | 同期の結果と、失敗の例外の文(S-12) |
| PUT `/api/lines/{line}/operator` | ラインの今の担当者を、だれにでも替えられる |
| POST `/api/runs/{kitting_no}/steps/{step}/start・end`、PUT `/ng-qty`、POST `/remarks` | 工程・生産数・NG・備考の記録。**記録者は本文の `worker_id` / `operator_id` で指定できる(なりすまし可)** |
| POST `/api/lines/{line}/events/start・{id}/end` | 付帯作業の記録 |
| PATCH / POST `/api/runs/{kitting_no}/events…`、PATCH / POST `/api/lines/{line}/events/{id}…`(訂正・取り消し・追加) | 実績の訂正。**現場で直せるのは、今の稼働日の前後12時間の範囲の記録だけ**(`FieldScope`。範囲の外は 409) |
| GET `…/corrections` | 訂正の履歴(理由・記入) |

- 現場のAPIが認証なしなのは設計(開発指針 9「認証(現場)」)。ただし次の点は、設計の範囲でも見直す価値がある:
  - **S-06**: `/api/masters` が `role` と、管理者を含む全員の名前・作業者IDを返す。管理画面のログインIDは作業者IDなので、攻撃者はIDを探さずに済み、S-07 の締め出しも狙える。現場の画面が `role` を使っていないなら、現場向けの応答から外す(または管理者を除く)のがよい。作業者IDの総当たり(lookup)にも回数の制限は無いが、IDは短い数字や記号なので、実質は一覧が見えるのと同じ
  - 実績を訂正できる範囲(12時間の前後)の制限は、サーバーで検査している(開発指針 0-4 に合う)。範囲の外の記録は管理画面からだけ
- CSRF(ほかのサイトのページからの送信): 現場のAPIは認証なしなので、CSRF という考えが当てはまらない(誰でも直接呼べる)。管理者のAPIは、SameSite=Strict の Cookie と `X-Genba-Admin` ヘッダーで守っている。**Content-Type が JSON 以外(`text/plain`、フォームの形式)の本文は 422 で断る**ことを確かめた。ヘッダーを付けるには CORS の事前確認(preflight)が要り、CORS は許可していない(3.1)

---

## 2. 入力と出力

### 2.1 SQLインジェクション、パス

- 生のSQLは、定数の `PRAGMA`(`db/session.py` の `busy_timeout` は `int()` を通した値、`api/health.py` は固定の文)と、`BEGIN IMMEDIATE` だけ。**利用者の入力を文字列でSQLに入れている箇所は無い**(`text()`・`exec_driver_sql`・f 文字列のSQLを全部探した)。ORM のパラメータで渡している。実際に `/api/lines/' OR 1=1--/board` を送っても、ライン名として 404 になるだけだった
- **パス: S-01(高)**。`backend/app/main.py` の画面の配信:

  ```python
  candidate = STATIC_DIR / path
  if path and candidate.is_file():
      return FileResponse(candidate)
  ```

  `path` に `..` を含めても、`STATIC_DIR` の中かを確かめていない。使い捨ての環境で確かめた結果(一時フォルダの、画面のフォルダの外に置いたファイルと、その隣のDB):

  | 送ったパス | 結果 |
  | --- | --- |
  | `/..%2fdata%2f<ファイル名>`(ブラウザが送る形。`..` は解決されない) | 200、ファイルの中身 |
  | `/%2e%2e/data/<ファイル名>` | 200 |
  | `/../data/<ファイル名>`(curl の `--path-as-is`) | 200 |
  | `/..%5cdata%5c<ファイル名>`(バックスラッシュ。Windows) | 200 |
  | `/..%2fdata%2fgenba.db`(本アプリのDB)、`genba.db-wal` | 200、DBの中身(WAL も) |

  - **認証は要らない**。ログインなしで、サーバーを動かしているアカウントが読めるファイルを何でも読める。本番の配置では、`config.toml`(ポート、既存アプリのフォルダ、共有フォルダのパス)、`genba.db`(管理者のパスワードのハッシュ、全員の氏名・作業者ID、全実績、監査ログ)、`logs\`、`exchange\actuals\*.csv`、`legacy_app_dir` の既存アプリのDB(計画の全データ)が取れる。さらに SYSTEM で動かしていれば(S-05)PC内のほぼ全てのファイル
  - 再現のしかた: アプリを起動し、`curl --path-as-is "http://<PC>:8000/..%2fdata%2fconfig.toml"`(フォルダの深さは、`..%2f` を足して合わせる)
  - 範囲: exe では `STATIC_DIR` は `_internal\frontend_dist`。`..%2f` を4つ重ねると基準のフォルダ(`C:\GenbaApp`)に届く
  - 直し方の案: `candidate = (STATIC_DIR / path).resolve()` にして `candidate.is_relative_to(STATIC_DIR.resolve())` のときだけ返す。そうでなければ index.html。`tests/` に「`..%2f` を含むパスが画面のフォルダの外を返さない」テストを足す。`/assets` は Starlette の `StaticFiles` で、これは安全に作ってある(問題なし)
- ダウンロード: 実績の書き出しのダウンロード(`/exports/{id}/file`)は、ファイル名をDBの値(サーバーが作った `actuals_YYYYMMDD_HHMMSS_NNNN.csv`)から出し、中身もDBの `content` から返す。**利用者がパスを指定する経路は無い**。区間の CSV の名前は、日付とDBにあるライン記号(`get_line` で確かめた値)から作る。`Content-Disposition` に入るのはこれだけ
- 連携フォルダ: 書き出し先は `exchange_dir\actuals\` に固定、ファイル名はサーバーが作る(`.tmp` に書いてから改名)。入力のパスは使わない。問題なし
- 既存アプリのフォルダ: `legacy_app_dir\db\<フォルダ>\inventory.db` は、フォルダを `iterdir()` で列挙したもの(利用者の入力ではない)。問題なし

### 2.2 CSV インジェクション(S-03)

書き出す CSV は 2 種類で、**どちらも、セルが `=` `+` `-` `@`(と、タブ、CR)で始まる場合の無害化をしていない**(`csv.writer` に値をそのまま渡している)。Excel で開くと、`=…`、`+…`、`-…`、`@…` は式として扱われる(最近の Excel は警告を出すが、外部のプログラムの呼び出しや、他のセルの値を外へ送る式を、ユーザーが許可してしまえば動く)。

自由入力の文字が出る列と、そうでない列を分けた:

**区間の CSV(`services/report_csv.py`)**

| 列 | 値の出どころ | 自由入力か |
| --- | --- | --- |
| **理由の記入** | 現場の画面から、**認証なしで**入れる付帯作業の「理由の記入」(`reason_text`、2000文字まで) | **はい。これが危険な列**。訂正(`PATCH …/events/{id}`)でも変えられる |
| 開始した人、終了した人 | 作業者の名前(既存アプリの `workers`、または管理画面で追加) | 管理者・既存アプリ側の入力。現場からは入れられない |
| 品名 | 既存アプリの計画の値 | 既存アプリ側の入力 |
| 設備、工程または理由、再開理由 | マスタの名前(管理者が追加) | 管理者の入力 |
| キッティングNo.、ロットNo.、ファイルNo. | 既存アプリの計画の値(キッティングNo. は形式の検査済み) | 既存アプリ側の入力 |
| 稼働日、時刻、分、数、フラグ | サーバーが作る | いいえ |

**実績の CSV(`services/actuals_export.py`)**: 備考や理由の記入は出さない。列は、書式版、書き出し日時、元のDB(フォルダ名)、キッティングNo.、ロットNo.、ファイルNo.、面、日付、生産数、NG面1・面2、担当者ID、面1のキッティングNo.。**現場の自由入力は出ない**(担当者IDは `operators` の値、数は整数)。文字の列は、すべて既存アプリのDB由来(既存アプリを使う人の入力)

- 再現のしかた: ラインの画面で付帯作業を開始し、理由の記入に `=HYPERLINK("http://example.invalid","x")` と入れて終了。管理画面で区間の CSV を出して Excel で開く(式として動く)
- 直し方の案:
  - 区間の CSV: **文字の列すべて**(特に「理由の記入」)で、先頭が `= + - @ \t \r` のとき先頭に `'` を付ける(または全体を引用符で囲み、先頭にタブを付ける)。数字や日付の列は、`-` で始まる負の数が無いので対象外にできる
  - 実績の CSV: 既存アプリの取込口が読むファイルなので、`'` を付けると**取り込みの値が変わる**。キッティングNo.・ロットNo. などは、書式で決まった文字しか入らないので(キッティングNo.は先頭が数字。ロットNo.は既存アプリの値)、無害化ではなく**値の検査**(先頭が `= + - @` のときは書き出さずに警告)にするのが安全。取込口を作るときに、取込口の側でも文字列として読む(式として評価しない)
  - テスト: 先頭が `=` の「理由の記入」が、区間の CSV で式にならないこと

### 2.3 XSS

- `frontend/src` に `dangerouslySetInnerHTML`、`innerHTML`、`eval`、`new Function`、`document.write` は **無い**(全探索)。画面の文字はすべて React の通常の出力(自動でエスケープされる)
- サーバーが返す文(`detail`)も、テキストとして出している。サーバーは入力を返すことがある(ライン名の 404 の文、422 の `input`)が、HTML にはならない
- リンクの `href` に利用者の値を入れる箇所は無い。`window.open` も無い
- `localStorage` に入れているのは、表示言語(`genba.lang`)だけ
- 低い問題: CSP が無い(S-10)ので、万一のときの被害を抑える層が無い

### 2.4 リクエストの大きさ(S-11)

- FastAPI / uvicorn は本文の大きさに上限が無い。**20MB の備考の本文を受け取って解析し**(文字数の検査は解析のあと)、422 で返した。422 の応答は `input` に入力をそのまま入れるので、**応答も大きい**
- 各項目の上限は決まっている(備考・理由の記入・訂正のメモは2000文字、`request_id` は100文字、名前は100文字、パスワードは256文字)。ただし本文全体の上限は無い
- 現場のAPIは認証なしで書き込める。`api_requests`(冪等性の記録。リクエストと応答を保存)は、`request_id` を変えて送り続ければ増え続ける。1件あたり小さいが、上限も掃除も無い
- 計画の検索 `/api/plans/search` は、毎回、有効な計画を全件読む(数千件)。認証なしで連続して呼べる
- CSV の取り込みの上限: **本アプリには CSV を取り込む機能は無い**(書き出しだけ)。書き出しの期間は `reports.max_days`(93日)で制限している。既存アプリのDBの取り込みは、読み取り専用で月次DBを読むだけ
- 直し方の案: uvicorn の前に本文の大きさを見るミドルウェア(例: 1MB で 413)を足す。`api_requests` は古いもの(例: 90日)を消す。現場のAPIに簡単な速度制限を付けるのは、現場の端末が数台なので、必須ではない

---

## 3. HTTP まわり

### 3.1 CORS、ヘッダー

- **CORS は許可していない**(`CORSMiddleware` なし)。別のオリジンから `OPTIONS` は 405、応答に `Access-Control-Allow-Origin` は付かない。問題なし
- **セキュリティヘッダーは付いていない**(S-10)。`/api/health` の応答で確かめた(`date`、`server: uvicorn`、`content-length`、`content-type` だけ)。付けたいもの:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`(または CSP の `frame-ancestors 'none'`)。管理画面を別のページの iframe に入れて、操作をだますことができる。SameSite=Strict の Cookie は iframe の中では(別のサイトの中なので)送られないので、実害はほぼ無いが、念のため
  - `Referrer-Policy: no-referrer`
  - CSP(`default-src 'self'` など)。React の画面だけなので付けやすい。印刷用の画面とスクリーンショットの確認(Playwright)で確かめる
  - `Server: uvicorn` を出さない設定(`server_header=False`)は、あってもよい
- 直し方の案: `main.py` に、ヘッダーを足すミドルウェアを1つ(`@app.middleware("http")`)。

### 3.2 `/docs` と `/openapi.json`(S-02)

- **本番でも開く**。確かめた: `/docs`、`/redoc`、`/openapi.json` はどれも 200
- 認証なしで、全APIの一覧、リクエストの形、管理者のAPIの名前が分かる。秘密の情報ではないが、攻撃のための地図になる。`/docs` は外部の CDN(jsdelivr)から画面の部品を読むので、社内LANでインターネットに出られない環境では表示できない(害はない)
- 直し方の案: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` を、exe(`is_frozen()`)のときだけ指定する。開発中は開いたままにする(`npm run gen:api` が `app.openapi()` を `openapi_export.py` で直接作るので、HTTP の `/openapi.json` は要らない)
- S-15: 画面の受け皿 `/{path:path}` は、`/api/…` の知らないパスも受けて index.html を 200 で返す(例: `/api/nothing` → 200 の HTML)。API の打ち間違いが見えにくい。`/api/` で始まるパスは 404 にする

### 3.3 エラー応答

- 想定内のエラー(業務ルールの違反、未ログイン、404、混雑)は、`detail` に日本語の文だけ。スタックトレースやパスは出ない
- 想定外の例外は uvicorn の既定で、本文は `Internal Server Error` だけ(スタックトレースは応答に出さず、サーバーのログに出る)。デバッグ用の設定は使っていない(`debug=True` なし)
- 出る恐れがあるもの:
  - **S-12**: 同期が失敗したとき、`plan_sync_runs.error_message` に `f"{type(e).__name__}: {e}"` を保存し、`GET /api/sync/status`(認証なし)が返す。例外の文には、既存アプリのフォルダのパス(`C:\Users\<名前>\…`)、DBのファイル名が入りうる(`LegacySourceError`の文は `legacy_app_dir` を含む)。`legacy_dbs`(読んだ月次DBの名前とファイルの更新日時)も同じ応答に入る。直し方の案: 現場向けの応答には「同期に失敗しています」だけにして、詳細は管理者向けのAPI(またはログ)に置く
  - 422(入力の検査の失敗)は、入力をそのまま返す。HTML ではないので XSS にはならない

---

## 4. データ

### 4.1 既存アプリのDBを読み取り専用で開いているか

- 既存アプリのDBを開く箇所は `integration/legacy/readonly.py` の `open_readonly()` **1つだけ**。`plans.py`、`workers.py`、`takt.py` は必ずこれを使う(`sqlite3.connect` をアプリの中で全部探した。残りは、本アプリのDBのバックアップ(`services/backup.py`。本アプリのDBを読む側)と、SQLAlchemy のエンジン(本アプリのDB)だけ)
- 開き方は、URI の `?mode=ro` + `PRAGMA query_only = ON` の二重。書き込みの文(`INSERT`、`UPDATE`、`DELETE`、`CREATE`)は、既存DBに向けて書かれていない。`plans.py` が `BEGIN … COMMIT` を使うのは、読み取りの一貫性のためだけ(書き込みはしない)
- 既存アプリのフォルダへ書く処理は無い(書き出しは `exchange_dir` と `backup_dir` のみ)。**書き込める経路は見つからなかった**
- 補足: 既存DBがWALモードのときの `mode=ro` は、`-shm` / `-wal` のファイルを既存アプリのフォルダに作ろうとして失敗することがある(DBそのものは書き換えない)。セキュリティではなく動作の話なので、ここでは調べていない
- 設定で、`paths.database` を既存アプリのDBに向けると、本アプリのDBの構造を作る処理(Alembic)が既存DBに書き込む。`config.toml` の誤りで起きるが、既存アプリの月次DBとは名前も場所も違うので、現実的には起きにくい(AGENTS.md に、Alembic を手で使うときの注意がある)

### 4.2 設定ファイル、DB、バックアップ、ログに入るもの

| 場所 | パスワード | 個人情報 |
| --- | --- | --- |
| `config.toml` | **無い**(ポート、パス、時刻、回数だけ)。共有フォルダのパスは入る | 無い |
| 本アプリのDB | scrypt のハッシュのみ(`admin_credentials`)。平文は無い | **作業者の氏名と作業者ID**(`operators`)、工程・付帯作業・訂正の記録者、備考と理由の記入(自由入力) |
| バックアップ(`backup_dir`) | DBの完全な複製なので、ハッシュも入る | 同上。**共有フォルダの権限で守る**(誰が読めるか) |
| 実績の CSV(`exchange\actuals\`) | 無い | 担当者ID |
| ログ(`logs\genba.log`) | 出ていない(ログイン要求の本文は出ない。確かめた) | S-13: アクセスログに `GET /api/operators/lookup?worker_id=<ID>` の形で作業者IDが残る(90日)。同期の例外にパスが入りうる |
| 監査ログ(`audit_log`) | パスワードの変更は `"(変更)"` とだけ | 管理者の操作の記録 |
| Git | 無い(6 を参照) | 6 を参照 |

- 直し方の案: アクセスログのクエリを出さない(uvicorn の access ログを自前の形式にする、または `worker_id` をクエリではなく POST の本文にする)。バックアップの共有フォルダは、担当者と管理者だけが読める権限にする(運用)

---

## 5. 配布と運用

### 5.1 自動起動の実行アカウント(S-05)

- 標準は、担当者のアカウントで「ログオンしているかどうかにかかわらず実行」(`-RunLevel Limited`)。**管理者権限(Highest)ではない**。これは良い
- `-RunAsSystem` を選ぶと **SYSTEM、`RunLevel Highest`** で動く。選べる形にしてあり、packaging.md も「SYSTEM も選べる」と書いている。この場合:
  - アプリが乗っ取られたとき(たとえば S-01)の被害が、PC全体に及ぶ
  - 次の「フォルダの権限」と重なると、権限昇格(下)
- **`C:\GenbaApp` の権限の指示が無い**(`packaging.md` にも `icacls` の記載が無い)。`C:\` の直下に作ったフォルダは、既定で `Authenticated Users` に「変更」が付く(PCによって違う。担当者PCで確かめる)。その場合、PCにログオンできる誰でも `GenbaApp.exe` を置き換えられる。SYSTEM で動かしていれば SYSTEM のコードの実行になる。担当者のアカウントなら担当者の権限での実行。さらに `config.toml`(`paths.database` を変えられる)、DB、バックアップ先も書き換えられる
- 直し方の案(運用):
  1. **SYSTEM では動かさない**(担当者のアカウント、または専用の低い権限のサービス用アカウント)。専用のアカウントなら、そのアカウントに `C:\GenbaApp\data`、`logs`、`exchange` の書き込みと、共有フォルダ(バックアップ)の書き込みだけを与える
  2. `C:\GenbaApp` を、`icacls C:\GenbaApp /inheritance:r /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "<実行するアカウント>:(OI)(CI)M"` のように継承を切って絞る。`app\`(exe)は実行アカウントに「読み取りと実行」だけにすると、置き換えを防げる
  3. 手順書(`packaging.md`)とスクリプトに、これを書く(スクリプトの `-RunAsSystem` には、警告の表示を足す)

### 5.2 ファイアウォールの規則(S-04)

- `New-NetFirewallRule -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Domain, Private`
- **`-RemoteAddress` が無い**(どの相手からも許可)。パブリックのプロファイルでは開けない作りだが、Windows が Wi-Fi を「プライベート」と判断していれば、同じネットワークの全員が届く
- アプリは `host = "0.0.0.0"`(全NIC)で待ち受ける(`config.example.toml` の既定)。PCに複数のNIC(有線・無線・VPN)があると、全部で待ち受ける
- 直し方の案: `-RemoteAddress LocalSubnet`(または、現場のタブレットと管理用PCの固定のアドレスの範囲 `192.168.x.0/24` など)を足す。`firewall-allow.ps1` に `-RemoteAddress` の引数を足す。`server.host` を、LAN側のアドレス1つに絞ることもできる(アドレス固定が前提)

### 5.3 HTTP のみで運用する危険(S-04)

- 管理画面のログイン(作業者IDとパスワード)、セッションの Cookie、実績の CSV がすべて**平文**で流れる。同じLANの誰かが通信を覗ければ(ARP スプーフィング、Wi-Fi の共有鍵が知られている、ポートミラー)、パスワードとセッションを盗める
- 現場のAPIは認証が無いので、覗かれて困るのは、管理画面だけ。ただし管理者のパスワードを**ほかのシステムと使い回している**と、被害がそちらに広がる
- 運用での対策案(コードを変えずにできる順):
  1. 管理画面のパスワードを、ほかのシステムと**使い回さない**。専用の長いパスワードにする(最低8文字は短い。12文字以上を運用で決める)
  2. 管理用PCは有線のLAN、または他と分けたVLAN / SSID に置く。現場のタブレットのWi-Fiは、管理用PCと同じ鍵を共有しない
  3. ファイアウォールを管理用PCとタブレットのアドレスに絞る(5.2)
  4. 管理画面を使うときだけ、担当者PCの上のブラウザ(`http://localhost:8000/admin`)で開く。LANに流れない
  5. 将来、HTTPS(社内の認証局の証明書)を入れる。そのとき Cookie に `Secure` を付ける。開発指針 9 の「必要になったら」の条件を、「管理画面を LAN 越しに使う運用が始まったら」とするのが適当
- 開発指針の判断(フェーズ1は HTTPS 不要)は、現場の画面だけなら妥当。管理画面を LAN 越しに使うなら、上の1〜3を最低限の運用にする

---

## 6. 依存とリポジトリ

### 6.1 脆弱性

| 道具 | 結果 |
| --- | --- |
| `npm audit`(frontend、開発用を含む) | **0件** |
| `pip-audit`(`requirements.txt`、venv の全パッケージ) | **既知の脆弱性なし** |

- `pip-audit` は、リポジトリの外(一時フォルダ)に入れて動かした。`requirements.txt` に日本語のコメントがあるので、Windows の既定の文字コード(cp932)では読めずに止まる。**`PYTHONUTF8=1` を付けると動く**(pip-audit が `-r` のファイルを読むときの話で、`pip install -r` は問題なし)
- `pip-audit` は、パッケージ名と版を、公開の脆弱性のデータベースに問い合わせる(通信が出る)。定期的に動かすなら、`requirements-dev.txt` に入れるかは、開発指針 0-8(ライブラリの追加の理由とライセンス)で決める。ここでは足していない
- 依存の版は固定済み、公開から2週間以上たった版という運用(`dependencies.md`)。これは良い

### 6.2 ライセンス

- npm: 製品に入るもの(`prod`)は 11 個すべて MIT。開発用は MIT / Apache-2.0 / ISC / BSD-3-Clause / Python-2.0 / CC-BY-4.0 / (MIT OR CC0-1.0)。**GPL・AGPL・SSPL・ライセンス不明は無い**
- Python: 製品に入るもの(fastapi、uvicorn、starlette、pydantic、sqlalchemy、alembic、tzdata など)は MIT / BSD / Apache-2.0。例外の扱い:
  - `pyinstaller`(GPL-2.0、ブートローダーの例外あり)、`pyinstaller-hooks-contrib`(GPL-2.0 と Apache-2.0)は**ビルドのときだけ**の道具で、開発指針 0-8 が認めている
  - `certifi`(MPL-2.0。弱いコピーレフト)は `httpx2` 経由でテストのときだけ入る。exe には同梱されない(`genba.spec` の excludes と packaging.md の確認で「httpx・httpx2・pytest は同梱されていない」)

### 6.3 Git の全履歴の検索

対象: 101コミット、全ブランチ(`git log --all`)。**見つけたものの中身は、ここには書かない**(場所だけ書く)。

| 調べたもの | 結果 |
| --- | --- |
| DB・config.toml・ログ・CSV・Excel・バックアップ・鍵の**ファイル**が、履歴のどこかで追加されたか | **無い**。`config.example.toml` だけ(中身は例の値で、パスワードなし)。500KB を超えるファイルも無い。いまの追跡ファイル(301)にも無い |
| パスワード・トークン・秘密鍵の文字列 | 鍵・トークンは **無い**。パスワードらしい代入は、テスト用の値(`backend/tests/admin/`)と、確認用DBの管理者(`frontend/e2e/serve.mjs`。毎回作り直すDBだけで使う)のみ。本番のパスワードではない |
| 内部のIPアドレス(10.x、172.16〜31.x、192.168.x)、共有フォルダのパス | `config.example.toml` と `packaging.md` / `test_config.py` の例(`//server/share/…`)のみ。実際のサーバー名は見つからない。IPのように見えたものは `package-lock.json` の版の番号 |
| `C:\Users\<名前>` のパス | **無い** |
| キッティングNo. の形(`ファイルNo.-回-ライン-年月日-連番`)の文字列 | 77種類。**すべて**テスト(`backend/tests/`、`frontend/src/**.test.ts`、`frontend/e2e/`)と `docs/spec.md` の例にあり、本番のコードや設定には無い。**実データから取ったものか、作ったものかは、コードからは判別できない** |
| ロットNo.、氏名 | 同様に、テストの作った値と見られる。実データのロットNo.を直接調べる方法は無い(実データを見ていない) |
| 作業者IDの形(`K0042` など) | 例とテストの値のみ(`cli.py` の使用例、`admin.md`、`packaging.md`、テスト)。実在の人かどうかは判別できない |
| 開発PCの名前 | `docs/STATUS.md`、`packaging.md`、`actuals-export.md` に「NANJYOU-H」「MSI」。作業のPCの記録としてあるもの。外に出すと内部のホスト名が分かる |
| コミットの作者 | 全コミットが同じ作者1人。メールアドレスは個人の Gmail(`git log` に出る)。リポジトリが非公開か確かめる |
| 実データから取った集計値 | `docs/design/actuals-export.md` の「実データでの試算」に、実データの件数(計画の件数、行数、割合)がある。個人や製品を特定する値ではない。リポジトリが外に出ると、会社の生産量が推測されうる |

- **お願い(要確認)**: 上の「キッティングNo. 77種類」のうち、`docs/spec.md` の例(`0722-2-S-251014-01`)と、日付が `251013` 〜 `251020` のものは、実際に使われている番号に近い。実データから取った値でないか、担当者に確かめてほしい。そうだった場合、履歴から消す(`git filter-repo`)かどうかは別に決める。現時点で、GitHub のリポジトリが非公開であることは、このPCからは確かめていない
- **確かめられないこと**: 実データそのもの(氏名、実在の作業者ID)との照合。実データを見ない前提で調べたので、「パターンに当たらないこと」しか言えない。`legacy-db/` は `.gitignore` にあり、追跡されていない(確認済み)

---

## 7. 画面の言語とベトナム語の訳

- `frontend/src/i18n/ja.ts`、`vi.ts`、`admin/messages.ts` に、**人名、作業者ID、メールアドレス、URL、電話番号、実データらしき番号は無い**(パターンで全探索)。作業者の名前は画面で、DB の値をそのまま出す(訳さない)
- ベトナム語の訳は、辞書(`vi.ts`)に静的に入っている。**外部の翻訳サービスは使っていない**(通信は出ない)。理由と設備のベトナム語の名前(`name_vi`)は、管理者が入れる。`GET /api/masters` で誰でも読める(秘密ではない)
- 選んだ言語は `localStorage`(`genba.lang`)だけ。個人情報ではない
- 画面に個人情報が出る場所(設計どおり): ライン画面の今の担当者の名前と作業者ID、記録した人の名前、管理画面の作業者の一覧と実績の担当者。いずれも、現場の画面は認証なし(S-06)。管理画面はログインが要る
- 管理画面は日本語だけ(admin.md)。言語を切り替えても、管理画面の情報は外に出ない

---

## 調べていないこと・限界

- 本番の担当者PCと、実データ、実際のタブレットは調べていない(開発PCの使い捨て環境と、コードだけ)
- 実際の exe(PyInstaller でできたもの)に対する S-01 の再現は、していない。コードは同じ `main.py` で、`STATIC_DIR` が `_internal\frontend_dist` になるだけなので、同じ結果になると考えられる(直したあとに exe でも確かめる)
- 負荷の試験、ファジング、依存ライブラリの中身の調査はしていない
- Windows の権限(ACL)、共有フォルダの権限、Wi-Fi のネットワークの種類(プライベート / パブリック)は、担当者PCで確かめる必要がある
- 履歴の検索は、パターンによるもの。パターンに当たらない形の秘密は見つけられない
