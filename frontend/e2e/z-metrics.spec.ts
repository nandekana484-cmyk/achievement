// 効率と進捗率の画面(AD-15)。ライン画面の上部、日報の効率、管理画面の「丁取り」を撮る(㉒〜㉔)。
// reports.spec.ts と screens.spec.ts が入れた記録(0915 の段取り・N1・生産など)に、丁取りが引けない計画(0940 = K行なし)の記録を足す。
// ほかの spec が使う計画の記録を変えないよう、最後(z-)に動かす。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const MORNING = "0915-1-S-261014-04"; // 14:30〜18:00 の計画。丁取り4・タクト25秒
const NO_K = "0940-1-S-261014-06"; // 丁取りが引けない(no_k_row)

test.use({ viewport: { width: 1440, height: 1000 } });

async function add(page: Page, kno: string, step: string, start: string, end: string, qty?: number) {
  const r = await page.request.post(`/api/runs/${kno}/events`, {
    data: { request_id: `e2e-metrics-${kno}-${step}`, reason: "forgot", worker_id: "Y001", step_type: step,
      start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00`, produced_qty: qty ?? null },
  });
  expect(r.status(), await r.text()).toBe(200);
}

test("㉒ ライン画面の効率と進捗率", async ({ page }) => {
  await add(page, NO_K, "setup", "09:00", "09:30"); // 丁取りが引けない計画。効率の対象外に数える
  await page.goto("/field/lines/S");
  const bar = page.locator(".kpi-bar");
  await expect(bar).toContainText("効率");
  await expect(bar).toContainText(/対象外 [1-9]\d*件/); // 0800(丁取りなし・タクトなし)の記録も screens.spec.ts が入れている
  await expect(bar).toContainText("進捗率");
  await expect(bar.locator(".progress-chip", { hasText: MORNING })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/22-line-efficiency.png` });
});

test("㉓㉔ 日報の効率と、丁取りが引けない計画の一覧", async ({ page }) => {
  await page.goto("/admin/reports");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "日報" }).click();
  const sheet = page.locator(".report-sheet").first();
  await expect(sheet).toContainText("効率: ");
  await expect(sheet).toContainText(/効率の対象外: \d+件\(.*K行が無い 1件/);
  await page.screenshot({ path: `${SCREENS}/23-daily-report-efficiency.png`, fullPage: true });

  await page.getByRole("link", { name: "丁取り" }).click();
  await expect(page.getByRole("heading", { name: "丁取りが引けない計画" })).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(NO_K) })).toContainText("K行が無い");
  await page.screenshot({ path: `${SCREENS}/24-teitori-unresolved.png`, fullPage: true });
});
