// 管理画面の日報を操作し、スクリーンショットを撮る(⑳ 日報の画面、㉑ 印刷のプレビュー。PDF も作る)。
// 記録は「押し忘れの追加」で過去の時刻に入れる(サーバーの時計は 10/21 10:00 から進む)。screens.spec.ts が使う計画と、
// ラインの今の担当者には触れない(記録した人は worker_id で指定する)。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const NIGHT = "0930-1-S-261014-05"; // 10/20 の夜から 10/21 の朝(稼働日の境目 8:15 をまたぐ片付け)
const MORNING = "0915-1-S-261014-04";

async function add(page: Page, kno: string, step: string, start: string, end: string, qty?: number) {
  const r = await page.request.post(`/api/runs/${kno}/events`, {
    data: { request_id: `e2e-report-${kno}-${step}-${start}`, reason: "forgot", worker_id: "Y001", step_type: step,
      start_at: `2026-10-${start}:00+09:00`, end_at: `2026-10-${end}:00+09:00`, produced_qty: qty ?? null },
  });
  expect(r.status(), await r.text()).toBe(200);
}

async function seedRecords(page: Page) {
  await add(page, NIGHT, "setup", "20T21:00", "20T21:30");
  await add(page, NIGHT, "production", "20T21:30", "20T23:50", 150);
  await add(page, NIGHT, "first_article", "20T23:50", "21T00:10");
  await add(page, NIGHT, "cleanup", "21T07:50", "21T08:30");
  await add(page, MORNING, "setup", "21T08:30", "21T08:50");
  await add(page, MORNING, "n1_check", "21T08:50", "21T09:00");
  await add(page, MORNING, "production", "21T09:00", "21T09:50", 120);
  // 付帯作業: 開始・終了してから、時刻を訂正で 9:10〜9:30 にする
  const start = await page.request.post("/api/lines/S/events/start", {
    data: { request_id: "e2e-report-ev-s", reason_id: 4, worker_id: "Y001" },
  });
  const ev = await start.json();
  await page.request.post(`/api/lines/S/events/${ev.id}/end`, { data: { request_id: "e2e-report-ev-e", worker_id: "Y001" } });
  const fix = await page.request.patch(`/api/lines/S/events/${ev.id}`, {
    data: { request_id: "e2e-report-ev-fix", reason: "forgot", worker_id: "Y001",
      start_at: "2026-10-21T09:10:00+09:00", end_at: "2026-10-21T09:30:00+09:00" },
  });
  expect(fix.status(), await fix.text()).toBe(200);
}

async function openReports(page: Page) {
  await page.goto("/admin/reports");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "日報" }).click();
  await expect(page.getByRole("heading", { name: "日報", exact: true })).toBeVisible();
}

test.use({ viewport: { width: 1440, height: 1000 } }); // 管理画面は PC で使う(A4 横向きの幅が入る大きさ)

test("⑳㉑ 日報の画面と印刷のプレビュー", async ({ page }) => {
  await seedRecords(page);
  await openReports(page);

  // ⑳ 稼働日 10/21: 上段に朝の記録、境目をまたぐ片付けは 8:15 からの分だけ
  await page.getByLabel("稼働日", { exact: true }).fill("2026-10-21");
  const sheet = page.locator(".report-sheet").first();
  await expect(sheet).toContainText("生産日報");
  await expect(sheet).toContainText("生産数の合計: 120");
  await expect(sheet.getByRole("table", { name: "上段 8:15〜20:15" }).getByRole("row", { name: new RegExp(MORNING) })).toBeVisible();
  await expect(sheet.getByRole("table", { name: "上段 8:15〜20:15" })).toContainText("付帯作業");
  await page.screenshot({ path: `${SCREENS}/20-daily-report.png`, fullPage: true });

  // ㉑ 稼働日 10/20 を印刷の形で(下段に夜の記録)。A4 横向きの PDF も作る
  await page.getByLabel("稼働日", { exact: true }).fill("2026-10-20");
  await expect(sheet).toContainText("生産数の合計: 150");
  await expect(sheet.getByRole("table", { name: "下段 20:15〜翌8:15" }).getByRole("row", { name: new RegExp(NIGHT) })).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("navigation", { name: "管理画面" })).toBeHidden(); // 印刷ではメニューと操作の欄を出さない
  await page.setViewportSize({ width: 1123, height: 794 }); // A4 横向き(96dpi)
  await page.screenshot({ path: `${SCREENS}/21-daily-report-print.png`, fullPage: true });
  await page.pdf({ path: `${SCREENS}/21-daily-report-print.pdf`, preferCSSPageSize: true, printBackground: true });

  // CSV(期間とライン)を出せる
  await page.emulateMedia({ media: "screen" });
  await page.getByLabel("期間の始め(稼働日)").fill("2026-10-20");
  await page.getByLabel("期間の終わり(稼働日)").fill("2026-10-21");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV を出す" }).click();
  expect((await download).suggestedFilename()).toBe("intervals_2026-10-20_2026-10-21_all.csv");
});
