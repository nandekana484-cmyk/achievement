// ライン画面を操作し、確認用のスクリーンショットを test-results/screens/ に撮る(①〜⑭、⑱⑲)。
// サーバーの時計は 2026-10-21 10:00 から進む(e2e/serve.mjs)。確認用の計画は app/services/demo_seed.py。
import { expect, type Page, test } from "@playwright/test";

const KNO = (fileNo: string, seq: number) => `${fileNo}-1-S-261014-${String(seq).padStart(2, "0")}`;
const FIRST = KNO("0722", 1); // 10/21 8:30〜11:30
const PAST = KNO("0950", 7); // 10/18 9:00〜12:00(過ぎて未着手。検索で選ぶ)
const MULTI1 = KNO("1000", 9); // 3ロット(DEMO-101〜103)の面1
const MULTI2 = "1000-2-S-261014-10"; // 同じ3ロットの面2

const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/screens/${name}.png` });
const step = (page: Page, name: string) => page.locator(".step-button", { hasText: name });

async function openLine(page: Page) {
  await page.goto("/field/lines/S");
  await expect(page.locator(".tt-plan").first()).toBeVisible();
}

/** 作業者IDで呼び出し(小文字で入れても当たる)、IDと名前を確かめてから決める。shotName を渡すと、確かめている状態を撮る。 */
async function pickOperator(page: Page, shotName?: string) {
  const dialog = page.getByRole("dialog", { name: "担当者の交代" });
  await dialog.getByLabel("作業者ID").fill("y001");
  await dialog.getByLabel("作業者ID").press("Enter"); // バーコードリーダーと同じ(文字の入力 + Enter)
  const found = dialog.getByRole("status", { name: "呼び出した作業者" });
  await expect(found).toContainText("ID Y001");
  await expect(found).toContainText("山田");
  if (shotName) await shot(page, shotName);
  await dialog.getByRole("button", { name: "この人にする" }).click();
  await expect(page.locator(".kpi-button")).toContainText("山田(Y001)");
}

test("ライン画面の操作", async ({ page }) => {
  // ① ライン選択
  await page.goto("/field");
  await expect(page.getByRole("link", { name: "Sライン" })).toBeVisible();
  await shot(page, "01-line-select");

  // ② ライン画面(計画を選んでいない。担当者は未設定)
  await page.getByRole("link", { name: "Sライン" }).click();
  await expect(page.locator(".tt-plan").first()).toBeVisible();
  await expect(page.getByText("担当者が設定されていません。ボタンを押す前に")).toBeVisible();
  await shot(page, "02-line-screen");

  // 担当者が未設定なら、工程のボタンはサーバーに送らず、先に担当者を選ぶ画面を出す
  await page.locator(".tt-plan", { hasText: FIRST }).click();
  await step(page, "段取り").click();
  const picker = page.getByRole("dialog", { name: "担当者の交代" });
  await expect(picker).toContainText("担当者を選んでから、もう一度ボタンを押してください");
  // 無いIDは呼び出せない
  await picker.getByLabel("作業者ID").fill("Z999");
  await picker.getByRole("button", { name: "呼び出し" }).click();
  await expect(picker.getByRole("alert")).toContainText("作業者IDが見つかりません");
  // 名前の一覧は名前順で、同じ名前の人はIDで区別できる
  // 管理者も作業者の1人として出る(demo-seed の管理者 A001)
  await expect(picker.locator(".choice")).toHaveText(["管理 花子(A001)", "佐藤(S002)", "山田(Y001)", "山田(Y015)"]);
  // ⑬ IDで呼び出して確認している状態
  await pickOperator(page, "13-operator-lookup");
  await expect(step(page, "段取り")).toContainText("未着手"); // 送っていない

  // ⑦ 409 のエラー表示: ほかの端末で先に段取りが開始され、この画面の表示がまだ古いまま押した
  const res = await page.request.post(`/api/runs/${FIRST}/steps/setup/start`, { data: { request_id: "e2e-other-tablet", operator_id: 1 } });
  expect(res.status()).toBe(200);
  await step(page, "段取り").click();
  await expect(page.getByRole("alert")).toContainText("段取りは開始されたまま終了していません");
  await shot(page, "07-error-409");
  await expect(step(page, "段取り")).toContainText("作業中", { timeout: 10_000 }); // 5秒ごとの読み直しで追いつく
  await step(page, "段取り").click();
  await expect(step(page, "段取り")).toContainText("済");

  // ③ 計画を選んだ状態(生産 1回目を作業中にする)
  await step(page, "生産 1回目").click();
  await expect(step(page, "生産 1回目")).toContainText("作業中");
  await shot(page, "03-plan-selected");

  // ④ 生産の終了のテンキー。失敗しても閉じず、入力した数を残す
  await step(page, "生産 1回目").click();
  const pad = page.getByRole("dialog", { name: "生産 1回目の終了" });
  for (const k of ["1", "2", "0"]) await pad.getByRole("button", { name: k, exact: true }).click();
  await expect(pad.getByLabel("入力した数")).toHaveText("120");
  await shot(page, "04-production-keypad");
  await page.route("**/steps/production/end", (route) =>
    route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "確認用のエラーです" }) }));
  await pad.getByRole("button", { name: "生産を終了" }).click();
  await expect(pad.getByRole("alert")).toContainText("確認用のエラーです");
  await expect(pad.getByLabel("入力した数")).toHaveText("120");
  await page.unroute("**/steps/production/end");
  await pad.getByRole("button", { name: "生産を終了" }).click();
  await expect(pad).toBeHidden();
  await expect(page.locator(".fact", { hasText: "良品数の合計" })).toContainText("120");

  // ⑤ 生産の2回目の再開理由(設備が必要な理由を選ぶと、設備も選べる)
  await step(page, "生産 2回目").click();
  const reason = page.getByRole("dialog", { name: "生産 2回目の開始" });
  await reason.getByRole("button", { name: "マシントラブル" }).click();
  await reason.getByRole("button", { name: "マウンター1" }).click();
  await shot(page, "05-restart-reason");
  await reason.getByRole("button", { name: "生産を開始" }).click();
  await expect(step(page, "生産 2回目")).toContainText("作業中");

  // ⑥ 付帯作業の作業中
  await page.locator(".reason-button", { hasText: "部品探し" }).click();
  const open = page.locator(".open-event", { hasText: "部品探し" });
  await expect(open).toContainText("作業中");
  await expect(open.getByRole("button", { name: "終了" })).toBeVisible();
  await open.scrollIntoViewIfNeeded();
  await shot(page, "06-line-event-doing");

  // ⑪ 複数ロットの計画を選んだ状態(枠はキッティングNo.ごとに1つ。右のパネルにロットの一覧)
  await page.locator(".tt-plan", { hasText: MULTI1 }).click();
  await expect(page.locator(".tt-plan", { hasText: MULTI1 })).toContainText("3ロット・計画数 300");
  const lotTable = page.getByRole("table", { name: "ロットの一覧" });
  await expect(lotTable.getByRole("row")).toHaveCount(4); // 見出し + 3ロット
  await shot(page, "11-multi-lot-plan");

  // 面1の計画では、面2のNGは選べない
  await page.getByRole("button", { name: "NG数を入力" }).click();
  let ngDialog = page.getByRole("dialog", { name: "NG数の入力" });
  await ngDialog.getByRole("group", { name: "ロット" }).getByRole("button", { name: /DEMO-101/ }).click();
  await expect(ngDialog.getByRole("group", { name: "面" }).getByRole("button", { name: /面2/ })).toBeDisabled();
  await ngDialog.getByRole("button", { name: "やめる" }).click();

  // ⑫ NGの入力: 面2の計画で、ロットを選び、面1(同じロットの面1の計画がある)を選んでテンキーで入れる
  await page.locator(".tt-plan", { hasText: MULTI2 }).click();
  await page.getByRole("button", { name: "NG数を入力" }).click();
  ngDialog = page.getByRole("dialog", { name: "NG数の入力" });
  await ngDialog.getByRole("group", { name: "ロット" }).getByRole("button", { name: /DEMO-102/ }).click();
  await ngDialog.getByRole("group", { name: "面" }).getByRole("button", { name: /面1/ }).click();
  for (const k of ["3"]) await ngDialog.getByRole("button", { name: k, exact: true }).click();
  await expect(ngDialog.getByLabel("入力した数")).toHaveText("3");
  await shot(page, "12-ng-input");
  await ngDialog.getByRole("button", { name: "NG数を記録" }).click();
  await expect(ngDialog).toBeHidden();
  await expect(page.getByRole("table", { name: "ロットの一覧" }).getByRole("row", { name: /DEMO-102/ })).toContainText("3");

  // ⑧ 検索の結果
  await page.getByRole("searchbox", { name: /計画を検索/ }).fill("基板");
  const results = page.getByRole("listbox", { name: "検索の結果" });
  await expect(results.getByRole("option", { name: new RegExp(PAST) })).toBeVisible();
  await shot(page, "08-search-results");

  // ⑨ 表示範囲外の計画を選んだ状態
  await results.getByRole("option", { name: new RegExp(PAST) }).click();
  await expect(page.getByText("表示範囲外の計画です(計画: 10/18 9:00〜)")).toBeVisible();
  await expect(page.locator(".plan-kno")).toHaveText(PAST);
  await shot(page, "09-outside-plan");
});

test("⑩ 稼働日の境目と、表示範囲の端で切れた計画", async ({ page }) => {
  await openLine(page);
  await expect(page.getByLabel("10/21 稼働日の始まり(8:15)")).toBeAttached();
  const next = page.getByLabel("10/22 次の稼働日の始まり(8:15)");
  // 次の稼働日の境目(10/22 8:15)を画面の中ほどに。境目の先に、次の稼働日の計画(8:30〜)が見える
  await next.evaluate((el) => {
    const box = el.closest(".timetable") as HTMLElement;
    box.scrollTop = (el as HTMLElement).offsetTop - box.clientHeight / 2 + 40;
  });
  await expect(page.locator(".tt-plan", { hasText: KNO("0940", 6) })).toBeInViewport();
  await shot(page, "10-workday-boundary");
  await expect(page.locator(".tt-plan", { hasText: KNO("0960", 8) })).toContainText("表示範囲の後へ続く");
});

test("キッティングNo.が完全に一致する1件は Enter でそのまま選ぶ", async ({ page }) => {
  await openLine(page);
  const box = page.getByRole("searchbox", { name: /計画を検索/ });
  await box.fill(PAST.toLowerCase());
  await box.press("Enter");
  await expect(page.locator(".plan-kno")).toHaveText(PAST);
  await expect(box).toHaveValue("");
});

for (const width of [1024, 1366]) {
  test(`横向き ${width}px で横にはみ出さない`, async ({ page }) => {
    await page.setViewportSize({ width, height: 768 });
    await openLine(page);
    await page.locator(".tt-plan").first().click();
    await expect(page.getByRole("region", { name: "選んだ計画" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    // 押す部分は高さ 56px 以上
    for (const sel of [".step-button", ".step-fix", ".reason-button", ".menu-item", ".kpi-button", ".search-input"]) {
      const heights = await page.locator(sel).evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
      expect(Math.min(...heights), sel).toBeGreaterThanOrEqual(56);
    }
  });
}

test("⑭ ベトナム語に切り替えたライン画面", async ({ page }) => {
  const VI = "Tiếng Việt";
  await page.goto("/field");
  await expect(page.locator(".lang-switch").getByRole("button", { name: VI })).toBeVisible(); // ライン選択の画面でも切り替えられる
  await openLine(page);
  await page.locator(".lang-switch").getByRole("button", { name: VI }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "vi");
  await expect(page.locator(".line-name")).toHaveText("Chuyền S"); // 自動で付けた名前(「Sライン」)は訳して出す
  await expect(page.getByRole("button", { name: "Bảng thời gian" })).toBeVisible();
  await page.locator(".tt-plan", { hasText: FIRST }).click();
  await expect(step(page, "Chuẩn bị (setup)")).toContainText("Bấm để"); // 状態はほかのテストの操作による
  // 計画の内容は訳さない。理由の名前はマスタのベトナム語の名前(初期データの理由には入れてある)
  await expect(page.locator(".plan-kno")).toHaveText(FIRST);
  await expect(page.locator(".reason-button", { hasText: "Tìm linh kiện" })).toBeVisible();
  await shot(page, "14-line-screen-vi");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);

  // その端末に記憶する(開き直してもベトナム語)。日本語に戻せる
  await page.reload();
  await expect(page.getByRole("button", { name: "Bảng thời gian" })).toBeVisible();
  await page.locator(".lang-switch").getByRole("button", { name: "日本語" }).click();
  await expect(page.getByRole("button", { name: "タイムテーブル", exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "ja");
});

// 実績の訂正(⑱⑲)。上のテストの計画と重ならないよう、別の計画(0800。10:30〜12:30)を使う。担当者を設定するので最後に置く
const PLAN = KNO("0800", 3);

async function record(page: Page, stepType: string, id: string, endBody: object = {}) {
  const base = `/api/runs/${PLAN}/steps/${stepType}`;
  expect((await page.request.post(`${base}/start`, { data: { request_id: `${id}-s`, worker_id: "Y001" } })).status()).toBe(200);
  expect((await page.request.post(`${base}/end`, { data: { request_id: `${id}-e`, worker_id: "Y001", ...endBody } })).status()).toBe(200);
}

test("⑱⑲ 実績の訂正(時刻を直す・取り消す・押し忘れの追加・訂正の履歴)", async ({ page }) => {
  // 担当者と、直す元の記録(段取り、生産 1回目)。どちらもほかの端末で押したことにする
  expect((await page.request.put("/api/lines/S/operator", { data: { request_id: "e2e-corr-op", worker_id: "Y001" } })).status()).toBe(200);
  await record(page, "setup", "e2e-corr-setup");
  await record(page, "production", "e2e-corr-prod", { produced_qty: 50 });

  await page.goto("/field/lines/S");
  await page.locator(".tt-plan", { hasText: PLAN }).click();
  await expect(step(page, "段取り")).toContainText("済");

  // ⑱ 段取りの開始を10分早める(キーボードを使わず、大きなボタンで)
  await page.getByRole("button", { name: "段取りの記録を直す" }).click();
  const fix = page.getByRole("dialog", { name: "段取りの記録を直す" });
  const startTime = fix.getByRole("group", { name: "開始の時刻" });
  const before = await startTime.locator("output").textContent();
  await startTime.getByRole("button", { name: "−10分" }).click();
  await expect(startTime.locator("output")).not.toHaveText(before ?? "");
  await expect(startTime).toContainText(`元: ${before}`);
  await expect(fix.getByRole("button", { name: "訂正を記録" })).toBeDisabled(); // 理由が必須
  await fix.getByRole("group", { name: "訂正の理由(必須)" }).getByRole("button", { name: "押し間違い" }).click();
  await shot(page, "18-correction-time");
  await fix.getByRole("button", { name: "訂正を記録" }).click();
  await expect(fix).toBeHidden();

  // 生産 1回目を取り消す → タイムテーブルと生産数から外れる
  await page.getByRole("button", { name: "生産の記録を直す" }).click();
  const prod = page.getByRole("dialog", { name: "生産の記録を直す" });
  await prod.getByRole("button", { name: "この記録を取り消す" }).click();
  await prod.getByRole("button", { name: "押し間違い" }).click();
  await prod.getByRole("button", { name: "取り消す", exact: true }).click();
  await expect(prod).toBeHidden();
  await expect(page.locator(".fact", { hasText: "良品数の合計" })).toContainText("0");
  await expect(step(page, "生産 1回目")).toContainText("未着手");

  // 押し忘れの追加: 初品チェック(既定は30分前〜今)
  await page.getByRole("button", { name: "押し忘れの追加" }).click();
  const addDialog = page.getByRole("dialog", { name: "押し忘れの追加" });
  await addDialog.getByRole("button", { name: "初品チェック" }).click();
  await addDialog.getByRole("button", { name: "記録を追加" }).click();
  await expect(addDialog).toBeHidden();
  await expect(step(page, "初品チェック")).toContainText("済");

  // ⑲ 訂正の履歴: 取り消した記録は取り消し線、訂正は新しい順
  await page.getByRole("button", { name: "訂正の履歴" }).first().click();
  const history = page.getByRole("dialog", { name: `訂正の履歴(${PLAN})` });
  await expect(history.getByRole("list", { name: "訂正の履歴(新しい順)" }).getByRole("listitem")).toHaveCount(3);
  await expect(history.locator(".correction-item").first()).toContainText("追加");
  await expect(history.locator(".record-voided")).toContainText("取消");
  await expect(history.locator(".record-row", { hasText: "初品チェック" })).toContainText("後から追加");
  await shot(page, "19-correction-history");
  await history.getByRole("button", { name: "閉じる" }).click();

  // 付帯作業も直せる(付帯作業を直す → 選ぶ → 時刻を直す)
  await page.locator(".reason-button", { hasText: "欠品" }).click();
  await expect(page.locator(".open-event", { hasText: "欠品" })).toBeVisible();
  await page.getByRole("button", { name: "付帯作業を直す" }).click();
  const lineFix = page.getByRole("dialog", { name: "付帯作業を直す" });
  await lineFix.getByRole("group", { name: "開始の時刻" }).getByRole("button", { name: "−1分" }).click();
  await lineFix.getByRole("button", { name: "押し忘れ" }).click();
  await lineFix.getByRole("button", { name: "訂正を記録" }).click();
  await expect(lineFix).toBeHidden();
});
