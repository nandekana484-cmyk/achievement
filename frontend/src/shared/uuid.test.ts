import { describe, expect, it } from "vitest";
import { uuidv4 } from "./uuid";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("uuidv4", () => {
  it("UUID v4 の形になる(版と変種のビットが立つ)", () => {
    for (let i = 0; i < 200; i++) expect(uuidv4()).toMatch(UUID_V4);
  });

  it("毎回ちがう値になる", () => {
    const ids = new Set(Array.from({ length: 1000 }, () => uuidv4()));
    expect(ids.size).toBe(1000);
  });

  it("乱数の全ビットが0でも1でも、版と変種を正しく入れる", () => {
    expect(uuidv4((b) => b.fill(0))).toBe("00000000-0000-4000-8000-000000000000");
    expect(uuidv4((b) => b.fill(0xff))).toBe("ffffffff-ffff-4fff-bfff-ffffffffffff");
  });

  it("crypto.randomUUID を使わない(HTTP では使えないため)", () => {
    const original = crypto.randomUUID;
    Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
    try {
      expect(uuidv4()).toMatch(UUID_V4);
    } finally {
      Object.defineProperty(crypto, "randomUUID", { value: original, configurable: true });
    }
  });
});
