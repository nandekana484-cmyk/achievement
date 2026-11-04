import { describe, expect, it } from "vitest";
import { barSize, barsPath, encodeCode39, isCode39, MIN_BAR_MM, modulesOf } from "./code39";
import { fitFontPx, fitListFontPx, listLines } from "./fitText";

describe("Code 39", () => {
  it("英大文字・数字・記号は表せる。英小文字・日本語・空は表せない", () => {
    for (const ok of ["SUF-0722", "0722-2-L-250512-01", "A B.C$/+%", "722"]) expect(isCode39(ok), ok).toBe(true);
    for (const ng of ["suf-1", "ロット1", "A_B", "", "A*B", "ＡＢＣ"]) expect(isCode39(ng), ng).toBe(false);
  });

  it("符号の長さは (文字数 + 2) × 16 - 1(JsBarcode の符号と一致する)", () => {
    for (const v of ["7", "722", "SUF-0722", "0722-2-L-250512-01"]) expect(encodeCode39(v)?.length, v).toBe(modulesOf(v));
  });

  it("符号は * で始まり * で終わる(* = 100010111011101)", () => {
    const star = "100010111011101";
    const data = encodeCode39("1") as string;
    expect(data.startsWith(star)).toBe(true);
    expect(data.endsWith(star)).toBe(true);
  });

  it("表せない値は符号にしない(大文字にも直さない)", () => {
    expect(encodeCode39("abc")).toBeNull();
  });

  it("path は 1 の連なりだけを描く", () => {
    expect(barsPath("0110100")).toBe("M1 0h2v1h-2zM4 0h1v1h-1z");
  });
});

describe("細いバーの幅", () => {
  it("枠に余裕があれば最大幅、狭ければ 0.25mm まで下げる", () => {
    expect(barSize("722", 100, 0.4)).toMatchObject({ barMm: 0.4, fits: true });
    const s = barSize("SUF-0722", 41.6, 0.4); // 159 本分
    expect(s.barMm).toBeGreaterThanOrEqual(MIN_BAR_MM);
    expect(s.widthMm).toBeLessThanOrEqual(41.6);
    expect(s.fits).toBe(true);
  });

  it("0.25mm でも収まらないときは 0.25mm のまま fits = false(0.25mm 未満にはしない)", () => {
    const s = barSize("12345678", 30);
    expect(s).toMatchObject({ barMm: MIN_BAR_MM, fits: false });
  });

  it("8文字のロットNo.が 0.25mm で収まる最小の幅", () => {
    expect(modulesOf("116713-2") * MIN_BAR_MM).toBeCloseTo(39.75, 2);
  });
});

describe("枠に収まる文字の大きさ", () => {
  it("収まるなら最大、収まらないなら縮め、最小は 8px", () => {
    const box = { widthPx: 90, heightPx: 120, maxPx: 20 };
    expect(fitFontPx("L001", box)).toBe(20);
    const many = Array.from({ length: 10 }, (_, i) => `11671${i}-2`).join(", ");
    const px = fitFontPx(many, box);
    expect(px).toBeLessThan(20);
    expect(px).toBeGreaterThanOrEqual(8);
    expect(fitFontPx(many.repeat(20), box)).toBe(8);
  });

  it("行数の上限を超えるときは縮める", () => {
    expect(fitFontPx("ABCDEFGHIJKLMNOPQRST", { widthPx: 100, heightPx: 200, maxPx: 24, maxLines: 1 })).toBeLessThan(24);
  });

  it("項目を並べるときは項目の途中で折り返さず、収まらなければ縮める(最小 8px)", () => {
    const items = Array.from({ length: 10 }, (_, i) => `DEMO-R${String(i + 1).padStart(2, "0")}`);
    const box = { widthPx: 140, heightPx: 136, maxPx: 20 };
    const px = fitListFontPx(items, box);
    expect(px).toBeGreaterThanOrEqual(8);
    expect(px).toBeLessThan(20);
    expect(listLines(items, px, box.widthPx) * px * 1.2).toBeLessThanOrEqual(box.heightPx);
    expect(fitListFontPx(items.concat(items, items, items), { ...box, heightPx: 40 })).toBe(8);
    expect(fitListFontPx(["L001"], box)).toBe(20);
  });
});
