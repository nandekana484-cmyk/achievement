import { describe, expect, it } from "vitest";
import { type ActualsRow, initialChoice, mismatches, NO_LINK, parseQty, quantitiesToSend, rowKey } from "./actuals";

const row = (lot_no: string, produced_qty: number, extra: Partial<ActualsRow> = {}): ActualsRow => ({
  kitting_no: "0900-1-S-251014-04", lot_no, file_no: "0900", side: 1, line_code: "S", product_name: "基板",
  planned_qty: 100, produced_qty, kitting_produced_total: 160, kitting_hidden_qty: 0, ng_side1: 0, ng_side2: 0,
  worker_id: "Y100", operator_name: "鈴木", completed_on: "2026-10-21", source_db: "2026-10", side1_kitting_no: null,
  exportable: true, warnings: [], notes: [], ...extra,
});

describe("実績の書き出しの合計の確かめ", () => {
  const rows = [row("A", 100), row("B", 60)];

  it("割り振りのままなら合う", () => {
    expect(mismatches(rows, {})).toEqual([]);
    expect(quantitiesToSend(rows, {})).toEqual([]);
  });

  it("1行だけ直すと合わない。両方直すと合う", () => {
    expect(mismatches(rows, { [rowKey(rows[0])]: 90 })).toEqual([{ kitting_no: "0900-1-S-251014-04", sum: 150, total: 160 }]);
    const edits = { [rowKey(rows[0])]: 90, [rowKey(rows[1])]: 70 };
    expect(mismatches(rows, edits)).toEqual([]);
    expect(quantitiesToSend(rows, edits)).toEqual([
      { kitting_no: "0900-1-S-251014-04", lot_no: "A", produced_qty: 90 },
      { kitting_no: "0900-1-S-251014-04", lot_no: "B", produced_qty: 70 },
    ]);
  });

  it("一覧に出さないロット(面2にまとめた分)も合計に入れる", () => {
    const one = [row("B", 60, { kitting_hidden_qty: 100 })];
    expect(mismatches(one, {})).toEqual([]);
    expect(mismatches(one, { [rowKey(one[0])]: 70 })).toEqual([{ kitting_no: "0900-1-S-251014-04", sum: 170, total: 160 }]);
  });

  it("入力欄の数", () => {
    expect(parseQty(" 12 ")).toBe(12);
    expect(parseQty("0")).toBe(0);
    expect(parseQty("-1")).toBeNull();
    expect(parseQty("1.5")).toBeNull();
    expect(parseQty("")).toBeNull();
  });
});

describe("ひも付けの確認の初期の選択", () => {
  it("未確定なら、サーバーが選んだ発行日の近い面2。選べる面2が無ければ空", () => {
    expect(initialChoice({ state: "pending", side2_kitting_no: null, suggested: "0722-2-S-251014-02" })).toBe("0722-2-S-251014-02");
    expect(initialChoice({ state: "pending", side2_kitting_no: null, suggested: null })).toBe("");
  });

  it("確定したものはその結果(つながないも)", () => {
    expect(initialChoice({ state: "confirmed", side2_kitting_no: "0722-2-S-251020-07", suggested: "0722-2-S-251014-02" })).toBe("0722-2-S-251020-07");
    expect(initialChoice({ state: "unlinked", side2_kitting_no: null, suggested: "0722-2-S-251014-02" })).toBe(NO_LINK);
  });
});
