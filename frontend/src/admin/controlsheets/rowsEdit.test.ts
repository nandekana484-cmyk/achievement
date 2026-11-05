import { describe, expect, it } from "vitest";
import { addRow, blankRow, firstBlankName, moveRow, removeRow, toPayload, updateRow } from "./rowsEdit";

const named = (...names: string[]) => names.map((name) => ({ ...blankRow(), name }));
const names = (rows: { name: string }[]) => rows.map((r) => r.name);

describe("管理表の行の編集", () => {
  it("行を最後に足す、指定の行の下に足す", () => {
    expect(names(addRow(named("A", "B")))).toEqual(["A", "B", ""]);
    expect(names(addRow(named("A", "B"), 0))).toEqual(["A", "", "B"]);
    expect(blankRow()).toMatchObject({ kind: "none", use_line: true, link: "none", procedure: "" });
  });

  it("行を削除する", () => {
    expect(names(removeRow(named("A", "B", "C"), 1))).toEqual(["A", "C"]);
  });

  it("行を上下に動かす(端では動かない)", () => {
    expect(names(moveRow(named("A", "B", "C"), 2, -1))).toEqual(["A", "C", "B"]);
    expect(names(moveRow(named("A", "B", "C"), 0, 1))).toEqual(["B", "A", "C"]);
    const rows = named("A", "B");
    expect(moveRow(rows, 0, -1)).toBe(rows);
    expect(moveRow(rows, 1, 1)).toBe(rows);
  });

  it("行の項目を変える。ほかの行は変えない", () => {
    const rows = named("A", "B");
    const next = updateRow(rows, 1, { use_line: false, kind: "internal" });
    expect(next[1]).toMatchObject({ name: "B", use_line: false, kind: "internal" });
    expect(next[0]).toBe(rows[0]);
  });

  it("工程名が空の最初の行の番号と、送る形", () => {
    expect(firstBlankName(named("A", " ", ""))).toBe(2);
    expect(firstBlankName(named("A"))).toBeNull();
    expect(toPayload([{ ...blankRow(), name: " X線 ", name_vi: "  " }])[0]).toMatchObject({ name: "X線", name_vi: null });
  });
});
