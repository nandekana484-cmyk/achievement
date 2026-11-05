import { describe, expect, it } from "vitest";
import type { Board } from "../../shared/api";
import { excludedCount } from "./metrics";

describe("excludedCount", () => {
  it("外した件数。板がまだ無ければ0", () => {
    expect(excludedCount(null)).toBe(0);
    expect(excludedCount({ efficiency: { excluded: 3 } } as unknown as Board)).toBe(3);
  });
});
