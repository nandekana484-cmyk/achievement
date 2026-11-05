// K社製品ロット管理票(AD-27): 管理画面の「管理表の内容」(一覧・登録・コピー・履歴)と、識別票のページの5つ目の種類(A4縦、ロットごとに1ページ)。
// 印刷のメディアで、登録した内容・未登録(空の8行)・20行(作業要領が各行3行)が1ページに収まること、ロット3つで3ページ、2回目の計画で初期値のチェックが入ること。
// 計画は demo-seed のラインK(ほかの spec と別。ファイルNo. 0722 = 例の内容、1000 = 3ロット・20行、0915 = 未登録)。様式は docs/design/forms/control-sheet-k.html。
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { pdfPageCount, pdfPageSizesMm } from "./pdf";

const SCREENS = "test-results/screens";
const FORM = resolve("..", "docs", "design", "forms", "control-sheet-k.html");
const H = { "X-Genba-Admin": "1" };
const KIND5 = "5 管理表(A4縦)";

test.use({ viewport: { width: 1366, height: 1000 }, deviceScaleFactor: 2 });

// window.print は呼ばれたことだけ数える(headless では印刷の画面が出ない)
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.print = () => undefined; });
});

const png = (b: Buffer) => `data:image/png;base64,${b.toString("base64")}`;

async function kittingOf(page: Page, file: string, run: number): Promise<string> {
  const b = await (await page.request.get("/api/lines/K/board", { params: { date: "2026-10-21" } })).json();
  const hit = b.plans.find((p: { plan: { kitting_no: string } }) => p.plan.kitting_no.startsWith(`${file}-${run}-`));
  expect(hit, `${file}-${run}`).toBeTruthy();
  return hit.plan.kitting_no;
}

async function adminLogin(page: Page) {
  const r = await page.request.post("/api/admin/login", { data: { worker_id: "A001", password: "e2e-admin-pass" }, headers: H });
  expect(r.status()).toBe(200);
}

async function register(page: Page, file: string, manager: string, rows: object[]) {
  const r = await page.request.put(`/api/admin/control-sheets/${file}`, { data: { manager_no: manager, rows }, headers: H });
  expect(r.status(), await r.text()).toBe(200);
}

/** 5つ目の種類だけにして「この種類を印刷」を押し、印刷のメディアにする。 */
async function printSheet(page: Page, kno: string, lots?: string[]) {
  await page.emulateMedia({ media: "screen" });
  await page.goto(`/field/print/id-slips/${kno}`);
  await expect(page.locator(".idslip-toolbar")).toBeVisible();
  for (const k of ["1 基板製品ロット現品票", "2 バーコード印字 完了", "3 1回目完了済み", "4 バーコード照合用"]) {
    const box = page.getByRole("checkbox", { name: k });
    if (await box.isChecked()) await box.setChecked(false);
  }
  const five = page.getByRole("checkbox", { name: KIND5 });
  if (!(await five.isChecked())) await five.setChecked(true);
  if (lots) for (const box of await page.locator(".idslip-lots input[type=checkbox]").all()) {
    const name = (await box.evaluate((el) => el.parentElement?.textContent ?? "")).trim();
    if ((await box.isChecked()) !== lots.includes(name)) await box.setChecked(lots.includes(name));
  }
  await page.getByRole("row", { name: KIND5 }).getByRole("button", { name: "この種類を印刷" }).click();
  await expect(page.locator(".idslip-page")).toHaveAttribute("data-printing", "5");
  await page.emulateMedia({ media: "print" });
}

const measure = (page: Page) => page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".idslip-group.is-printing .sk")].map((sk) => {
  const inner = sk.querySelector<HTMLElement>(".sk-inner")!;
  const fonts = [...sk.querySelectorAll<HTMLElement>(".sk-proc, .sk-name")].map((e) => parseFloat(getComputedStyle(e).fontSize));
  return { level: Number(sk.dataset.level), heightMm: inner.getBoundingClientRect().height / (96 / 25.4), minFontPx: Math.min(...fonts, 99), rows: sk.querySelectorAll(".sk-row").length };
}));

