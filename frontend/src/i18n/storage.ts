// 選んだ言語をその端末に記憶する(localStorage)。使えない環境(プライベートモードなど)でも落ちず、日本語にする。
import { DEFAULT_LANG, isLang, type Lang } from "./translate";

export const LANG_STORAGE_KEY = "genba.lang";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

function defaultStorage(): StorageLike | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null; // アクセスしただけで例外になる環境がある
  }
}

export function loadLang(storage: StorageLike | null = defaultStorage()): Lang {
  try {
    const value = storage?.getItem(LANG_STORAGE_KEY);
    return isLang(value) ? value : DEFAULT_LANG;
  } catch {
    return DEFAULT_LANG;
  }
}

/** 記憶できたら true。記憶できなくても、画面の言語は切り替わる(その端末で次に開いたときは日本語)。 */
export function saveLang(lang: Lang, storage: StorageLike | null = defaultStorage()): boolean {
  try {
    if (!storage) return false;
    storage.setItem(LANG_STORAGE_KEY, lang);
    return true;
  } catch {
    return false;
  }
}
