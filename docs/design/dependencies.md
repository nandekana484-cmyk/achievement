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
