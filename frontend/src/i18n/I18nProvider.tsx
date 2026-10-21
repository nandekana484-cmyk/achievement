// 今の言語と t() を画面に配る。言語を切り替えると、その端末に記憶し、画面全体を描き直す。
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { loadLang, saveLang } from "./storage";
import { DEFAULT_LANG, type Lang, makeTranslate, type Translate } from "./translate";

export type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: Translate };

const I18nContext = createContext<I18n>({ lang: DEFAULT_LANG, setLang: () => undefined, t: makeTranslate(DEFAULT_LANG) });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => loadLang());
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    saveLang(next);
  }, []);
  const value = useMemo(() => ({ lang, setLang, t: makeTranslate(lang) }), [lang, setLang]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = value.t("app.title");
  }, [lang, value]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** 今の言語、切り替え、t('キー')。 */
export function useI18n(): I18n {
  return useContext(I18nContext);
}
