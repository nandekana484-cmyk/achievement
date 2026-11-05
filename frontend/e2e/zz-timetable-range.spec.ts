// ライン画面のタイムテーブルの表示範囲(AD-23)。ラインTで、(1)ラインを開いたとき、表示範囲の中の前の計画(未着手を含む)が出る、
// (2)片付けが終わっていない計画があると範囲の始まりが広がる、(3)広げる限度(72時間)を超える計画は警告を出す、を撮る。
// サーバーの時計は 10/21 10:00 で動かせないので、(1)と(3)はボードの server_time と stale_kitting_nos を差し替えて撮る(差し替えは撮るときだけ)。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const FIRST = "0722-1-T-261014-01"; // 10/21 8:30〜11:30
const UNTOUCHED = "0800-1-T-261014-03"; // 10/21 10:30〜12:30(ほかの spec が記録を入れない)
const BOARD = "**/api/lines/T/board**";

test.use({ viewport: { width: 1440, height: 1000 } });

/** ボードの応答を、時計と警告だけ差し替える。 */
async function mockBoard(page: Page, patch: { server_time?: string; stale_kitting_nos?: string[] }) {
  await page.route(BOARD, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, ...patch } });
  });
}

test("㊿ 計画終了を過ぎて未着手の計画も、表示範囲の中なら出る(斜線と「未着手」)", async ({ page }) => {
  await mockBoard(page, { server_time: "2026-10-21T14:00:00+09:00" }); // 今 14:00 のつもりで見る(0800-1 は 12:30 に終わっている)
  await page.goto("/field/lines/T");
  const block = page.locator(".tt-plan", { hasText: UNTOUCHED });
  await expect(block).toBeVisible();
  await expect(block).toHaveClass(/tt-overdue/);
  await expect(block).toContainText("未着手");
  await page.screenshot({ path: `${SCREENS}/50-overdue-unstarted.png` }); // 開いた直後(今の時刻のあたりまでスクロール。上に前の計画がある)
  await block.click(); // 選べる
  await expect(page.locator(".tt-plan.tt-selected", { hasText: UNTOUCHED })).toBeVisible();
});

test("51 片付けが終わっていない計画があると、表示範囲の始まりが最初の記録の12時間前まで広がる", async ({ page }) => {
  const r = await page.request.post(`/api/runs/${FIRST}/events`, {
    data: { request_id: "e2e-range-add", reason: "forgot", worker_id: "Y001", step_type: "setup",
      start_at: "2026-10-20T21:00:00+09:00", end_at: "2026-10-20T21:30:00+09:00", produced_qty: null },
  });
  expect(r.status(), await r.text()).toBe(200);
  const board = await (await page.request.get("/api/lines/T/board", { params: { date: "2026-10-21" } })).json();
  expect(board.display_start).toBe("2026-10-20T09:00:00+09:00"); // 最初の記録 10/20 21:00 の12時間前
  expect(board.display_end).toBe("2026-10-22T20:15:00+09:00");
  expect(board.stale_kitting_nos).toEqual([]);
  await page.goto("/field/lines/T");
  await expect(page.locator(".tt-plan", { hasText: FIRST })).toBeVisible();
  await page.locator(".tt-event").first().scrollIntoViewIfNeeded(); // 広げた範囲にある 10/20 21:00 の記録
  await page.screenshot({ path: `${SCREENS}/51-range-widened.png` });
});

test("52 広げる限度を超える古い計画は、警告を出す", async ({ page }) => {
  await mockBoard(page, { stale_kitting_nos: ["0950-1-T-261014-07"] });
  await page.goto("/field/lines/T");
  await expect(page.getByRole("alert").filter({ hasText: "片付けが終わっていない古い計画" })).toContainText("0950-1-T-261014-07");
  await page.screenshot({ path: `${SCREENS}/52-stale-warning.png` });
});
