// ライン画面を操作し、確認用のスクリーンショットを test-results/screens/ に撮る(①〜⑦)。
import { expect, type Page, test } from "@playwright/test";

const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/screens/${name}.png` });
const step = (page: Page, name: string) => page.locator(".step-button", { hasText: name });

test("ライン画面の操作", async ({ page }) => {
  // ① ライン選択
  await page.goto("/field");
  const lineLink = page.getByRole("link", { name: "Sライン" });
  await expect(lineLink).toBeVisible();
  await shot(page, "01-line-select");

  // ② ライン画面(計画を選んでいない。担当者は未設定)
  await lineLink.click();
  await expect(page.locator(".tt-plan").first()).toBeVisible();
  await expect(page.getByText("担当者が設定されていません。ボタンを押す前に")).toBeVisible();
  await shot(page, "02-line-screen");

  // ⑦ 409 のエラー表示: 担当者を選ばずに工程のボタンを押す
  await page.locator(".tt-plan", { hasText: "0722-1-S-" }).click();
  await expect(page.getByRole("region", { name: "選んだ計画" })).toBeVisible();
  await step(page, "段取り").click();
  await expect(page.getByRole("alert")).toContainText("担当者が設定されていません");
  await shot(page, "07-error-409");

  // 担当者を選んでから、段取りを開始する
  await page.getByRole("button", { name: "担当者を選ぶ" }).click();
  await page.getByRole("dialog", { name: "担当者の交代" }).getByRole("button", { name: "山田" }).click();
  await expect(page.locator(".kpi-button")).toContainText("山田");
  await step(page, "段取り").click();
  await expect(step(page, "段取り")).toContainText("作業中");
  await step(page, "段取り").click();
  await expect(step(page, "段取り")).toContainText("済");

  // ③ 計画を選んだ状態(生産 1回目を作業中にする)
  await step(page, "生産 1回目").click();
  await expect(step(page, "生産 1回目")).toContainText("作業中");
  await shot(page, "03-plan-selected");

  // ④ 生産の終了のテンキー
  await step(page, "生産 1回目").click();
  const pad = page.getByRole("dialog", { name: "生産 1回目の終了" });
  for (const k of ["1", "2", "0"]) await pad.getByRole("button", { name: k, exact: true }).click();
  await expect(pad.getByLabel("入力した数")).toHaveText("120");
  await shot(page, "04-production-keypad");
  await pad.getByRole("button", { name: "生産を終了" }).click();
  await expect(page.locator(".fact", { hasText: "生産数の合計" })).toContainText("120");

  // ⑤ 生産の2回目の再開理由(設備が必要な理由を選ぶと、設備も選べる)
  await step(page, "生産 2回目").click();
  const reason = page.getByRole("dialog", { name: "生産 2回目の開始" });
  await reason.getByRole("button", { name: "マシントラブル" }).click();
  await reason.getByRole("button", { name: "マウンター1" }).click();
  await shot(page, "05-restart-reason");
  await reason.getByRole("button", { name: "生産を開始" }).click();
  await expect(step(page, "生産 2回目")).toContainText("作業中");

  // ⑥ 付帯作業の作業中
  await page.locator(".reason-button", { hasText: "部品探し" }).click();
  const open = page.locator(".open-event", { hasText: "部品探し" });
  await expect(open).toContainText("作業中");
  await expect(open.getByRole("button", { name: "終了" })).toBeVisible();
  await open.scrollIntoViewIfNeeded();
  await shot(page, "06-line-event-doing");
});

for (const width of [1024, 1366]) {
  test(`横向き ${width}px で横にはみ出さない`, async ({ page }) => {
    await page.setViewportSize({ width, height: 768 });
    await page.goto("/field/lines/S");
    await expect(page.locator(".tt-plan").first()).toBeVisible();
    await page.locator(".tt-plan").first().click();
    await expect(page.getByRole("region", { name: "選んだ計画" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    // 押す部分は高さ 56px 以上
    for (const sel of [".step-button", ".reason-button", ".menu-item", ".kpi-button"]) {
      const heights = await page.locator(sel).evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
      expect(Math.min(...heights), sel).toBeGreaterThanOrEqual(56);
    }
  });
}
