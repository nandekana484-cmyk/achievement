// 終了していない古い記録(AD-23 2-a、2-b)。ラインWに、10日前に始めて終了していない段取りと生産がある(serve.mjs の --stale-open)。
// ライン画面: 帯を押してもその計画を選べる(範囲の端の枠は e2e/zz-timetable-range.spec.ts)。警告は実際のデータで出る(52)。
// 管理画面: 一覧(ラインで絞り込み)から、終了の時刻を入れる・取り消す。直したあとのライン画面は警告が消え、帯が止まる(53〜55)。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const SETUP = "0722-1-W-261014-01"; // 段取りが終了していない
const PROD = "0915-1-W-261014-04"; // 生産が終了していない

test.use({ viewport: { width: 1440, height: 1000 } });

const board = async (page: Page) => (await page.request.get("/api/lines/W/board", { params: { date: "2026-10-21" } })).json();

test("52 ライン画面: 古い終了していない記録の警告。帯を押しても選べる", async ({ page }) => {
  const b = await board(page);
  expect(b.stale_kitting_nos).toEqual([SETUP, PROD]);
  await page.goto("/field/lines/W");
  const alert = page.getByRole("alert").filter({ hasText: "終了していない古い記録のある計画" });
  await expect(alert).toContainText(SETUP);
  await expect(alert).toContainText("管理者に連絡してください");
  await page.screenshot({ path: `${SCREENS}/52-stale-warning.png` });

  // 帯(実績)を押しても、その計画が選ばれる(終了していない帯は範囲の頭から今まで伸びている)
  const band = page.locator(".tt-event.tt-open").first();
  await expect(band).toBeVisible();
  await band.click();
  await expect(page.locator(".tt-plan.tt-selected")).toHaveCount(1);
  await expect(page.locator(".step-button").first()).toBeVisible(); // 右のパネルに工程のボタンが出る
});

test("53 管理画面: 終了していない古い記録の一覧(ラインで絞り込み)から、終了の時刻を入れる・取り消す", async ({ page }) => {
  await page.goto("/admin/open-runs");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "終了していない古い記録" }).click();
  await page.getByLabel("ライン", { exact: true }).selectOption("W");
  const table = page.getByRole("table", { name: "終了していない古い記録" });
  await expect(table.getByRole("row")).toHaveCount(3); // 見出し + 2件
  await page.getByLabel("ライン", { exact: true }).selectOption("S");
  await expect(page.getByText("終了していない古い記録はありません")).toBeVisible(); // 絞り込める
  await page.getByLabel("ライン", { exact: true }).selectOption("W");
  await expect(table).toContainText(SETUP);
  await page.screenshot({ path: `${SCREENS}/53-open-runs-list.png`, fullPage: true });

  // 段取りに終了の時刻を入れる
  await page.getByLabel(`終了の時刻(${SETUP} 段取り)`).fill("2026-10-11T10:30");
  await page.getByRole("row", { name: new RegExp(SETUP) }).getByRole("button", { name: "終了時刻を入れる" }).click();
  await expect(page.getByRole("dialog")).toContainText("終了の時刻 2026-10-11 10:30");
  await page.getByRole("dialog").getByRole("button", { name: "終了時刻を入れる" }).click();
  await expect(page.getByRole("status")).toContainText(`${SETUP} の段取りに終了の時刻を入れました`);

  // 生産は取り消す(印を付けるだけ)
  await page.getByRole("row", { name: new RegExp(PROD) }).getByRole("button", { name: "取り消す" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "取り消す" }).click();
  await expect(page.getByRole("status")).toContainText(`${PROD} の生産を取り消しました`);
  await expect(page.getByText("終了していない古い記録はありません")).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/54-open-runs-done.png`, fullPage: true });
});

test("55 直したあとのライン画面: 警告が消え、帯が止まる", async ({ page }) => {
  const b = await board(page);
  expect(b.stale_kitting_nos).toEqual([]);
  const setup = b.plans.find((p: { plan: { kitting_no: string } }) => p.plan.kitting_no === SETUP);
  const rec = setup.events.find((e: { step_type: string }) => e.step_type === "setup");
  expect(rec.end_at).toBe("2026-10-11T10:30:00+09:00");
  const prod = b.plans.find((p: { plan: { kitting_no: string } }) => p.plan.kitting_no === PROD);
  expect(prod.events.find((e: { step_type: string }) => e.step_type === "production").voided_at).not.toBeNull(); // 行は残る
  await page.goto("/field/lines/W");
  await expect(page.locator(".tt-plan").first()).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "終了していない古い記録のある計画" })).toHaveCount(0);
  await expect(page.locator(".tt-event.tt-open")).toHaveCount(0);
  await page.screenshot({ path: `${SCREENS}/55-after-admin-fix.png` });
});
