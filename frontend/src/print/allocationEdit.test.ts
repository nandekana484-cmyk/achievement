import { describe, expect, it } from "vitest";
import { canSaveAllocation, parseQty, showAllocation, sumOf, toQuantities } from "./allocationEdit";

describe("割り振りの入力", () => {
  it("数だけ読む(空・負・小数は読まない)", () => {
    expect(parseQty(" 98 ")).toBe(98);
    for (const bad of ["", "-1", "1.5", "あ"]) expect(parseQty(bad)).toBeNull();
  });

  it("合計は、読めない欄があれば null", () => {
    expect(sumOf(["98", "100", "100"])).toBe(298);
    expect(sumOf(["98", "", "100"])).toBeNull();
  });

  it("保存できるのは、作業者IDがあり、合計が生産数の合計と一致するとき", () => {
    expect(canSaveAllocation(["98", "100", "100"], 298, "Y100")).toBe(true);
    expect(canSaveAllocation(["100", "100", "100"], 298, "Y100")).toBe(false); // 合計が合わない
    expect(canSaveAllocation(["98", "100", "100"], 298, " ")).toBe(false); // 作業者IDが必須
  });

  it("{ロットNo.: 数} にする", () => {
    expect(toQuantities([{ lot_no: "A" }, { lot_no: "B" }], ["1", "2"])).toEqual({ A: 1, B: 2 });
  });

  it("割り振りの画面は、サーバーが editable のときだけ出す", () => {
    expect(showAllocation(null)).toBe(false);
    expect(showAllocation({ editable: false } as never)).toBe(false);
    expect(showAllocation({ editable: true } as never)).toBe(true);
  });
});
