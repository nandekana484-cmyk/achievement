import { describe, expect, it } from "vitest";
import { format, isLang, localName, makeTranslate } from "./translate";

describe("差し込み", () => {
  it("{name} を値に置き換える(数も文字にする)", () => {
    expect(format("{count}ロット", { count: 3 })).toBe("3ロット");
    expect(format("{a}・{b}・{a}", { a: "X", b: 0 })).toBe("X・0・X");
  });

  it("渡されていない名前はそのまま残す。値を渡さなければ元の文", () => {
    expect(format("{lot}・面{side}", { lot: "L1" })).toBe("L1・面{side}");
    expect(format("{count}ロット")).toBe("{count}ロット");
  });

  it("値の中の {…} は、もう一度は置き換えない", () => {
    expect(format("{a}{b}", { a: "{b}", b: "x" })).toBe("{b}x");
  });
});

describe("t()", () => {
  it("キーから選んだ言語の文を返す", () => {
    expect(makeTranslate("ja")("unit.lots", { count: 2 })).toBe("2ロット");
    expect(makeTranslate("vi")("unit.lots", { count: 2 })).toBe("2 lô");
  });
});

describe("言語", () => {
  it("知っている言語だけを受け付ける", () => {
    expect(isLang("ja") && isLang("vi")).toBe(true);
    expect(isLang("en") || isLang(null) || isLang(1)).toBe(false);
  });

  it("マスタの名前は、ベトナム語が空なら日本語の名前", () => {
    expect(localName("vi", "部品探し", "Tìm linh kiện")).toBe("Tìm linh kiện");
    expect(localName("vi", "部品探し", null)).toBe("部品探し");
    expect(localName("vi", "部品探し", "")).toBe("部品探し");
    expect(localName("ja", "部品探し", "Tìm linh kiện")).toBe("部品探し");
  });
});