test("64 管理画面「管理表の内容」: 登録・コピー・履歴・未登録の一覧", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel("作業者ID").fill("a001");
  await page.getByLabel("パスワード").fill("e2e-admin-pass");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.getByRole("link", { name: "管理表の内容" }).click();
  await expect(page.getByRole("heading", { name: "管理表の内容", level: 1 })).toBeVisible();
  const list = page.getByRole("table", { name: "管理表の内容" });
  await expect(list.getByRole("row", { name: /0722/ })).toContainText("未登録(今の計画にある)"); // 計画にあって未登録
  await page.screenshot({ path: `${SCREENS}/64-admin-control-sheets-list-before.png`, fullPage: true });

  // 様式の例(SMT-1、X線検査)を登録する
  await list.getByRole("row", { name: /0722/ }).getByRole("button", { name: "登録する" }).click();
  await page.getByLabel("管理No").fill("MP-0722");
  await page.getByRole("button", { name: "行を追加", exact: true }).click();
  const r1 = page.getByRole("listitem", { name: "1 行目" });
  await r1.getByLabel("工程名(日本語)").fill("SMT-1(リフロー)");
  await r1.getByLabel("区分").selectOption("internal");
  await r1.getByLabel(/作業要領・注意点/).fill("Side B");
  await r1.getByLabel("将来の自動入力のための対応(今は印刷に使いません)").selectOption("run1");
  await page.getByRole("button", { name: "行を追加", exact: true }).click();
  const r2 = page.getByRole("listitem", { name: "2 行目" });
  await r2.getByLabel("工程名(日本語)").fill("X線検査");
  await r2.getByLabel("工程名のベトナム語(任意)").fill("Kiểm tra X-quang");
  await r2.getByLabel("区分").selectOption("internal");
  await r2.getByLabel(/作業要領・注意点/).fill("ロケーション\n検査数  5 枚");
  await r2.getByLabel(/ライン名の欄を使う/).uncheck(); // 斜線
  await r2.getByLabel("将来の自動入力のための対応(今は印刷に使いません)").selectOption("xray");
  // 並べ替えと削除: 3行目を足して、2行目の上へ動かし、消す
  await page.getByRole("button", { name: "行を追加", exact: true }).click();
  const r3 = page.getByRole("listitem", { name: "3 行目" });
  await r3.getByLabel("工程名(日本語)").fill("仮の行");
  await r3.getByRole("button", { name: "上へ" }).click();
  await expect(page.getByRole("listitem", { name: "2 行目" }).getByLabel("工程名(日本語)")).toHaveValue("仮の行");
  await page.getByRole("listitem", { name: "2 行目" }).getByRole("button", { name: "この行を削除" }).click();
  await expect(page.getByRole("listitem", { name: "2 行目" }).getByLabel("工程名(日本語)")).toHaveValue("X線検査");
  await page.getByRole("button", { name: "保存する" }).click();
  await expect(page.getByRole("status")).toContainText("保存しました(版 1)");
  await page.screenshot({ path: `${SCREENS}/65-admin-control-sheets-editor.png`, fullPage: true });

  // もう一度保存すると版 2。履歴から前の版を読み込める
  await page.getByLabel("管理No").fill("MP-0722A");
  await page.getByRole("button", { name: "保存する" }).click();
  await expect(page.getByRole("status")).toContainText("保存しました(版 2)");
  await expect(page.locator(".cs-history li")).toHaveCount(2);
  await page.locator(".cs-history li", { hasText: "版 1" }).getByRole("button", { name: "この版を読み込む" }).click();
  await expect(page.getByLabel("管理No")).toHaveValue("MP-0722");
  await page.getByRole("button", { name: "保存する" }).click(); // 前の版の内容で、新しい版 3
  await expect(page.getByRole("status")).toContainText("保存しました(版 3)");

  // ほかのファイルNo.へコピー
  await page.getByRole("button", { name: "一覧に戻る" }).click();
  await page.getByLabel("ファイルNo.", { exact: true }).fill("0800");
  await page.getByLabel("コピー元").selectOption("0722");
  await page.getByRole("button", { name: "登録する", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "ファイルNo. 0800 の管理表の内容" })).toBeVisible();
  await expect(page.getByRole("listitem", { name: "1 行目" }).getByLabel("工程名(日本語)")).toHaveValue("SMT-1(リフロー)");
  await expect(page.getByLabel("管理No")).toHaveValue(""); // 管理No はコピーしない
  await page.getByRole("button", { name: "一覧に戻る" }).click();
  await expect(list.getByRole("row", { name: /0722/ })).toContainText("登録済み");
  await expect(list.getByRole("row", { name: /0722/ })).toContainText("管理 花子");
  await expect(list.getByRole("row", { name: /0915/ })).toContainText("未登録(今の計画にある)");
  await page.screenshot({ path: `${SCREENS}/66-admin-control-sheets-list.png`, fullPage: true });
});

