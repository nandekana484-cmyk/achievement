import { describe, expect, it } from "vitest";
import { LANG_STORAGE_KEY, loadLang, saveLang } from "./storage";

const memory = () => {
  const data = new Map<string, string>();
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v), data };
};

const broken = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
};

describe("選んだ言語の記憶", () => {
  it("最初は日本語。記憶したら次からはその言語", () => {
    const s = memory();
    expect(loadLang(s)).toBe("ja");
    expect(saveLang("vi", s)).toBe(true);
    expect(s.data.get(LANG_STORAGE_KEY)).toBe("vi");
    expect(loadLang(s)).toBe("vi");
  });

  it("知らない値が入っていたら日本語", () => {
    const s = memory();
    s.setItem(LANG_STORAGE_KEY, "en");
    expect(loadLang(s)).toBe("ja");
  });

  it("読めない・書けない環境でも落ちない(日本語にする)", () => {
    expect(loadLang(broken)).toBe("ja");
    expect(saveLang("vi", broken)).toBe(false);
    expect(loadLang(null)).toBe("ja");
    expect(saveLang("vi", null)).toBe(false);
  });

  it("localStorage が無い環境(このテストの node)でも落ちない", () => {
    expect(loadLang()).toBe("ja");
    expect(() => saveLang("vi")).not.toThrow();
  });
});
