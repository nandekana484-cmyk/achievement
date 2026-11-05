// 識別票4種類の印刷(AD-20)。印刷のメディアで、種類ごとに A6 の大きさで1枚1ページになること
// (1枚の識別票 = 1ページ。ロット1つで1ページ、ロット3つで3ページ、4つ目はロット10個でも1ページ。印刷の画面の組み直し(afterprint)でも変わらないこと)と、細いバーの幅が 0.25mm 以上であること、見た目(スクリーンショット)。
// 計画は demo-seed(ラインS: 0722 の組、1000 の3ロットの組)と --record-samples(ラインR: 1300 の10ロットの組、1303 の3ロットの組)。
// 様式(docs/design/forms/id-*.html)は CDN の JsBarcode を読むので、同じ内容の手元のファイルに差し替えて開く。最後に動かす。
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { pdfPageCount, pdfPageSizesMm } from "./pdf";

const SCREENS = "test-results/screens";
const FORMS = resolve("..", "docs", "design", "forms");
const JSBARCODE = resolve("node_modules", "jsbarcode", "dist", "JsBarcode.all.min.js");
const S1 = "0722-1-S-261014-01"; // 1回目(面1)の計画
const S2 = "0722-2-S-261014-02"; // 2回目(面2)の計画
const H1 = "1000-1-S-261014-09"; // 3ロット(DEMO-101〜103)
const R10 = "1300-1-R-261014-41"; // 10ロット(DEMO-R01〜R10)
const R3 = "1303-1-R-261014-47"; // 3ロット(DEMO-R40〜R42)
const MM = 25.4 / 96;

test.use({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 3 });

// window.print は呼ばれたことだけ数える(headless では印刷の画面が出ず、すぐ afterprint で「全部の種類の表示」に戻ってしまうため)
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __prints: number }).__prints = 0;
    window.print = () => { (window as unknown as { __prints: number }).__prints += 1; };
  });
});
const printCalls = (page: Page) => page.evaluate(() => (window as unknown as { __prints: number }).__prints);

const url = (kno: string) => `/field/print/id-slips/${kno}`;
const KIND_NAMES = { 1: "1 基板製品ロット現品票", 2: "2 バーコード印字 完了", 3: "3 1回目完了済み", 4: "4 バーコード照合用" } as const;
type Kind = keyof typeof KIND_NAMES;

const checkbox = (page: Page, kind: Kind) => page.getByRole("checkbox", { name: KIND_NAMES[kind] });

async function setup(page: Page, kno: string, kinds: Kind[]) {
  await page.goto(url(kno));
  await expect(page.locator(".idslip-toolbar")).toBeVisible();
  for (const k of [1, 2, 3, 4] as Kind[]) {
    if ((await checkbox(page, k).isChecked()) !== kinds.includes(k)) await checkbox(page, k).setChecked(kinds.includes(k));
  }
}

/** 「この種類を印刷」を押し(window.print は headless では何も起きない)、印刷のメディアの PDF を作る。バーコードの印刷での大きさは PDF の前に測る(PDF を作ると afterprint が飛び、全部の種類の表示に戻るため)。 */
async function printKind(page: Page, kind: Kind) {
  await page.getByRole("row", { name: KIND_NAMES[kind] }).getByRole("button", { name: "この種類を印刷" }).click();
  await expect(page.locator(".idslip-page")).toHaveAttribute("data-printing", String(kind));
  expect(await printCalls(page)).toBeGreaterThan(0);
  await page.emulateMedia({ media: "print" });
  const bars = await page.evaluate(() => [...document.querySelectorAll<SVGElement>(".idslip-group.is-printing svg.slip-bc-svg")].map((s) => ({
    value: s.getAttribute("aria-label"), modules: Number(s.dataset.modules), widthMm: s.getBoundingClientRect().width * (25.4 / 96),
  })));
  const pdf = await page.pdf({ preferCSSPageSize: true });
  return { pdf, pages: pdfPageCount(pdf), sizes: pdfPageSizesMm(pdf), bars };
}

const near = (a: number, b: number) => Math.abs(a - b) < 1.2;

test("㊸ 初期値のチェック: 1回目は 2・3・4、2回目は 1・4。バーコードは Code 39", async ({ page }) => {
  await page.goto(url(S1));
  await expect(page.locator(".idslip-toolbar")).toBeVisible();
  expect([await checkbox(page, 1).isChecked(), await checkbox(page, 2).isChecked(), await checkbox(page, 3).isChecked(), await checkbox(page, 4).isChecked()]).toEqual([false, true, true, true]);
  await page.goto(url(S2));
  await expect(page.locator(".idslip-toolbar")).toBeVisible();
  expect([await checkbox(page, 1).isChecked(), await checkbox(page, 2).isChecked(), await checkbox(page, 3).isChecked(), await checkbox(page, 4).isChecked()]).toEqual([true, false, false, true]);
  await expect(page.locator(".slip-frame-p[data-kind='1']")).toHaveCount(1); // 1ロット
  await expect(page.locator(".idslip-warn")).toHaveCount(0);
  // 表示の値: 722(先頭の0を外す)、下のバーコードは SUF-0722
  await expect(page.locator(".slip1-fileno")).toHaveText("722");
  await expect(page.locator("svg[aria-label='SUF-0722']")).toHaveCount(1);
  await expect(page.locator("svg[aria-label='722']")).toHaveCount(1);
});

