import { describe, expect, it } from "vitest";
import { efficiencyText, excludedText, reasonLabel } from "./efficiency";

const report = (efficiency: number | null, reasons: { reason: string; count: number }[]) =>
  ({ efficiency: { efficiency, excluded: reasons.reduce((n, r) => n + r.count, 0), reasons } }) as Parameters<typeof efficiencyText>[0];

describe("日報の効率", () => {
  it("効率を割合で出す。計算に入れた計画が無ければ「—」", () => {
    expect(efficiencyText(report(0.8, []))).toBe("効率: 80%");
    expect(efficiencyText(report(null, []))).toBe("効率: —");
  });

  it("外した計画が無ければ何も出さない。あれば件数と理由ごとの件数", () => {
    expect(excludedText(report(0.8, []))).toBeNull();
    expect(excludedText(report(0.8, [{ reason: "no_k_row", count: 2 }, { reason: "no_takt", count: 1 }]))).toBe(
      "効率の対象外: 3件(K行が無い 2件、目標タクトが無い 1件)",
    );
  });

  it("知らない status は不明な状態として値を添える", () => {
    expect(reasonLabel("brand_new")).toBe("不明な状態(brand_new)");
    expect(reasonLabel("no_row")).toBe("丁取りがまだ取れていない");
  });
});