test("67 登録した内容で印刷: 2回目の計画で初期値のチェック、A4の1ページ、様式と並べる", async ({ page }) => {
  const k2 = await kittingOf(page, "0722", 2);
  await page.goto(`/field/print/id-slips/${k2}`);
  await expect(page.getByRole("checkbox", { name: KIND5 })).toBeChecked(); // 2回目(面2)は初期値で入る
  await expect(page.getByRole("checkbox", { name: "1 基板製品ロット現品票" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "2 バーコード印字 完了" })).not.toBeChecked();
  const k1 = await kittingOf(page, "0722", 1);
  await page.goto(`/field/print/id-slips/${k1}`);
  await expect(page.getByRole("checkbox", { name: KIND5 })).not.toBeChecked(); // 1回目は入っていない(入れれば出せる)
  await expect(page.locator(".idslip-warn", { hasText: "未登録" })).toHaveCount(0);

  await printSheet(page, k2);
  const [m] = await measure(page);
  console.log("登録した内容:", JSON.stringify(m));
  expect(m.rows).toBe(2);
  expect(m.heightMm).toBeLessThanOrEqual(281);
  const pdf = await page.pdf({ preferCSSPageSize: true });
  expect(pdfPageCount(pdf)).toBe(1);
  const s = pdfPageSizesMm(pdf)[0];
  expect(Math.abs(s.width - 210) < 1.2 && Math.abs(s.height - 297) < 1.2, `${s.width}×${s.height}`).toBe(true);
  // 欄の中身
  const text = await page.locator(".idslip-group.is-printing .sk").innerText();
  expect(text).toContain("MP-0722");
  expect(text).toContain("SMT-1(リフロー)");
  expect(text).toContain("検査数");
  expect(text).toContain("5 枚");
  await expect(page.locator(".is-printing .sk-fileno")).toHaveText("722");
  await expect(page.locator(".is-printing .sk-row").nth(1).locator("td").nth(3)).toHaveClass(/sk-diagonal/); // ライン名の欄の斜線
  await expect(page.locator(".is-printing .sk-row").nth(0).locator("td").nth(3)).not.toHaveClass(/sk-diagonal/);
  const lots = (await (await page.request.get(`/api/id-slips/${k2}`)).json()).lots;
  await expect(page.locator(".is-printing .sk-a")).toHaveText(String(lots[0].planned_qty)); // A = plans.planned_qty
  await expect(page.locator(".is-printing .sk-c")).toHaveText(String(lots[0].order_qty)); // C = plans.order_qty
  await expect(page.locator(".is-printing .sk-proc.sk-lined")).toHaveCount(2); // 作業要領の欄の罫線
  await page.emulateMedia({ media: "screen" });
  const frame = page.locator(".idslip-group[data-kind='5'] .slip-frame").first();
  const ours = await frame.screenshot({ path: `${SCREENS}/67-control-sheet-registered.png` });

  // 様式(HTML)と並べる
  const form = await page.context().newPage();
  await form.setViewportSize({ width: 900, height: 1200 });
  await form.goto(`file:///${FORM.replaceAll("\\", "/")}`);
  const orig = await form.locator(".sheet").screenshot({ path: `${SCREENS}/68-control-sheet-form-original.png` });
  await form.setViewportSize({ width: 2000, height: 1300 });
  await form.setContent(`<body style="margin:0;background:#ddd;display:flex;gap:16px;padding:16px;align-items:flex-start;font:12px sans-serif">
    <figure style="margin:0"><figcaption>様式(HTML)</figcaption><img src="${png(orig)}" style="height:1100px"></figure>
    <figure style="margin:0"><figcaption>本アプリ(登録した内容)</figcaption><img src="${png(ours)}" style="height:1100px"></figure></body>`);
  await form.screenshot({ path: `${SCREENS}/69-control-sheet-side-by-side.png`, fullPage: true });
  await form.close();
});

