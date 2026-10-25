# AIアシスタント向けの指示

このリポジトリは「現場実績入力・稼働率可視化Webアプリ」です。

- **作業を始める前に、必ず `docs/spec.md`(開発指針)を読むこと。** 仕様の唯一の基準です
- 特に `docs/spec.md` の「0. AIアシスタントへの指示」は必ず守ること
- 「11. 未確定事項」にある内容は勝手に決めず、仮置きで実装するときは `TODO(要確認): <項目名>` をコードに残すこと
- 既存の生産管理アプリのDBには絶対に書き込まないこと

## 構成

- `backend/` Python + FastAPI + SQLAlchemy(SQLite)。`app/` の層は api / services / db / integration / core / domain
- `frontend/` React + TypeScript + Vite。`src/field`(現場画面)、`src/admin`(管理画面)、`src/print`(記録用紙)
- 本番は、ビルドした `frontend/dist` をFastAPIが配信する1プロセス構成

## コマンド

Python は 3.14(`.python-version`)、Node.js は 22.12 以上(`frontend/.nvmrc`。vitest 5 が 22.12 以上を要る。20 ではテストが動かない)。
PATH の `python` は既存アプリ用の 3.10 の可能性があるため、**Python のコマンドはすべて venv の中で実行する**。

- venv の作成(初回のみ): `cd backend` → `py -3.14 -m venv .venv` → `.\.venv\Scripts\Activate.ps1` → `pip install -r requirements-dev.txt`
- venv の有効化: `cd backend` → `.\.venv\Scripts\Activate.ps1`(以降は `python ...` でよい)
- バックエンドのテスト: `cd backend` → `python -m pytest`
  (有効化していない場合は `.\.venv\Scripts\python.exe -m pytest`)
- バックエンドの起動: `cd backend` → `python -m uvicorn app.main:app --reload --port 8000`
  (有効化していない場合は `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`)
- マスタの追加と一覧(開発用): `cd backend` → `python -m app.cli operators add <名前> --id <作業者ID>`(legacy_app_dir の設定時は断る) / `operators list` / `equipment add <ライン> <名前> [--vi <ベトナム語の名前>]` / `equipment set-vi <ID> <名前>` / `equipment list` / `reasons list` / `reasons set-vi <ID> <名前>` / `lines list` / `admin set-password --worker-id <作業者ID>`(管理画面のパスワード。入力は画面に出ない) / `operators add <名前> --id <ID> --admin`(開発用の管理者)(対象は config.toml の `paths.database`)
- DBの構造の変更: モデル(`app/db/models.py`)を変えたら、マイグレーションを `app/db/migrations/versions/` に追加する。起動時に自動で最新に更新される(`tests/test_db.py` がモデルとマイグレーションの食い違いを検出する)
  - **Alembic を手で使う**(`python -m alembic ...`)**ときの対象は、config.toml(`GENBA_CONFIG`)の `paths.database`**。本番のDBを指していないか確認してから実行する
- フロントエンドの依存の導入: `cd frontend` → `npm ci`(`package-lock.json` のとおりに入れる)
  - 依存を足す・変える(`npm install`)ときは npm 11 を使う: `npx -y npm@11.21.0 install ...`(npm 10 は vitest 5 の peer を解けずに `edgesOut` のエラーで止まる。詳細: docs/design/dependencies.md)
