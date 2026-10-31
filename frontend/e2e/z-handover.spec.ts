// 管理画面の「引き継ぎの確認」(AD-16)。出し直しで古くなった計画(ラインV。実績あり)の実績を、新しいキッティングNo.へ移す(㉕)。
// 古い計画に実績を入れるのは「押し忘れの追加」(サーバーの時計は 10/21 10:00 から進む)。ほかの確認に影響しないよう最後(z-)に動かす。
import { expect, type Page, test } from "@playwright/test";

const SCREENS = "test-results/screens";
const OLD = "1100-1-V-261014-21";
const NEW = "1100-1-V-261014-22";

test.use({ viewport: { width: 1440, height: 900 } });

async function add(page: Page, step: string, start: string, end: string, qty?: number) {
  const r = await page.request.post(`/api/runs/${OLD}/events`, {
    data: { request_id: `e2e-handover-${step}`, reason: "forgot", worker_id: "Y001", step_type: step,
      start_at: `2026-10-21T${start}:00+09:00`, end_at: `2026-10-21T${end}:00+09:00`, produced_qty: qty ?? null },
  });
  expect(r.status(), await r.text()).toBe(200);
}

test("㉕ 引き継ぎの確認(実績を新しいキッティングNo.へ移す)", async ({ page }) => {
  await add(page, "production", "09:00", "09:50", 100);
  await add(page, "cleanup", "09:50", "10:00");
  await page.goto("/admin/handover");
  await page.getByLabel("作業者ID").fill("A001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "引き継ぎの確認" }).click();
  const row = page.getByRole("row", { name: new RegExp(OLD) });
  await expect(row).toContainText("出し直しで古くなった");
  await expect(row).toContainText("完了済み");
  await expect(page.getByLabel(`${OLD} の移す先`)).toHaveValue(NEW);
  await page.screenshot({ path: `${SCREENS}/25-handover-list.png`, fullPage: true });

  await row.getByRole("button", { name: "移す" }).click();
  await expect(page.getByRole("dialog")).toContainText(`${OLD} の実績を ${NEW} へ移します`);
  await page.screenshot({ path: `${SCREENS}/26-handover-confirm.png` });
  await page.getByRole("dialog").getByRole("button", { name: "移す" }).click();
  await expect(page.getByRole("status")).toContainText(`${OLD} の実績を ${NEW} へ移しました`);
  await expect(page.getByRole("table", { name: "確定した引き継ぎ" })).toContainText(NEW);
  await page.screenshot({ path: `${SCREENS}/27-handover-done.png`, fullPage: true });

  // 移したあと、ライン画面の実績は新しいキッティングNo.に出る
  const board = await (await page.request.get("/api/lines/V/board", { params: { date: "2026-10-21" } })).json();
  expect(board.plans.filter((p: { events: unknown[] }) => p.events.length > 0).map((p: { plan: { kitting_no: string } }) => p.plan.kitting_no)).toEqual([NEW]);
});
