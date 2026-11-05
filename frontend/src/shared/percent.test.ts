import { describe, expect, it } from "vitest";
import { formatPercent } from "./percent";

describe("formatPercent", () => {
  it("割合を%にする。空は「—」", () => {
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(0.3333)).toBe("33%");
    expect(formatPercent(1.5)).toBe("150%");
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
  });

  it("200%ちょうどまでは数、200.1% と 250% は「***%」", () => {
    expect(formatPercent(2)).toBe("200%");
    expect(formatPercent(2.001)).toBe("***%");
    expect(formatPercent(2.5)).toBe("***%");
    expect(formatPercent(25)).toBe("***%");
  });
});
