// 管理画面の「実績の書き出し」: ログイン → 一覧 → 数を直す → 書き出し → ダウンロード(㉒㉓)。
// ラインU(demo-seed --lot-suffix U)だけを使い、ほかの確認(ラインS・T)には触れない。記録した人は worker_id で指定する。
import { readFile } from "node:fs/promises";
import { expect, type Page, test } from "@playwright/test";

const SIDE2 = "1000-2-U-261014-10"; // 3ロット(DEMO-101U 150、102U 100、103U 50)の面2。面1は 1000-1-U-261014-09
const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });

async function api(page: Page, method: "post" | "put", url: string, data: Record<string, unknown>) {
  const r = await page.request[method](url, { data: { request_id: `e2e-actuals-${url}-${JSON.stringify(data)}`, worker_id: "Y001", ...data } });
  expect(r.status(), await r.text()).toBe(200);
}

/** 面2の計画で、生産(310枚)・NG・片付けを記録して完了にする。 */
async function completeSide2(page: Page) {
  await api(page, "post", `/api/runs/${SIDE2}/steps/production/start`, {});
  await api(page, "post", `/api/runs/${SIDE2}/steps/production/end`, { produced_qty: 310 });
  await api(page, "put", `/api/runs/${SIDE2}/ng-qty`, { lot_no: "DEMO-101U", side: 1, ng_qty: 2 });
  await api(page, "put", `/api/runs/${SIDE2}/ng-qty`, { lot_no: "DEMO-101U", side: 2, ng_qty: 1 });
  await api(page, "post", `/api/runs/${SIDE2}/steps/cleanup/start`, {});
  await api(page, "post", `/api/runs/${SIDE2}/steps/cleanup/end`, {});
}

test.use({ viewport: { width: 1600, height: 1000 } }); // 管理画面は PC で使う

test("㉒㉓ 実績の書き出し(一覧・数を直す・書き出し)", async ({ page }) => {
  await completeSide2(page);
  await page.goto("/admin/actuals");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "実績の書き出し" }).click();
  await expect(page.getByRole("heading", { name: "実績の書き出し", exact: true })).toBeVisible();

  await page.getByRole("combobox", { name: "ライン" }).selectOption("U");
  await page.getByRole("button", { name: "表示" }).click();
  const table = page.locator(".actuals-table");
  await expect(table.locator("tbody tr")).toHaveCount(3); // 面2の行だけ(面1の行は面2にまとめる)
  const qty = (lot: string) => page.getByLabel(`${SIDE2} ${lot} の生産数`);
  await expect(qty("DEMO-101U")).toHaveValue("150");
  await expect(qty("DEMO-103U")).toHaveValue("60"); // 余りは最後のロット
  await expect(table.getByRole("row", { name: /DEMO-101U/ })).toContainText("山田(Y001)"); // 片付けを終えた人

  // 1行だけ直すと合計が合わず、書き出せない
  await qty("DEMO-101U").fill("140");
  await expect(page.getByRole("alert")).toHaveText(
    `キッティングNo. ${SIDE2} のロットの生産数の合計(300)が、記録の累計(310)と一致しません。ロットの数を直してください`);
  const exportButton = page.getByRole("button", { name: "CSV に書き出す" });
  await expect(exportButton).toBeDisabled();
  await shot(page, "22-actuals-mismatch");

  await qty("DEMO-103U").fill("70");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await exportButton.click();
  await expect(page.getByRole("status")).toContainText(/actuals_\d{8}_\d{6}_\d{4}\.csv に書き出しました\(3行\)/);
  const history = page.getByRole("table", { name: "書き出しの履歴" });
  await expect(history.locator("tbody tr")).toHaveCount(1);
  await expect(page.getByRole("note")).toContainText("Excel で保存せずに");
  await shot(page, "23-actuals-exported");

  const [download] = await Promise.all([page.waitForEvent("download"), history.getByRole("button", { name: "ダウンロード" }).click()]);
  const text = (await readFile(await download.path())).toString("utf-8");
  expect(text.startsWith("﻿書式版,書き出し日時,元のDB(フォルダ名),キッティングNo.,ロットNo.,ファイルNo.,面,日付,生産数(累計),NG面1,NG面2,担当者ID\r\n")).toBe(true);
  const lines = text.trim().split("\r\n").slice(1).map((l) => l.split(","));
  expect(lines.every((l) => l.length === 12 && l[0] === "1")).toBe(true);
  expect(lines.map((l) => l.slice(2))).toEqual([
    ["demo", SIDE2, "DEMO-101U", "1000", "2", "2026-10-21", "140", "2", "1", "Y001"],
    ["demo", SIDE2, "DEMO-102U", "1000", "2", "2026-10-21", "100", "0", "0", "Y001"],
    ["demo", SIDE2, "DEMO-103U", "1000", "2", "2026-10-21", "70", "0", "0", "Y001"],
  ]);
});