test("70 未登録のときは空の8行(番号だけ)で印刷し、操作バーに「未登録」を出す", async ({ page }) => {
  const k = await kittingOf(page, "0915", 1);
  await page.goto(`/field/print/id-slips/${k}`);
  await page.getByRole("checkbox", { name: KIND5 }).setChecked(true);
  await expect(page.getByRole("alert").filter({ hasText: "このファイルNo.の管理表の内容は未登録です" })).toBeVisible();
  await printSheet(page, k);
  const [m] = await measure(page);
  expect(m.rows).toBe(8);
  expect(m.heightMm).toBeLessThanOrEqual(281);
  expect(await page.locator(".is-printing .sk-row").evaluateAll((rows) => rows.map((r) => r.textContent))).toEqual(["1", "2", "3", "4", "5", "6", "7", "8"]); // 番号だけ
  expect(pdfPageCount(await page.pdf({ preferCSSPageSize: true }))).toBe(1);
  await page.emulateMedia({ media: "screen" });
  await page.locator(".idslip-group[data-kind='5'] .slip-frame").first().screenshot({ path: `${SCREENS}/70-control-sheet-unregistered.png` });
  await page.screenshot({ path: `${SCREENS}/71-control-sheet-unregistered-toolbar.png` });
});

test("72 20行・作業要領が各行3行でも1ページ(文字は 8px 以上)。ロット3つで3ページ", async ({ page }) => {
  await adminLogin(page);
  const rows = Array.from({ length: 20 }, (_, i) => ({
    name: `工程${i + 1}`, name_vi: `Công đoạn ${i + 1}`, kind: i % 2 ? "external" : "internal", use_line: i % 3 !== 0, link: "none",
    procedure: `${i + 1}行目の作業要領\n注意点 その2\n注意点 その3`,
  }));
  await register(page, "1000", "MP-1000", rows);
  const k = await kittingOf(page, "1000", 2);
  await printSheet(page, k);
  const all = await measure(page);
  console.log("20行:", JSON.stringify(all));
  await page.locator(".idslip-group.is-printing .slip-frame").first().screenshot({ path: `${SCREENS}/72-control-sheet-20rows.png` });
  expect(all).toHaveLength(3); // ロット3つで3ページ
  for (const m of all) {
    expect(m.rows).toBe(20);
    expect(m.heightMm).toBeLessThanOrEqual(281);
    expect(m.minFontPx).toBeGreaterThanOrEqual(8);
  }
  const pdf = await page.pdf({ preferCSSPageSize: true });
  expect(pdfPageCount(pdf)).toBe(3);
  // 1ロットだけなら1ページ
  await printSheet(page, k, ["DEMO-101"]);
  expect(pdfPageCount(await page.pdf({ preferCSSPageSize: true }))).toBe(1);
});
