import { describe, expect, it } from "vitest";
import { ja, type Messages } from "./ja";
import { vi } from "./vi";

// 訳の抜けと余分なキーは型のエラーになる(npm run build の tsc で確かめる)。
// @ts-expect-error キーが足りない
const missing: Messages = { "app.title": "x" };
// @ts-expect-error ja.ts に無いキー
const extra: Messages = { ...ja, "no.such.key": "x" };
void missing;
void extra;

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("辞書", () => {
  it("vi.ts は ja.ts と同じキーをすべて持つ", () => {
    expect(Object.keys(vi).sort()).toEqual(Object.keys(ja).sort());
  });

  it("空の文は無い", () => {
    for (const [key, text] of [...Object.entries(ja), ...Object.entries(vi)]) {
      expect(text.trim(), key).not.toBe("");
    }
  });

  it("差し込みの名前は ja.ts と同じ", () => {
    for (const key of Object.keys(ja) as (keyof Messages)[]) {
      expect(placeholders(vi[key]), key).toEqual(placeholders(ja[key]));
    }
  });
});
