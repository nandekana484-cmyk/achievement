// 現場の画面での面1と面2の紐づけ(AD-19)。1回目 Sライン、2回目 Uライン(キー H ではつながらない)を、2回目の画面で紐づけ、
// 管理画面に出るまで(㉚㉛)。書き出したあとに外すと、「書き出し後に紐づけ・割り振りが変わった計画」に出る(㉜)。
// 計画は demo-seed --side-pair(e2e/serve.mjs)。記録は「押し忘れの追加」で過去の時刻に入れる。最後(z-)に動かす。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const SIDE1 = "1200-1-S-261014-31"; // 1回目 Sライン
const SIDE2 = "1200-2-U-261014-32"; // 2回目 Uライン(同じロットNo. DEMO-L1、同じファイルNo. 1200)

test.use({ viewport: { width: 1440, height: 1000 } });

async function add(page: Page, kno: string, step: string, start: string, end: string, qty?: number) {
  const r = await page.request.post(`/api/runs/${kno}/events`, {
    data: { request_id: `e2e-side-${kno}-${step}`, reason: "forgot", worker_id: "Y001", step_type: step,
      start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00`, produced_qty: qty ?? null },
  });
  expect(r.status(), await r.text()).toBe(200);
}

async function adminActuals(page: Page) {
  await page.goto("/admin/actuals");
  await expect(page.getByRole("heading", { name: /ログイン|実績の書き出し/ }).first()).toBeVisible();
  if (page.url().includes("/admin/login")) { // 2回目からは、ログインが残っている
    await page.getByLabel("作業者ID").fill("A001");
    await page.getByLabel("パスワード").fill("e2e-admin-pass");
    await page.getByRole("button", { name: "ログイン" }).click();
    await page.getByRole("link", { name: "実績の書き出し" }).click();
  }
  await page.getByRole("combobox", { name: "ライン" }).selectOption("U");
  await page.getByRole("button", { name: "表示" }).click();
}

test("㉚㉛㉜ 現場で面1と面2を紐づけ、管理画面に出る。書き出し後に外すと一覧に出る", async ({ page }) => {
  for (const kno of [SIDE1, SIDE2]) {
    await add(page, kno, "production", "08:30", "09:00", 100);
    await add(page, kno, "cleanup", "09:00", "09:10");
  }
  const op = await page.request.put("/api/lines/U/operator", { data: { request_id: "e2e-side-op", worker_id: "Y001" } });
  expect(op.status(), await op.text()).toBe(200);

  // 2回目の画面: 同じロットNo.・ファイルNo.の1回目がちょうど1つなので、欄に最初から入っている(候補2)
  await page.goto("/field/lines/U");
  await page.locator(".tt-plan", { hasText: SIDE2 }).click();
  const field = page.getByLabel("1回目のキッティングNo.", { exact: true });
  await expect(field.locator("input")).toHaveValue(SIDE1);
  await page.screenshot({ path: `${SCREENS}/30-side-link-field.png` });
  await field.getByRole("button", { name: "紐づける" }).click();
  await expect(field).toContainText(`紐づけ済み: ${SIDE1}`);
  await expect(field).toContainText("山田(Y001)");
  await page.screenshot({ path: `${SCREENS}/31-side-link-linked.png` });

  // 管理画面: 現場の紐づけとして出る(管理者の確定は待たない)
  await adminActuals(page);
  const links = page.getByRole("table", { name: "ひも付けの確認" });
  await expect(links.getByRole("row", { name: new RegExp(SIDE1) })).toContainText("確定済み");
  await expect(links.getByRole("row", { name: new RegExp(SIDE1) })).toContainText("(現場)");
  await expect(page.getByText("ひも付けの確認が")).toHaveCount(0); // 未確定は無い
  await page.screenshot({ path: `${SCREENS}/32-side-link-admin.png`, fullPage: true });

  // 書き出す → 現場で外す(書き出し済みの確認が出る。断りはしない)
  await page.getByRole("button", { name: "CSV に書き出す" }).click();
  await expect(page.getByRole("status")).toContainText(/に書き出しました/);
  await page.goto("/field/lines/U");
  await page.locator(".tt-plan", { hasText: SIDE2 }).click();
  await page.getByLabel("1回目のキッティングNo.", { exact: true }).getByRole("button", { name: "外す" }).click();
  const dialog = page.getByRole("dialog", { name: "紐づけの確認" });
  await expect(dialog).toContainText("書き出し済みです。既存アプリの値は管理者が直す必要があります");
  await page.screenshot({ path: `${SCREENS}/33-side-link-exported-confirm.png` });
  await dialog.getByRole("button", { name: "外す" }).click();
  await expect(page.getByLabel("1回目のキッティングNo.", { exact: true }).getByRole("button", { name: "紐づける" })).toBeVisible();

  // 管理画面: 書き出し後に紐づけ・割り振りが変わった計画
  await adminActuals(page);
  const changes = page.getByRole("table", { name: "書き出し後に紐づけ・割り振りが変わった計画" });
  await expect(changes.getByRole("row", { name: new RegExp(SIDE2) })).toContainText(SIDE1);
  await expect(changes.getByRole("row", { name: new RegExp(SIDE2) })).toContainText("山田(Y001)(現場)");
  await page.screenshot({ path: `${SCREENS}/34-side-link-changes.png`, fullPage: true });
  await changes.getByRole("button", { name: "確認済み" }).click();
  await expect(page.getByRole("table", { name: "書き出し後に紐づけ・割り振りが変わった計画" })).toHaveCount(0);
});
