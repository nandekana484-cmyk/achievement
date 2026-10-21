// 言語と、キーから文を作る関数(React に依存しない部分)。詳細: docs/design/i18n.md
import { ja, type MessageKey, type Messages } from "./ja";
import { vi } from "./vi";

export type Lang = "ja" | "vi";
export const LANGS: Lang[] = ["ja", "vi"];
export const DEFAULT_LANG: Lang = "ja";

/** 切り替えのボタンに出す言語の名前(どちらの言語でも、その言語での名前を出す)。 */
export const LANG_NAMES: Record<Lang, string> = { ja: "日本語", vi: "Tiếng Việt" };

const DICTIONARIES: Record<Lang, Messages> = { ja, vi };

export type Params = Record<string, string | number>;
export type Translate = (key: MessageKey, params?: Params) => string;

/** 「{count}ロット」の {count} を差し込む。渡されていない名前はそのまま残す(抜けに気づけるように)。 */
export function format(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole));
}

export function makeTranslate(lang: Lang): Translate {
  const dict = DICTIONARIES[lang];
  return (key, params) => format(dict[key] ?? ja[key], params);
}

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as string[]).includes(value);
}

/** マスタの名前(理由・設備)。ベトナム語を選んでいて、ベトナム語の名前があればそれ、無ければ日本語の名前。 */
export function localName(lang: Lang, name: string, nameVi: string | null | undefined): string {
  return lang === "vi" && nameVi ? nameVi : name;
}
