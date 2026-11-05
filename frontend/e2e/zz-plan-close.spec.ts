// 計画終了(AD-24)。ラインYで、遅れた未着手の計画で表示範囲が広がり、計画終了すると範囲が元に戻って灰色の「終了(手動)」になる(56〜59)。
// ラインZで、上限より古い遅れた未着手の計画の警告と、検索から選んでの計画終了(60〜61)。ほかの spec と別のラインで行う。
// 「遅れた未着手」の判定は、本アプリの最初の記録(ラインWの古い記録。serve.mjs の --stale-open)より後に終わる計画が対象。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const LAG = "0950-1-Y-261014-07"; // 10/18 9:00〜12:00(遅れた未着手の計画)
const SOON = "0800-1-Y-261014-03"; // 10/21 10:30〜12:30(これからの計画)
const OLD = "1200-1-Z-261014-25"; // 10/11 9:00〜12:00(上限より古い)

test.use({ viewport: { width: 1440, height: 1000 } });

const board = async (page: Page, line: string) => (await page.request.get(`/api/lines/${line}/board`, { params: { date: "2026-10-21" } })).json();

async function setOperator(page: Page, line: string) {
  const r = await page.request.put(`/api/lines/${line}/operator`, { data: { request_id: `e2e-close-op-${line}`, worker_id: "Y001" } });
  expect(r.status(), await r.text()).toBe(200);
}

test("56 遅れた未着手の計画で範囲が広がる。計画終了すると灰色の「終了(手動)」になり、範囲が元に戻る", async ({ page }) => {
  await setOperator(page, "Y");
  const b = await board(page, "Y");
  expect(b.display_start).toBe("2026-10-18T08:15:00+09:00"); // 遅れた未着手の計画(10/18 9:00)の12時間前は上限(72時間前)より古いので、上限まで
  expect(b.stale_plans).toEqual([]);
  await page.goto("/field/lines/Y");
  const block = page.locator(".tt-plan", { hasText: LAG });
  await expect(block).toHaveClass(/tt-overdue/); // 未着手の斜線
  await block.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SCREENS}/56-lagging-widened.png` });
  await block.click();
  await expect(page.getByRole("button", { name: "計画終了", exact: true })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/57-close-button.png` });

  await page.getByRole("button", { name: "計画終了", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("作業者ID")).toHaveValue("Y001"); // ラインの今の担当者を最初から入れる
  const submit = dialog.getByRole("button", { name: "計画終了にする" });
  await expect(submit).toBeDisabled(); // 理由が必須
  await dialog.getByLabel("その他").check();
  await expect(submit).toBeDisabled(); // その他は文が必須
  await dialog.getByLabel("その他の内容(必須)").fill("客先の都合で中止");
  await expect(submit).toBeEnabled();
  await page.screenshot({ path: `${SCREENS}/58-close-dialog.png` });
  await submit.click();

  await expect(page.getByRole("button", { name: "計画終了を取り消す" })).toBeVisible();
  await expect(page.locator(".step-button").first()).toBeDisabled(); // 先に取り消さないと工程は押せない
  expect((await board(page, "Y")).display_start).toBe("2026-10-20T20:15:00+09:00"); // 範囲が元に戻る(計画 10/18 は範囲の外になる)

  // 取り消す(作業者ID必須)。範囲がまた広がる
  await page.getByRole("button", { name: "計画終了を取り消す" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "取り消す" }).click();
  await expect(page.getByRole("button", { name: "計画終了", exact: true })).toBeVisible();
  expect((await board(page, "Y")).display_start).toBe("2026-10-18T08:15:00+09:00");

  // 範囲の中の、これからの計画を計画終了にすると、灰色の「終了(手動)」(未着手の斜線は出さない)
  const soon = page.locator(".tt-plan", { hasText: SOON });
  await soon.click();
  await page.getByRole("button", { name: "計画終了", exact: true }).click();
  await page.getByRole("dialog").getByLabel("遅延して中止").check();
  await page.getByRole("dialog").getByRole("button", { name: "計画終了にする" }).click();
  const gray = page.locator(".tt-plan.tt-closed", { hasText: SOON });
  await expect(gray).toContainText("終了(手動)");
  await expect(gray).not.toHaveClass(/tt-overdue/);
  await gray.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SCREENS}/59-closed-manual.png` });
});

test("60 上限より古い遅れた未着手の計画は警告に出る。検索から選んで計画終了できる", async ({ page }) => {
  await setOperator(page, "Z");
  const b = await board(page, "Z");
  expect(b.stale_plans.map((p: { kitting_no: string }) => p.kitting_no)).toEqual([OLD]);
  await page.goto("/field/lines/Z");
  const alert = page.getByRole("alert").filter({ hasText: "計画終了を過ぎて作業が始まっていない古い計画" });
  await expect(alert).toContainText(OLD);
  await expect(alert).toContainText("DEMO-OLD");
  await expect(alert).toContainText("検索から選んで、計画終了するか作業を始めてください");
  await page.screenshot({ path: `${SCREENS}/60-stale-plan-warning.png` });

  await page.getByRole("searchbox", { name: /計画を検索/ }).fill(OLD);
  await page.getByRole("listbox", { name: "検索の結果" }).getByRole("option", { name: new RegExp(OLD) }).click();
  await expect(page.getByText("表示範囲外の計画です(計画: 10/11 9:00〜)")).toBeVisible();
  await page.getByRole("button", { name: "計画終了", exact: true }).click(); // 検索で選んだ計画にも出る
  await page.getByRole("dialog").getByLabel("計画変更").check();
  await page.getByRole("dialog").getByRole("button", { name: "計画終了にする" }).click();
  await expect(page.getByRole("button", { name: "計画終了を取り消す" })).toBeVisible();
  expect((await board(page, "Z")).stale_plans).toEqual([]); // 警告の対象から外れる
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "計画終了を過ぎて作業が始まっていない古い計画" })).toHaveCount(0);
  await page.screenshot({ path: `${SCREENS}/61-after-close-stale.png` });
});
