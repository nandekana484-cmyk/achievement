// 生産記録票のロットへの割り振り(AD-18d): 3ロットの両面の組(demo-seed --record-samples の 1303)で、現場で「差を引くロット」を選んで保存し、
// 印刷のページの数量の欄(A と B の取消線と実績)と、管理画面の書き出しの初期値が同じ値になること。最後に動かす。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const F1 = "1303-1-R-261014-47";
const F2 = "1303-2-R-261014-47";

test.use({ viewport: { width: 1280, height: 1000 } });

async function add(page: Page, kno: string, steps: [string, string, string, number?][]) {
  for (const [i, [step, start, end, qty]] of steps.entries()) {
    const r = await page.request.post(`/api/runs/${kno}/events`, {
      data: { request_id: `e2e-alloc-${kno}-${i}`, reason: "forgot", worker_id: "Y001", step_type: step,
        start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00`, produced_qty: qty ?? null },
    });
    expect(r.status(), await r.text()).toBe(200);
  }
}

test("㊵〜㊷ 割り振り: 差を引くロットを選んで保存 → 数量の欄と書き出しの初期値が同じ", async ({ page }) => {
  await add(page, F1, [["production", "08:30", "09:00", 295], ["cleanup", "09:00", "09:05"]]);
  await add(page, F2, [["production", "09:10", "09:40", 298], ["cleanup", "09:40", "09:50"]]); // 計画 100 × 3 = 300 に対して 298

  await page.goto(`/field/print/production-record/${F2}`);
  const sheet = page.locator(".record-sheet");
  const row = (lot: string) => sheet.locator("tr.rec-lot", { hasText: lot });
  // 今の規則: 計画数の順に割り振り、余りは最後のロット → 100 / 100 / 98
  await expect(row("DEMO-R42")).toContainText("98");
  await expect(row("DEMO-R42").locator("s.rec-a-old")).toHaveCount(2); // A と B に取消線
  await expect(row("DEMO-R40").locator("s")).toHaveCount(0);
  await page.screenshot({ path: `${SCREENS}/42-record-allocation-rule.png`, fullPage: true });

  // 差を最初のロットから引く
  await page.getByRole("button", { name: "割り振り" }).click();
  await page.getByRole("radio", { name: "差を引くロット DEMO-R40" }).check();
  await expect(page.getByLabel("割り振り DEMO-R40")).toHaveValue("98");
  await expect(page.getByLabel("割り振り DEMO-R42")).toHaveValue("100");
  await expect(page.getByRole("button", { name: "保存する" })).toBeDisabled(); // 作業者IDが必須
  await page.getByLabel("作業者ID").fill("Y001");
  await page.getByLabel("割り振り DEMO-R41").fill("99"); // 直接直して合計が合わなくなると保存できない
  await expect(page.getByText("合計が生産数の合計と合いません")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存する" })).toBeDisabled();
  await page.getByLabel("割り振り DEMO-R41").fill("100");
  await page.locator(".record-alloc").screenshot({ path: `${SCREENS}/43-record-allocation-panel.png` });
  await page.getByRole("button", { name: "保存する" }).click();

  // 保存するとすぐ、数量の欄が変わる: 最初のロットに取消線(A と B)と実績、最後のロットは取消線なし
  await expect(row("DEMO-R40").locator("s.rec-a-old")).toHaveCount(2);
  await expect(row("DEMO-R40").locator("b.rec-a-actual").first()).toHaveText("98");
  await expect(row("DEMO-R40").locator("b.rec-a-actual").nth(1)).toHaveText("198"); // B - A + 実績 = 200 - 100 + 98
  await expect(row("DEMO-R42").locator("s")).toHaveCount(0);
  await expect(page.getByText("保存した割り振りを使っています")).toBeVisible();
  await sheet.locator(".rec-lots").screenshot({ path: `${SCREENS}/44-record-allocation-saved.png` });
  await page.screenshot({ path: `${SCREENS}/45-record-allocation-page.png`, fullPage: true });

  // 管理画面の書き出しの初期値も、保存した割り振り
  await page.goto("/admin/actuals");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "実績の書き出し" }).click();
  await page.getByRole("combobox", { name: "ライン" }).selectOption("R");
  await page.getByRole("button", { name: "表示" }).click();
  const qty = (lot: string) => page.getByLabel(`${F2} ${lot} の生産数`);
  await expect(qty("DEMO-R40")).toHaveValue("98");
  await expect(qty("DEMO-R41")).toHaveValue("100");
  await expect(qty("DEMO-R42")).toHaveValue("100");
  const rows = page.locator(".actuals-table tbody tr", { hasText: F2 + " " }); // 3ロット分の行だけを撮る
  const first = await page.locator(".actuals-table tbody tr", { hasText: "DEMO-R40" }).boundingBox();
  const last = await page.locator(".actuals-table tbody tr", { hasText: "DEMO-R42" }).boundingBox();
  const head = await page.locator(".actuals-table thead").boundingBox();
  void rows;
  if (first && last && head) {
    await page.screenshot({ path: `${SCREENS}/46-actuals-allocation-initial.png`, fullPage: true,
      clip: { x: head.x, y: head.y, width: head.width, height: head.height } });
    await page.screenshot({ path: `${SCREENS}/46-actuals-allocation-initial.png`, fullPage: true,
      clip: { x: head.x, y: first.y, width: head.width, height: last.y + last.height - first.y } });
  }
});
