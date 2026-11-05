// ライン画面のタイムテーブルの表示範囲(AD-23)。ラインXで（ほかの spec と計画を分ける。記録を入れる）、(1)ラインを開いたとき、表示範囲の中の前の計画(未着手を含む)が出る、
// (2)片付けが終わっていない計画があると範囲の始まりが広がるを撮る。
// サーバーの時計は 10/21 10:00 で動かせないので、(1)はボードの server_time を差し替えて撮る。警告(3)は e2e/zz-open-runs.spec.ts で実際のデータで撮る。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const LATE = "0950-1-X-261014-07"; // 10/18 9:00〜12:00(計画は範囲の外。10/20 21:00 に始めて片付けが終わっていない)
const UNTOUCHED = "0800-1-X-261014-03"; // 10/21 10:30〜12:30(ほかの spec が記録を入れない)
const BOARD = "**/api/lines/X/board**";

test.use({ viewport: { width: 1440, height: 1000 } });

/** ボードの応答の時計(server_time)だけ差し替える。 */
async function mockBoard(page: Page, patch: { server_time?: string }) {
  await page.route(BOARD, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, ...patch } });
  });
}

test("㊿ 計画終了を過ぎて未着手の計画も、表示範囲の中なら出る(斜線と「未着手」)", async ({ page }) => {
  await mockBoard(page, { server_time: "2026-10-21T14:00:00+09:00" }); // 今 14:00 のつもりで見る(0800-1 は 12:30 に終わっている)
  await page.goto("/field/lines/X");
  const block = page.locator(".tt-plan", { hasText: UNTOUCHED });
  await expect(block).toBeVisible();
  await expect(block).toHaveClass(/tt-overdue/);
  await expect(block).toContainText("未着手");
  await page.screenshot({ path: `${SCREENS}/50-overdue-unstarted.png` }); // 開いた直後(今の時刻のあたりまでスクロール。上に前の計画がある)
  await block.click(); // 選べる
  await expect(page.locator(".tt-plan.tt-selected", { hasText: UNTOUCHED })).toBeVisible();
});

test("51 片付けが終わっていない計画があると、表示範囲の始まりが最初の記録の12時間前まで広がる", async ({ page }) => {
  const r = await page.request.post(`/api/runs/${LATE}/events`, {
    data: { request_id: "e2e-range-add", reason: "forgot", worker_id: "Y001", step_type: "setup",
      start_at: "2026-10-20T21:00:00+09:00", end_at: "2026-10-20T21:30:00+09:00", produced_qty: null },
  });
  expect(r.status(), await r.text()).toBe(200);
  const board = await (await page.request.get("/api/lines/X/board", { params: { date: "2026-10-21" } })).json();
  expect(board.display_start).toBe("2026-10-20T09:00:00+09:00"); // 最初の記録 10/20 21:00 の12時間前
  expect(board.display_end).toBe("2026-10-22T20:15:00+09:00");
  expect(board.stale_kitting_nos).toEqual([]);
  await page.goto("/field/lines/X");
  // 計画の時刻(10/18)は範囲の外でも、片付け前なので範囲の端に枠が出て、選べる(2-a)
  const edge = page.locator(".tt-plan.tt-edge", { hasText: LATE });
  await expect(edge).toBeVisible();
  await expect(edge).toContainText("範囲外・片付け前");
  await page.locator(".tt-event").first().scrollIntoViewIfNeeded(); // 広げた範囲にある 10/20 21:00 の記録
  await page.screenshot({ path: `${SCREENS}/51-range-widened.png` });
  await page.locator(".tt-event").first().click(); // 帯を押しても、その計画を選べる
  await expect(page.locator(".tt-plan.tt-selected", { hasText: LATE })).toHaveCount(1);
});
