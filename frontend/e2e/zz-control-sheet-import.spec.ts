// 管理表の内容の Excel 取り込み(AD-28): 管理画面でブックを選ぶ → 確かめるだけの結果 → 登録するシートを選んで登録 → 識別票のページで管理表を印刷すると取り込んだ内容が出る。
// ブックは e2e/serve.mjs が backend/tests/make_e2e_book.py で作る(テストのコードで作ったもの。ユーザーの Excel ではない)。
// 取り込むファイルNo.は 0930(新規)と 0940(手で登録済み → 変更あり)。zz-control-sheet.spec.ts の 0722・0915・1000 と重ならないようにしている。
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { pdfPageCount } from "./pdf";

const SCREENS = "test-results/screens";
const BOOK = resolve("test-results", "e2e-data", "import-test.xlsx");
const H = { "X-Genba-Admin": "1" };

test.use({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });

async function login(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("作業者ID").fill("a001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "管理表の内容" }).click();
}

test("74 管理画面で Excel を取り込む: 確かめる(DBに書かない)→ 登録 → 一覧と履歴", async ({ page }) => {
  await login(page);
  // 0940 は先に手で登録しておく(取り込みで上書きされる)
  const put = await page.request.put("/api/admin/control-sheets/0940", { data: { manager_no: "手で直した", rows: [{ name: "手で直した行", name_vi: "vi" }] }, headers: H });
  expect(put.status()).toBe(200);
  await page.reload();

  await page.getByLabel("ブックを選ぶ").setInputFiles(BOOK);
  const table = page.getByRole("table", { name: /確かめる結果/ });
  await expect(table).toBeVisible();
  await expect(page.getByText("新規 1・変更あり 1・変更なし 0・飛ばした 1・エラー 1")).toBeVisible();
  await expect(table.getByRole("row", { name: /930/ }).first()).toContainText("新規");
  await expect(table.getByRole("row", { name: /0940/ })).toContainText("変更あり");
  await expect(table.getByRole("row", { name: /0940/ })).toContainText("管理画面で直した内容を上書きします");
  await expect(table.getByRole("row", { name: /Sheet1/ })).toContainText("飛ばした");
  await expect(table.getByRole("row", { name: /0960/ })).toContainText("エラー");
  await expect(table.getByRole("row", { name: /0960/ })).toContainText("見出し「管理No」が見つかりません");
  await expect(page.getByRole("alert").filter({ hasText: "1 件は、管理画面で作った・直した内容を上書きします" })).toBeVisible();
  await table.getByRole("row", { name: /0940/ }).locator("summary").click(); // 今の内容との違い
  await expect(table.getByRole("row", { name: /0940/ })).toContainText("「手で直した」→「MP-0940N」");
  await expect(table.getByRole("row", { name: /0940/ })).toContainText("1 行目「手で直した行」(工程名が変わった・なくなった)のベトナム語「vi」と対応「なし」は消えます"); // 工程名が変わった行のベトナム語は引き継げない
  await expect(page.getByText("引き継げずに消えるものは 1 件です")).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/74-import-preview.png`, fullPage: true });

  // 確かめただけでは登録されていない
  const before = await (await page.request.get("/api/admin/control-sheets/0930", { headers: H })).status();
  expect(before).toBe(404);

  await page.getByRole("button", { name: "登録(2 件)" }).click();
  await expect(page.getByRole("status").filter({ hasText: "2 件を登録しました(ブック「import-test.xlsx」)" })).toBeVisible();
  const list = page.getByRole("table", { name: "管理表の内容" });
  await expect(list.getByRole("row", { name: /0930/ })).toContainText("登録済み");
  await expect(list.getByRole("row", { name: /0930/ })).toContainText("MP-0930");
  await expect(list.getByRole("row", { name: /0940/ })).toContainText("MP-0940N");
  const history = page.getByRole("table", { name: "取り込みの履歴" });
  await expect(history.getByRole("row", { name: /import-test\.xlsx/ })).toContainText("管理 花子");
  await page.screenshot({ path: `${SCREENS}/75-import-after.png`, fullPage: true });

  // 上書きの前の内容(手で直したもの)は履歴から見られる
  await list.getByRole("row", { name: /0940/ }).getByRole("button", { name: "編集" }).click();
  await expect(page.locator(".cs-history li")).toHaveCount(2);
  await expect(page.locator(".cs-history li").first()).toContainText("Excel から取り込み(ブック「import-test.xlsx」)");
  await page.locator(".cs-history li", { hasText: "版 1" }).getByRole("button", { name: "この版を読み込む" }).click();
  await expect(page.getByLabel("管理No")).toHaveValue("手で直した");
});

test("75 取り込んだ内容が、識別票のページの管理表に出る(登録した行 + 8行になるまでの空の行)", async ({ page }) => {
  const board = await (await page.request.get("/api/lines/K/board", { params: { date: "2026-10-21" } })).json();
  const kno = board.plans.find((p: { plan: { kitting_no: string } }) => p.plan.kitting_no.startsWith("0930-1-")).plan.kitting_no;
  await page.addInitScript(() => { window.print = () => undefined; });
  await page.goto(`/field/print/id-slips/${kno}`);
  for (const k of ["1 基板製品ロット現品票", "2 バーコード印字 完了", "3 1回目完了済み", "4 バーコード照合用"]) await page.getByRole("checkbox", { name: k }).setChecked(false);
  await page.getByRole("checkbox", { name: "5 管理表(A4縦)" }).setChecked(true);
  await expect(page.locator(".idslip-warn", { hasText: "未登録" })).toHaveCount(0); // 取り込んだので未登録ではない
  await page.getByRole("row", { name: "5 管理表(A4縦)" }).getByRole("button", { name: "この種類を印刷" }).click();
  await page.emulateMedia({ media: "print" });
  const sheet = page.locator(".idslip-group.is-printing .sk");
  await expect(sheet.locator(".sk-manager-value")).toHaveText("MP-0930");
  const rows = sheet.locator(".sk-row");
  await expect(rows).toHaveCount(8);
  await expect(rows.nth(0)).toContainText("リフロー");
  await expect(rows.nth(0)).toContainText("社内");
  await expect(rows.nth(0)).not.toContainText("INTERNO"); // 区分に入れて、工程名から外した
  await expect(rows.nth(0).locator(".sk-proc")).toHaveText("Side A\n温度 245℃");
  await expect(rows.nth(1)).toContainText("社外");
  const diagonal = await rows.evaluateAll((all) => all.map((r) => r.children[3].classList.contains("sk-diagonal")));
  expect(diagonal).toEqual([false, true, false, true, true, true, true, true]); // 取り込んだ斜線(2行目)、使う行(1・3行目)、足した空の行(4〜8)
  expect(pdfPageCount(await page.pdf({ preferCSSPageSize: true }))).toBe(1);
  await page.emulateMedia({ media: "screen" });
  await page.locator(".idslip-group[data-kind='5'] .slip-frame").first().screenshot({ path: `${SCREENS}/76-import-printed.png` });
});
