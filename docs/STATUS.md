# 開発の状況(引き継ぎ)

作業を再開するときは、まずこの文書を読む。仕様の基準は [docs/spec.md](spec.md)、作業の決まりは [AGENTS.md](../AGENTS.md)。

- 最終更新: 2026-10-31(AD-15)
- main の最新: `git log -1 --format="%h %s" main` で確かめる(ここにはハッシュを書かない。書いても、この文書を直すコミットで古くなるため)

## 進め方

指示書(人とレビュー役のAIが作る)→ 実装(VS Code のAI)→ 完了報告 → レビュー → main に取り込み

- 作業は `feature/<内容>` のブランチで行う。main への取り込みはレビューのあと([AGENTS.md](../AGENTS.md) の「2拠点での作業ルール」)

## できていること

- 計画の同期: すべての月次DBを読む、ロットごとに正とするDBを決める、取消にしない条件と一括取消の安全装置([spec 6.1](spec.md#61-計画の取得既存--本アプリ)、[legacy-integration.md](design/legacy-integration.md))
- 生産の区切りで入れる数は良品の数(NGを含まない)。NGは別に入力する。画面の文言・日報・実績の書き出しの説明はこれに合わせた(CSV の見出し「生産数」「生産数(累計)」はそのまま)([spec 5.4](spec.md#54-回の工程))
- 実績の記録: 工程、生産の区切り、NG、備考、完了、付帯作業([spec 5.4〜5.7](spec.md#54-回の工程)、[run-records.md](design/run-records.md))
- 実績の訂正(現場の画面から): 工程の記録の時刻・生産数の変更、取り消し(印を付けて計算から外す)、押し忘れの後からの追加、付帯作業の時刻・理由の変更と取り消し、訂正の履歴(run_corrections)、完了の写しの作り直し。現場で直せるのはタイムテーブルの表示範囲の記録だけ(config.toml の `[corrections]`)([spec 5.4](spec.md#54-回の工程)、[run-records.md](design/run-records.md))
- 計画のまとまり: キッティングNo.の単位で画面と実績を扱う
- NG: ロットと面ごとに入力する
- 作業者: 既存アプリ(master.db の workers)から読み込み、作業者IDで呼び出す。計画の同期がエラーでも読み込む([spec 5.6](spec.md#56-誰がやったか))
- ライン画面: 48時間のタイムテーブル、計画の検索([spec 7.1](spec.md#71-現場画面タブレット)、[line-screen.md](design/line-screen.md))
- 管理画面(1回目): ログイン(作業者IDとパスワード、セッション、締め出し。接続元IPごとの制限、scrypt n=2^17)、設備・理由・ラインの管理、作業者の一覧、audit_log([spec 7.2](spec.md#72-管理画面pc)、[admin.md](design/admin.md))
- 日報と区間の CSV(管理画面): ラインと稼働日の日報(A4 横向きの印刷。上段 8:15〜20:15・下段 20:15〜翌8:15 のガントチャート)、稼働日をまたぐ記録を分けた「時間の区間」の CSV(BOM 付き UTF-8、CRLF。期間の上限は `[reports] max_days`)。日付の初期値はサーバーの今の稼働日。9行を超えると2ページ以上に続ける。集計はアプリでは行わず CSV で行う([spec 7.2](spec.md#72-管理画面pc)、[reports.md](design/reports.md))
- 表示言語の切り替え: 日本語とベトナム語(訳の初版を取り込み済み)。選んだ言語は端末に記憶。理由と設備はベトナム語の名前(name_vi)を出す([spec 7.5](spec.md#75-表示言語の切り替え)、[i18n.md](design/i18n.md))
- 書き込みのロック([db-writes.md](design/db-writes.md))
- コードの大きさのチェック(`tools/check_code_size.py`)
- 本番の形(exe): `packaging\build.ps1` でフォルダ形式の exe(ウィンドウを出さない形)と zip を作れる。基準のフォルダ(GENBA_HOME)から config.toml とDBを読む。起動の失敗はログのファイルに残る。担当者PCで使う自動起動(担当者のアカウントで、ログオンしているかどうかにかかわらず実行)とファイアウォールのスクリプト([spec 10](spec.md#10-開発配布運用)、[packaging.md](design/packaging.md))
- DBのバックアップ: 起動時(更新の前)と毎日 12:30 に backup_dir へ。世代は30([spec 9](spec.md#9-非機能要件))
- ログ: `logs\genba.log` に日ごとに分けて保存
- 実績の書き出し(管理画面): 片付けが終わった計画を、1行 = キッティングNo.+ロットNo.(面2の計画があるロットは面2の行にまとめる)の CSV(BOM 付きの UTF-8)で `exchange_dir\actuals` に書き出す。生産数はキッティングNo.の累計をロットに割り振り、画面で直せる(合計が合わないと書き出せない)。面1と面2は、ロットNo.+キッティングNo.の回を除いた部分(キー H)でひも付け、つながらない面1は管理者が「ひも付けの確認」で確定する(確定は表 side_links に残す。やり直しは新しい行。MSI で作った。2026-10-25 に main に取り込み)。CSV は13列(書式版 2。最後の列「面1のキッティングNo.」に、つながる面1の計画を入れる。書き出し日時の形は固定)(2026-10-25 に main に取り込み)。書き出しの履歴とダウンロード([spec 5.9](spec.md#59-実績の書き出し既存アプリに戻すための-csv)、[actuals-export.md](design/actuals-export.md))
- アクセス制限(AD-10、2026-10-25): 登録したIPアドレス(1台と CIDR、IPv6 も)だけが画面・API・静的ファイルを使える。現場用と管理画面用の2つの一覧(空なら制限しない。管理画面用が空なら現場用と同じ)、127.0.0.1 と ::1 は常に許可、TCP 接続の相手だけで判定(X-Forwarded-For は信用しない)、403 と日本語の画面、拒否のログ(同じIPは1分に1回)、起動のログ。管理画面の「アクセス制限」ページ(自分を締め出す変更は断る)と、緊急用の `GenbaCli.exe ip list / add / remove / disable-all`。開発サーバー(5173)では効かない。ファイアウォールの `-RemoteAddress` との二重の守りの手順は [security.md](design/security.md)。一覧を一度も読めないときは制限する側に倒す(127.0.0.1 と ::1 以外は 403)。管理画面で一覧が空になる変更(制限がなくなる、または広がる)は確認のダイアログを出す(初めに選ばれているのはキャンセル)。**担当者PCでの登録はまだ**([spec 7.2](spec.md#72-管理画面pc)、[spec 9](spec.md#9-非機能要件))
- 効率と進捗率(AD-15、2026-10-31): 「稼働率」を「効率」に置き換え(効率 = Σ(目標タクト × 良品台数 ÷ 丁取り数) ÷ Σ(実所要時間)。付帯作業は分母に入れない)、進捗率は時間ベース(工程の時間 ÷ 計画の時間。生産中の計画だけ)に変えた。計算は `services/metrics.py` の1か所で、ライン画面のバー・日報・区間の CSV(末尾に目標タクトと丁取り数)が同じ値になる。丁取りは既存アプリ 4.1.0 のビュー `v_board_teitori` を計画の同期で読み(表 board_teitori、マイグレーション 0015)、引けない計画は効率から外して件数と理由を出す。管理画面に「丁取り」(引けない計画の一覧)。完了の写しに丁取り数を残す。**実データでの丁取りの取得率は未確認**(NANJYOU-H の master.db にはビューも想定タクトの行も無い。既存アプリ 4.1.0 を入れた PC で確かめる)([spec 5.8](spec.md#58-効率と進捗率)、[metrics.md](design/metrics.md))
- 依存ライブラリの更新(2026-10-22): vite 7.3.7、vitest 5.0.3、react-router-dom 7.18.4、httpx → httpx2。npm audit 0件、pytest の警告 0件。更新後の exe の動作確認(起動、2つ目の停止、GenbaCli、バックアップ、自動起動とファイアウォールのスクリプト)の結果は [packaging.md](design/packaging.md) の末尾([dependencies.md](design/dependencies.md))
- 版 0.2.0(AD-13、2026-10-31): 版を 0.1.0 → 0.2.0 に上げ、`packaging\dist0.2.0\` と zip を作り直した(NANJYOU-H)。確認用のフォルダで /field・/admin/login・/api/health(version 0.2.0)と、二重起動の終了コード 2 を確かめた。sqlite3.dll は 3.50.4.0。ログイン時間のテストの上限は 1 秒 → 3 秒(NANJYOU-H で約1.5秒。scrypt の設定は変えていない)

## 次にやること(この順番の予定)

1. 実際のタブレットでの試用(ベトナム語の訳も、現場で使いながら直す)
2. 管理画面からの実績の訂正(範囲の制限なし・source=admin で同じサービスを呼ぶ)。日報と区間の CSV はできた
3. 既存アプリへの実績の反映: 本アプリの書き出し(CSV。書式版 2・13列)はできた。残りは既存アプリ側の取込口(NG の足し込み「面1 = 面1の欄 + 面2の欄」は取込口が行う。面1の計画は、列「面1のキッティングNo.」から取り、推測しない)
4. 記録用紙の印刷(A4、1回目と2回目)
5. 本番への配置: exe化とバックアップはできた。スクリプトは確認用の名前で確かめた(自動起動は AD-12 から専用アカウントが必須。SYSTEM は無くした)([packaging.md](design/packaging.md) の末尾)。残りは担当者PCでの登録と確認(zip の展開、config.toml、共有フォルダへのバックアップの書き込み、タブレットからの接続、専用アカウント・フォルダの権限・ファイアウォールの相手の範囲・アクセス制限の登録)
   - **未確認**: 担当者のアカウントでの自動起動(`install-autostart.ps1 -User`。パスワードの入力が要るため流していない)
   - **未確認**: 毎日 12:30 のバックアップ(起動時のバックアップは確かめた)

## 決まっていないこと

一覧は [spec 11. 未確定事項](spec.md#11-未確定事項)。特に大事なもの:

- 稼働率の定義
- 日報のNG数の合計の数え方(仮置き: 日報に出る計画の最新のNG数の合計)
- 既存アプリの実績の取込口の作り(書き出しの CSV の形は [spec 5.9](spec.md#59-実績の書き出し既存アプリに戻すための-csv) で決めた)

## 既知の問題

- セキュリティの調査(AD-9)の結果と修正は [security.md](design/security.md)。高の S-01・S-15(AD-11)と、S-02・S-03・S-06(role)・S-07〜S-14(AD-12。本番の `/docs` を閉じる、セキュリティヘッダー、本文の上限、同期エラーのパス、CSV の無害化、ログインの IP 制限、パスワード変更でセッション無効、アクセスログの作業者ID、scrypt の強化、管理者ルートの認証テスト)は修正済み。アクセス制限(AD-10)を追加した。**残り**: S-04・S-05 を担当者PCで実施する(専用アカウント・フォルダの権限・ファイアウォールの相手の範囲。手順は [packaging.md](design/packaging.md))、現場のPIN(S-06 の本題)、履歴のキッティングNo.の確認(S-16)
- 実績の書き出しのひも付けをキー H にしたので、実データの試算では、面2があるのに H でつながらない面1が 241行(6.4%)ある。これは「ひも付けの確認」で管理者が確定する([actuals-export.md](design/actuals-export.md) の「実データでの試算」)
- npm 10 は、依存を足す・変える(`npm install`)ときに `edgesOut` のエラーで止まる。`npx -y npm@11.21.0 install ...` を使う(`npm ci` は npm 10 で通る。[dependencies.md](design/dependencies.md))
- `build.ps1` の zip の段階が、作った直後のファイルを開けずに1回失敗した(やり直すと通った)
- 実データで、ラインの食い違いが20件、想定タクトの無い計画が2件ある。どちらも既存アプリ側の問題

## PCごとに用意が必要なもの(Git に入らないもの)

- Python 3.14 と venv(`backend/.venv`)
- Node.js 22.12 以上(vitest 5 が要る)と `npm ci`
- Playwright のブラウザ(`npx playwright install chromium`)
- `backend/data/config.toml`(`config.example.toml` からコピーして、PCに合わせて直す)
- 開発用DB(`backend/data/genba.db`。起動すると自動で作られ、最新の形になる)
- exe を作るとき: PyInstaller(`pip install -r requirements-dev.txt` で入る)。作ったものは `packaging/build/`、`packaging/dist/`(Git の対象外)

## 各PCの状況

| PC | Python | Node.js | config.toml |
| --- | --- | --- | --- |
| MSI | 3.14.4 | 22.23.2 | `legacy_app_dir` は設定しない(このPCの既存アプリのフォルダには月次DBと想定タクトの表が無いため)。確認用データ(`python -m app.cli demo-seed`)を使う |
| NANJYOU-H | 3.14.7 | 22.23.2(2026-10-23 に nvm で入れ替え) | 実データを読む設定 |

## 別のPCで再開する手順

1. `git switch main` → `git pull`
2. `cd backend` → venv の中で `pip install -r requirements-dev.txt`(2026-10-22 から httpx の代わりに httpx2。古い httpx は `pip uninstall -y httpx httpcore` で消してよい)
3. 開発サーバーを止める → `cd frontend` → `npm ci`
4. 起動する(DBは自動で最新の形になる)。`/api/health` が ok を返すことを確かめる
5. `backend/data/config.toml` の設定を確かめる(`config.example.toml` と見比べ、増えた項目を足す)
