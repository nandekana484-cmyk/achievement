// 管理画面の「アクセス制限」を操作し、スクリーンショットを撮る(㉕㉖)。確認用のサーバーは 127.0.0.1 で動くので、
// 接続元はサーバーのPC自身(常に許可される)。許可されない接続元の 403 は pytest(tests/admin/test_ip_access.py)で確かめる。
import { expect, type Page, test } from "@playwright/test";

const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });

async function login(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("作業者ID").fill("a001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page.getByRole("navigation", { name: "管理画面" })).toContainText("管理 花子(A001)");
}

test.use({ viewport: { width: 1366, height: 900 } });

test("㉕㉖ アクセス制限(一覧・追加・今の接続元を追加・一覧が空になる変更の確認・無効化)", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "アクセス制限" }).click();
  const status = page.getByRole("group", { name: "今の状態" });
  await expect(status).toContainText("今の接続元: 127.0.0.1(サーバーのPC自身。常に許可されます)");
  await expect(status).toContainText("現場用: 制限なし");
  await expect(status).toContainText("管理画面用: 一覧が空(現場用と同じ)");
  await expect(page.getByText("登録はありません(制限していません)")).toBeVisible();

  // 書き方の誤りは、送る前に気づく
  const form = page.getByRole("form", { name: "アクセスを許可する範囲を追加" });
  await form.getByLabel("IPアドレスまたは範囲").fill("192.168.3.999");
  await form.getByRole("button", { name: "追加", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("書き方を確かめてください(例 192.168.3.5、192.168.3.0/24)");

  // 範囲の追加(現場用)
  await form.getByLabel("IPアドレスまたは範囲").fill("192.168.3.0/24");
  await form.getByLabel("メモ").fill("タブレット");
  await form.getByRole("button", { name: "追加", exact: true }).click();
  const table = page.locator(".admin-table");
  await expect(table.getByRole("row", { name: /192\.168\.3\.0\/24/ })).toContainText("タブレット");
  await expect(status).toContainText("現場用: 制限あり(有効な範囲 1件)");
  await expect(status).toContainText("この接続元で現場の画面: 使えます"); // サーバーのPC自身は常に許可

  // 今の接続元を管理画面用に追加(追加すると、もう一度は押せない)
  await form.getByLabel("区分").selectOption("admin");
  await form.getByRole("button", { name: "今の接続元を追加" }).click();
  await expect(table.getByRole("row", { name: /127\.0\.0\.1\/32/ })).toContainText("管理画面用");
  await expect(status).toContainText("管理画面用: 制限あり(有効な範囲 1件)");
  await expect(form.getByRole("button", { name: "今の接続元を追加" })).toBeDisabled();
  await shot(page, "25-admin-access");

  // 一覧が空になる変更は、確認してから送る。初めに選ばれているのは「キャンセル」
  const disableButton = (net: RegExp) => table.getByRole("row", { name: net }).getByRole("button", { name: "無効にする" });
  const dialog = page.getByRole("dialog");
  await disableButton(/192\.168\.3\.0\/24/).click(); // 現場用の最後の1件(管理画面用は残る)
  await expect(dialog).toContainText("現場用の一覧が空になると、現場の画面はすべての接続元に許可されます。よろしいですか");
  await dialog.getByRole("button", { name: "無効にする" }).click();
  await expect(table.getByRole("row", { name: /192\.168\.3\.0\/24/ })).toContainText("無効(");

  await disableButton(/127\.0\.0\.1\/32/).click(); // 最後の1件 = 制限がなくなる
  await expect(dialog).toContainText("一覧が空になると、すべての接続元が許可されます。よろしいですか");
  await expect(dialog.getByRole("button", { name: "キャンセル" })).toBeFocused();
  await shot(page, "26-admin-access-confirm");
  await dialog.getByRole("button", { name: "キャンセル" }).click(); // やめると、何も変わらない
  await expect(dialog).toBeHidden();
  await expect(table.getByRole("row", { name: /127\.0\.0\.1\/32/ })).toContainText("有効");
  await disableButton(/127\.0\.0\.1\/32/).click();
  await page.keyboard.press("Escape"); // Esc でもキャンセル
  await expect(dialog).toBeHidden();
  await expect(table.getByRole("row", { name: /127\.0\.0\.1\/32/ })).toContainText("有効");
  await disableButton(/127\.0\.0\.1\/32/).click();
  await dialog.getByRole("button", { name: "無効にする" }).click();
  await expect(table.getByRole("row", { name: /127\.0\.0\.1\/32/ })).toContainText("無効(");
  await expect(status).toContainText("現場用: 制限なし");
  await expect(status).toContainText("管理画面用: 一覧が空(現場用と同じ)");
  await expect(table.getByRole("row")).toHaveCount(3); // 見出し + 無効にした2行(行は消えない)
});
