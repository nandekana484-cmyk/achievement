import { describe, expect, it } from "vitest";
import { makeTranslate } from "../../i18n/translate";
import type { Operator } from "../../shared/api";
import { operatorLabel, sortOperators } from "./operatorLabel";

const t = makeTranslate("ja");
const op = (id: number, name: string, worker_id: string | null): Operator => ({ id, name, worker_id, role: "operator", sort_order: 0 });

describe("作業者の表示", () => {
  it("名前の横に作業者IDを出す(無ければ名前だけ)", () => {
    expect(operatorLabel("山田", "Y001", t)).toBe("山田(Y001)");
    expect(operatorLabel("山田", null, t)).toBe("山田");
  });

  it("名前順、同じ名前は作業者IDの順", () => {
    const sorted = sortOperators([op(1, "山田", "Y015"), op(2, "佐藤", "S002"), op(3, "山田", "Y001")]);
    expect(sorted.map((o) => operatorLabel(o.name, o.worker_id, t))).toEqual(["佐藤(S002)", "山田(Y001)", "山田(Y015)"]);
  });
});