test("㊹ ライン画面で計画を選ぶと「識別票」のボタンが出て、印刷用のページを開く", async ({ page }) => {
  await page.goto(`/field/lines/S?kitting_no=${S1}`);
  await page.getByRole("link", { name: "識別票" }).click();
  await expect(page).toHaveURL(new RegExp(`/field/print/id-slips/${S1}`));
  await expect(page.locator(".idslip-head strong")).toHaveText(S1);
});

/** 「ロット」の欄で、選ぶロットを1つにする。 */
async function onlyLot(page: Page, lot: string) {
  for (const box of await page.locator(".idslip-lots input[type=checkbox]").all()) {
    const name = (await box.evaluate((el) => el.parentElement?.textContent ?? "")).trim();
    if ((await box.isChecked()) !== (name === lot)) await box.setChecked(name === lot);
  }
}

test("㊺ 種類ごとに A6 で1枚1ページ: ロット1つで1ページ、ロット3つで3ページ、4つ目は1ページ", async ({ page }) => {
  await setup(page, H1, [1, 2, 3, 4]);
  await onlyLot(page, "DEMO-101");
  for (const kind of [1, 2, 3, 4] as Kind[]) {
    expect((await printKind(page, kind)).pages, `種類${kind}・ロット1つ`).toBe(1);
    await page.emulateMedia({ media: "screen" });
  }
  await page.getByRole("button", { name: "すべて選ぶ" }).click();
  const result: Record<number, { pages: number; sizes: { width: number; height: number }[] }> = {};
  for (const kind of [1, 2, 3, 4] as Kind[]) {
    const r = await printKind(page, kind);
    result[kind] = r;
    await page.emulateMedia({ media: "screen" });
  }
  console.log("ページ数と用紙(mm):", JSON.stringify(Object.fromEntries(Object.entries(result).map(([k, v]) => [k, [v.pages, v.sizes[0]?.width.toFixed(1), v.sizes[0]?.height.toFixed(1)]]))));
  expect(result[1].pages).toBe(3);
  expect(result[2].pages).toBe(3);
  expect(result[3].pages).toBe(3);
  expect(result[4].pages).toBe(1); // 4つ目はキッティングNo.ごと(全ロットを1枚に並べる)
  for (const kind of [1, 4] as Kind[]) for (const s of result[kind].sizes) expect(near(s.width, 105) && near(s.height, 148), `${kind}: ${s.width}×${s.height}`).toBe(true);
  for (const kind of [2, 3] as Kind[]) for (const s of result[kind].sizes) expect(near(s.width, 148) && near(s.height, 105), `${kind}: ${s.width}×${s.height}`).toBe(true);
});

test("㊺b 印刷の画面の組み直し(afterprint)が起きても、押した種類のページだけが出る", async ({ page }) => {
  // 面1の計画は 2・3・4 にチェックが入っている。Chrome の印刷の画面は用紙を変えるたびに afterprint を飛ばして組み直す
  await setup(page, S1, [2, 3, 4]);
  await onlyLot(page, "DEMO-001");
  const first = await printKind(page, 2);
  expect(first.pages).toBe(1);
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  const again = await page.pdf({ preferCSSPageSize: true });
  expect(pdfPageCount(again)).toBe(1); // 2 と 3 のページが重なって2ページにならない
  expect(await page.locator(".idslip-group.is-printing").count()).toBe(1);
});

test("㊻ 4つ目はロット10個でも1ページに収まり、文字は 8px より小さくならない", async ({ page }) => {
  await setup(page, R10, [4]);
  const r = await printKind(page, 4);
  expect(r.pages).toBe(1);
  expect(near(r.sizes[0].width, 105) && near(r.sizes[0].height, 148)).toBe(true);
  const fit = await page.evaluate(() => {
    const frame = document.querySelector<HTMLElement>(".slip-frame")!.getBoundingClientRect();
    const val = document.querySelector<HTMLElement>(".slip4-lots")!;
    const text = val.querySelector<HTMLElement>(".slip-fit")!;
    const slip = document.querySelector<HTMLElement>(".slip4")!;
    return {
      fontPx: Number(text.dataset.fontPx), cellOverflow: val.scrollHeight > val.clientHeight + 1 || val.scrollWidth > val.clientWidth + 1,
      slipOverflow: slip.scrollHeight > slip.clientHeight + 1, frameH: frame.height / (96 / 25.4), text: text.textContent,
    };
  });
  console.log("ロット10個の文字の大きさ(px):", fit.fontPx, "枠の高さ(mm):", fit.frameH.toFixed(1));
  expect(fit.text).toContain("DEMO-R10");
  expect(fit.fontPx).toBeGreaterThanOrEqual(8);
  expect(fit.cellOverflow).toBe(false);
  expect(fit.slipOverflow).toBe(false);
});

