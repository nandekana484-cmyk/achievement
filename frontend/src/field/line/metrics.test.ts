import { describe, expect, it } from "vitest";
import type { Board } from "../../shared/api";
import { excludedCount, progressItems } from "./metrics";

const plan = (kitting_no: string, in_progress: boolean, progress: number | null) =>
  ({ plan: { kitting_no }, in_progress, progress }) as unknown as Board["plans"][number];

describe("progressItems", () => {
  it("生産中の計画だけを、割合の文字にして出す", () => {
    const items = progressItems([plan("K1", true, 0.2), plan("K2", false, null), plan("K3", true, 0.456)]);
    expect(items).toEqual([
      { kittingNo: "K1", text: "20%", over: false },
      { kittingNo: "K3", text: "46%", over: false },
    ]);
  });

  it("100%を超えてもそのまま出し、over にする。計画の時間が無ければ「—」", () => {
    expect(progressItems([plan("K1", true, 1.5), plan("K2", true, 1), plan("K3", true, null)])).toEqual([
      { kittingNo: "K1", text: "150%", over: true },
      { kittingNo: "K2", text: "100%", over: false },
      { kittingNo: "K3", text: "—", over: false },
    ]);
  });
});

describe("excludedCount", () => {
  it("外した件数。板がまだ無ければ0", () => {
    expect(excludedCount(null)).toBe(0);
    expect(excludedCount({ efficiency: { excluded: 3 } } as unknown as Board)).toBe(3);
  });
});
