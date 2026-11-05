# 依存ライブラリの更新の設計メモ

開発指針(docs/spec.md)の 0-8(ライブラリの追加とライセンス)にかかわる、版の選び方と更新の手順の細かい内容。

## 版の選び方

- 版は固定する(`package.json` は `^` を付けない。`requirements*.txt` は `==`)
- 公開から2週間以上たった版にする(公開の直後に見つかる問題を避けるため)
- 製品に組み込むものは GPL・AGPL を使わない。`package-lock.json` のライセンスの集計で確かめる

## 2026-10-22 の更新(feature/deps-and-exe-check)

| ライブラリ | 前 | 後 | 理由 |
| --- | --- | --- | --- |
| vite | 5.4.11 | 7.3.7 | npm audit(vite・esbuild)。8 系は下の npm の不具合のため見送った |
| @vitejs/plugin-react | 4.3.4 | 5.2.0 | vite 7 に合わせる(6 系は vite 8 が必要) |
| vitest | 3.2.7 | 5.0.3 | npm audit(vitest・tinypool。5 系は tinypool を使わない)。**Node.js 22.12 以上が必要** |
| react-router-dom | 6.30.6 | 7.18.4 | npm audit(react-router の moderate 2件)。画面のコードの変更は要らなかった |
| httpx(Python) | 0.28.1 | 外した | starlette 1.x の TestClient が httpx を非推奨にした |
| httpx2(Python) | なし | 2.13.1 | 上の代わり(BSD-3-Clause)。テストのときだけ使う。exe には入れない(`genba.spec` の excludes) |
| truststore(Python) | なし | 0.10.4 | httpx2 が使う(MIT)。最新は公開から2週間たっていないため固定した |

- 結果: npm audit は 7件 → 0件。pytest の警告は 1件 → 0件
- esbuild は vite が使う 0.28.2 になった(直接の依存ではない)

## npm 10 の不具合(edgesOut)

- vitest 5 の peer(`vite: ^6.4.0 || ^7.0.0 || ^8.0.0`)を解くときに、npm 10(Node.js 22 に付いてくる 10.9.8)が `Cannot read properties of null (reading 'edgesOut')` で止まる。vite 8 の任意の peer(`@vitejs/devtools` → vitest)をたどるところで起きる
- 依存を足す・変える(`npm install`)ときは npm 11 を使う: `npx -y npm@11.21.0 install ...`
- `npm ci`(lock のとおりに入れる)は npm 10 でも通る。各PCでは今までどおり `npm ci` でよい

## httpx2・truststore の確認(2026-10-23)

PyPI の公開ページ(JSON API)、GitHub、pypistats.org で確かめた。

| | httpx2 2.13.1(と、それが固定する httpcore2 2.13.1) | truststore 0.10.4 |
| --- | --- | --- |
| 作者(PyPI の Author) | Tom Christie(httpx の作者) | Seth Michael Larson、David Glick |
| 管理者(PyPI の Maintainer) | Pydantic Services Inc.(engineering@pydantic.dev) | (記載なし) |
| リポジトリ | https://github.com/pydantic/httpx2(Pydantic の組織。2026-05-11 作成、スター約1,600) | https://github.com/sethmlarson/truststore(2022-01-07 作成、スター約250) |
| 公開日 | 2026-09-23(最初の版は 2026-05-11。これまで22版) | 2025-08-12(最初の版は 2022-03-10。これまで17版) |
| ダウンロード数(直近1か月) | 約2億3千万(httpcore2 も同じくらい) | 約2億4千万 |
| ライセンス | BSD-3-Clause | MIT |
| PyPI の公開元の証明(PEP 740 の attestation) | 無し | 無し |

- **httpx2 が要る理由**: Starlette(FastAPI が使う)の `starlette/testclient.py`(1.9.0)は、まず `import httpx2 as httpx` を試し、無ければ httpx を使って `StarletteDeprecationWarning`「Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.」を出す。どちらも無ければ「requires the httpx2 package」で止まる
  - Starlette の依存の情報(extra `full`)に `httpx2>=2.0.0` が入ったのは 1.3.0(2026-06-11)から。FastAPI 0.150.0 の extra `standard` / `all` にも `httpx2>=2.0.0` がある
  - Starlette の説明(README)も「`httpx2` - Required if you want to use the `TestClient`」としている
