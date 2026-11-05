// 表示する日の選択(AD-25): ほかの日を選ぶと「表示のみ」になり、工程のボタンは押せないが、計画を選んで識別票の印刷のページに進める。
// 現品票(識別票の1つ目)の PDF は A6 の1ページで、下の空きが 3mm 以下。ほかの spec と別のラインDで行う(今日 10/21 ではない 10/24 の計画)。
import { expect, type Page, test } from "@playwright/test";
import { pdfPageCount, pdfPageSizesMm } from "./pdf";

const SCREENS = "test-results/screens";
const DAY = "2026-10-24";
const MM = 25.4 / 96;

test.use({ viewport: { width: 1440, height: 1000 } });

async function firstPlan(page: Page): Promise<string> {
  const b = await (await page.request.get("/api/lines/D/board", { params: { date: DAY } })).json();
  expect(b.plans.length).toBeGreaterThan(0);
  return b.plans[0].plan.kitting_no;
}

test("61 ほかの日を選ぶと「表示のみ」: 工程のボタンは押せず、計画を選んで識別票の印刷のページに進める", async ({ page }) => {
  const today = await (await page.request.get("/api/lines/D/board")).json();
  expect(today.date).toBe("2026-10-21");
  expect(today.today).toBe("2026-10-21");
  const other = await (await page.request.get("/api/lines/D/board", { params: { date: DAY } })).json();
  expect(other.date).toBe(DAY);
  expect(other.display_start).toBe("2026-10-23T20:15:00+09:00"); // 前後12時間だけ
  expect(other.display_end).toBe("2026-10-25T20:15:00+09:00");
  const kno = await firstPlan(page);

  await page.goto("/field/lines/D");
  await expect(page.getByText("表示のみ")).toHaveCount(0); // 今日は帯なし
  await expect(page.getByRole("button", { name: "今日", exact: true })).toBeDisabled();

  await page.getByLabel("表示する稼働日").fill(DAY);
  await expect(page).toHaveURL(/day=2026-10-24/); // URL に入る
  await expect(page.getByText("表示のみ(今日ではありません)")).toBeVisible();
  await page.locator(".tt-plan").first().click();
  for (const step of ["段取り", "生産", "片付け"]) await expect(page.locator(".step-button", { hasText: step }).first()).toBeDisabled();
  await expect(page.getByRole("button", { name: "NG数を入力" })).toBeDisabled();
  await page.screenshot({ path: `${SCREENS}/61-day-select-pc.png` });

  // 再読み込みしても同じ日を出す
  await page.reload();
  await expect(page.getByText("表示のみ(今日ではありません)")).toBeVisible();
  await expect(page.getByLabel("表示する稼働日")).toHaveValue(DAY);

  // 表示のみでも、識別票の印刷のページに進める
  await page.locator(".tt-plan").first().click();
  await page.getByRole("link", { name: "識別票" }).click();
  await expect(page).toHaveURL(new RegExp(`/field/print/id-slips/${kno}`));
  await expect(page.locator(".idslip-head strong")).toHaveText(kno);

  // 「今日」で戻る
  await page.goto(`/field/lines/D?day=${DAY}`);
  await page.getByRole("button", { name: "今日", exact: true }).click();
  await expect(page).not.toHaveURL(/day=/);
  await expect(page.getByText("表示のみ")).toHaveCount(0);
});

test("62 ハンディターミナルくらいの幅でも、日を選ぶ欄と「今日」が使える", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(`/field/lines/D?day=${DAY}`);
  await expect(page.getByText("表示のみ(今日ではありません)")).toBeVisible();
  const input = page.getByLabel("表示する稼働日");
  const today = page.getByRole("button", { name: "今日", exact: true });
  for (const el of [input, today]) {
    const box = await el.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390, JSON.stringify(box)).toBe(true);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.screenshot({ path: `${SCREENS}/62-day-select-handy.png` });
  await today.click();
  await expect(page).not.toHaveURL(/day=/);
});

test("63 現品票(識別票の1つ目)は A6 の1ページで、下の空きが 3mm 以下", async ({ page }) => {
  const kno = await firstPlan(page);
  await page.goto(`/field/print/id-slips/${kno}`);
  await expect(page.locator(".idslip-toolbar")).toBeVisible();
  const box = page.getByRole("checkbox", { name: "1 基板製品ロット現品票" });
  await box.setChecked(true);
  await page.addInitScript(() => { window.print = () => undefined; });
  await page.getByRole("row", { name: "1 基板製品ロット現品票" }).getByRole("button", { name: "この種類を印刷" }).click();
  await page.emulateMedia({ media: "print" });
  const gap = await page.evaluate(() => {
    const slip = document.querySelector<HTMLElement>(".idslip-group.is-printing .slip1")!;
    const main = slip.firstElementChild as HTMLElement; // 表の部分
    const bottom = slip.querySelector<HTMLElement>(".slip1-bottom")!;
    return {
      gapMm: (bottom.getBoundingClientRect().top - main.getBoundingClientRect().bottom) / (96 / 25.4),
      scale: slip.getBoundingClientRect().height / slip.offsetHeight,
      overflow: slip.scrollHeight - slip.clientHeight,
    };
  });
  console.log("現品票の空き(mm):", JSON.stringify(gap));
  const pdf = await page.pdf({ preferCSSPageSize: true });
  expect(pdfPageCount(pdf)).toBe(1);
  const s = pdfPageSizesMm(pdf)[0];
  expect(Math.abs(s.width - 105) < 1.2 && Math.abs(s.height - 148) < 1.2).toBe(true);
  expect(gap.gapMm).toBeLessThanOrEqual(3);
  expect(gap.gapMm).toBeGreaterThanOrEqual(0);
  expect(gap.overflow).toBeLessThanOrEqual(0);
  await page.emulateMedia({ media: "screen" });
  const frame = page.locator(".idslip-group[data-kind='1'] .slip-frame").first();
  await frame.screenshot({ path: `${SCREENS}/63-id-slip-1-after.png` });
  await page.addStyleTag({ content: ".slip1 { --slip1-grow: 1 !important; }" }); // 広げる前(行の高さを元に戻す)の確認用
  await frame.screenshot({ path: `${SCREENS}/63-id-slip-1-before.png` });
});