test("㊼ 細いバーの幅は印刷で 0.25mm 以上(種類とバーコードごと)", async ({ page }) => {
  const rows: string[] = [];
  const cases: [string, Kind[], string][] = [
    [H1, [1, 2, 3], "3ロットの組"], [R10, [4], "10ロットの組"], [R3, [1, 4], "3ロットの組(Q)"],
  ];
  for (const [kno, kinds, label] of cases) {
    await setup(page, kno, kinds);
    for (const kind of kinds) {
      const { bars } = await printKind(page, kind);
      for (const b of bars) {
        const bar = b.widthMm / b.modules;
        rows.push(`${label} 種類${kind} ${b.value}: ${bar.toFixed(3)}mm(全体 ${b.widthMm.toFixed(1)}mm)`);
        expect(bar, `${b.value}`).toBeGreaterThanOrEqual(0.2499);
      }
      await page.emulateMedia({ media: "screen" });
    }
  }
  console.log(rows.join("\n"));
  expect(rows.length).toBeGreaterThanOrEqual(8); // 種類ごとにバーコードを測れている
});

test("㊽ Code 39 で表せない値は、バーコードを描かずに文字だけ出し、操作バーに警告を出す", async ({ page }) => {
  await page.route("**/api/id-slips/*", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.lots[0].lot_no = "ロット-a";
    body.lots[1].lot_no = "ok-b";
    await route.fulfill({ response: res, json: body });
  });
  await setup(page, H1, [1, 4]);
  await expect(page.getByRole("alert").filter({ hasText: "ロット-a" })).toHaveCount(1);
  await expect(page.getByRole("alert").filter({ hasText: "ok-b" })).toHaveCount(1);
  await expect(page.locator(".slip-bc-fallback", { hasText: "ロット-a" })).toHaveCount(1);
  await expect(page.locator("svg[aria-label='ロット-a']")).toHaveCount(0);
  await expect(page.locator(".slip1-val", { hasText: "ロット-a" })).toHaveCount(1); // 値の文字は出る(大文字には直さない)
});

test("㊾ スクリーンショット(4種類。4つ目はロット複数)と、様式の HTML と並べたもの", async ({ page, browser }) => {
  await setup(page, R3, [1, 2, 3, 4]);
  const shots: Record<Kind, string> = { 1: "47-id-slip-1.png", 2: "48-id-slip-2.png", 3: "49-id-slip-3.png", 4: "50-id-slip-4.png" };
  for (const kind of [1, 2, 3, 4] as Kind[]) await page.locator(`.idslip-group[data-kind='${kind}'] .slip-frame`).first().screenshot({ path: `${SCREENS}/${shots[kind]}` });
  await page.screenshot({ path: `${SCREENS}/51-id-slips-page.png`, fullPage: true });

  // 様式(CDN の JsBarcode は手元のファイルに差し替える)
  const ctx = await browser.newContext({ deviceScaleFactor: 3, viewport: { width: 700, height: 800 } });
  const form = await ctx.newPage();
  await form.route("https://cdn.jsdelivr.net/**", (route) => route.fulfill({ body: readFileSync(JSBARCODE), contentType: "application/javascript" }));
  const originals: [Kind, string, string][] = [
    [1, "id-1-lot-slip.html", ".slip-card"], [2, "id-2-barcode-printed.html", ".card-landscape"],
    [3, "id-3-side1-done.html", ".card-landscape"], [4, "id-4-barcode-check.html", ".label-card"],
  ];
  const png = (b: Buffer) => `data:image/png;base64,${b.toString("base64")}`;
  const compose = await ctx.newPage();
  for (const [kind, file, sel] of originals) {
    await form.goto(`file:///${resolve(FORMS, file).replaceAll("\\", "/")}`);
    const orig = await form.locator(sel).screenshot({ path: `${SCREENS}/52-form-${kind}-original.png` });
    const ours = readFileSync(`${SCREENS}/${shots[kind]}`);
    await compose.setContent(`<body style="margin:0;background:#ddd;display:flex;gap:16px;padding:16px;align-items:flex-start;font:12px sans-serif">
      <figure style="margin:0"><figcaption>様式(HTML)</figcaption><img src="${png(orig)}" style="max-height:640px"></figure>
      <figure style="margin:0"><figcaption>本アプリ(確認用データ)</figcaption><img src="${png(ours)}" style="max-height:640px"></figure></body>`);
    await compose.screenshot({ path: `${SCREENS}/53-form-${kind}-side-by-side.png`, fullPage: true });
  }
  await ctx.close();
});
