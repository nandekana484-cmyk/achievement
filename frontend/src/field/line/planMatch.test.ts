import { describe, expect, it } from "vitest";
import type { Plan } from "../../shared/api";
import { exactKittingMatch, foldForMatch, isOutsideDisplay, outsideMessage } from "./planMatch";

const plan = (kitting_no: string, lot_no = "L1", start: string | null = "2026-10-21T09:00:00+09:00", end: string | null = "2026-10-21T12:00:00+09:00"): Plan => ({
  kitting_no, file_no: "0722", line_code: "S", product_name: "基板", run_no: 1, planned_qty: 100,
  planned_start: start, planned_end: end, deadline: null, issue_date: "2026-10-14", issue_seq: 1, status: "active",
  takt_sec: null, source_db: null, lots: [{ lot_no, product_name: "基板", planned_qty: 100 }], warnings: [],
});

describe("exactKittingMatch", () => {
  it("キッティングNo.が完全に一致する1件を返す(大文字・小文字、全角・半角、前後の空白は無視)", () => {
    const results = [plan("0722-1-S-251018-01"), plan("0722-1-S-251018-011")];
    expect(exactKittingMatch(results, "0722-1-S-251018-01")?.kitting_no).toBe("0722-1-S-251018-01");
    expect(exactKittingMatch(results, " ０７２２－１－ｓ－２５１０１８－０１ ")?.kitting_no).toBe("0722-1-S-251018-01");
  });

  it("一部一致だけ・一致が2件(ロット違い)なら選ばない", () => {
    expect(exactKittingMatch([plan("0722-1-S-251018-01")], "0722-1-S")).toBeNull();
    expect(exactKittingMatch([plan("0722-1-S-251018-01", "L1"), plan("0722-1-S-251018-01", "L2")], "0722-1-S-251018-01")).toBeNull();
    expect(exactKittingMatch([], "0722")).toBeNull();
  });

  it("比べるための形", () => {
    expect(foldForMatch(" ｔ４５８ ")).toBe("T458");
  });
});

describe("表示範囲の外", () => {
  const board = { display_start: "2026-10-20T20:15:00+09:00", display_end: "2026-10-22T20:15:00+09:00" };

  it("表示範囲と重なるかで判定する。日程が空なら外", () => {
    expect(isOutsideDisplay(plan("A"), board)).toBe(false);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-18T09:00:00+09:00", "2026-10-18T12:00:00+09:00"), board)).toBe(true);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-20T18:00:00+09:00", "2026-10-20T20:15:00+09:00"), board)).toBe(true);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-20T18:00:00+09:00", "2026-10-20T21:00:00+09:00"), board)).toBe(false);
    expect(isOutsideDisplay(plan("A", "L1", null, null), board)).toBe(true);
  });

  it("表示範囲外の文", () => {
    expect(outsideMessage(plan("A", "L1", "2026-10-18T09:00:00+09:00"))).toBe("表示範囲外の計画です(計画: 10/18 9:00〜)");
    expect(outsideMessage(plan("A", "L1", null, null))).toBe("表示範囲外の計画です(計画: 日程なし)");
  });
});
