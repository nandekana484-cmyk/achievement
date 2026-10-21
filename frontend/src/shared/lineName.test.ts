import { describe, expect, it } from "vitest";
import { makeTranslate } from "../i18n/translate";
import { lineName } from "./lineName";

describe("ラインの名前", () => {
  it("自動で付けた名前のままなら、選んだ言語の形で出す", () => {
    const line = { line_code: "S", name: "Sライン", auto_named: true };
    expect(lineName(line, makeTranslate("ja"))).toBe("Sライン");
    expect(lineName(line, makeTranslate("vi"))).toBe("Chuyền S");
  });

  it("人が変えた名前は、どの言語でもそのまま出す", () => {
    const line = { line_code: "S", name: "第1実装ライン", auto_named: false };
    expect(lineName(line, makeTranslate("vi"))).toBe("第1実装ライン");
  });
});
