# 開発の状況(引き継ぎ)

作業を再開するときは、まずこの文書を読む。仕様の基準は [docs/spec.md](spec.md)、作業の決まりは [AGENTS.md](../AGENTS.md)。

- 最終更新: 2026-10-21
- main の最新: Merge branch 'feature/packaging'(この文書を直したコミットを含む)

## 進め方

指示書(人とレビュー役のAIが作る)→ 実装(VS Code のAI)→ 完了報告 → レビュー → main に取り込み

- 作業は `feature/<内容>` のブランチで行う。main への取り込みはレビューのあと([AGENTS.md](../AGENTS.md) の「2拠点での作業ルール」)

## できていること

- 計画の同期: すべての月次DBを読む、ロットごとに正とするDBを決める、取消にしない条件と一括取消の安全装置([spec 6.1](spec.md#61-計画の取得既存--本アプリ)、[legacy-integration.md](design/legacy-integration.md))
- 実績の記録: 工程、生産の区切り、NG、備考、完了、付帯作業([spec 5.4〜5.7](spec.md#54-回の工程)、[run-records.md](design/run-records.md))
- 計画のまとまり: キッティングNo.の単位で画面と実績を扱う
- NG: ロットと面ごとに入力する
- 作業者: 既存アプリ(master.db の workers)から読み込み、作業者IDで呼び出す。計画の同期がエラーでも読み込む([spec 5.6](spec.md#56-誰がやったか))
- ライン画面: 48時間のタイムテーブル、計画の検索([spec 7.1](spec.md#71-現場画面タブレット)、[line-screen.md](design/line-screen.md))
- 表示言語の切り替え: 日本語とベトナム語(訳の初版を取り込み済み)。選んだ言語は端末に記憶。理由と設備はベトナム語の名前(name_vi)を出す([spec 7.5](spec.md#75-表示言語の切り替え)、[i18n.md](design/i18n.md))
- 書き込みのロック([db-writes.md](design/db-writes.md))
- コードの大きさのチェック(`tools/check_code_size.py`)
- 本番の形(exe): `packaging\build.ps1` でフォルダ形式の exe(ウィンドウを出さない形)と zip を作れる。基準のフォルダ(GENBA_HOME)から config.toml とDBを読む。起動の失敗はログのファイルに残る。担当者PCで使う自動起動(担当者のアカウントで、ログオンしているかどうかにかかわらず実行)とファイアウォールのスクリプト([spec 10](spec.md#10-開発配布運用)、[packaging.md](design/packaging.md))
- DBのバックアップ: 起動時(更新の前)と毎日 12:30 に backup_dir へ。世代は30([spec 9](spec.md#9-非機能要件))
- ログ: `logs\genba.log` に日ごとに分けて保存

## 次にやること(この順番の予定)

1. 実際のタブレットでの試用(ベトナム語の訳も、現場で使いながら直す)
2. 管理画面(ログイン、実績の訂正、マスタ(ベトナム語の名前、ラインの名前を含む)、24時間の日報)
3. 既存アプリへの実績の反映
   - NG は「面1 = 面1の欄 + 面2の欄」の形への変換が必要([run-records.md](design/run-records.md))
   - 生産数をロットに分けるかは未決定
4. 記録用紙の印刷(A4、1回目と2回目)
5. 本番への配置: exe化とバックアップはできた。残りは担当者PCでの登録と確認(zip の展開、config.toml、自動起動とファイアウォールのスクリプトの実行、共有フォルダへのバックアップの書き込み、タブレットからの接続)
6. 依存ライブラリの更新
   - 先に NANJYOU-H の Node を 22 に上げる
   - そのあと vite・vitest・esbuild を更新し、pytest の httpx の警告に対応する

## 決まっていないこと

一覧は [spec 11. 未確定事項](spec.md#11-未確定事項)。特に大事なもの:

- 稼働率の定義
- 想定タクトの単位(仮置き: 1枚あたりの秒)
- 生産数のロットへの分け方
- 実績の取込口の仕様(列、文字コード、実績日の定義)

## 既知の問題

- npm audit の残り: 7件(critical 2: vitest・tinypool、high 1: vite、moderate 4: esbuild・@vitest/mocker・react-router・react-router-dom)。「次にやること」の 6 で対応する
- 実データで、ラインの食い違いが20件、想定タクトの無い計画が2件ある。どちらも既存アプリ側の問題

## PCごとに用意が必要なもの(Git に入らないもの)

- Python 3.14 と venv(`backend/.venv`)
- Node.js(22 推奨)と `npm ci`
- Playwright のブラウザ(`npx playwright install chromium`)
- `backend/data/config.toml`(`config.example.toml` からコピーして、PCに合わせて直す)
- 開発用DB(`backend/data/genba.db`。起動すると自動で作られ、最新の形になる)
- exe を作るとき: PyInstaller(`pip install -r requirements-dev.txt` で入る)。作ったものは `packaging/build/`、`packaging/dist/`(Git の対象外)

## 各PCの状況

| PC | Python | Node.js | config.toml |
| --- | --- | --- | --- |
| MSI | 3.14.4 | 22.23.2 | `legacy_app_dir` は設定しない(このPCの既存アプリのフォルダには月次DBと想定タクトの表が無いため)。確認用データ(`python -m app.cli demo-seed`)を使う |
| NANJYOU-H | 3.14.7 | 20.19.6 | 実データを読む設定 |

## 別のPCで再開する手順

1. `git switch main` → `git pull`
2. `cd backend` → venv の中で `pip install -r requirements-dev.txt`
3. 開発サーバーを止める → `cd frontend` → `npm ci`
4. 起動する(DBは自動で最新の形になる)。`/api/health` が ok を返すことを確かめる
5. `backend/data/config.toml` の設定を確かめる(`config.example.toml` と見比べ、増えた項目を足す)