- フロントエンドの開発: `cd frontend` → `npm run dev`(`/api` は8000番へ転送)
- フロントエンドのビルド: `cd frontend` → `npm run build`
- 本番の版(exe と zip)を作る: リポジトリ直下で `powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1`(`-SkipTests` でテストを省く)。できたものは `packaging\dist\`(詳細: docs/design/packaging.md)
  - `packaging\*.ps1` は UTF-8(BOM 付き)・改行 CRLF で保存する(PowerShell 5.1 が日本語を読めるように)
- APIの型の生成: `cd frontend` → `npm run gen:api`(APIを変えたら必ず実行し、`src/api/schema.ts` もコミットする。手書きの fetch は使わない)
- フロントエンドのテスト: `cd frontend` → `npm test`(vitest)。画面の確認: `npm run build` → `npm run e2e`(Playwright)
- 画面の確認用のデータ: `cd backend` → `python -m app.cli demo-seed --line S --date YYYY-MM-DD [--lot-suffix U]`(`legacy_app_dir` が設定されていると止まる。`--lot-suffix` はロットNo.の末尾に付ける文字で、ほかのラインと同じロットNo.にしないとき)

## 2拠点での作業ルール

開発は2拠点の別々のPCで行う。GitHub のリポジトリ(`origin`)を介して同期する。

- **作業の前に、必ず main を `git pull` する**(`git switch main` → `git pull`)
- 作業は `feature/<内容>` のブランチで行い、完了したら push する。**main への取り込みはレビュー後**に行う(main へ直接コミットしない)
- **既存アプリのDB、本番データ、`config.toml` は絶対にコミットしない。**
  テスト用の既存DBの複製は、各PCの `legacy-db/`(Git の対象外)に置く
- 依存ライブラリを追加・変更したら、`backend/requirements.txt`(`requirements-dev.txt`)/ `frontend/package-lock.json` を必ずコミットする
- pull して依存が変わっていたら、`pip install -r requirements-dev.txt`(venv の中で)と `npm ci` をやり直す

## 作業の決まり

- 完了報告は次の形式で書く
  1. Python と Node のバージョン
  2. テストとビルドの結果(警告も)
  3. git status
  4. 迷った点・確認したい点
  5. 指示に応じた追加の項目
  6. docs/spec.md と違う判断
  7. 作業したPC名(`$env:COMPUTERNAME`)と push したブランチ
  8. `tools/check_code_size.py` の結果
- PowerShell 5.1 でコミットするときは、メッセージをファイルに書いて `git commit -F <ファイル>` で渡す(日本語や複数行の引数が崩れるため)。commit と push は分け、間で `git log` を見て確かめる
- `npm ci` の前に、開発サーバー(`npm run dev`)を止める(動いていると node_modules のファイルを消せずに失敗する)
- `uvicorn --reload` は、環境変数と config.toml の変更を読み直さない。変えたら止めて起動し直す

## 書き方の約束

- 現在時刻は `app.core.clock.now()` を使う(`datetime.now()` を直接使わない)
- PCに依存する値は `app.core.config` から読む(パスやポートを直書きしない)
- 業務ルールは `services/` と `domain/` に置き、`api/` には書かない
- 新しいロジックにはテストを付ける
- 画面の文言は日本語。用語は `docs/spec.md` の「2. 用語集」に従う
  - 画面の文言は `frontend/src/i18n/ja.ts` に書き、画面では `t("キー")` で出す(`.tsx` に直接書かない。テストで検出する)。`vi.ts` にも同じキーを足す(詳細: docs/design/i18n.md)
  - 管理画面(`frontend/src/admin/`)は日本語だけ。文言は `src/admin/messages.ts` に書き、`at("キー")` で出す(vi.ts には足さない。詳細: docs/design/admin.md)

## コードの大きさとコメントのルール

- アプリのコードは1ファイル300行を目安とし、400行を超えたら責務ごとに分割する。テストは500行を超えたらテーマごとに分ける
- 関数は50行程度まで。超えるときは処理の段階ごとに分ける
- コメント:
  - モジュールと公開する関数には、何をするかを1〜3行で書く
  - 処理の中のコメントは、「なぜそうするのか」がコードから読み取れない場合だけ書く。コードの言い換えは書かない
  - 背景、調査結果、判断の理由、経緯は `docs/design/` の .md に書き、コードには「詳細: docs/design/○○.md」と1行だけ残す(`docs/spec.md` の該当の節からも参照する)
- 作業の最後に、必ず `python tools/check_code_size.py --top 10`(リポジトリ直下で)を実行し、結果を完了報告に入れる(完了報告の「8」とする)
  - 目安に当たるファイルだけが一覧に出る。アプリのコードで400行を超える「要分割」があると終了コードが 1 になる
