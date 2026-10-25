// アクセス制限の画面の、画面に依存しない部分: 入力の書き方の確認と、今の状態の文。
// サーバーも同じ確認をする(書き方の誤りは 409)。ここは、送る前に気づけるようにするだけ。
import type { components } from "../../api/schema";

export type AccessInfo = components["schemas"]["AccessOut"];
export type NetworkRow = components["schemas"]["AllowedNetworkOut"];
export type Scope = NetworkRow["scope"];

const IPV4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
const IPV6 = /^[0-9a-f:]+(\.\d{1,3}){0,3}$/i;

function validIpv4(text: string): boolean {
  const m = IPV4.exec(text);
  return m !== null && m.slice(1).every((part) => Number(part) <= 255);
}

function validIpv6(text: string): boolean {
  if (!text.includes(":") || !IPV6.test(text) || text.split("::").length > 2) return false;
  return text.split(":").length <= 9 && !text.includes(":::");
}

/** 1台(192.168.3.5)か範囲(192.168.3.0/24)の書き方に見えるか。IPv6 も。 */
export function looksLikeNetwork(input: string): boolean {
  const text = input.trim();
  if (!text) return false;
  const [address, prefix, ...rest] = text.split("/");
  if (rest.length > 0) return false;
  const v4 = validIpv4(address);
  const v6 = !v4 && validIpv6(address);
  if (!v4 && !v6) return false;
  if (prefix === undefined) return true;
  return /^\d{1,3}$/.test(prefix) && Number(prefix) <= (v4 ? 32 : 128);
}

export type AccessSummary = {
  fieldCount: number;
  adminCount: number;
  fieldRestricted: boolean;
  adminRestricted: boolean;
  anyRestriction: boolean;
};

/** 有効な範囲の数と、どちらが制限されているか。 */
export function summarize(info: AccessInfo): AccessSummary {
  const active = info.networks.filter((n) => n.active);
  const fieldCount = active.filter((n) => n.scope === "field").length;
  const adminCount = active.filter((n) => n.scope === "admin").length;
  return {
    fieldCount, adminCount,
    fieldRestricted: info.field_restricted, adminRestricted: info.admin_restricted,
    anyRestriction: info.field_restricted || info.admin_restricted,
  };
}

/** 今の接続元がすでに有効な範囲に入っているか(「今の接続元を追加」の重複を避ける)。 */
export function alreadyListed(info: AccessInfo, scope: Scope): boolean {
  return info.networks.some((n) => n.active && n.scope === scope && (n.network === `${info.my_ip}/32` || n.network === `${info.my_ip}/128`));
}
