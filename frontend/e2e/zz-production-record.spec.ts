// 生産記録票の印刷(AD-18)。印刷のメディアで A4 縦 1 ページに収まること(10ロット、各面の生産の区切り6つ、付帯作業5件)と、
// 両面1組・片面だけ・「1回目 Sライン、2回目 Uライン」・面1とつながっていない面2の見た目(スクリーンショット)。
// 計画は demo-seed --record-samples(ラインR)と --side-pair(e2e/serve.mjs)。記録は「押し忘れの追加」で過去の時刻に入れる。最後に動かす。
import { expect, type Page, test } from "@playwright/test";
import { pdfPageCount } from "./pdf";

const SCREENS = "test-results/screens";
const R1 = "1300-1-R-261014-41"; // 10ロットの両面の組(キッティングNo.でつながる)
const R2 = "1300-2-R-261014-41";
const ONE = "1301-1-R-261014-43"; // 片面だけ
const LONELY = "1302-2-R-261014-45"; // 面1とつながっていない面2
const S1 = "1200-1-S-261014-31"; // 1回目 Sライン
const S2 = "1200-2-U-261014-32"; // 2回目 Uライン(z-side-link.spec.ts で記録を入れてある)
const A4_PRINT_HEIGHT_PX = ((297 - 16) / 25.4) * 96; // 余白 8mm を除いた高さ

test.use({ viewport: { width: 1280, height: 1000 } });

type Step = [string, string, string, number?];

