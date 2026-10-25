import { describe, expect, it } from "vitest";
import { type AccessInfo, alreadyListed, looksLikeNetwork, summarize } from "./accessLogic";

const row = (id: number, network: string, scope: "field" | "admin", active = true) => ({
  id, network, scope, note: null, created_by: null, created_at: "2026-10-25T10:00:00+09:00", active, disabled_at: null, disabled_by: null,
});

const info = (over: Partial<AccessInfo> = {}): AccessInfo => ({
  my_ip: "192.168.3.5", my_ip_is_loopback: false, field_restricted: false, admin_restricted: false, field_allowed: true, admin_allowed: true,
  networks: [], ...over,
});

describe("looksLikeNetwork", () => {
  it.each(["192.168.3.5", "192.168.3.0/24", " 10.0.0.0/8 ", "0.0.0.1/32", "fd00::1", "fd00::/64", "::1", "::ffff:192.168.3.5", "fe80::1/128"])(
    "%s は書き方として正しい", (text) => expect(looksLikeNetwork(text)).toBe(true));

  it.each(["", "  ", "abc", "192.168.3", "192.168.3.256", "192.168.3.0/33", "192.168.3.0/", "192.168.3.0/24/1", "1.2.3.4.5", "fd00::/129",
    "fd00:::1", "1::2::3", "192.168.3.0/-1", "192.168.3.0/x", "http://10.0.0.1"])(
    "%j は書き方として正しくない", (text) => expect(looksLikeNetwork(text)).toBe(false));
});

describe("summarize", () => {
  it("有効な範囲だけを数える(無効にしたものは数えない)", () => {
    const s = summarize(info({
      field_restricted: true,
      networks: [row(1, "192.168.3.0/24", "field"), row(2, "10.0.0.0/8", "field", false), row(3, "192.168.9.5/32", "admin")],
    }));
    expect(s).toMatchObject({ fieldCount: 1, adminCount: 1, fieldRestricted: true, adminRestricted: false, anyRestriction: true });
  });

  it("一覧が空なら制限なし", () => {
    expect(summarize(info()).anyRestriction).toBe(false);
  });
});

describe("alreadyListed", () => {
  it("今の接続元が、同じ区分の有効な1台として載っているか", () => {
    const i = info({ networks: [row(1, "192.168.3.5/32", "field"), row(2, "192.168.3.5/32", "admin", false)] });
    expect(alreadyListed(i, "field")).toBe(true);
    expect(alreadyListed(i, "admin")).toBe(false); // 無効にしたものは数えない
  });

  it("範囲の中にいても、1台としては載っていない", () => {
    expect(alreadyListed(info({ networks: [row(1, "192.168.3.0/24", "field")] }), "field")).toBe(false);
  });
});
