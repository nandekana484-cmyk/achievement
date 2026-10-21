// 管理画面(ログインとマスタ)を操作し、スクリーンショットを撮る(⑮〜⑰)。管理者 A001 は e2e/serve.mjs で用意する。
import { expect, type Page, test } from "@playwright/test";

const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });

async function login(page: Page) {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login$/); // ログインしていなければ、ログイン画面に戻す
  await page.getByLabel("作業者ID").fill("a001"); // 作業者IDは正規化して照合する
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page.getByRole("navigation", { name: "管理画面" })).toContainText("管理 花子(A001)");
}

test.use({ viewport: { width: 1366, height: 900 } }); // 管理画面は PC で使う

test("⑮ ログイン画面(間違えたときの文)", async ({ page }) => {
  await page.goto("/field");
  await page.getByRole("link", { name: "管理画面" }).click(); // ライン選択の画面の隅のリンク
  await expect(page).toHaveURL(/\/admin\/login$/);
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("wrong-password");
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page.getByRole("alert")).toHaveText("作業者IDかパスワードが違います");
  await shot(page, "15-admin-login");
});

test("⑯ 理由の一覧と変更", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "理由" }).click();
  const table = page.locator(".admin-table");
  const row = table.getByRole("row", { name: /部品探し/ });
  await row.getByRole("button", { name: "編集" }).click();
  const editing = table.locator(".admin-editing");
  await editing.getByLabel("ベトナム語の名前").fill("Tìm linh kiện (kho)");
  await editing.getByLabel("稼働率に含める").check();
  await editing.getByRole("button", { name: "保存" }).click();
  await expect(page.getByRole("status")).toHaveText("保存しました");
  await expect(table.getByRole("row", { name: /部品探し/ })).toContainText("Tìm linh kiện (kho)");
  // 無効にすると、現場の画面では選べなくなる(行は残る)
  await table.getByRole("row", { name: /計画切替/ }).getByRole("button", { name: "無効にする" }).click();
  await expect(table.getByRole("row", { name: /計画切替/ }).getByRole("button", { name: "有効に戻す" })).toBeVisible();
  await shot(page, "16-admin-reasons");
  const masters = await page.request.get("/api/masters");
  expect((await masters.json()).reasons.map((r: { name: string }) => r.name)).not.toContain("計画切替");

  // ほかの確認に影響しないよう、元に戻す
  await table.getByRole("row", { name: /計画切替/ }).getByRole("button", { name: "有効に戻す" }).click();
  await expect(table.getByRole("row", { name: /計画切替/ }).getByRole("button", { name: "無効にする" })).toBeVisible();
  await table.getByRole("row", { name: /部品探し/ }).getByRole("button", { name: "編集" }).click();
  await editing.getByLabel("ベトナム語の名前").fill("Tìm linh kiện");
  await editing.getByLabel("稼働率に含める").uncheck();
  await editing.getByRole("button", { name: "保存" }).click();
  await expect(table.getByRole("row", { name: /部品探し/ })).not.toContainText("(kho)");
});

test("⑰ 設備の追加", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "設備" }).click();
  const form = page.getByRole("form", { name: "設備を追加" });
  await form.getByLabel("名前", { exact: true }).fill("印刷機");
  await form.getByLabel("ベトナム語の名前").fill("Máy in");
  await form.getByRole("button", { name: "追加" }).click();
  await expect(page.locator(".admin-table").getByRole("row", { name: /印刷機/ })).toContainText("Máy in");
  await shot(page, "17-admin-equipment");

  // ログアウトすると、管理画面はログイン画面に戻る
  await page.getByRole("button", { name: "ログアウト" }).click();
  await expect(page).toHaveURL(/\/admin\/login$/);
  await page.goto("/admin/equipment");
  await expect(page).toHaveURL(/\/admin\/login$/);
});