async function add(page: Page, kno: string, steps: Step[]) {
  for (const [i, [step, start, end, qty]] of steps.entries()) {
    const r = await page.request.post(`/api/runs/${kno}/events`, {
      data: { request_id: `e2e-rec-${kno}-${i}`, reason: "forgot", worker_id: "Y001", step_type: step,
        start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00`, produced_qty: qty ?? null },
    });
    expect(r.status(), await r.text()).toBe(200);
  }
}

/** 最初の工程の開始が from の、一通りの工程(生産は6つの区切り)。 */
function full(hour: number, minute: number): Step[] {
  const at = (m: number) => `${String(hour + Math.floor((minute + m) / 60)).padStart(2, "0")}:${String((minute + m) % 60).padStart(2, "0")}`;
  const steps: Step[] = [["setup", at(0), at(5)], ["n1_check", at(5), at(8)], ["first_article", at(8), at(10)]];
  for (let i = 0; i < 6; i++) steps.push(["production", at(10 + i * 3), at(13 + i * 3), 20]);
  steps.push(["xray", at(28), at(30)], ["cleanup", at(30), at(35)]);
  return steps;
}

async function trouble(page: Page, reasonId: number, text: string, start: string, end: string, n: number) {
  const s = await page.request.post("/api/lines/R/events/start", { data: { request_id: `e2e-rec-ev-s-${n}`, worker_id: "Y001", reason_id: reasonId, reason_text: text } });
  expect(s.status(), await s.text()).toBe(200);
  const { id } = await s.json();
  const e = await page.request.post(`/api/lines/R/events/${id}/end`, { data: { request_id: `e2e-rec-ev-e-${n}`, worker_id: "Y001" } });
  expect(e.status(), await e.text()).toBe(200);
  const p = await page.request.patch(`/api/lines/R/events/${id}`, {
    data: { request_id: `e2e-rec-ev-p-${n}`, reason: "mistake", worker_id: "Y001",
      start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00` },
  });
  expect(p.status(), await p.text()).toBe(200);
}

async function fitsOnePage(page: Page) {
  await page.emulateMedia({ media: "print" });
  const box = await page.locator(".record-sheet").boundingBox();
  const pdf = await page.pdf({ preferCSSPageSize: true });
  return { height: box?.height ?? 0, pages: pdfPageCount(pdf) };
}

test("㉟〜㊴ 生産記録票: A4縦1ページに収まる。両面1組・片面・S/U・面1なし", async ({ page }) => {
  const op = await page.request.put("/api/lines/R/operator", { data: { request_id: "e2e-rec-op", worker_id: "Y001" } });
  expect(op.status(), await op.text()).toBe(200);
  const masters = await (await page.request.get("/api/masters?line_code=R")).json();
  const reason = masters.reasons.find((r: { name: string; usable_as_line_event: boolean }) => r.name === "その他トラブル" && r.usable_as_line_event);

  // 10ロットの両面の組: 各面に生産の区切り6つ、付帯作業は合わせて5件(1回目 3件、2回目 2件)
  await add(page, R1, full(8, 20));
  await add(page, R2, full(9, 0));
  await trouble(page, reason.id, "吸着エラー", "08:30", "08:34", 1);
  await trouble(page, reason.id, "フィーダー詰まり", "08:40", "08:42", 2);
  await trouble(page, reason.id, "部品切れ", "08:45", "08:50", 3);
  await trouble(page, reason.id, "ノズル交換", "09:10", "09:14", 4);
  await trouble(page, reason.id, "リフロー炉の温度待ち", "09:20", "09:25", 5);
  await add(page, ONE, full(7, 10));
  await add(page, LONELY, full(7, 40));
  if ((await page.request.get(`/api/production-records/${S1}`)).status() !== 200) { // z-side-link.spec.ts を通さずに動かしたとき
    for (const k of [S1, S2]) await add(page, k, [["production", "08:30", "09:00", 100], ["cleanup", "09:00", "09:10"]]);
  }
  const link = await page.request.post(`/api/runs/${S2}/side-link`, { data: { request_id: "e2e-rec-link", worker_id: "Y001", side1_kitting_no: S1 } });
  expect(link.status(), await link.text()).toBe(200);

  // ライン画面の「生産記録票」から一覧へ
  await page.goto("/field/lines/R");
  await page.getByRole("link", { name: "生産記録票" }).click();
  await expect(page.getByRole("heading", { name: "生産記録票の印刷" })).toBeVisible();
  const list = page.getByRole("table", { name: "生産記録票の印刷" });
  await expect(list.getByRole("row", { name: new RegExp(R2) })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/35-record-list.png`, fullPage: true });
  const all = await (await page.request.get("/api/production-records")).json();
  const unlinked = all.filter((r: { side2_unlinked: boolean }) => r.side2_unlinked).length;
  console.log(`生産記録票の一覧: ${all.length}組、そのうち面1とつながっていない面2 ${unlinked}件`);
  await page.getByLabel("キッティングNo.").fill("1300-1-R");
  await expect(list.getByRole("row")).toHaveCount(2); // 見出し + 10ロットの組
  await expect(list.getByRole("row", { name: new RegExp(R2) })).toContainText(R1);

  // 10ロットの組: 印刷のメディアで A4 縦 1 ページに収まる
  await page.goto(`/field/print/production-record/${R2}`);
  const sheet = page.locator(".record-sheet");
  await expect(sheet).toContainText("DEMO-R10");
  await expect(sheet.locator(".rec-steps").first().locator("tr")).toHaveCount(1 + 10); // 見出し + 工程10行(生産6行)
  await page.screenshot({ path: `${SCREENS}/36-record-ten-lots-screen.png`, fullPage: true });
  const fit = await fitsOnePage(page);
  expect(fit.height).toBeLessThanOrEqual(A4_PRINT_HEIGHT_PX);
  expect(fit.pages).toBe(1);
  await expect(page.locator(".record-toolbar")).toBeHidden(); // 操作バーは印刷に出ない
  const font = await sheet.locator(".rec-steps td").first().evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(font).toBeGreaterThanOrEqual(8);
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.screenshot({ path: `${SCREENS}/36-record-ten-lots.png`, fullPage: true });
  await page.emulateMedia({ media: "screen" });
  await page.setViewportSize({ width: 1280, height: 1000 });

  // 1回目 Sライン、2回目 Uライン(紐づけたあとの1枚)
  await page.goto(`/field/print/production-record/${S2}`);
  await expect(page.locator(".rec-face").nth(0)).toContainText(S1);
  await expect(page.locator(".rec-face").nth(1)).toContainText(S2);
  await expect(page.locator(".rec-face").nth(0)).toContainText("S");
  await expect(page.locator(".rec-face").nth(1)).toContainText("U");
  await expect(page.getByText("1回目と紐づける")).toHaveCount(0);
  expect((await fitsOnePage(page)).pages).toBe(1);
  await page.screenshot({ path: `${SCREENS}/37-record-s-u.png`, fullPage: true });
  await page.emulateMedia({ media: "screen" });

  // 片面だけ: 2回目は空欄
  await page.goto(`/field/print/production-record/${ONE}`);
  await expect(page.locator(".rec-face").nth(1)).toContainText("LẦN 2");
  await expect(page.locator(".rec-face").nth(1).locator("tbody td").first()).toHaveText("");
  expect((await fitsOnePage(page)).pages).toBe(1);
  await page.screenshot({ path: `${SCREENS}/38-record-one-side.png`, fullPage: true });
  await page.emulateMedia({ media: "screen" });

  // 面1とつながっていない面2: 2回目だけ。印刷の上に「1回目と紐づける」が出て、紐づけの画面へ進める
  await page.goto(`/field/print/production-record/${LONELY}`);
  await expect(page.getByText("1回目と紐づいていません")).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/39-record-unlinked.png`, fullPage: true });
  expect((await fitsOnePage(page)).pages).toBe(1);
  await page.emulateMedia({ media: "screen" });
  await page.getByRole("link", { name: "1回目と紐づける" }).click();
  await expect(page).toHaveURL(new RegExp(`/field/lines/R\\?kitting_no=${LONELY}`));
  await expect(page.getByLabel("1回目のキッティングNo.", { exact: true })).toBeVisible();
});
