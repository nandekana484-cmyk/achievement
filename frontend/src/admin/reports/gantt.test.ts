import { describe, expect, it } from "vitest";
import { barBox, formatDateTime, hourTicks, paginate } from "./gantt";

const upper = { start: "2026-10-21T08:15:00+09:00", end: "2026-10-21T20:15:00+09:00" };

describe("日報のガントチャート", () => {
  it("行をページに分ける(行が無くても1ページ)", () => {
    expect(paginate([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(paginate([], 2)).toEqual([[]]);
  });

  it("棒の位置は段の12時間に対する割合。短い棒にも最低の幅を付け、右端からはみ出さない", () => {
    expect(barBox({ start: "2026-10-21T08:15:00+09:00", end: "2026-10-21T14:15:00+09:00" }, upper)).toEqual({ left: 0, width: 50 });
    const short = barBox({ start: "2026-10-21T11:15:00+09:00", end: "2026-10-21T11:15:10+09:00" }, upper);
    expect(short).toEqual({ left: 25, width: 0.4 });
    expect(barBox({ start: "2026-10-21T20:15:00+09:00", end: "2026-10-21T20:15:00+09:00" }, upper).width).toBe(0);
  });

  it("1時間ごとの目盛りは両端を含む13本(日本時間)", () => {
    const ticks = hourTicks(upper);
    expect(ticks).toHaveLength(13);
    expect(ticks[0]).toEqual({ left: 0, label: "8:15" });
    expect(ticks[12]).toEqual({ left: 100, label: "20:15" });
  });

  it("出力した日時の形", () => {
    expect(formatDateTime("2026-10-21T00:05:00Z")).toBe("2026/10/21 9:05");
  });
});
