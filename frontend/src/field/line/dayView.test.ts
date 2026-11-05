import { describe, expect, it } from "vitest";
import { addDays, dayBounds, isReadOnlyDay, isSelectableDay, parseDay } from "./dayView";

describe("表示する日", () => {
  it("URL の日付は形が正しいものだけ読む", () => {
    expect(parseDay("2026-11-03")).toBe("2026-11-03");
    expect(parseDay("2026-13-40")).toBeNull();
    expect(parseDay("11/03")).toBeNull();
    expect(parseDay(null)).toBeNull();
  });

  it("選べるのは今日の31日前から14日後まで", () => {
    expect(dayBounds("2026-11-05")).toEqual({ min: "2026-10-05", max: "2026-11-19" });
    expect(isSelectableDay("2026-10-05", "2026-11-05")).toBe(true);
    expect(isSelectableDay("2026-10-04", "2026-11-05")).toBe(false);
    expect(isSelectableDay("2026-11-19", "2026-11-05")).toBe(true);
    expect(isSelectableDay("2026-11-20", "2026-11-05")).toBe(false);
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });

  it("今日と違う日は表示のみ", () => {
    expect(isReadOnlyDay({ date: "2026-11-03", today: "2026-11-05" })).toBe(true);
    expect(isReadOnlyDay({ date: "2026-11-05", today: "2026-11-05" })).toBe(false);
    expect(isReadOnlyDay(null)).toBe(false);
  });
});