- **判断**: Starlette と FastAPI の公開している依存の情報が httpx2 を名指ししていること、作者が httpx と同じで、管理が Pydantic の組織であること、ダウンロード数が httpx と同じ規模であることから、本物の公開元のものと判断した。truststore は 2022 年から続く、pip も使っているライブラリ
  - 公開元の証明(attestation)は付いていないので、上の状況から判断している
- httpx2 と truststore はテストのときだけ使う(`requirements-dev.txt`)。exe には入れない

## Excel を読むライブラリ(AD-28、2026-11-06)

管理画面「管理表の内容」の Excel 取り込み([control-sheet.md](control-sheet.md))のため。

| ライブラリ | 版 | ライセンス | 使い道 | 公開日 |
| --- | --- | --- | --- | --- |
| openpyxl | 3.1.5 | MIT | .xlsx と .xlsm を読む(`data_only=True`、`keep_vba=False` = マクロは動かさない)。依存に et-xmlfile 2.0.0(MIT) | 2024-06 |
| xlrd | 2.0.2 | BSD | .xls を読む。`formatting_info=True` で開く(罫線の斜線を読むため)。xlrd 2 は .xls だけ(.xlsx は読まない) | 2025 |
| xlwt | 1.3.0 | BSD | **開発用だけ**(`requirements-dev.txt`)。テストで .xls のブックを作る。製品には入れない | 2017 |

- どれも公開から2週間以上。製品に組み込むのは openpyxl と xlrd(MIT / BSD。GPL・AGPL ではない)
- 関数の中で読み込む(使うときだけ)。`packaging/genba.spec` の hiddenimports に openpyxl と xlrd を足した(**exe のビルドは確かめていない**。次に `packaginguild.ps1` を動かすときに、取り込みが exe でも動くか確かめる)
- ユーザーの Excel は、テストにもリポジトリにも入れない(最後に保存した人の名前などが入っているため)

## 脆弱性の確認(npm audit と pip-audit)

- フロントエンド: `cd frontend` → `npm audit`(開発用を含む)。2026-10-25 は 0件
- バックエンド: pip-audit は `requirements*.txt` には入れていない(開発指針 0-8)。使うときは、venv の外に入れる(`pip install pip-audit --target <一時フォルダ>`)か、venv に一時的に入れる
  - **日本語のコメントがある `requirements.txt` は、Windows の既定の文字コード(cp932)で読めずに止まる**(`UnicodeDecodeError: 'cp932' codec can't decode byte`)。**`PYTHONUTF8=1` を付けて動かす**
  - PowerShell: `$env:PYTHONUTF8 = "1"; python -m pip_audit -r requirements.txt --progress-spinner off`(venv の中で。venv の全パッケージを調べるときは `-r` を外す)
  - pip-audit は、パッケージ名と版を公開の脆弱性のデータベースに問い合わせる(通信が出る。ソースやデータは送らない)
- 2026-10-25(AD-9)は、`npm audit` 0件、pip-audit は既知の脆弱性なし

## 2026-11-04 JsBarcode の追加(AD-20)

| ライブラリ | 前 | 後 | 理由 |
| --- | --- | --- | --- |
| jsbarcode | なし | 3.12.3 | 識別票の Code 39 のバーコード。ライセンスは **MIT**(`node_modules/jsbarcode/MIT-LICENSE.txt`)。アプリに含める(ビルドで `dist` に入る)。CDN からは読み込まない |

- 使うのは符号にする処理だけ(`JsBarcode(object, 値, { format: "CODE39" })` で 0/1 の列を得る)。SVG はアプリ側で mm の大きさで描く(`frontend/src/print/idslips/code39.ts`)
- 依存の変更は npm 11(`npx -y npm@11.21.0 install jsbarcode`)で行った。追加した依存は jsbarcode 1つ(依存なし)
- `npm audit` は moderate 3件(minimatch → @redocly/openapi-core → openapi-typescript。開発のときだけ使う型の生成)。jsbarcode ではなく、今回の変更で増えたものではない
