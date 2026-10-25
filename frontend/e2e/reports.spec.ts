// 管理画面の日報を操作し、スクリーンショットを撮る(⑳ 日報の画面、㉑ 印刷のプレビュー。PDF も作る)。9行を超える日(2ページ)も確かめる。
// 記録は「押し忘れの追加」で過去の時刻に入れる(サーバーの時計は 10/21 10:00 から進む)。screens.spec.ts が使う計画と、
// ラインの今の担当者には触れない(記録した人は worker_id で指定する)。
import { expect, type Page, test } from "@playwright/test";
import { pdfContent, pdfPageCount } from "./pdf";

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
  // 日付の初期値は、サーバーの今の稼働日(確認用の時計は 10/21 10:00。ブラウザの日付ではない)
  await expect(page.getByLabel("稼働日", { exact: true })).toHaveValue("2026-10-21");
  await expect(page.getByLabel("期間の始め(稼働日)")).toHaveValue("2026-10-21");
  await expect(page.getByLabel("期間の終わり(稼働日)")).toHaveValue("2026-10-21");
  const sheet = page.locator(".report-sheet").first();
  await expect(sheet).toContainText("生産日報");
  await expect(sheet).toContainText("良品数の合計: 120");
  await expect(sheet.getByRole("table", { name: "上段 8:15〜20:15" }).getByRole("row", { name: new RegExp(MORNING) })).toBeVisible();
  await expect(sheet.getByRole("table", { name: "上段 8:15〜20:15" })).toContainText("付帯作業");
  await page.screenshot({ path: `${SCREENS}/20-daily-report.png`, fullPage: true });

  // ㉑ 稼働日 10/20 を印刷の形で(下段に夜の記録)。A4 横向きの PDF も作る
  await page.getByLabel("稼働日", { exact: true }).fill("2026-10-20");
  await expect(sheet).toContainText("良品数の合計: 150");
  await expect(sheet.getByRole("table", { name: "下段 20:15〜翌8:15" }).getByRole("row", { name: new RegExp(NIGHT) })).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("navigation", { name: "管理画面" })).toBeHidden(); // 印刷ではメニューと操作の欄を出さない
  await page.setViewportSize({ width: 1123, height: 794 }); // A4 横向き(96dpi)
  await page.screenshot({ path: `${SCREENS}/21-daily-report-print.png`, fullPage: true });
  // 「背景のグラフィック」を付けない(printBackground: false)PDF でも、棒の色(生産の緑 #1a7f37)が出る
  const pdf = await page.pdf({ path: `${SCREENS}/21-daily-report-print.pdf`, preferCSSPageSize: true, printBackground: false });
  expect(pdfContent(pdf)).toMatch(/\.102 \.498 \.2157 rg/); // #1a7f37(PDF では先頭の 0 を省いて書く)
  expect(await page.locator(".report-bar").first().evaluate((el) => getComputedStyle(el).getPropertyValue("print-color-adjust"))).toBe("exact");

  // CSV(期間とライン)を出せる
  await page.emulateMedia({ media: "screen" });
  await page.getByLabel("期間の始め(稼働日)").fill("2026-10-20");
  await page.getByLabel("期間の終わり(稼働日)").fill("2026-10-21");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV を出す" }).click();
  expect((await download).suggestedFilename()).toBe("intervals_2026-10-20_2026-10-21_all.csv");
});

test("日報は9行を超えると2ページになり、見出しが2ページ目にも出る", async ({ page }) => {
  // ラインTの10件の計画(demo-seed の計画)すべてに、10/21 の朝の段取りを後から追加する → 10行
  const knos = ["0722-1-T-261014-01", "0722-2-T-261014-02", "0800-1-T-261014-03", "0915-1-T-261014-04", "0930-1-T-261014-05",
    "0940-1-T-261014-06", "0950-1-T-261014-07", "0960-1-T-261014-08", "1000-1-T-261014-09", "1000-2-T-261014-10"];
  for (const kno of knos) await add(page, kno, "setup", "21T08:30", "21T08:50");
  await openReports(page);
  await page.getByLabel("ライン", { exact: true }).first().selectOption("T");
  await page.getByLabel("稼働日", { exact: true }).fill("2026-10-21");

  const sheets = page.locator(".report-sheet");
  await expect(sheets).toHaveCount(2);
  for (const [i, sheet] of [sheets.nth(0), sheets.nth(1)].entries()) {
    await expect(sheet.getByRole("heading", { name: "生産日報" })).toBeVisible(); // 見出し(最上部)を繰り返す
    await expect(sheet).toContainText("良品数の合計");
    await expect(sheet.locator(".report-legend")).toBeVisible();
    await expect(sheet.getByRole("table", { name: "上段 8:15〜20:15" })).toBeVisible(); // 上段・下段の目盛りも繰り返す
    await expect(sheet.getByRole("table", { name: "下段 20:15〜翌8:15" })).toBeVisible();
    await expect(sheet).toContainText(`${i + 1} / 2 ページ`);
  }
  await expect(sheets.nth(0).getByRole("table", { name: "上段 8:15〜20:15" }).getByRole("row")).toHaveCount(10); // 軸 + 9行
  await expect(sheets.nth(1).getByRole("table", { name: "上段 8:15〜20:15" }).getByRole("row")).toHaveCount(2); // 軸 + 1行
  await page.screenshot({ path: `${SCREENS}/22-daily-report-2pages.png`, fullPage: true });

  // 印刷でも2ページ(A4 横向き)
  await page.emulateMedia({ media: "print" });
  const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: false });
  expect(pdfPageCount(pdf)).toBe(2);
});
