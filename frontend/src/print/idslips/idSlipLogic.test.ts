import { describe, expect, it } from "vitest";
import { barcodeWarnings, defaultKinds, type IdSlip, initialSelection, pagesOf, toggleKind, toggleLot } from "./idSlipLogic";

const slip = (over: Partial<IdSlip> = {}): IdSlip => ({
  kitting_no: "0722-1-S-251014-01", line_code: "S", run_no: 1, file_no: "722", suf: "SUF-0722", product_name: "基板A",
  lots: [{ lot_no: "L001", order_qty: 1000, planned_qty: 300 }, { lot_no: "L002", order_qty: null, planned_qty: 200 }, { lot_no: "L003", order_qty: 500, planned_qty: 100 }],
  lot_list: "L001, L002, L003", control_sheet: { registered: false, manager_no: "", rows: [] }, ...over,
});

describe("初期値の種類", () => {
  it("1回目(面1)の計画は 2・3・4", () => {
    expect(defaultKinds(1)).toEqual([2, 3, 4]);
    expect(initialSelection(slip()).kinds).toEqual([2, 3, 4]);
  });

  it("2回目(面2)の計画は 1・4・5(管理表)", () => {
    expect(defaultKinds(2)).toEqual([1, 4, 5]);
    expect(initialSelection(slip({ run_no: 2 })).kinds).toEqual([1, 4, 5]);
  });

  it("ロットは全ロット", () => {
    const sel = initialSelection(slip());
    expect(sel.lots).toEqual(["L001", "L002", "L003"]);
  });

  it("初期値以外の種類もチェックを入れれば出せる(片面製品で1つ目を1回目の計画で出す)", () => {
    const sel = initialSelection(slip());
    const next = { ...sel, kinds: toggleKind(sel.kinds, 1) };
    expect(next.kinds).toEqual([1, 2, 3, 4]); // 1回目の計画の初期値は 2・3・4。1 を足しても 5(管理表)は入らない
    expect(toggleKind(next.kinds, 5)).toEqual([1, 2, 3, 4, 5]); // チェックを入れれば出せる(片面製品)
    expect(pagesOf(1, next)).toHaveLength(3);
  });
});

describe("ロットの選択とページ数(1枚の識別票 = 1ページ)", () => {
  it("ロットごとの種類は、選んだロットの数だけ(ロット1つで1ページ)", () => {
    const sel = { ...initialSelection(slip()), lots: ["L001"] };
    for (const kind of [1, 2, 3] as const) expect(pagesOf(kind, sel)).toEqual([{ lot: "L001" }]);
  });

  it("ロット3つで3ページ。同じロットの同じ種類を2ページ以上出さない", () => {
    const sel = initialSelection(slip());
    for (const kind of [1, 2, 3] as const) expect(pagesOf(kind, sel).map((p) => p.lot)).toEqual(["L001", "L002", "L003"]);
    expect(pagesOf(1, { ...sel, lots: ["L001", "L001", "L002"] }).map((p) => p.lot)).toEqual(["L001", "L002"]);
  });

  it("4つ目はキッティングNo.ごとに1ページ(ロットの選択に関係なく)", () => {
    const sel = { ...initialSelection(slip()), lots: [] };
    expect(pagesOf(4, sel)).toEqual([{ lot: null }]);
    expect(pagesOf(4, initialSelection(slip()))).toEqual([{ lot: null }]);
  });

  it("ロットを外す・戻す(計画のロットの順)", () => {
    const all = ["L001", "L002", "L003"];
    expect(toggleLot(all, all, "L002")).toEqual(["L001", "L003"]);
    expect(toggleLot(all, ["L001", "L003"], "L002")).toEqual(all);
  });
});

describe("Code 39 で表せない値の警告", () => {
  const sel = (kinds: (1 | 2 | 3 | 4)[], lots?: string[]) => ({ ...initialSelection(slip()), kinds, ...(lots ? { lots } : {}) });

  it("表せる値なら警告は出ない", () => {
    expect(barcodeWarnings(slip(), sel([1, 2, 3, 4]))).toEqual([]);
  });

  it("英小文字・日本語のロットNo.は、1を選んだときだけ警告する", () => {
    const s = slip({ lots: [{ lot_no: "ab-1", order_qty: 1, planned_qty: 1 }, { lot_no: "ロット2", order_qty: 1, planned_qty: 1 }, { lot_no: "OK-3", order_qty: 1, planned_qty: 1 }] });
    const all = s.lots.map((l) => l.lot_no);
    expect(barcodeWarnings(s, { ...sel([1], all) })).toEqual([{ field: "lot", value: "ab-1" }, { field: "lot", value: "ロット2" }]);
    expect(barcodeWarnings(s, { ...sel([2, 3, 4], all) })).toEqual([]);
    expect(barcodeWarnings(s, { ...sel([1], ["OK-3"]) })).toEqual([]); // 選ばないロットは警告しない
  });

  it("キッティングNo.は4を選んだときに警告する(大文字には直さない)", () => {
    const s = slip({ kitting_no: "0722-1-s-251014-01" });
    expect(barcodeWarnings(s, sel([4]))).toEqual([{ field: "kitting", value: "0722-1-s-251014-01" }]);
    expect(barcodeWarnings(s, sel([2]))).toEqual([]);
  });

  it("ファイルNo.(SUF- の値)に小文字があるとき", () => {
    expect(barcodeWarnings(slip({ suf: "SUF-s010" }), sel([2]))).toEqual([{ field: "file", value: "SUF-s010" }]);
  });
});
